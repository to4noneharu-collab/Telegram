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
AL = Path("TMessagesProj/src/main/java/org/telegram/messenger/ApplicationLoader.java")

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
            "Ты отвечаешь в мессенджере от моего имени. Учитывай историю переписки. " +
            "Ответь кратко, по делу и вежливо. Не представляйся, не пиши что ты ИИ. Верни только текст ответа.";
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

    /** История диалогов: key = account_dialogId → список {role, content} */
    private static final ConcurrentHashMap<String, java.util.LinkedList<String[]>> dialogHistory = new ConcurrentHashMap<>();

    public static int getHistoryLimit(int account) {
        try { return prefs(account).getInt("history_limit", 12); }
        catch (Throwable t) { return 12; }
    }

    public static void setHistoryLimit(int account, int n) {
        prefs(account).edit().putInt("history_limit", Math.max(0, Math.min(40, n))).apply();
    }

    public static boolean isHistoryEnabled(int account) {
        try { return prefs(account).getBoolean("history_enabled", true); }
        catch (Throwable t) { return true; }
    }

    public static void setHistoryEnabled(int account, boolean v) {
        prefs(account).edit().putBoolean("history_enabled", v).apply();
    }

    private static String histKey(int account, long dialogId) {
        return account + "_" + dialogId;
    }

    public static void addToHistory(int account, long dialogId, String role, String content) {
        if (!isHistoryEnabled(account) || content == null || content.length() == 0) return;
        int limit = getHistoryLimit(account);
        if (limit <= 0) return;
        String key = histKey(account, dialogId);
        java.util.LinkedList<String[]> list = dialogHistory.get(key);
        if (list == null) {
            list = new java.util.LinkedList<>();
            dialogHistory.put(key, list);
        }
        // не дублируем подряд одинаковые
        if (!list.isEmpty()) {
            String[] last = list.getLast();
            if (role.equals(last[0]) && content.equals(last[1])) return;
        }
        list.add(new String[]{role, content});
        while (list.size() > limit) {
            list.removeFirst();
        }
    }

    public static void clearHistory(int account, long dialogId) {
        dialogHistory.remove(histKey(account, dialogId));
    }

    public static void clearAllHistory(int account) {
        String prefix = account + "_";
        dialogHistory.keySet().removeIf(k -> k.startsWith(prefix));
    }

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
        chat(account, systemPrompt, userMessage, 0, callback);
    }

    public static void chat(final int account, final String systemPrompt, final String userMessage, final long dialogId, final Callback callback) {
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

        // снимок истории
        final java.util.ArrayList<String[]> histSnapshot = new java.util.ArrayList<>();
        if (dialogId != 0 && isHistoryEnabled(account)) {
            java.util.LinkedList<String[]> list = dialogHistory.get(histKey(account, dialogId));
            if (list != null) {
                histSnapshot.addAll(list);
            }
        }

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

                // история (без последнего user, его добавим отдельно)
                for (int i = 0; i < histSnapshot.size(); i++) {
                    String[] pair = histSnapshot.get(i);
                    JSONObject m = new JSONObject();
                    m.put("role", pair[0]);
                    m.put("content", pair[1]);
                    messages.put(m);
                }

                // текущее сообщение пользователя (если его ещё нет в конце истории)
                boolean needUser = true;
                if (!histSnapshot.isEmpty()) {
                    String[] last = histSnapshot.get(histSnapshot.size() - 1);
                    if ("user".equals(last[0]) && userMessage.equals(last[1])) {
                        needUser = false;
                    }
                }
                if (needUser) {
                    JSONObject user = new JSONObject();
                    user.put("role", "user");
                    user.put("content", userMessage);
                    messages.put(user);
                }
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

    /** "private" = только ЛС, "all" = все чаты */
    public static String getAutoScope(int account) {
        try {
            String s = prefs(account).getString("auto_scope", "private");
            return TextUtils.isEmpty(s) ? "private" : s;
        } catch (Throwable t) { return "private"; }
    }

    public static void setAutoScope(int account, String scope) {
        if (!"all".equals(scope)) scope = "private";
        prefs(account).edit().putString("auto_scope", scope).apply();
    }

    /** Задержка «подумать» до начала набора, мс (по умолчанию 800) */
    public static int getThinkDelayMs(int account) {
        try { return prefs(account).getInt("think_delay_ms", 800); }
        catch (Throwable t) { return 800; }
    }
    public static void setThinkDelayMs(int account, int ms) {
        prefs(account).edit().putInt("think_delay_ms", Math.max(0, ms)).apply();
    }

    /** Скорость печати: миллисекунд на символ (по умолчанию 40 ≈ 25 симв/сек) */
    public static int getTypeMsPerChar(int account) {
        try { return prefs(account).getInt("type_ms_per_char", 40); }
        catch (Throwable t) { return 40; }
    }
    public static void setTypeMsPerChar(int account, int ms) {
        prefs(account).edit().putInt("type_ms_per_char", Math.max(0, ms)).apply();
    }

    /** Шанс дополнительного «раздумья» 0–100% (по умолчанию 30) */
    public static int getThinkChance(int account) {
        try { return prefs(account).getInt("think_chance", 30); }
        catch (Throwable t) { return 30; }
    }
    public static void setThinkChance(int account, int pct) {
        prefs(account).edit().putInt("think_chance", Math.max(0, Math.min(100, pct))).apply();
    }

    /** Длительность доп. раздумья, мс (по умолчанию 1200) */
    public static int getExtraThinkMs(int account) {
        try { return prefs(account).getInt("extra_think_ms", 1200); }
        catch (Throwable t) { return 1200; }
    }
    public static void setExtraThinkMs(int account, int ms) {
        prefs(account).edit().putInt("extra_think_ms", Math.max(0, ms)).apply();
    }

    private static boolean observersRegistered = false;

    /** Подписка на новые сообщения для всех аккаунтов */
    public static synchronized void ensureObservers() {
        if (observersRegistered) return;
        observersRegistered = true;
        for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {
            final int account = a;
            NotificationCenter.getInstance(account).addObserver(new NotificationCenter.NotificationCenterDelegate() {
                @Override
                public void didReceivedNotification(int id, int account2, Object... args) {
                    if (id != NotificationCenter.didReceiveNewMessages) return;
                    try {
                        if (args == null || args.length < 2) return;
                        boolean scheduled = args.length > 2 && args[2] instanceof Boolean && (Boolean) args[2];
                        if (scheduled) return;
                        ArrayList<MessageObject> messages = (ArrayList<MessageObject>) args[1];
                        if (messages == null) return;
                        for (int i = 0; i < messages.size(); i++) {
                            MessageObject mo = messages.get(i);
                            if (mo != null && mo.messageOwner != null) {
                                onIncomingMessage(account, mo.messageOwner);
                            }
                        }
                    } catch (Throwable e) {
                        FileLog.e(e);
                    }
                }
            }, NotificationCenter.didReceiveNewMessages);
        }
        FileLog.d("PikmiAI: auto-reply observers registered");
    }

    /**
     * Если автоответчик включён и отправитель в списке — генерирует и отправляет ответ.
     */
    public static void onIncomingMessage(final int account, final TLRPC.Message message) {
        try {
            ensureObservers(); // на всякий случай
            if (message == null || message.out) return;
            if (message.action != null) return;
            if (!isAutoReplyEnabled(account)) return;
            if (TextUtils.isEmpty(getApiKey(account))) return;

            long dialogId = MessageObject.getDialogId(message);
            if (dialogId == 0) return;

            boolean isPrivate = dialogId > 0;
            String scope = getAutoScope(account);
            if ("private".equals(scope) && !isPrivate) return;

            long fromId = 0;
            if (message.from_id != null) {
                if (message.from_id.user_id != 0) fromId = message.from_id.user_id;
            }
            if (fromId == 0 && isPrivate) {
                fromId = dialogId;
            }
            if (fromId == 0) return;
            if (!isAutoReplyUser(account, fromId)) return;

            // не отвечаем самим себе
            if (fromId == UserConfig.getInstance(account).getClientUserId()) return;

            String key = account + "_" + dialogId + "_" + message.id;
            Long prev = recentAutoReplies.putIfAbsent(key, System.currentTimeMillis());
            if (prev != null) return;

            if (recentAutoReplies.size() > 300) {
                long now = System.currentTimeMillis();
                recentAutoReplies.entrySet().removeIf(e -> now - e.getValue() > 600000);
            }

            String text = message.message;
            if (TextUtils.isEmpty(text)) {
                if (message.media != null) text = "[медиа-сообщение]";
                else return;
            }

            final long finalDialogId = dialogId;
            final String incoming = text;
            final int msgId = message.id;

            // Сразу отмечаем прочитанным
            try {
                markDialogAsRead(account, finalDialogId, msgId);
            } catch (Throwable e) {
                FileLog.e(e);
            }

            final int thinkDelay = getThinkDelayMs(account);
            final int typeMs = getTypeMsPerChar(account);
            final int thinkChance = getThinkChance(account);
            final int extraThink = getExtraThinkMs(account);

            // сохраняем входящее в историю
            addToHistory(account, finalDialogId, "user", incoming);

            mainHandler.postDelayed(() -> {
                chat(account, getAutoPrompt(account), incoming, finalDialogId, new Callback() {
                    @Override
                    public void onResult(String reply) {
                        if (TextUtils.isEmpty(reply)) return;
                        addToHistory(account, finalDialogId, "assistant", reply);
                        simulateTypingAndSend(account, finalDialogId, reply, typeMs, thinkChance, extraThink);
                    }
                    @Override
                    public void onError(String error) {
                        FileLog.e("PikmiAI auto-reply error: " + error);
                    }
                });
            }, thinkDelay);
        } catch (Throwable e) {
            FileLog.e(e);
        }
    }

    private static void markDialogAsRead(int account, long dialogId, int maxId) {
        try {
            MessagesController mc = MessagesController.getInstance(account);
            // maxPositiveId, maxNegativeId, maxPositiveDate, maxNegativeDate, wasUnread, pinned, threadId, reaction, threadUnread, unreadCount
            mc.markDialogAsRead(dialogId, maxId, maxId, Math.max(1, (int) (System.currentTimeMillis() / 1000)), false, 0, 0, true, 0);
        } catch (Throwable e) {
            try {
                MessagesController.getInstance(account).markDialogAsRead(dialogId, maxId, maxId, 0, false, 0, 0, true, 0);
            } catch (Throwable e2) {
                FileLog.e(e2);
            }
        }
    }

    private static void simulateTypingAndSend(final int account, final long dialogId, final String reply,
                                              final int typeMsPerChar, final int thinkChance, final int extraThinkMs) {
        try {
            final MessagesController mc = MessagesController.getInstance(account);
            // action: 0 = typing
            mc.sendTyping(dialogId, 0, 0, 0);

            int typingDuration = Math.max(400, reply.length() * Math.max(0, typeMsPerChar));
            // ограничим, чтобы не висело минутами
            if (typingDuration > 15000) typingDuration = 15000;

            int pause = 0;
            if (thinkChance > 0 && (int) (Math.random() * 100) < thinkChance) {
                pause = extraThinkMs + (int) (Math.random() * Math.max(1, extraThinkMs / 2));
                // во время раздумья typing может пропасть — возобновим перед отправкой
            }

            final int totalDelay = typingDuration + pause;

            // периодически обновляем typing
            final int[] ticks = new int[]{0};
            final Runnable tick = new Runnable() {
                @Override
                public void run() {
                    try {
                        if (ticks[0] * 4000 < totalDelay) {
                            mc.sendTyping(dialogId, 0, 0, 0);
                            ticks[0]++;
                            mainHandler.postDelayed(this, 4000);
                        }
                    } catch (Throwable ignore) {}
                }
            };
            mainHandler.postDelayed(tick, 3500);

            mainHandler.postDelayed(() -> {
                try {
                    SendMessagesHelper.SendMessageParams params =
                            SendMessagesHelper.SendMessageParams.of(reply, dialogId);
                    params.notify = true;
                    SendMessagesHelper.getInstance(account).sendMessage(params);
                    FileLog.d("PikmiAI auto-reply sent to " + dialogId + " after " + totalDelay + "ms");
                } catch (Throwable e) {
                    FileLog.e(e);
                }
            }, totalDelay);
        } catch (Throwable e) {
            FileLog.e(e);
            try {
                SendMessagesHelper.SendMessageParams params =
                        SendMessagesHelper.SendMessageParams.of(reply, dialogId);
                params.notify = true;
                SendMessagesHelper.getInstance(account).sendMessage(params);
            } catch (Throwable e2) {
                FileLog.e(e2);
            }
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
    private int autoScopeRow;
    private int modelRow;
    private int thinkDelayRow;
    private int typeSpeedRow;
    private int thinkChanceRow;
    private int extraThinkRow;
    private int historyEnabledRow;
    private int historyLimitRow;
    private int clearHistoryRow;
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
        autoScopeRow = rowCount++;
        modelRow = rowCount++;
        thinkDelayRow = rowCount++;
        typeSpeedRow = rowCount++;
        thinkChanceRow = rowCount++;
        extraThinkRow = rowCount++;
        historyEnabledRow = rowCount++;
        historyLimitRow = rowCount++;
        clearHistoryRow = rowCount++;
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
        org.telegram.messenger.PikmiAI.ensureObservers();
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
            } else if (position == autoScopeRow) {
                final String cur = PikmiAI.getAutoScope(currentAccount);
                final String[] opts = new String[]{"Только личные чаты (ЛС)", "Все чаты"};
                int checked = "all".equals(cur) ? 1 : 0;
                new android.app.AlertDialog.Builder(getParentActivity())
                        .setTitle("Где работает автоответчик")
                        .setSingleChoiceItems(opts, checked, (d, which) -> {
                            PikmiAI.setAutoScope(currentAccount, which == 1 ? "all" : "private");
                            if (adapter != null) adapter.notifyItemChanged(autoScopeRow);
                            d.dismiss();
                        })
                        .setNegativeButton("Отмена", null)
                        .show();

            } else if (position == thinkDelayRow) {
                showNumberDialog("Задержка «подумать» (мс)", PikmiAI.getThinkDelayMs(currentAccount), v -> {
                    PikmiAI.setThinkDelayMs(currentAccount, v);
                    if (adapter != null) adapter.notifyItemChanged(thinkDelayRow);
                });
            } else if (position == typeSpeedRow) {
                showNumberDialog("Мс на символ (скорость печати)", PikmiAI.getTypeMsPerChar(currentAccount), v -> {
                    PikmiAI.setTypeMsPerChar(currentAccount, v);
                    if (adapter != null) adapter.notifyItemChanged(typeSpeedRow);
                });
            } else if (position == thinkChanceRow) {
                showNumberDialog("Шанс раздумий (0–100%)", PikmiAI.getThinkChance(currentAccount), v -> {
                    PikmiAI.setThinkChance(currentAccount, Math.min(100, v));
                    if (adapter != null) adapter.notifyItemChanged(thinkChanceRow);
                });
            } else if (position == extraThinkRow) {
                showNumberDialog("Длительность раздумий (мс)", PikmiAI.getExtraThinkMs(currentAccount), v -> {
                    PikmiAI.setExtraThinkMs(currentAccount, v);
                    if (adapter != null) adapter.notifyItemChanged(extraThinkRow);
                });

            } else if (position == historyEnabledRow) {
                boolean next = !PikmiAI.isHistoryEnabled(currentAccount);
                PikmiAI.setHistoryEnabled(currentAccount, next);
                if (view instanceof TextCheckCell) ((TextCheckCell) view).setChecked(next);
            } else if (position == historyLimitRow) {
                showNumberDialog("Сколько сообщений помнить (0–40)", PikmiAI.getHistoryLimit(currentAccount), v -> {
                    PikmiAI.setHistoryLimit(currentAccount, Math.min(40, v));
                    if (adapter != null) adapter.notifyItemChanged(historyLimitRow);
                });
            } else if (position == clearHistoryRow) {
                new android.app.AlertDialog.Builder(getParentActivity())
                        .setTitle("Очистить историю")
                        .setMessage("Сбросить память диалогов для этого аккаунта?")
                        .setPositiveButton("Очистить", (d, w) -> {
                            PikmiAI.clearAllHistory(currentAccount);
                            if (getParentActivity() != null)
                                android.widget.Toast.makeText(getParentActivity(), "История очищена", android.widget.Toast.LENGTH_SHORT).show();
                        })
                        .setNegativeButton("Отмена", null)
                        .show();

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


    private interface IntCallback { void onValue(int v); }

    private void showNumberDialog(String title, int current, IntCallback cb) {
        if (getParentActivity() == null) return;
        final EditText input = new EditText(getParentActivity());
        input.setInputType(android.text.InputType.TYPE_CLASS_NUMBER);
        input.setSingleLine(true);
        input.setText(String.valueOf(current));
        input.setPadding(AndroidUtilities.dp(20), AndroidUtilities.dp(16), AndroidUtilities.dp(20), AndroidUtilities.dp(16));
        new android.app.AlertDialog.Builder(getParentActivity())
                .setTitle(title)
                .setView(input)
                .setPositiveButton("OK", (d, w) -> {
                    try {
                        int v = Integer.parseInt(input.getText().toString().trim());
                        if (cb != null) cb.onValue(Math.max(0, v));
                    } catch (Exception ignore) {}
                })
                .setNegativeButton("Отмена", null)
                .show();
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
            return pos == rewriteRow || pos == autoReplyRow || pos == autoScopeRow || pos == modelRow
                    || pos == thinkDelayRow || pos == typeSpeedRow || pos == thinkChanceRow || pos == extraThinkRow
                    || pos == historyEnabledRow || pos == historyLimitRow || pos == clearHistoryRow
                    || pos == resetPromptRow
                    || pos == addUserRow || (pos >= usersStartRow && pos < usersEndRow);
        }

        @Override
        public int getItemCount() { return rowCount; }

        @Override
        public int getItemViewType(int position) {
            if (position == headerRow || position == apiKeyHeaderRow || position == promptHeaderRow
                    || position == autoPromptHeaderRow || position == usersHeaderRow) return 0;
            if (position == rewriteRow || position == autoReplyRow || position == historyEnabledRow) return 1;
            if (position == section1Row || position == section2Row || position == section3Row) return 2;
            if (position == apiKeyRow || position == promptRow || position == autoPromptRow) return 3;
            if (position == autoScopeRow || position == modelRow || position == thinkDelayRow || position == typeSpeedRow
                    || position == thinkChanceRow || position == extraThinkRow || position == historyLimitRow
                    || position == clearHistoryRow || position == resetPromptRow || position == addUserRow
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
                    else if (position == historyEnabledRow)
                        cell.setTextAndCheck("Память диалога", PikmiAI.isHistoryEnabled(currentAccount), true);
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

                    if (position == thinkDelayRow) {
                        cell.setTextAndValue("Подумать перед ответом", PikmiAI.getThinkDelayMs(currentAccount) + " мс", true);
                    } else if (position == typeSpeedRow) {
                        cell.setTextAndValue("Скорость печати", PikmiAI.getTypeMsPerChar(currentAccount) + " мс/символ", true);
                    } else if (position == thinkChanceRow) {
                        cell.setTextAndValue("Шанс раздумий", PikmiAI.getThinkChance(currentAccount) + "%", true);
                    } else if (position == extraThinkRow) {
                        cell.setTextAndValue("Длительность раздумий", PikmiAI.getExtraThinkMs(currentAccount) + " мс", true);
                    } else if (position == historyLimitRow) {
                        cell.setTextAndValue("Глубина истории", PikmiAI.getHistoryLimit(currentAccount) + " сообщ.", true);
                    } else if (position == clearHistoryRow) {
                        cell.setText("Очистить память диалогов", false);
                        cell.setTextColor(Theme.getColor(Theme.key_text_RedRegular));
                    } else if (position == autoScopeRow) {
                        String scope = PikmiAI.getAutoScope(currentAccount);
                        String label = "all".equals(scope) ? "Все чаты" : "Только ЛС";
                        cell.setTextAndValue("Область автоответа", label, true);
                    } else if (position == modelRow) {
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
                            "\nОбласть: " + ("all".equals(PikmiAI.getAutoScope(currentAccount)) ? "все чаты" : "только ЛС") +
                            "\n\nАвтоответчик отвечает пользователям из списка. " +
                            "Добавляйте по ID или @username.");
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


    # Ранняя регистрация observers в ApplicationLoader
    if AL.exists():
        al = AL.read_text(encoding="utf-8")
        if "PG_AI_OBSERVERS" not in al:
            if "applicationInited = true;" in al:
                al = al.replace(
                    "applicationInited = true;",
                    "applicationInited = true;\n"
                    "        AndroidUtilities.runOnUIThread(() -> {\n"
                    "            try { org.telegram.messenger.PikmiAI.ensureObservers(); } catch (Throwable ignore) {}\n"
                    "        }, 3000); // PG_AI_OBSERVERS",
                    1
                )
                AL.write_text(al, encoding="utf-8")
                print("observers: регистрация в ApplicationLoader")
            else:
                print("предупреждение: не нашёл applicationInited в ApplicationLoader")
        else:
            print("observers: уже есть в ApplicationLoader")
    else:
        print("ApplicationLoader.java не найден")

    print("Готово: Pikmi AI — своя модель + автоответчик (ЛС/все чаты)")



if __name__ == "__main__":
    main()
