#!/usr/bin/env python3
"""Pikmi AI (Groq): перепись исходящих + автоответчик + полноценный экран настроек.

- API-ключ, промпт, модель — в клиенте, отдельно на аккаунт
- Модель можно выбрать из списка или вписать свою
- Автоответчик: список пользователей, которым отвечать автоматически
- Перепись исходящих перед отправкой

Идемпотентен.
"""
import re
import sys
from pathlib import Path

HELPER = Path("TMessagesProj/src/main/java/org/telegram/messenger/PikmiAI.java")
SETTINGS = Path("TMessagesProj/src/main/java/org/telegram/ui/PikmiAISettingsActivity.java")
CAE = Path("TMessagesProj/src/main/java/org/telegram/ui/Components/ChatActivityEnterView.java")
DA = Path("TMessagesProj/src/main/java/org/telegram/ui/DialogsActivity.java")
MC = Path("TMessagesProj/src/main/java/org/telegram/messenger/MessagesController.java")

JAVA_HELPER = r'''package org.telegram.messenger;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Handler;
import android.os.Looper;
import android.text.TextUtils;

import org.json.JSONArray;
import org.json.JSONObject;
import org.telegram.tgnet.TLRPC;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Pikmi AI на базе Groq.
 * Настройки отдельно для каждого аккаунта.
 */
public class PikmiAI {

    private static final String PREFS_PREFIX = "pikmigram_ai_";
    public static final String DEFAULT_PROMPT =
            "Перепиши сообщение вежливо, спокойно и без негатива. Сохрани смысл и язык оригинала. " +
            "Не добавляй приветствий, подписей и пояснений. Верни только готовый текст сообщения.";
    public static final String DEFAULT_AUTO_PROMPT =
            "Ты отвечаешь в мессенджере от моего имени. Ответь кратко, по делу и вежливо на входящее сообщение. " +
            "Не представляйся, не пиши что ты ИИ. Верни только текст ответа.";
    private static final String GROQ_URL = "https://api.groq.com/openai/v1/chat/completions";
    public static final String DEFAULT_MODEL = "llama-3.3-70b-versatile";

    public static final String[] MODELS = {
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "llama-3.1-70b-versatile",
            "gemma2-9b-it",
            "mixtral-8x7b-32768"
    };
    public static final String[] MODEL_LABELS = {
            "Llama 3.3 70B (качество)",
            "Llama 3.1 8B (быстрая)",
            "Llama 3.1 70B",
            "Gemma 2 9B",
            "Mixtral 8x7B"
    };

    private static final ExecutorService executor = Executors.newSingleThreadExecutor();
    private static final Handler mainHandler = new Handler(Looper.getMainLooper());
    public static final ThreadLocal<Boolean> skipRewrite = new ThreadLocal<>();

    /** Чтобы не отвечать повторно на то же сообщение */
    private static final ConcurrentHashMap<String, Long> recentAutoReplies = new ConcurrentHashMap<>();

    public interface Callback {
        void onResult(String text);
        void onError(String error);
    }

    private static SharedPreferences prefs(int account) {
        return ApplicationLoader.applicationContext.getSharedPreferences(PREFS_PREFIX + account, Context.MODE_PRIVATE);
    }

    public static boolean isRewriteEnabled(int account) {
        try { return prefs(account).getBoolean("rewrite_enabled", false); }
        catch (Throwable t) { return false; }
    }

    public static boolean isAutoReplyEnabled(int account) {
        try { return prefs(account).getBoolean("auto_reply_enabled", false); }
        catch (Throwable t) { return false; }
    }

    public static String getApiKey(int account) {
        try { return prefs(account).getString("api_key", ""); }
        catch (Throwable t) { return ""; }
    }

    public static String getPrompt(int account) {
        try {
            String p = prefs(account).getString("prompt", null);
            return TextUtils.isEmpty(p) ? DEFAULT_PROMPT : p;
        } catch (Throwable t) { return DEFAULT_PROMPT; }
    }

    public static String getAutoPrompt(int account) {
        try {
            String p = prefs(account).getString("auto_prompt", null);
            return TextUtils.isEmpty(p) ? DEFAULT_AUTO_PROMPT : p;
        } catch (Throwable t) { return DEFAULT_AUTO_PROMPT; }
    }

    public static String getModel(int account) {
        try {
            String m = prefs(account).getString("model", null);
            return TextUtils.isEmpty(m) ? DEFAULT_MODEL : m;
        } catch (Throwable t) { return DEFAULT_MODEL; }
    }

    public static Set<String> getAutoReplyUsers(int account) {
        try {
            Set<String> set = prefs(account).getStringSet("auto_users", null);
            return set != null ? new HashSet<>(set) : new HashSet<>();
        } catch (Throwable t) { return new HashSet<>(); }
    }

    public static void setRewriteEnabled(int account, boolean v) {
        prefs(account).edit().putBoolean("rewrite_enabled", v).apply();
    }

    public static void setAutoReplyEnabled(int account, boolean v) {
        prefs(account).edit().putBoolean("auto_reply_enabled", v).apply();
    }

    public static void setApiKey(int account, String key) {
        prefs(account).edit().putString("api_key", key == null ? "" : key.trim()).apply();
    }

    public static void setPrompt(int account, String prompt) {
        prefs(account).edit().putString("prompt", prompt == null ? "" : prompt).apply();
    }

    public static void setAutoPrompt(int account, String prompt) {
        prefs(account).edit().putString("auto_prompt", prompt == null ? "" : prompt).apply();
    }

    public static void setModel(int account, String model) {
        prefs(account).edit().putString("model", model == null || model.trim().isEmpty() ? DEFAULT_MODEL : model.trim()).apply();
    }

    public static void setAutoReplyUsers(int account, Set<String> users) {
        prefs(account).edit().putStringSet("auto_users", users != null ? users : new HashSet<>()).apply();
    }

    public static void addAutoReplyUser(int account, long userId) {
        Set<String> set = getAutoReplyUsers(account);
        set.add(String.valueOf(userId));
        setAutoReplyUsers(account, set);
    }

    public static void removeAutoReplyUser(int account, long userId) {
        Set<String> set = getAutoReplyUsers(account);
        set.remove(String.valueOf(userId));
        setAutoReplyUsers(account, set);
    }

    public static boolean isAutoReplyUser(int account, long userId) {
        return getAutoReplyUsers(account).contains(String.valueOf(userId));
    }

    public static void chat(final int account, final String systemPrompt, final String userMessage, final Callback callback) {
        if (TextUtils.isEmpty(userMessage)) {
            if (callback != null) callback.onResult("");
            return;
        }
        final String apiKey = getApiKey(account);
        if (TextUtils.isEmpty(apiKey)) {
            if (callback != null) callback.onError("API-ключ Groq не задан");
            return;
        }
        final String model = getModel(account);
        final String sysPrompt = systemPrompt != null ? systemPrompt : DEFAULT_PROMPT;

        executor.execute(() -> {
            try {
                JSONObject body = new JSONObject();
                body.put("model", model);
                body.put("temperature", 0.5);
                body.put("max_tokens", 1024);

                JSONArray messages = new JSONArray();
                JSONObject sys = new JSONObject();
                sys.put("role", "system");
                sys.put("content", sysPrompt);
                messages.put(sys);
                JSONObject user = new JSONObject();
                user.put("role", "user");
                user.put("content", userMessage);
                messages.put(user);
                body.put("messages", messages);

                URL url = new URL(GROQ_URL);
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("POST");
                conn.setConnectTimeout(15000);
                conn.setReadTimeout(45000);
                conn.setDoOutput(true);
                conn.setRequestProperty("Content-Type", "application/json");
                conn.setRequestProperty("Authorization", "Bearer " + apiKey);

                byte[] bytes = body.toString().getBytes(StandardCharsets.UTF_8);
                conn.setFixedLengthStreamingMode(bytes.length);
                OutputStream os = conn.getOutputStream();
                os.write(bytes);
                os.close();

                int code = conn.getResponseCode();
                BufferedReader reader = new BufferedReader(new InputStreamReader(
                        code >= 200 && code < 300 ? conn.getInputStream() : conn.getErrorStream(),
                        StandardCharsets.UTF_8));
                StringBuilder sb = new StringBuilder();
                String line;
                while ((line = reader.readLine()) != null) sb.append(line);
                reader.close();
                conn.disconnect();

                if (code < 200 || code >= 300) {
                    String err = sb.toString();
                    try {
                        JSONObject ej = new JSONObject(err);
                        if (ej.has("error")) err = ej.getJSONObject("error").optString("message", err);
                    } catch (Throwable ignore) {}
                    final String finalErr = err;
                    mainHandler.post(() -> { if (callback != null) callback.onError(finalErr); });
                    return;
                }

                JSONObject resp = new JSONObject(sb.toString());
                String result = resp.getJSONArray("choices").getJSONObject(0)
                        .getJSONObject("message").getString("content").trim();
                if (result.length() >= 2 && result.startsWith("\"") && result.endsWith("\"")) {
                    result = result.substring(1, result.length() - 1).trim();
                }
                final String finalResult = result;
                mainHandler.post(() -> { if (callback != null) callback.onResult(finalResult); });
            } catch (Throwable e) {
                FileLog.e(e);
                final String msg = e.getMessage() != null ? e.getMessage() : "Ошибка сети";
                mainHandler.post(() -> { if (callback != null) callback.onError(msg); });
            }
        });
    }

    public static void rewrite(final int account, final String original, final Callback callback) {
        chat(account, getPrompt(account), original, callback);
    }

    /**
     * Вызывается при получении нового входящего сообщения.
     * Если автоответчик включён и отправитель в списке — генерирует и отправляет ответ.
     */
    public static void onIncomingMessage(final int account, final TLRPC.Message message) {
        try {
            if (message == null || message.out) return;
            if (!isAutoReplyEnabled(account)) return;
            if (TextUtils.isEmpty(getApiKey(account))) return;

            long fromId = 0;
            if (message.from_id != null) {
                if (message.from_id.user_id != 0) fromId = message.from_id.user_id;
                else if (message.from_id.channel_id != 0) fromId = -message.from_id.channel_id;
            }
            if (fromId == 0 && message.peer_id != null && message.peer_id.user_id != 0) {
                fromId = message.peer_id.user_id;
            }
            if (fromId == 0 || !isAutoReplyUser(account, fromId)) return;

            // только личные чаты
            if (message.peer_id == null || message.peer_id.user_id == 0) return;

            String key = account + "_" + message.dialog_id + "_" + message.id;
            Long prev = recentAutoReplies.putIfAbsent(key, System.currentTimeMillis());
            if (prev != null) return;

            // чистим старые ключи
            if (recentAutoReplies.size() > 200) {
                long now = System.currentTimeMillis();
                recentAutoReplies.entrySet().removeIf(e -> now - e.getValue() > 600000);
            }

            String text = message.message;
            if (TextUtils.isEmpty(text)) {
                if (message.media != null) text = "[медиа]";
                else return;
            }

            final long dialogId = message.dialog_id != 0 ? message.dialog_id : fromId;
            final String incoming = text;

            // небольшая задержка, чтобы выглядело естественнее
            mainHandler.postDelayed(() -> {
                chat(account, getAutoPrompt(account), incoming, new Callback() {
                    @Override
                    public void onResult(String reply) {
                        if (TextUtils.isEmpty(reply)) return;
                        try {
                            SendMessagesHelper.SendMessageParams params =
                                    SendMessagesHelper.SendMessageParams.of(reply, dialogId);
                            params.notify = true;
                            SendMessagesHelper.getInstance(account).sendMessage(params);
                        } catch (Throwable e) {
                            FileLog.e(e);
                        }
                    }
                    @Override
                    public void onError(String error) {
                        FileLog.e("PikmiAI auto-reply error: " + error);
                    }
                });
            }, 1500 + (int) (Math.random() * 2000));
        } catch (Throwable e) {
            FileLog.e(e);
        }
    }
}
'''

JAVA_SETTINGS = r'''package org.telegram.ui;

import android.content.Context;
import android.content.DialogInterface;
import android.text.InputType;
import android.text.TextUtils;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.inputmethod.EditorInfo;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;

import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import org.telegram.messenger.AndroidUtilities;
import org.telegram.messenger.ContactsController;
import org.telegram.messenger.LocaleController;
import org.telegram.messenger.MessagesController;
import org.telegram.messenger.PikmiAI;
import org.telegram.messenger.R;
import org.telegram.messenger.UserObject;
import org.telegram.tgnet.TLRPC;
import org.telegram.ui.ActionBar.ActionBar;
import org.telegram.ui.ActionBar.BaseFragment;
import org.telegram.ui.ActionBar.Theme;
import org.telegram.ui.Cells.HeaderCell;
import org.telegram.ui.Cells.ShadowSectionCell;
import org.telegram.ui.Cells.TextCheckCell;
import org.telegram.ui.Cells.TextInfoPrivacyCell;
import org.telegram.ui.Cells.TextSettingsCell;
import org.telegram.ui.Components.EditTextBoldCursor;
import org.telegram.ui.Components.LayoutHelper;
import org.telegram.ui.Components.RecyclerListView;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.Set;

public class PikmiAISettingsActivity extends BaseFragment {

    private RecyclerListView listView;
    private ListAdapter adapter;

    private int rowCount;
    private int headerRow;
    private int rewriteRow;
    private int autoReplyRow;
    private int modelRow;
    private int section1Row;
    private int apiKeyHeaderRow;
    private int apiKeyRow;
    private int promptHeaderRow;
    private int promptRow;
    private int autoPromptHeaderRow;
    private int autoPromptRow;
    private int resetPromptRow;
    private int section2Row;
    private int usersHeaderRow;
    private int usersStartRow;
    private int usersEndRow;
    private int addUserRow;
    private int section3Row;
    private int infoRow;

    private EditTextBoldCursor apiKeyEdit;
    private EditTextBoldCursor promptEdit;
    private EditTextBoldCursor autoPromptEdit;

    private ArrayList<Long> userList = new ArrayList<>();

    @Override
    public boolean onFragmentCreate() {
        super.onFragmentCreate();
        loadUsers();
        updateRows();
        return true;
    }

    private void loadUsers() {
        userList.clear();
        Set<String> set = PikmiAI.getAutoReplyUsers(currentAccount);
        for (String s : set) {
            try { userList.add(Long.parseLong(s)); } catch (Exception ignore) {}
        }
    }

    private void updateRows() {
        rowCount = 0;
        headerRow = rowCount++;
        rewriteRow = rowCount++;
        autoReplyRow = rowCount++;
        modelRow = rowCount++;
        section1Row = rowCount++;
        apiKeyHeaderRow = rowCount++;
        apiKeyRow = rowCount++;
        promptHeaderRow = rowCount++;
        promptRow = rowCount++;
        autoPromptHeaderRow = rowCount++;
        autoPromptRow = rowCount++;
        resetPromptRow = rowCount++;
        section2Row = rowCount++;
        usersHeaderRow = rowCount++;
        usersStartRow = rowCount;
        rowCount += userList.size();
        usersEndRow = rowCount;
        addUserRow = rowCount++;
        section3Row = rowCount++;
        infoRow = rowCount++;
    }

    @Override
    public View createView(Context context) {
        actionBar.setBackButtonImage(R.drawable.ic_ab_back);
        actionBar.setAllowOverlayTitle(true);
        actionBar.setTitle("Pikmi AI (Groq)");
        actionBar.setActionBarMenuOnItemClick(new ActionBar.ActionBarMenuOnItemClick() {
            @Override
            public void onItemClick(int id) {
                if (id == -1) finishFragment();
            }
        });

        fragmentView = new FrameLayout(context);
        FrameLayout frame = (FrameLayout) fragmentView;
        frame.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundGray));

        listView = new RecyclerListView(context);
        listView.setLayoutManager(new LinearLayoutManager(context, LinearLayoutManager.VERTICAL, false));
        listView.setVerticalScrollBarEnabled(false);
        frame.addView(listView, LayoutHelper.createFrame(LayoutHelper.MATCH_PARENT, LayoutHelper.MATCH_PARENT));
        adapter = new ListAdapter(context);
        listView.setAdapter(adapter);

        listView.setOnItemClickListener((view, position) -> {
            if (position == rewriteRow) {
                boolean next = !PikmiAI.isRewriteEnabled(currentAccount);
                PikmiAI.setRewriteEnabled(currentAccount, next);
                if (view instanceof TextCheckCell) ((TextCheckCell) view).setChecked(next);
            } else if (position == autoReplyRow) {
                boolean next = !PikmiAI.isAutoReplyEnabled(currentAccount);
                PikmiAI.setAutoReplyEnabled(currentAccount, next);
                if (view instanceof TextCheckCell) ((TextCheckCell) view).setChecked(next);
            } else if (position == modelRow) {
                showModelDialog();
            } else if (position == resetPromptRow) {
                PikmiAI.setPrompt(currentAccount, PikmiAI.DEFAULT_PROMPT);
                PikmiAI.setAutoPrompt(currentAccount, PikmiAI.DEFAULT_AUTO_PROMPT);
                if (promptEdit != null) promptEdit.setText(PikmiAI.DEFAULT_PROMPT);
                if (autoPromptEdit != null) autoPromptEdit.setText(PikmiAI.DEFAULT_AUTO_PROMPT);
                AndroidUtilities.runOnUIThread(() -> {
                    if (getParentActivity() != null)
                        android.widget.Toast.makeText(getParentActivity(), "Промпты сброшены", android.widget.Toast.LENGTH_SHORT).show();
                });
            } else if (position == addUserRow) {
                showAddUserDialog();
            } else if (position >= usersStartRow && position < usersEndRow) {
                final long uid = userList.get(position - usersStartRow);
                new android.app.AlertDialog.Builder(getParentActivity())
                        .setTitle("Удалить?")
                        .setMessage("Убрать пользователя из автоответчика?")
                        .setPositiveButton("Удалить", (d, w) -> {
                            PikmiAI.removeAutoReplyUser(currentAccount, uid);
                            loadUsers();
                            updateRows();
                            adapter.notifyDataSetChanged();
                        })
                        .setNegativeButton("Отмена", null)
                        .show();
            }
        });

        return fragmentView;
    }

    private void showModelDialog() {
        if (getParentActivity() == null) return;
        final String current = PikmiAI.getModel(currentAccount);
        final String[] labels = new String[PikmiAI.MODEL_LABELS.length + 1];
        System.arraycopy(PikmiAI.MODEL_LABELS, 0, labels, 0, PikmiAI.MODEL_LABELS.length);
        labels[labels.length - 1] = "Своя модель…";

        int checked = labels.length - 1;
        for (int i = 0; i < PikmiAI.MODELS.length; i++) {
            if (PikmiAI.MODELS[i].equals(current)) { checked = i; break; }
        }

        new android.app.AlertDialog.Builder(getParentActivity())
                .setTitle("Модель Groq")
                .setSingleChoiceItems(labels, checked, (d, which) -> {
                    if (which < PikmiAI.MODELS.length) {
                        PikmiAI.setModel(currentAccount, PikmiAI.MODELS[which]);
                        if (adapter != null) adapter.notifyItemChanged(modelRow);
                        d.dismiss();
                    } else {
                        d.dismiss();
                        showCustomModelDialog(current);
                    }
                })
                .setNegativeButton("Отмена", null)
                .show();
    }

    private void showCustomModelDialog(String current) {
        if (getParentActivity() == null) return;
        final EditText input = new EditText(getParentActivity());
        input.setHint("например llama-3.3-70b-versatile");
        input.setSingleLine(true);
        input.setText(current);
        input.setPadding(AndroidUtilities.dp(20), AndroidUtilities.dp(16), AndroidUtilities.dp(20), AndroidUtilities.dp(16));
        new android.app.AlertDialog.Builder(getParentActivity())
                .setTitle("Своя модель")
                .setView(input)
                .setPositiveButton("Сохранить", (d, w) -> {
                    String m = input.getText().toString().trim();
                    if (!TextUtils.isEmpty(m)) {
                        PikmiAI.setModel(currentAccount, m);
                        if (adapter != null) adapter.notifyItemChanged(modelRow);
                    }
                })
                .setNegativeButton("Отмена", null)
                .show();
    }

    private void showAddUserDialog() {
        if (getParentActivity() == null) return;
        final EditText input = new EditText(getParentActivity());
        input.setHint("ID пользователя или @username");
        input.setSingleLine(true);
        input.setPadding(AndroidUtilities.dp(20), AndroidUtilities.dp(16), AndroidUtilities.dp(20), AndroidUtilities.dp(16));
        new android.app.AlertDialog.Builder(getParentActivity())
                .setTitle("Добавить в автоответчик")
                .setMessage("Введите числовой ID пользователя или @username")
                .setView(input)
                .setPositiveButton("Добавить", (d, w) -> {
                    String raw = input.getText().toString().trim();
                    if (TextUtils.isEmpty(raw)) return;
                    if (raw.startsWith("@")) raw = raw.substring(1);
                    try {
                        long id = Long.parseLong(raw);
                        PikmiAI.addAutoReplyUser(currentAccount, id);
                        loadUsers();
                        updateRows();
                        adapter.notifyDataSetChanged();
                    } catch (NumberFormatException e) {
                        // username — резолвим
                        final String username = raw;
                        AndroidUtilities.runOnUIThread(() -> {
                            if (getParentActivity() != null)
                                android.widget.Toast.makeText(getParentActivity(), "Резолв @" + username + "…", android.widget.Toast.LENGTH_SHORT).show();
                        });
                        MessagesController.getInstance(currentAccount).getUserNameResolver().resolve(username, (peerId) -> {
                            if (peerId != null && peerId != 0) {
                                long id = peerId > 0 ? peerId : -peerId;
                                // для user peerId положительный
                                if (peerId > 0) {
                                    PikmiAI.addAutoReplyUser(currentAccount, peerId);
                                    AndroidUtilities.runOnUIThread(() -> {
                                        loadUsers();
                                        updateRows();
                                        if (adapter != null) adapter.notifyDataSetChanged();
                                        if (getParentActivity() != null)
                                            android.widget.Toast.makeText(getParentActivity(), "Добавлен: " + peerId, android.widget.Toast.LENGTH_SHORT).show();
                                    });
                                } else {
                                    AndroidUtilities.runOnUIThread(() -> {
                                        if (getParentActivity() != null)
                                            android.widget.Toast.makeText(getParentActivity(), "Нужен пользователь, не канал/чат", android.widget.Toast.LENGTH_SHORT).show();
                                    });
                                }
                            } else {
                                AndroidUtilities.runOnUIThread(() -> {
                                    if (getParentActivity() != null)
                                        android.widget.Toast.makeText(getParentActivity(), "Пользователь не найден", android.widget.Toast.LENGTH_SHORT).show();
                                });
                            }
                        });
                    }
                })
                .setNegativeButton("Отмена", null)
                .show();
    }

    @Override
    public void onPause() {
        super.onPause();
        if (apiKeyEdit != null) PikmiAI.setApiKey(currentAccount, apiKeyEdit.getText().toString());
        if (promptEdit != null) PikmiAI.setPrompt(currentAccount, promptEdit.getText().toString());
        if (autoPromptEdit != null) PikmiAI.setAutoPrompt(currentAccount, autoPromptEdit.getText().toString());
    }

    private class ListAdapter extends RecyclerListView.SelectionAdapter {
        private final Context mContext;

        public ListAdapter(Context context) { mContext = context; }

        @Override
        public boolean isEnabled(RecyclerView.ViewHolder holder) {
            int pos = holder.getAdapterPosition();
            return pos == rewriteRow || pos == autoReplyRow || pos == modelRow || pos == resetPromptRow
                    || pos == addUserRow || (pos >= usersStartRow && pos < usersEndRow);
        }

        @Override
        public int getItemCount() { return rowCount; }

        @Override
        public int getItemViewType(int position) {
            if (position == headerRow || position == apiKeyHeaderRow || position == promptHeaderRow
                    || position == autoPromptHeaderRow || position == usersHeaderRow) return 0;
            if (position == rewriteRow || position == autoReplyRow) return 1;
            if (position == section1Row || position == section2Row || position == section3Row) return 2;
            if (position == apiKeyRow || position == promptRow || position == autoPromptRow) return 3;
            if (position == modelRow || position == resetPromptRow || position == addUserRow
                    || (position >= usersStartRow && position < usersEndRow)) return 4;
            return 5;
        }

        @Override
        public RecyclerView.ViewHolder onCreateViewHolder(ViewGroup parent, int viewType) {
            View view;
            switch (viewType) {
                case 0:
                    view = new HeaderCell(mContext);
                    view.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundWhite));
                    break;
                case 1:
                    view = new TextCheckCell(mContext);
                    view.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundWhite));
                    break;
                case 2:
                    view = new ShadowSectionCell(mContext);
                    break;
                case 3: {
                    FrameLayout frame = new FrameLayout(mContext);
                    frame.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundWhite));
                    EditTextBoldCursor edit = new EditTextBoldCursor(mContext);
                    edit.setTextSize(TypedValue.COMPLEX_UNIT_DIP, 16);
                    edit.setHintTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteHintText));
                    edit.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText));
                    edit.setBackground(null);
                    edit.setPadding(AndroidUtilities.dp(21), AndroidUtilities.dp(15), AndroidUtilities.dp(21), AndroidUtilities.dp(15));
                    edit.setGravity(Gravity.START | Gravity.TOP);
                    frame.addView(edit, LayoutHelper.createFrame(LayoutHelper.MATCH_PARENT, LayoutHelper.WRAP_CONTENT));
                    view = frame;
                    break;
                }
                case 4:
                    view = new TextSettingsCell(mContext);
                    view.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundWhite));
                    break;
                default:
                    view = new TextInfoPrivacyCell(mContext);
                    break;
            }
            return new RecyclerListView.Holder(view);
        }

        @Override
        public void onBindViewHolder(RecyclerView.ViewHolder holder, int position) {
            switch (holder.getItemViewType()) {
                case 0: {
                    HeaderCell cell = (HeaderCell) holder.itemView;
                    if (position == headerRow) cell.setText("Функции");
                    else if (position == apiKeyHeaderRow) cell.setText("API-ключ Groq");
                    else if (position == promptHeaderRow) cell.setText("Промпт переписи исходящих");
                    else if (position == autoPromptHeaderRow) cell.setText("Промпт автоответчика");
                    else if (position == usersHeaderRow) cell.setText("Кому отвечать автоматически");
                    break;
                }
                case 1: {
                    TextCheckCell cell = (TextCheckCell) holder.itemView;
                    if (position == rewriteRow)
                        cell.setTextAndCheck("Переписывать исходящие", PikmiAI.isRewriteEnabled(currentAccount), true);
                    else if (position == autoReplyRow)
                        cell.setTextAndCheck("Автоответчик", PikmiAI.isAutoReplyEnabled(currentAccount), true);
                    break;
                }
                case 3: {
                    FrameLayout frame = (FrameLayout) holder.itemView;
                    EditTextBoldCursor edit = (EditTextBoldCursor) frame.getChildAt(0);
                    if (position == apiKeyRow) {
                        apiKeyEdit = edit;
                        edit.setHint("gsk_...");
                        edit.setSingleLine(true);
                        edit.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD);
                        String key = PikmiAI.getApiKey(currentAccount);
                        if (!TextUtils.equals(edit.getText(), key)) edit.setText(key);
                        edit.setMinHeight(AndroidUtilities.dp(50));
                    } else if (position == promptRow) {
                        promptEdit = edit;
                        edit.setHint("Как переписывать исходящие…");
                        edit.setSingleLine(false);
                        edit.setMinLines(3);
                        edit.setMaxLines(8);
                        String p = PikmiAI.getPrompt(currentAccount);
                        if (!TextUtils.equals(edit.getText(), p)) edit.setText(p);
                    } else if (position == autoPromptRow) {
                        autoPromptEdit = edit;
                        edit.setHint("Как отвечать автоматически…");
                        edit.setSingleLine(false);
                        edit.setMinLines(3);
                        edit.setMaxLines(8);
                        String p = PikmiAI.getAutoPrompt(currentAccount);
                        if (!TextUtils.equals(edit.getText(), p)) edit.setText(p);
                    }
                    break;
                }
                case 4: {
                    TextSettingsCell cell = (TextSettingsCell) holder.itemView;
                    cell.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText));
                    if (position == modelRow) {
                        String model = PikmiAI.getModel(currentAccount);
                        String label = model;
                        for (int i = 0; i < PikmiAI.MODELS.length; i++) {
                            if (PikmiAI.MODELS[i].equals(model)) { label = PikmiAI.MODEL_LABELS[i]; break; }
                        }
                        cell.setTextAndValue("Модель", label, true);
                    } else if (position == resetPromptRow) {
                        cell.setText("Сбросить промпты по умолчанию", false);
                        cell.setTextColor(Theme.getColor(Theme.key_text_RedRegular));
                    } else if (position == addUserRow) {
                        cell.setText("Добавить пользователя", false);
                        cell.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlueText2));
                    } else if (position >= usersStartRow && position < usersEndRow) {
                        long uid = userList.get(position - usersStartRow);
                        TLRPC.User user = MessagesController.getInstance(currentAccount).getUser(uid);
                        String name = user != null ? UserObject.getUserName(user) : ("ID " + uid);
                        cell.setTextAndValue(name, String.valueOf(uid), true);
                    }
                    break;
                }
                case 5: {
                    TextInfoPrivacyCell cell = (TextInfoPrivacyCell) holder.itemView;
                    cell.setText("Настройки отдельные для каждого аккаунта.\nМодель: " + PikmiAI.getModel(currentAccount) +
                            "\n\nАвтоответчик отвечает только пользователям из списка (личные чаты). " +
                            "Можно указать ID или @username.");
                    cell.setBackground(Theme.getThemedDrawableByKey(mContext, R.drawable.greydivider, Theme.key_windowBackgroundGrayShadow));
                    break;
                }
            }
        }
    }
}
'''


def die(msg, hint=None):
    print("ОШИБКА: " + msg)
    if hint:
        print("--- подсказка ---")
        print(hint)
    sys.exit(1)


def main():
    HELPER.parent.mkdir(parents=True, exist_ok=True)
    HELPER.write_text(JAVA_HELPER, encoding="utf-8")
    print("PikmiAI.java: создан")

    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(JAVA_SETTINGS, encoding="utf-8")
    print("PikmiAISettingsActivity.java: создан")

    # меню
    if not DA.exists():
        die("не найден DialogsActivity.java")
    da = DA.read_text(encoding="utf-8")
    if "PG_AI_MENU" not in da:
        if "PikmiUpdater.check(getParentActivity(), true);" in da:
            da = da.replace(
                "org.telegram.messenger.PikmiUpdater.check(getParentActivity(), true);\n        });",
                "org.telegram.messenger.PikmiUpdater.check(getParentActivity(), true);\n        });\n"
                "        io.add(R.drawable.msg_edit, \"PikmiGram: AI (Groq)\", () -> { // PG_AI_MENU\n"
                "            presentFragment(new org.telegram.ui.PikmiAISettingsActivity());\n"
                "        });",
                1
            )
        else:
            rx = re.compile(
                r"(io\.add\(R\.drawable\.outline_groups_24, getString\(R\.string\.NewGroup\), \(\) -> \{\s*"
                r"Bundle args = new Bundle\(\);\s*"
                r"presentFragment\(new GroupCreateActivity\(args\)\);\s*\}\);)"
            )
            if not rx.search(da):
                die("DialogsActivity: не нашёл якорь меню")
            insert = (
                "\n        io.addGap();\n"
                "        io.add(R.drawable.msg_edit, \"PikmiGram: AI (Groq)\", () -> { // PG_AI_MENU\n"
                "            presentFragment(new org.telegram.ui.PikmiAISettingsActivity());\n"
                "        });"
            )
            da = rx.sub(lambda m: m.group(1) + insert, da, count=1)
        DA.write_text(da, encoding="utf-8")
        print("меню AI: добавлено")
    else:
        if "PikmiAI.showSettings" in da:
            da = da.replace(
                "org.telegram.messenger.PikmiAI.showSettings(getParentActivity(), currentAccount);",
                "presentFragment(new org.telegram.ui.PikmiAISettingsActivity());"
            )
            DA.write_text(da, encoding="utf-8")
        print("меню AI: уже есть")

    # перехват исходящих
    if not CAE.exists():
        die("не найден ChatActivityEnterView.java")
    cae = CAE.read_text(encoding="utf-8")
    if "PG_AI_REWRITE" not in cae:
        sig = (
            "public boolean processSendingText(CharSequence text, boolean notify, int scheduleDate, "
            "int scheduleRepeatPeriod, long payStars) {"
        )
        if sig not in cae:
            die("ChatActivityEnterView: не нашёл processSendingText")
        insert = '''public boolean processSendingText(CharSequence text, boolean notify, int scheduleDate, int scheduleRepeatPeriod, long payStars) {
        // PG_AI_REWRITE
        if (org.telegram.messenger.PikmiAI.isRewriteEnabled(currentAccount)
                && text != null && text.length() > 0
                && !Boolean.TRUE.equals(org.telegram.messenger.PikmiAI.skipRewrite.get())) {
            final CharSequence original = text;
            final boolean fNotify = notify;
            final int fScheduleDate = scheduleDate;
            final int fScheduleRepeatPeriod = scheduleRepeatPeriod;
            final long fPayStars = payStars;
            org.telegram.messenger.PikmiAI.rewrite(currentAccount, original.toString(), new org.telegram.messenger.PikmiAI.Callback() {
                @Override
                public void onResult(String newText) {
                    org.telegram.messenger.PikmiAI.skipRewrite.set(Boolean.TRUE);
                    try {
                        processSendingText(newText, fNotify, fScheduleDate, fScheduleRepeatPeriod, fPayStars);
                    } finally {
                        org.telegram.messenger.PikmiAI.skipRewrite.set(null);
                    }
                }
                @Override
                public void onError(String error) {
                    if (parentActivity != null) {
                        android.widget.Toast.makeText(parentActivity, "AI: " + error, android.widget.Toast.LENGTH_SHORT).show();
                    }
                    org.telegram.messenger.PikmiAI.skipRewrite.set(Boolean.TRUE);
                    try {
                        processSendingText(original, fNotify, fScheduleDate, fScheduleRepeatPeriod, fPayStars);
                    } finally {
                        org.telegram.messenger.PikmiAI.skipRewrite.set(null);
                    }
                }
            });
            return true;
        }
'''
        cae = cae.replace(sig, insert, 1)
        CAE.write_text(cae, encoding="utf-8")
        print("перехват исходящих: добавлен")
    else:
        print("перехват исходящих: уже есть")

    # автоответчик — хук в MessagesController при обработке новых сообщений
    if not MC.exists():
        die("не найден MessagesController.java")
    mc = MC.read_text(encoding="utf-8")
    if "PG_AI_AUTOREPLY" in mc:
        print("автоответчик: уже есть")
    else:
        # Ищем место после обработки нового сообщения. Типичный якорь — processNewMessages / processNewDifference
        # Более надёжно: в конце processUpdateArray или когда message кладётся в dialogs
        # Простой якорь: вызов updateInterfaceWithMessages или putMessage
        anchor = None
        # Вариант: после "messagesDict[a].put(message.id, messageObject);" в processNewMessages-подобном коде
        # Ищем характерный фрагмент
        candidates = [
            "updateInterfaceWithMessages(messageObject.getDialogId(), messageObjects, from",
            "updateInterfaceWithMessages(dialogId, arrayList, ",
        ]
        for c in candidates:
            if c in mc:
                anchor = c
                break

        if anchor:
            # Вставляем вызов перед updateInterfaceWithMessages для каждого messageObject — сложно.
            # Проще: вставить в цикл где messageObject создаётся.
            pass

        # Надёжный вариант — хук в MessagesController.processNewDifference / при new messages
        # Ищем: for (int a = 0; a < messages.size(); a++) { MessageObject messageObject
        old_hook = (
            "                    boolean isDialogCreated = createdDialogIds.contains(message.dialog_id);\n"
            "                    MessageObject obj = new MessageObject(currentAccount, message, usersDict, chatsDict, isDialogCreated, isDialogCreated);\n"
            "                    if (obj.type == MessageObject.TYPE_ACTION_PHOTO) {"
        )
        new_hook = (
            "                    boolean isDialogCreated = createdDialogIds.contains(message.dialog_id);\n"
            "                    MessageObject obj = new MessageObject(currentAccount, message, usersDict, chatsDict, isDialogCreated, isDialogCreated);\n"
            "                    if (!message.out && message.action == null) { // PG_AI_AUTOREPLY\n"
            "                        org.telegram.messenger.PikmiAI.onIncomingMessage(currentAccount, message);\n"
            "                    }\n"
            "                    if (obj.type == MessageObject.TYPE_ACTION_PHOTO) {"
        )
        if old_hook in mc:
            mc = mc.replace(old_hook, new_hook, 1)
            MC.write_text(mc, encoding="utf-8")
            print("автоответчик: хук добавлен")
        else:
            print("предупреждение: не нашёл якорь для хука автоответчика в processUpdateArray")

    print("Готово: Pikmi AI — своя модель + автоответчик со списком пользователей")


if __name__ == "__main__":
    main()
