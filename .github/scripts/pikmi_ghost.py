#!/usr/bin/env python3
"""Pikmi Ghost / Offline mode — полноценный экран настроек.

- Режим оффлайна / тихие сообщения: блокировка online-статуса (в т.ч. при отправке)
- Без автопрочтения: ЛС + группы + каналы (markDialogAsRead, completeReadTask, mentions)
- Фикс push в фоне

Идемпотентен.
"""
import re
import sys
from pathlib import Path

HELPER = Path("TMessagesProj/src/main/java/org/telegram/messenger/PikmiGhost.java")
SETTINGS = Path("TMessagesProj/src/main/java/org/telegram/ui/PikmiGhostSettingsActivity.java")
MC = Path("TMessagesProj/src/main/java/org/telegram/messenger/MessagesController.java")
AL = Path("TMessagesProj/src/main/java/org/telegram/messenger/ApplicationLoader.java")
NS = Path("TMessagesProj/src/main/java/org/telegram/messenger/NotificationsService.java")
DA = Path("TMessagesProj/src/main/java/org/telegram/ui/DialogsActivity.java")

JAVA_HELPER = r'''package org.telegram.messenger;

import android.content.Context;
import android.content.SharedPreferences;

/**
 * Ghost / offline: скрытие онлайна, без автопрочтения, тихая активность.
 * Настройки на каждый аккаунт.
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

    public static boolean isNoRead(int account) {
        try { return prefs(account).getBoolean("no_read_groups", false); }
        catch (Throwable t) { return false; }
    }

    // совместимость со старым именем
    public static boolean isNoReadGroups(int account) {
        return isNoRead(account);
    }

    public static void setOfflineMode(int account, boolean v) {
        prefs(account).edit().putBoolean("offline_mode", v).apply();
    }

    public static void setSilentSend(int account, boolean v) {
        prefs(account).edit().putBoolean("silent_send", v).apply();
    }

    public static void setNoRead(int account, boolean v) {
        prefs(account).edit().putBoolean("no_read_groups", v).apply();
    }

    public static void setNoReadGroups(int account, boolean v) {
        setNoRead(account, v);
    }

    /** Не показывать online. */
    public static boolean shouldHideOnline(int account) {
        return isOfflineMode(account) || isSilentSend(account);
    }

    /** Не читать сообщения (ЛС, группы, каналы). */
    public static boolean shouldSkipRead(int account, long dialogId) {
        if (!isNoRead(account)) return false;
        if (dialogId == 0) return false;
        return true;
    }
}
'''

JAVA_SETTINGS = r'''package org.telegram.ui;

import android.content.Context;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;

import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import org.telegram.messenger.AndroidUtilities;
import org.telegram.messenger.PikmiGhost;
import org.telegram.messenger.R;
import org.telegram.ui.ActionBar.ActionBar;
import org.telegram.ui.ActionBar.BaseFragment;
import org.telegram.ui.ActionBar.Theme;
import org.telegram.ui.Cells.HeaderCell;
import org.telegram.ui.Cells.ShadowSectionCell;
import org.telegram.ui.Cells.TextCheckCell;
import org.telegram.ui.Cells.TextInfoPrivacyCell;
import org.telegram.ui.Components.LayoutHelper;
import org.telegram.ui.Components.RecyclerListView;

public class PikmiGhostSettingsActivity extends BaseFragment {

    private RecyclerListView listView;
    private ListAdapter adapter;

    private int rowCount;
    private int headerRow;
    private int offlineRow;
    private int silentRow;
    private int noReadRow;
    private int sectionRow;
    private int infoRow;

    @Override
    public boolean onFragmentCreate() {
        super.onFragmentCreate();
        rowCount = 0;
        headerRow = rowCount++;
        offlineRow = rowCount++;
        silentRow = rowCount++;
        noReadRow = rowCount++;
        sectionRow = rowCount++;
        infoRow = rowCount++;
        return true;
    }

    @Override
    public View createView(Context context) {
        actionBar.setBackButtonImage(R.drawable.ic_ab_back);
        actionBar.setAllowOverlayTitle(true);
        actionBar.setTitle("Pikmi: Оффлайн / Ghost");
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
            if (position == offlineRow) {
                boolean next = !PikmiGhost.isOfflineMode(currentAccount);
                PikmiGhost.setOfflineMode(currentAccount, next);
                if (view instanceof TextCheckCell) ((TextCheckCell) view).setChecked(next);
            } else if (position == silentRow) {
                boolean next = !PikmiGhost.isSilentSend(currentAccount);
                PikmiGhost.setSilentSend(currentAccount, next);
                if (view instanceof TextCheckCell) ((TextCheckCell) view).setChecked(next);
            } else if (position == noReadRow) {
                boolean next = !PikmiGhost.isNoRead(currentAccount);
                PikmiGhost.setNoRead(currentAccount, next);
                if (view instanceof TextCheckCell) ((TextCheckCell) view).setChecked(next);
            }
        });

        return fragmentView;
    }

    private class ListAdapter extends RecyclerListView.SelectionAdapter {
        private final Context mContext;

        ListAdapter(Context context) { mContext = context; }

        @Override
        public boolean isEnabled(RecyclerView.ViewHolder holder) {
            int pos = holder.getAdapterPosition();
            return pos == offlineRow || pos == silentRow || pos == noReadRow;
        }

        @Override
        public int getItemCount() { return rowCount; }

        @Override
        public int getItemViewType(int position) {
            if (position == headerRow) return 0;
            if (position == offlineRow || position == silentRow || position == noReadRow) return 1;
            if (position == sectionRow) return 2;
            return 3;
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
                default:
                    view = new TextInfoPrivacyCell(mContext);
                    break;
            }
            return new RecyclerListView.Holder(view);
        }

        @Override
        public void onBindViewHolder(RecyclerView.ViewHolder holder, int position) {
            switch (holder.getItemViewType()) {
                case 0:
                    ((HeaderCell) holder.itemView).setText("Функции (аккаунт " + (currentAccount + 1) + ")");
                    break;
                case 1: {
                    TextCheckCell cell = (TextCheckCell) holder.itemView;
                    if (position == offlineRow) {
                        cell.setTextAndValueAndCheck("Режим оффлайна", "Не показывать online, пока открыт Telegram", PikmiGhost.isOfflineMode(currentAccount), true, true);
                    } else if (position == silentRow) {
                        cell.setTextAndValueAndCheck("Тихие сообщения", "Не выходить в online при отправке и активности", PikmiGhost.isSilentSend(currentAccount), true, true);
                    } else if (position == noReadRow) {
                        cell.setTextAndValueAndCheck("Без автопрочтения", "Не читать в ЛС, группах и каналах", PikmiGhost.isNoRead(currentAccount), true, false);
                    }
                    break;
                }
                case 3: {
                    TextInfoPrivacyCell cell = (TextInfoPrivacyCell) holder.itemView;
                    cell.setText("Оффлайн и «тихие сообщения» блокируют отправку online-статуса на сервер, в том числе при написании.\n\n"
                            + "Без автопрочтения: у вас в клиенте сообщения читаются, но серверу Telegram статус «прочитано» не отправляется. Оффлайн/тихие также отключают индикатор «печатает».\n\n"
                            + "Настройки сохраняются отдельно для каждого аккаунта.");
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
    print("PikmiGhost.java: создан")

    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(JAVA_SETTINGS, encoding="utf-8")
    print("PikmiGhostSettingsActivity.java: создан")

    if not MC.exists():
        die("не найден MessagesController.java")
    mc = MC.read_text(encoding="utf-8")

    # --- ONLINE: переписываем блок updateTimerProc ---
    # Когда ghost: не слать online; активно слать offline даже при открытом приложении
    if "PG_GHOST_ONLINE_BLOCK" not in mc:
        old_online = (
            "            if (!ignoreSetOnline && getConnectionsManager().getPauseTime() == 0 && ApplicationLoader.isScreenOn && !ApplicationLoader.mainInterfacePausedStageQueue) {\n"
            "                if (ApplicationLoader.mainInterfacePausedStageQueueTime != 0 && Math.abs(ApplicationLoader.mainInterfacePausedStageQueueTime - System.currentTimeMillis()) > 1000) {\n"
            "                    if (statusSettingState != 1 && (lastStatusUpdateTime == 0 || Math.abs(System.currentTimeMillis() - lastStatusUpdateTime) >= 55000 || offlineSent)) {\n"
            "                        statusSettingState = 1;\n"
            "\n"
            "                        if (statusRequest != 0) {\n"
            "                            getConnectionsManager().cancelRequest(statusRequest, true);\n"
            "                        }\n"
            "\n"
            "                        TL_account.updateStatus req = new TL_account.updateStatus();\n"
            "                        req.offline = false;\n"
            "                        statusRequest = getConnectionsManager().sendRequest(req, (response, error) -> {\n"
            "                            if (error == null) {\n"
            "                                lastStatusUpdateTime = System.currentTimeMillis();\n"
            "                                offlineSent = false;\n"
            "                                statusSettingState = 0;\n"
            "                            } else {\n"
            "                                if (lastStatusUpdateTime != 0) {\n"
            "                                    lastStatusUpdateTime += 5000;\n"
            "                                }\n"
            "                            }\n"
            "                            statusRequest = 0;\n"
            "                        });\n"
            "                    }\n"
            "                }\n"
            "            } else if (statusSettingState != 2 && !offlineSent && Math.abs(System.currentTimeMillis() - getConnectionsManager().getPauseTime()) >= 2000) {\n"
        )
        new_online = (
            "            // PG_GHOST_ONLINE_BLOCK\n"
            "            final boolean pgHideOnline = org.telegram.messenger.PikmiGhost.shouldHideOnline(currentAccount);\n"
            "            if (!pgHideOnline && !ignoreSetOnline && getConnectionsManager().getPauseTime() == 0 && ApplicationLoader.isScreenOn && !ApplicationLoader.mainInterfacePausedStageQueue) {\n"
            "                if (ApplicationLoader.mainInterfacePausedStageQueueTime != 0 && Math.abs(ApplicationLoader.mainInterfacePausedStageQueueTime - System.currentTimeMillis()) > 1000) {\n"
            "                    if (statusSettingState != 1 && (lastStatusUpdateTime == 0 || Math.abs(System.currentTimeMillis() - lastStatusUpdateTime) >= 55000 || offlineSent)) {\n"
            "                        statusSettingState = 1;\n"
            "\n"
            "                        if (statusRequest != 0) {\n"
            "                            getConnectionsManager().cancelRequest(statusRequest, true);\n"
            "                        }\n"
            "\n"
            "                        TL_account.updateStatus req = new TL_account.updateStatus();\n"
            "                        req.offline = false;\n"
            "                        statusRequest = getConnectionsManager().sendRequest(req, (response, error) -> {\n"
            "                            if (error == null) {\n"
            "                                lastStatusUpdateTime = System.currentTimeMillis();\n"
            "                                offlineSent = false;\n"
            "                                statusSettingState = 0;\n"
            "                            } else {\n"
            "                                if (lastStatusUpdateTime != 0) {\n"
            "                                    lastStatusUpdateTime += 5000;\n"
            "                                }\n"
            "                            }\n"
            "                            statusRequest = 0;\n"
            "                        });\n"
            "                    }\n"
            "                }\n"
            "            } else if ((pgHideOnline || (statusSettingState != 2 && !offlineSent && Math.abs(System.currentTimeMillis() - getConnectionsManager().getPauseTime()) >= 2000)) && (pgHideOnline ? (statusSettingState != 2 || !offlineSent) : true)) {\n"
            "                if (pgHideOnline && offlineSent && statusSettingState == 2) {\n"
            "                    // уже offline — ничего\n"
            "                } else if (statusSettingState != 2 && !offlineSent || pgHideOnline && !offlineSent) {\n"
        )
        # The else if rewrite is getting too messy. Simpler approach:

        # Just replace the condition for online branch and change the offline else if condition
        pass

    # Simpler reliable patches:
    # A) online condition
    if "PG_GHOST_ONLINE" not in mc and "PG_GHOST_ONLINE_BLOCK" not in mc:
        a = "if (!ignoreSetOnline && getConnectionsManager().getPauseTime() == 0 && ApplicationLoader.isScreenOn && !ApplicationLoader.mainInterfacePausedStageQueue) {"
        b = "if (!ignoreSetOnline && !org.telegram.messenger.PikmiGhost.shouldHideOnline(currentAccount) && getConnectionsManager().getPauseTime() == 0 && ApplicationLoader.isScreenOn && !ApplicationLoader.mainInterfacePausedStageQueue) { // PG_GHOST_ONLINE"
        if a not in mc:
            die("online condition not found")
        mc = mc.replace(a, b, 1)
        print("online: block going online")
    else:
        print("online: condition already patched")

    # B) Force offline while ghost: change else if offline branch condition
    if "PG_GHOST_FORCE_OFFLINE" not in mc:
        a = "} else if (statusSettingState != 2 && !offlineSent && Math.abs(System.currentTimeMillis() - getConnectionsManager().getPauseTime()) >= 2000) {"
        b = "} else if (org.telegram.messenger.PikmiGhost.shouldHideOnline(currentAccount) && !offlineSent || statusSettingState != 2 && !offlineSent && Math.abs(System.currentTimeMillis() - getConnectionsManager().getPauseTime()) >= 2000) { // PG_GHOST_FORCE_OFFLINE"
        if a not in mc:
            print("WARN: offline branch not found")
        else:
            mc = mc.replace(a, b, 1)
            print("online: force offline while ghost")
    else:
        print("force offline: already")

    # C) Never send offline=false under ghost (safety)
    if "PG_GHOST_ONLINE_FORCE" not in mc:
        if "req.offline = false;" in mc:
            mc = mc.replace(
                "req.offline = false;",
                "req.offline = org.telegram.messenger.PikmiGhost.shouldHideOnline(currentAccount); // will fix\n"
                "                        if (org.telegram.messenger.PikmiGhost.shouldHideOnline(currentAccount)) { req.offline = true; statusSettingState = 2; } else { req.offline = false; } // PG_GHOST_ONLINE_FORCE",
                1
            )
            print("online: hard block offline=false")
        else:
            print("WARN: req.offline=false not found")
    else:
        print("hard block: already")

    # D) READ: ensure markDialogAsRead does NOT early-return (local UI), only completeReadTask blocks server
    # Remove old early returns if present
    for marker, block in [
        ("PG_GHOST_NOREAD\n",
         "        // PG_GHOST_NOREAD\n"
         "        if (org.telegram.messenger.PikmiGhost.shouldSkipRead(currentAccount, dialogId)) {\n"
         "            return;\n"
         "        }\n"),
        ("PG_GHOST_NOREAD_NOW\n",
         "        // PG_GHOST_NOREAD_NOW\n"
         "        if (org.telegram.messenger.PikmiGhost.shouldSkipRead(currentAccount, dialogId)) {\n"
         "            return;\n"
         "        }\n"),
    ]:
        if block in mc:
            mc = mc.replace(block, "        // " + marker.strip() + " local read allowed; server blocked in completeReadTask\n")
            print("removed early return:", marker.strip())

    # completeReadTask - server block
    if "PG_GHOST_COMPLETE_READ" not in mc:
        sig3 = "private void completeReadTask(ReadTask task) {"
        if sig3 not in mc:
            print("WARN: completeReadTask not found")
        else:
            mc = mc.replace(
                sig3,
                sig3 + "\n"
                "        // PG_GHOST_COMPLETE_READ\n"
                "        if (task != null && org.telegram.messenger.PikmiGhost.shouldSkipRead(currentAccount, task.dialogId)) {\n"
                "            return;\n"
                "        }\n",
                1
            )
            print("completeReadTask: server read blocked")
    else:
        print("completeReadTask: already")

    # markMentionsAsRead - server-side, block
    if "PG_GHOST_MENTIONS" not in mc:
        sig4 = "public void markMentionsAsRead(long dialogId, long topicId) {"
        if sig4 in mc:
            mc = mc.replace(
                sig4,
                sig4 + "\n"
                "        // PG_GHOST_MENTIONS\n"
                "        if (org.telegram.messenger.PikmiGhost.shouldSkipRead(currentAccount, dialogId)) {\n"
                "            return;\n"
                "        }\n",
                1
            )
            print("markMentionsAsRead: blocked")

    # E) sendTyping - block when hide online / silent
    if "PG_GHOST_TYPING" not in mc:
        sig_t = "public boolean sendTyping(long dialogId, long threadMsgId, int action, String emojicon, int classGuid) {"
        if sig_t not in mc:
            print("WARN: sendTyping not found")
        else:
            mc = mc.replace(
                sig_t,
                sig_t + "\n"
                "        // PG_GHOST_TYPING\n"
                "        if (org.telegram.messenger.PikmiGhost.shouldHideOnline(currentAccount)) {\n"
                "            return false;\n"
                "        }\n",
                1
            )
            print("sendTyping: blocked under ghost")
    else:
        print("sendTyping: already")

    # also the shorter overload
    if "PG_GHOST_TYPING2" not in mc:
        sig_t2 = "public boolean sendTyping(long dialogId, long threadMsgId, int action, int classGuid) {"
        if sig_t2 in mc:
            mc = mc.replace(
                sig_t2,
                sig_t2 + "\n"
                "        // PG_GHOST_TYPING2\n"
                "        if (org.telegram.messenger.PikmiGhost.shouldHideOnline(currentAccount)) {\n"
                "            return false;\n"
                "        }\n",
                1
            )
            print("sendTyping overload: blocked")

    MC.write_text(mc, encoding="utf-8")

    # push fixes (same as before)
    if AL.exists():
        al = AL.read_text(encoding="utf-8")
        if "PG_GHOST_PUSH" not in al and "applicationInited = true;" in al:
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
            print("push: ApplicationLoader")
        else:
            print("push: ApplicationLoader skip/exists")

    if NS.exists():
        ns = NS.read_text(encoding="utf-8")
        if "PG_GHOST_NOTIFY_SVC" not in ns:
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
                startService(new Intent(this, NotificationsService.class));
            } catch (Throwable ignore) {}
        }
    }'''
            if old_destroy in ns:
                ns = ns.replace(old_destroy, new_destroy, 1)
                NS.write_text(ns, encoding="utf-8")
                print("NotificationsService: OK")
            else:
                print("NotificationsService: anchor miss")

    mc2 = MC.read_text(encoding="utf-8")
    if "PG_GHOST_KEEPALIVE" not in mc2:
        old_ka = 'keepAliveService = mainPreferences.getBoolean("keepAliveService", false);'
        if old_ka in mc2:
            MC.write_text(mc2.replace(old_ka, 'keepAliveService = mainPreferences.getBoolean("keepAliveService", true); // PG_GHOST_KEEPALIVE', 1), encoding="utf-8")
            print("keepAlive: OK")

    # Menu → full fragment
    if not DA.exists():
        die("не найден DialogsActivity.java")
    da = DA.read_text(encoding="utf-8")
    if "PG_GHOST_MENU" in da:
        # upgrade showSettings dialog → fragment
        if "PikmiGhost.showSettings" in da:
            da = da.replace(
                "org.telegram.messenger.PikmiGhost.showSettings(getParentActivity(), currentAccount);",
                "presentFragment(new org.telegram.ui.PikmiGhostSettingsActivity());"
            )
            DA.write_text(da, encoding="utf-8")
            print("меню: обновлено на Fragment")
        else:
            print("меню: уже Fragment")
    else:
        inserted = False
        if "PG_AI_MENU" in da and "PikmiAISettingsActivity" in da:
            da = da.replace(
                "presentFragment(new org.telegram.ui.PikmiAISettingsActivity());\n        });",
                "presentFragment(new org.telegram.ui.PikmiAISettingsActivity());\n        });\n"
                "        io.add(R.drawable.msg_secret, \"PikmiGram: Оффлайн / Ghost\", () -> { // PG_GHOST_MENU\n"
                "            presentFragment(new org.telegram.ui.PikmiGhostSettingsActivity());\n"
                "        });",
                1
            )
            inserted = "PG_GHOST_MENU" in da
        if not inserted:
            rx = re.compile(
                r"(io\.add\(R\.drawable\.outline_groups_24, getString\(R\.string\.NewGroup\), \(\) -> \{\s*"
                r"Bundle args = new Bundle\(\);\s*"
                r"presentFragment\(new GroupCreateActivity\(args\)\);\s*\}\);)"
            )
            if not rx.search(da):
                die("не нашёл якорь меню")
            da = rx.sub(
                lambda m: m.group(1) + "\n"
                "        io.addGap();\n"
                "        io.add(R.drawable.msg_secret, \"PikmiGram: Оффлайн / Ghost\", () -> { // PG_GHOST_MENU\n"
                "            presentFragment(new org.telegram.ui.PikmiGhostSettingsActivity());\n"
                "        });",
                da,
                count=1
            )
        DA.write_text(da, encoding="utf-8")
        print("меню: добавлено")

    print("Готово: Ghost — полный экран + жёсткая блокировка online/read")


if __name__ == "__main__":
    main()
