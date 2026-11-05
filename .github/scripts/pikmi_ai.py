#!/usr/bin/env python3
"""Pikmi AI (Groq): перепись исходящих сообщений + настройки на аккаунт.

- API-ключ и промпт задаются в клиенте
- Настройки индивидуальны для каждого аккаунта
- Перед отправкой текст проходит через Groq и уходит уже отредактированным

Идемпотентен.
"""
import re
import sys
from pathlib import Path

HELPER = Path("TMessagesProj/src/main/java/org/telegram/messenger/PikmiAI.java")
CAE = Path("TMessagesProj/src/main/java/org/telegram/ui/Components/ChatActivityEnterView.java")
DA = Path("TMessagesProj/src/main/java/org/telegram/ui/DialogsActivity.java")

JAVA = r'''package org.telegram.messenger;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.SharedPreferences;
import android.os.Handler;
import android.os.Looper;
import android.text.TextUtils;
import android.util.TypedValue;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;

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
 * Настройки (ключ, промпт, вкл/выкл) хранятся отдельно для каждого аккаунта.
 */
public class PikmiAI {

    private static final String PREFS_PREFIX = "pikmigram_ai_";
    private static final String DEFAULT_PROMPT =
            "Перепиши сообщение вежливо, спокойно и без негатива. Сохрани смысл и язык оригинала. " +
            "Не добавляй приветствий, подписей и пояснений. Верни только готовый текст сообщения.";
    private static final String GROQ_URL = "https://api.groq.com/openai/v1/chat/completions";
    private static final String MODEL = "llama-3.3-70b-versatile";

    private static final ExecutorService executor = Executors.newSingleThreadExecutor();
    private static final Handler mainHandler = new Handler(Looper.getMainLooper());

    /** Флаг, чтобы не зациклить processSendingText */
    public static final ThreadLocal<Boolean> skipRewrite = new ThreadLocal<>();

    public interface Callback {
        void onResult(String text);
        void onError(String error);
    }

    private static SharedPreferences prefs(int account) {
        return ApplicationLoader.applicationContext.getSharedPreferences(PREFS_PREFIX + account, Context.MODE_PRIVATE);
    }

    public static boolean isRewriteEnabled(int account) {
        try {
            return prefs(account).getBoolean("rewrite_enabled", false);
        } catch (Throwable t) {
            return false;
        }
    }

    public static boolean isAutoReplyEnabled(int account) {
        try {
            return prefs(account).getBoolean("auto_reply_enabled", false);
        } catch (Throwable t) {
            return false;
        }
    }

    public static String getApiKey(int account) {
        try {
            return prefs(account).getString("api_key", "");
        } catch (Throwable t) {
            return "";
        }
    }

    public static String getPrompt(int account) {
        try {
            String p = prefs(account).getString("prompt", null);
            return TextUtils.isEmpty(p) ? DEFAULT_PROMPT : p;
        } catch (Throwable t) {
            return DEFAULT_PROMPT;
        }
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

    public static void showSettings(final Activity activity, final int account) {
        if (activity == null) return;

        ScrollView scroll = new ScrollView(activity);
        LinearLayout root = new LinearLayout(activity);
        root.setOrientation(LinearLayout.VERTICAL);
        int pad = AndroidUtilities.dp(20);
        root.setPadding(pad, pad, pad, pad);
        scroll.addView(root);

        TextView title = new TextView(activity);
        title.setText("Pikmi AI (Groq) — аккаунт " + (account + 1));
        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 18);
        title.setPadding(0, 0, 0, AndroidUtilities.dp(12));
        root.addView(title);

        final Switch swRewrite = new Switch(activity);
        swRewrite.setText("Переписывать исходящие");
        swRewrite.setChecked(isRewriteEnabled(account));
        root.addView(swRewrite);

        final Switch swAuto = new Switch(activity);
        swAuto.setText("Автоответчик (в следующей версии)");
        swAuto.setChecked(isAutoReplyEnabled(account));
        swAuto.setEnabled(false);
        root.addView(swAuto);

        TextView keyLabel = new TextView(activity);
        keyLabel.setText("\nAPI-ключ Groq");
        keyLabel.setPadding(0, AndroidUtilities.dp(12), 0, AndroidUtilities.dp(4));
        root.addView(keyLabel);

        final EditText keyInput = new EditText(activity);
        keyInput.setHint("gsk_...");
        keyInput.setSingleLine(true);
        keyInput.setText(getApiKey(account));
        root.addView(keyInput);

        TextView promptLabel = new TextView(activity);
        promptLabel.setText("\nПромпт (системный)");
        promptLabel.setPadding(0, AndroidUtilities.dp(12), 0, AndroidUtilities.dp(4));
        root.addView(promptLabel);

        final EditText promptInput = new EditText(activity);
        promptInput.setHint("Как переписывать сообщения...");
        promptInput.setMinLines(4);
        promptInput.setMaxLines(10);
        promptInput.setText(getPrompt(account));
        root.addView(promptInput);

        TextView hint = new TextView(activity);
        hint.setText("\nКлюч и промпт — отдельно для каждого аккаунта.\nМодель: " + MODEL);
        hint.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
        hint.setPadding(0, AndroidUtilities.dp(8), 0, 0);
        root.addView(hint);

        new AlertDialog.Builder(activity)
                .setView(scroll)
                .setPositiveButton("Сохранить", (d, w) -> {
                    setRewriteEnabled(account, swRewrite.isChecked());
                    setAutoReplyEnabled(account, swAuto.isChecked());
                    setApiKey(account, keyInput.getText().toString());
                    setPrompt(account, promptInput.getText().toString());
                    Toast.makeText(activity, "Сохранено", Toast.LENGTH_SHORT).show();
                })
                .setNegativeButton("Отмена", null)
                .setNeutralButton("Сбросить промпт", (d, w) -> promptInput.setText(DEFAULT_PROMPT))
                .show();
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
    HELPER.write_text(JAVA, encoding="utf-8")
    print("PikmiAI.java: создан")

    # --- меню ---
    if not DA.exists():
        die("не найден DialogsActivity.java")
    da = DA.read_text(encoding="utf-8")
    if "PG_AI_MENU" not in da:
        if "PikmiUpdater.check(getParentActivity(), true);" in da:
            da = da.replace(
                "org.telegram.messenger.PikmiUpdater.check(getParentActivity(), true);\n        });",
                "org.telegram.messenger.PikmiUpdater.check(getParentActivity(), true);\n        });\n"
                "        io.add(R.drawable.msg_edit, \"PikmiGram: AI (Groq)\", () -> { // PG_AI_MENU\n"
                "            org.telegram.messenger.PikmiAI.showSettings(getParentActivity(), currentAccount);\n"
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
                "            org.telegram.messenger.PikmiAI.showSettings(getParentActivity(), currentAccount);\n"
                "        });"
            )
            da = rx.sub(lambda m: m.group(1) + insert, da, count=1)
        DA.write_text(da, encoding="utf-8")
        print("меню AI: добавлено")
    else:
        print("меню AI: уже есть")

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
        die("ChatActivityEnterView: не нашёл processSendingText с ожидаемой сигнатурой",
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
                    if (getParentActivity() != null) {
                        android.widget.Toast.makeText(getParentActivity(), "AI: " + error, android.widget.Toast.LENGTH_SHORT).show();
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
    print("Готово: Pikmi AI (настройки + перепись исходящих через Groq)")


if __name__ == "__main__":
    main()
