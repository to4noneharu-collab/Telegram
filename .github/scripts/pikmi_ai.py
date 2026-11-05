#!/usr/bin/env python3
"""Pikmi AI (Groq): перепись исходящих + полноценный экран настроек.

- API-ключ и промпт задаются в клиенте
- Настройки индивидуальны для каждого аккаунта
- Экран настроек в стиле Telegram (BaseFragment + ячейки)
- Перед отправкой текст проходит через Groq

Идемпотентен.
"""
import re
import sys
from pathlib import Path

HELPER = Path("TMessagesProj/src/main/java/org/telegram/messenger/PikmiAI.java")
SETTINGS = Path("TMessagesProj/src/main/java/org/telegram/ui/PikmiAISettingsActivity.java")
CAE = Path("TMessagesProj/src/main/java/org/telegram/ui/Components/ChatActivityEnterView.java")
DA = Path("TMessagesProj/src/main/java/org/telegram/ui/DialogsActivity.java")

JAVA_HELPER = r'''package org.telegram.messenger;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Handler;
import android.os.Looper;
import android.text.TextUtils;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Pikmi AI на базе Groq.
 * Настройки (ключ, промпт, вкл/выкл) — отдельно для каждого аккаунта.
 */
public class PikmiAI {

    private static final String PREFS_PREFIX = "pikmigram_ai_";
    public static final String DEFAULT_PROMPT =
            "Перепиши сообщение вежливо, спокойно и без негатива. Сохрани смысл и язык оригинала. " +
            "Не добавляй приветствий, подписей и пояснений. Верни только готовый текст сообщения.";
    private static final String GROQ_URL = "https://api.groq.com/openai/v1/chat/completions";
    public static final String MODEL = "llama-3.3-70b-versatile";

    private static final ExecutorService executor = Executors.newSingleThreadExecutor();
    private static final Handler mainHandler = new Handler(Looper.getMainLooper());

    public static final ThreadLocal<Boolean> skipRewrite = new ThreadLocal<>();

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

    public static void rewrite(final int account, final String original, final Callback callback) {
        if (TextUtils.isEmpty(original)) {
            if (callback != null) callback.onResult(original);
            return;
        }
        final String apiKey = getApiKey(account);
        if (TextUtils.isEmpty(apiKey)) {
            if (callback != null) callback.onError("API-ключ Groq не задан");
            return;
        }
        final String systemPrompt = getPrompt(account);

        executor.execute(() -> {
            try {
                JSONObject body = new JSONObject();
                body.put("model", MODEL);
                body.put("temperature", 0.4);
                body.put("max_tokens", 1024);

                JSONArray messages = new JSONArray();
                JSONObject sys = new JSONObject();
                sys.put("role", "system");
                sys.put("content", systemPrompt);
                messages.put(sys);
                JSONObject user = new JSONObject();
                user.put("role", "user");
                user.put("content", original);
                messages.put(user);
                body.put("messages", messages);

                URL url = new URL(GROQ_URL);
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("POST");
                conn.setConnectTimeout(15000);
                conn.setReadTimeout(30000);
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
}
'''

JAVA_SETTINGS = r'''package org.telegram.ui;

import android.content.Context;
import android.graphics.Canvas;
import android.text.Editable;
import android.text.InputType;
import android.text.TextUtils;
import android.text.TextWatcher;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.inputmethod.EditorInfo;
import android.widget.FrameLayout;
import android.widget.LinearLayout;

import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import org.telegram.messenger.AndroidUtilities;
import org.telegram.messenger.LocaleController;
import org.telegram.messenger.PikmiAI;
import org.telegram.messenger.R;
import org.telegram.ui.ActionBar.ActionBar;
import org.telegram.ui.ActionBar.BaseFragment;
import org.telegram.ui.ActionBar.Theme;
import org.telegram.ui.ActionBar.ThemeDescription;
import org.telegram.ui.Cells.HeaderCell;
import org.telegram.ui.Cells.ShadowSectionCell;
import org.telegram.ui.Cells.TextCheckCell;
import org.telegram.ui.Cells.TextDetailSettingsCell;
import org.telegram.ui.Cells.TextInfoPrivacyCell;
import org.telegram.ui.Cells.TextSettingsCell;
import org.telegram.ui.Components.EditTextBoldCursor;
import org.telegram.ui.Components.LayoutHelper;
import org.telegram.ui.Components.RecyclerListView;

import java.util.ArrayList;

/**
 * Полноценный экран настроек Pikmi AI (Groq).
 * Настройки привязаны к текущему аккаунту.
 */
public class PikmiAISettingsActivity extends BaseFragment {

    private RecyclerListView listView;
    private ListAdapter adapter;

    private int rowCount;
    private int headerRow;
    private int rewriteRow;
    private int autoReplyRow;
    private int section1Row;
    private int apiKeyHeaderRow;
    private int apiKeyRow;
    private int promptHeaderRow;
    private int promptRow;
    private int resetPromptRow;
    private int section2Row;
    private int infoRow;

    private EditTextBoldCursor apiKeyEdit;
    private EditTextBoldCursor promptEdit;

    @Override
    public boolean onFragmentCreate() {
        super.onFragmentCreate();
        updateRows();
        return true;
    }

    private void updateRows() {
        rowCount = 0;
        headerRow = rowCount++;
        rewriteRow = rowCount++;
        autoReplyRow = rowCount++;
        section1Row = rowCount++;
        apiKeyHeaderRow = rowCount++;
        apiKeyRow = rowCount++;
        promptHeaderRow = rowCount++;
        promptRow = rowCount++;
        resetPromptRow = rowCount++;
        section2Row = rowCount++;
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
                if (id == -1) {
                    finishFragment();
                }
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
                if (view instanceof TextCheckCell) {
                    ((TextCheckCell) view).setChecked(next);
                }
            } else if (position == autoReplyRow) {
                // пока заглушка
            } else if (position == resetPromptRow) {
                PikmiAI.setPrompt(currentAccount, PikmiAI.DEFAULT_PROMPT);
                if (promptEdit != null) {
                    promptEdit.setText(PikmiAI.DEFAULT_PROMPT);
                }
                AndroidUtilities.runOnUIThread(() -> {
                    if (getParentActivity() != null) {
                        android.widget.Toast.makeText(getParentActivity(), "Промпт сброшен", android.widget.Toast.LENGTH_SHORT).show();
                    }
                });
            }
        });

        return fragmentView;
    }

    @Override
    public void onPause() {
        super.onPause();
        // сохраняем поля при уходе с экрана
        if (apiKeyEdit != null) {
            PikmiAI.setApiKey(currentAccount, apiKeyEdit.getText().toString());
        }
        if (promptEdit != null) {
            PikmiAI.setPrompt(currentAccount, promptEdit.getText().toString());
        }
    }

    private class ListAdapter extends RecyclerListView.SelectionAdapter {

        private final Context mContext;

        public ListAdapter(Context context) {
            mContext = context;
        }

        @Override
        public boolean isEnabled(RecyclerView.ViewHolder holder) {
            int pos = holder.getAdapterPosition();
            return pos == rewriteRow || pos == autoReplyRow || pos == resetPromptRow;
        }

        @Override
        public int getItemCount() {
            return rowCount;
        }

        @Override
        public int getItemViewType(int position) {
            if (position == headerRow || position == apiKeyHeaderRow || position == promptHeaderRow) {
                return 0; // HeaderCell
            }
            if (position == rewriteRow || position == autoReplyRow) {
                return 1; // TextCheckCell
            }
            if (position == section1Row || position == section2Row) {
                return 2; // ShadowSectionCell
            }
            if (position == apiKeyRow || position == promptRow) {
                return 3; // edit field
            }
            if (position == resetPromptRow) {
                return 4; // TextSettingsCell
            }
            if (position == infoRow) {
                return 5; // TextInfoPrivacyCell
            }
            return 0;
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
                case 5:
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
                    if (position == headerRow) {
                        cell.setText("Функции");
                    } else if (position == apiKeyHeaderRow) {
                        cell.setText("API-ключ Groq");
                    } else if (position == promptHeaderRow) {
                        cell.setText("Системный промпт");
                    }
                    break;
                }
                case 1: {
                    TextCheckCell cell = (TextCheckCell) holder.itemView;
                    if (position == rewriteRow) {
                        cell.setTextAndCheck("Переписывать исходящие", PikmiAI.isRewriteEnabled(currentAccount), true);
                    } else if (position == autoReplyRow) {
                        cell.setTextAndCheck("Автоответчик (скоро)", PikmiAI.isAutoReplyEnabled(currentAccount), false);
                        cell.setEnabled(false);
                    }
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
                        edit.setImeOptions(EditorInfo.IME_ACTION_DONE);
                        String key = PikmiAI.getApiKey(currentAccount);
                        if (!TextUtils.equals(edit.getText(), key)) {
                            edit.setText(key);
                        }
                        edit.setMinHeight(AndroidUtilities.dp(50));
                    } else if (position == promptRow) {
                        promptEdit = edit;
                        edit.setHint("Как переписывать сообщения...");
                        edit.setSingleLine(false);
                        edit.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
                        edit.setImeOptions(EditorInfo.IME_ACTION_NONE);
                        edit.setMinLines(4);
                        edit.setMaxLines(10);
                        String prompt = PikmiAI.getPrompt(currentAccount);
                        if (!TextUtils.equals(edit.getText(), prompt)) {
                            edit.setText(prompt);
                        }
                    }
                    break;
                }
                case 4: {
                    TextSettingsCell cell = (TextSettingsCell) holder.itemView;
                    cell.setText("Сбросить промпт по умолчанию", false);
                    cell.setTextColor(Theme.getColor(Theme.key_text_RedRegular));
                    break;
                }
                case 5: {
                    TextInfoPrivacyCell cell = (TextInfoPrivacyCell) holder.itemView;
                    cell.setText("Настройки сохраняются отдельно для каждого аккаунта.\nМодель: " + PikmiAI.MODEL + "\n\nПри включённой переписи исходящие сообщения перед отправкой проходят через Groq и уходят уже в отредактированном виде.");
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

    # --- меню: открываем Fragment ---
    if not DA.exists():
        die("не найден DialogsActivity.java")
    da = DA.read_text(encoding="utf-8")
    if "PG_AI_MENU" in da:
        # обновим вызов на presentFragment, если ещё старый showSettings
        if "PikmiAI.showSettings" in da:
            da = da.replace(
                "org.telegram.messenger.PikmiAI.showSettings(getParentActivity(), currentAccount);",
                "presentFragment(new org.telegram.ui.PikmiAISettingsActivity());"
            )
            DA.write_text(da, encoding="utf-8")
            print("меню AI: обновлён вызов на Fragment")
        else:
            print("меню AI: уже есть")
    else:
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
        print("меню AI: добавлено (Fragment)")

    # --- перехват processSendingText ---
    if not CAE.exists():
        die("не найден ChatActivityEnterView.java")
    cae = CAE.read_text(encoding="utf-8")
    if "PG_AI_REWRITE" in cae:
        print("перехват: уже есть")
        return

    sig = (
        "public boolean processSendingText(CharSequence text, boolean notify, int scheduleDate, "
        "int scheduleRepeatPeriod, long payStars) {"
    )
    if sig not in cae:
        die("ChatActivityEnterView: не нашёл processSendingText",
            __import__("subprocess").run(
                "grep -n 'processSendingText' %s | head -5" % CAE, shell=True,
                capture_output=True, text=True).stdout)

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
    print("перехват processSendingText: добавлен")
    print("Готово: Pikmi AI — полноценный экран настроек + перепись исходящих")


if __name__ == "__main__":
    main()
