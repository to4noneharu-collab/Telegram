#!/usr/bin/env python3
"""Pikmi Ghost / Offline mode.

Настройки (на аккаунт):
  - Режим оффлайна: всегда отправлять offline-статус
  - Тихие сообщения: не выходить в online при активности/отправке
  - Без прочтения в группах: не вызывать markDialogAsRead для групп/каналов

Фикс фоновых уведомлений:
  - принудительно pushService=true
  - keepAliveService по возможности
  - NotificationsService остаётся START_STICKY + перезапуск

Идемпотентен.
"""
import re
import sys
from pathlib import Path

HELPER = Path("TMessagesProj/src/main/java/org/telegram/messenger/PikmiGhost.java")
MC = Path("TMessagesProj/src/main/java/org/telegram/messenger/MessagesController.java")
AL = Path("TMessagesProj/src/main/java/org/telegram/messenger/ApplicationLoader.java")
NS = Path("TMessagesProj/src/main/java/org/telegram/messenger/NotificationsService.java")
DA = Path("TMessagesProj/src/main/java/org/telegram/ui/DialogsActivity.java")

JAVA = r'''package org.telegram.messenger;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.SharedPreferences;
import android.util.TypedValue;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;

/**
 * Режим оффлайна / «призрак»: скрытие онлайна, без автопрочтения групп, тихая активность.
 */
public class PikmiGhost {

    private static final String PREFS = "pikmigram_ghost_";

    private static SharedPreferences prefs(int account) {
        return ApplicationLoader.applicationContext.getSharedPreferences(PREFS + account, Context.MODE_PRIVATE);
    }

    public static boolean isOfflineMode(int account) {
        try { return prefs(account).getBoolean("offline_mode", false); }
        catch (Throwable t) { return false; }
    }

    public static boolean isSilentSend(int account) {
        try { return prefs(account).getBoolean("silent_send", false); }
        catch (Throwable t) { return false; }
    }

    public static boolean isNoReadGroups(int account) {
        try { return prefs(account).getBoolean("no_read_groups", false); }
        catch (Throwable t) { return false; }
    }

    public static void setOfflineMode(int account, boolean v) {
        prefs(account).edit().putBoolean("offline_mode", v).apply();
    }

    public static void setSilentSend(int account, boolean v) {
        prefs(account).edit().putBoolean("silent_send", v).apply();
    }

    public static void setNoReadGroups(int account, boolean v) {
        prefs(account).edit().putBoolean("no_read_groups", v).apply();
    }

    /** Не показывать online (оффлайн-режим или тихая отправка). */
    public static boolean shouldHideOnline(int account) {
        return isOfflineMode(account) || isSilentSend(account);
    }

    /** Не читать сообщения в этом диалоге (группы/каналы). */
    public static boolean shouldSkipRead(int account, long dialogId) {
        if (!isNoReadGroups(account)) return false;
        // личные чаты: dialogId > 0; группы/каналы: dialogId < 0
        return dialogId < 0;
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
        title.setText("Pikmi: Оффлайн / Ghost");
        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 18);
        title.setPadding(0, 0, 0, AndroidUtilities.dp(12));
        root.addView(title);

        final Switch swOffline = new Switch(activity);
        swOffline.setText("Режим оффлайна\n(в сети не показываться, пока открыт Telegram)");
        swOffline.setChecked(isOfflineMode(account));
        root.addView(swOffline);

        final Switch swSilent = new Switch(activity);
        swSilent.setText("Тихие сообщения\n(не выходить в online при отправке и активности)");
        swSilent.setChecked(isSilentSend(account));
        root.addView(swSilent);

        final Switch swNoRead = new Switch(activity);
        swNoRead.setText("Без прочтения в группах\n(не читать сообщения в группах/каналах)");
        swNoRead.setChecked(isNoReadGroups(account));
        root.addView(swNoRead);

        TextView hint = new TextView(activity);
        hint.setText("\nНастройки для аккаунта " + (account + 1) + ".\n"
                + "Оффлайн и «тихие» блокируют отправку online-статуса на сервер.\n"
                + "Без прочтения действует только на группы и каналы (не на личные чаты).");
        hint.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
        hint.setPadding(0, AndroidUtilities.dp(12), 0, 0);
        root.addView(hint);

        new AlertDialog.Builder(activity)
                .setView(scroll)
                .setPositiveButton("Сохранить", (d, w) -> {
                    setOfflineMode(account, swOffline.isChecked());
                    setSilentSend(account, swSilent.isChecked());
                    setNoReadGroups(account, swNoRead.isChecked());
                    Toast.makeText(activity, "Сохранено", Toast.LENGTH_SHORT).show();
                })
                .setNegativeButton("Отмена", null)
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
    print("PikmiGhost.java: создан")

    # --- MessagesController: block online status ---
    if not MC.exists():
        die("не найден MessagesController.java")
    mc = MC.read_text(encoding="utf-8")

    if "PG_GHOST_ONLINE" not in mc:
        old = (
            "if (!ignoreSetOnline && getConnectionsManager().getPauseTime() == 0 && "
            "ApplicationLoader.isScreenOn && !ApplicationLoader.mainInterfacePausedStageQueue) {"
        )
        new = (
            "if (!ignoreSetOnline && !org.telegram.messenger.PikmiGhost.shouldHideOnline(currentAccount) "
            "&& getConnectionsManager().getPauseTime() == 0 && "
            "ApplicationLoader.isScreenOn && !ApplicationLoader.mainInterfacePausedStageQueue) { // PG_GHOST_ONLINE"
        )
        if old not in mc:
            die("MessagesController: не нашёл условие online-статуса",
                __import__("subprocess").run(
                    "grep -n 'ignoreSetOnline && getConnectionsManager' %s" % MC,
                    shell=True, capture_output=True, text=True).stdout)
        mc = mc.replace(old, new, 1)
        print("online-статус: хук добавлен")
    else:
        print("online-статус: уже есть")

    # --- markDialogAsRead ---
    if "PG_GHOST_NOREAD" not in mc:
        sig = (
            "public void markDialogAsRead(long dialogId, int maxPositiveId, int maxNegativeId, "
            "int maxDate, boolean popup, long threadId, int countDiff, boolean readNow, int scheduledCount) {"
        )
        if sig not in mc:
            die("MessagesController: не нашёл markDialogAsRead")
        insert = (
            sig + "\n"
            "        // PG_GHOST_NOREAD\n"
            "        if (org.telegram.messenger.PikmiGhost.shouldSkipRead(currentAccount, dialogId)) {\n"
            "            return;\n"
            "        }\n"
        )
        mc = mc.replace(sig, insert, 1)
        print("markDialogAsRead: хук добавлен")
    else:
        print("markDialogAsRead: уже есть")

    # markDialogAsReadNow
    if "PG_GHOST_NOREAD_NOW" not in mc:
        sig2 = "public void markDialogAsReadNow(long dialogId, long replyId) {"
        if sig2 in mc:
            mc = mc.replace(
                sig2,
                sig2 + "\n"
                "        // PG_GHOST_NOREAD_NOW\n"
                "        if (org.telegram.messenger.PikmiGhost.shouldSkipRead(currentAccount, dialogId)) {\n"
                "            return;\n"
                "        }\n",
                1
            )
            print("markDialogAsReadNow: хук добавлен")
        else:
            print("markDialogAsReadNow: не найден (пропуск)")

    MC.write_text(mc, encoding="utf-8")

    # --- Фоновые уведомления: pushService + keepAlive ---
    if AL.exists():
        al = AL.read_text(encoding="utf-8")
        if "PG_GHOST_PUSH" not in al:
            # После postInit / loadConfig — включить push
            if "applicationInited = true;" in al:
                al = al.replace(
                    "applicationInited = true;",
                    "applicationInited = true;\n"
                    "        try { // PG_GHOST_PUSH\n"
                    "            android.content.SharedPreferences _pgN = MessagesController.getGlobalNotificationsSettings();\n"
                    "            if (!_pgN.getBoolean(\"pushService\", true)) {\n"
                    "                _pgN.edit().putBoolean(\"pushService\", true).apply();\n"
                    "            }\n"
                    "            AndroidUtilities.runOnUIThread(() -> {\n"
                    "                try { ApplicationLoader.startPushService(); } catch (Throwable ignore) {}\n"
                    "            }, 1500);\n"
                    "        } catch (Throwable ignore) {}\n",
                    1
                )
                AL.write_text(al, encoding="utf-8")
                print("push fix: ApplicationLoader")
            else:
                print("предупреждение: applicationInited не найден")
        else:
            print("push fix: уже есть")
    else:
        print("ApplicationLoader не найден")

    # NotificationsService — усилить sticky + перезапуск
    if NS.exists():
        ns = NS.read_text(encoding="utf-8")
        if "PG_GHOST_NOTIFY_SVC" not in ns:
            if "return START_STICKY;" in ns:
                ns = ns.replace(
                    "return START_STICKY;",
                    "return START_STICKY; // PG_GHOST_NOTIFY_SVC",
                    1
                )
            # onDestroy уже шлёт broadcast — добавим startService на новый API
            if "public void onDestroy()" in ns and "startForegroundService" not in ns:
                old_destroy = '''    public void onDestroy() {
        super.onDestroy();
        SharedPreferences preferences = MessagesController.getGlobalNotificationsSettings();
        if (preferences.getBoolean("pushService", true)) {
            Intent intent = new Intent("org.telegram.start");
            intent.setPackage(getPackageName());
            sendBroadcast(intent);
        }
    }'''
                new_destroy = '''    public void onDestroy() {
        super.onDestroy();
        // PG_GHOST_NOTIFY_SVC
        SharedPreferences preferences = MessagesController.getGlobalNotificationsSettings();
        if (preferences.getBoolean("pushService", true)) {
            try {
                Intent intent = new Intent("org.telegram.start");
                intent.setPackage(getPackageName());
                sendBroadcast(intent);
            } catch (Throwable ignore) {}
            try {
                Intent svc = new Intent(this, NotificationsService.class);
                if (android.os.Build.VERSION.SDK_INT >= 26) {
                    // обычный startService; foreground настраивается системой Telegram при необходимости
                    startService(svc);
                } else {
                    startService(svc);
                }
            } catch (Throwable ignore) {}
        }
    }'''
                if old_destroy in ns:
                    ns = ns.replace(old_destroy, new_destroy, 1)
                    print("NotificationsService: onDestroy усилен")
                else:
                    print("NotificationsService: onDestroy не совпал (частично OK)")
            NS.write_text(ns, encoding="utf-8")
        else:
            print("NotificationsService: уже пропатчен")

    # keepAliveService default true при загрузке prefs
    mc2 = MC.read_text(encoding="utf-8")
    if "PG_GHOST_KEEPALIVE" not in mc2:
        old_ka = 'keepAliveService = mainPreferences.getBoolean("keepAliveService", false);'
        new_ka = 'keepAliveService = mainPreferences.getBoolean("keepAliveService", true); // PG_GHOST_KEEPALIVE'
        if old_ka in mc2:
            mc2 = mc2.replace(old_ka, new_ka, 1)
            MC.write_text(mc2, encoding="utf-8")
            print("keepAliveService: default true")
        else:
            print("keepAliveService: строка не найдена")
    else:
        print("keepAliveService: уже есть")

    # --- Меню ---
    if not DA.exists():
        die("не найден DialogsActivity.java")
    da = DA.read_text(encoding="utf-8")
    if "PG_GHOST_MENU" not in da:
        inserted = False
        if "PG_AI_MENU" in da:
            # после AI пункта
            ai_block = (
                "        io.add(R.drawable.msg_edit, \"PikmiGram: AI (Groq)\", () -> { // PG_AI_MENU\n"
                "            presentFragment(new org.telegram.ui.PikmiAISettingsActivity());\n"
                "        });"
            )
            if ai_block in da:
                da = da.replace(
                    ai_block,
                    ai_block + "\n"
                    "        io.add(R.drawable.msg_secret, \"PikmiGram: Оффлайн / Ghost\", () -> { // PG_GHOST_MENU\n"
                    "            org.telegram.messenger.PikmiGhost.showSettings(getParentActivity(), currentAccount);\n"
                    "        });",
                    1
                )
                inserted = True
        if not inserted and "PikmiUpdater.check(getParentActivity(), true);" in da:
            da = da.replace(
                "org.telegram.messenger.PikmiUpdater.check(getParentActivity(), true);\n        });",
                "org.telegram.messenger.PikmiUpdater.check(getParentActivity(), true);\n        });\n"
                "        io.add(R.drawable.msg_secret, \"PikmiGram: Оффлайн / Ghost\", () -> { // PG_GHOST_MENU\n"
                "            org.telegram.messenger.PikmiGhost.showSettings(getParentActivity(), currentAccount);\n"
                "        });",
                1
            )
            inserted = True
        if not inserted:
            rx = re.compile(
                r"(io\.add\(R\.drawable\.outline_groups_24, getString\(R\.string\.NewGroup\), \(\) -> \{\s*"
                r"Bundle args = new Bundle\(\);\s*"
                r"presentFragment\(new GroupCreateActivity\(args\)\);\s*\}\);)"
            )
            if rx.search(da):
                da = rx.sub(
                    lambda m: m.group(1) + "\n"
                    "        io.addGap();\n"
                    "        io.add(R.drawable.msg_secret, \"PikmiGram: Оффлайн / Ghost\", () -> { // PG_GHOST_MENU\n"
                    "            org.telegram.messenger.PikmiGhost.showSettings(getParentActivity(), currentAccount);\n"
                    "        });",
                    da,
                    count=1
                )
                inserted = True
        if not inserted:
            die("DialogsActivity: не удалось вставить пункт меню")
        DA.write_text(da, encoding="utf-8")
        print("меню Ghost: добавлено")
    else:
        print("меню Ghost: уже есть")

    print("Готово: Pikmi Ghost (оффлайн / тихие / без прочтения групп + push fix)")


if __name__ == "__main__":
    main()
