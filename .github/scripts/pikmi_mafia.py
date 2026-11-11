#!/usr/bin/env python3
"""Pikmi Mafia — меню авторега/игры внутри клиента.

Аккаунты = зарегистрированные в Telegram (UserConfig), режимы solo / twins.
Полный порт логики Go-модуля (голосование, ночные ходы) — каркас настроек + хранение;
автодействия подключаются итеративно.

Идемпотентен.
"""
import re
import sys
from pathlib import Path

HELPER = Path("TMessagesProj/src/main/java/org/telegram/messenger/PikmiMafia.java")
SETTINGS = Path("TMessagesProj/src/main/java/org/telegram/ui/PikmiMafiaSettingsActivity.java")
DA = Path("TMessagesProj/src/main/java/org/telegram/ui/DialogsActivity.java")

JAVA_HELPER = r'''package org.telegram.messenger;

import android.content.Context;
import android.content.SharedPreferences;
import android.text.TextUtils;

import java.util.ArrayList;

/**
 * Настройки модуля «Мафия / авторег».
 * Список аккаунтов берётся из UserConfig (все активированные в клиенте).
 */
public class PikmiMafia {

    private static final String PREFS = "pikmigram_mafia";

    public static final String MODE_SOLO = "solo";
    public static final String MODE_TWINS = "twins";

    public static final String BOT_BAKU = "baku";
    public static final String BOT_TRUE = "true";
    public static final String BOT_MAFIOSO = "mafioso";
    public static final String BOT_COMBAT = "combat";

    private static SharedPreferences prefs() {
        return ApplicationLoader.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public static boolean isEnabled() {
        try { return prefs().getBoolean("enabled", false); } catch (Throwable t) { return false; }
    }
    public static void setEnabled(boolean v) { prefs().edit().putBoolean("enabled", v).apply(); }

    public static String getMode() {
        try {
            String m = prefs().getString("mode", MODE_SOLO);
            return MODE_TWINS.equals(m) ? MODE_TWINS : MODE_SOLO;
        } catch (Throwable t) { return MODE_SOLO; }
    }
    public static void setMode(String m) {
        prefs().edit().putString("mode", MODE_TWINS.equals(m) ? MODE_TWINS : MODE_SOLO).apply();
    }

    public static boolean isMainInTwins() {
        try { return prefs().getBoolean("main_in_twins", true); } catch (Throwable t) { return true; }
    }
    public static void setMainInTwins(boolean v) { prefs().edit().putBoolean("main_in_twins", v).apply(); }

    public static String getBotMode() {
        try {
            String m = prefs().getString("bot_mode", BOT_BAKU);
            if (BOT_TRUE.equals(m) || BOT_MAFIOSO.equals(m) || BOT_COMBAT.equals(m)) return m;
            return BOT_BAKU;
        } catch (Throwable t) { return BOT_BAKU; }
    }
    public static void setBotMode(String m) {
        if (!BOT_TRUE.equals(m) && !BOT_MAFIOSO.equals(m) && !BOT_COMBAT.equals(m)) m = BOT_BAKU;
        prefs().edit().putString("bot_mode", m).apply();
        // дефолтный username бота
        if (TextUtils.isEmpty(getBotUsername()) || isDefaultBotUsername(getBotUsername())) {
            setBotUsername(defaultBotForMode(m));
        }
    }

    private static boolean isDefaultBotUsername(String u) {
        return "MafiaBakuBlackBot".equalsIgnoreCase(u)
                || "TrueMafiaBlackBot".equalsIgnoreCase(u)
                || "TrueMafiaBot".equalsIgnoreCase(u)
                || "MafiososBot".equalsIgnoreCase(u)
                || "CombatMafiaSOBot".equalsIgnoreCase(u);
    }

    public static String defaultBotForMode(String mode) {
        if (BOT_TRUE.equals(mode)) return isTrueFree() ? "TrueMafiaBot" : "TrueMafiaBlackBot";
        if (BOT_MAFIOSO.equals(mode)) return "MafiososBot";
        if (BOT_COMBAT.equals(mode)) return "CombatMafiaSOBot";
        return "MafiaBakuBlackBot";
    }

    public static String botModeLabel() {
        String m = getBotMode();
        if (BOT_TRUE.equals(m)) return isTrueFree() ? "True Mafia (free)" : "True Mafia Black";
        if (BOT_MAFIOSO.equals(m)) return "Mafioso";
        if (BOT_COMBAT.equals(m)) return "Mafia Combat";
        return "Mafia Baku Black";
    }

    public static boolean isTrueFree() {
        try { return prefs().getBoolean("true_free", false); } catch (Throwable t) { return false; }
    }
    public static void setTrueFree(boolean v) {
        prefs().edit().putBoolean("true_free", v).apply();
        if (BOT_TRUE.equals(getBotMode())) setBotUsername(defaultBotForMode(BOT_TRUE));
    }

    public static String getBotUsername() {
        try {
            String u = prefs().getString("bot", null);
            if (TextUtils.isEmpty(u)) return defaultBotForMode(getBotMode());
            return u.replace("@", "").trim();
        } catch (Throwable t) { return defaultBotForMode(getBotMode()); }
    }
    public static void setBotUsername(String u) {
        if (u == null) u = "";
        prefs().edit().putString("bot", u.replace("@", "").trim()).apply();
    }

    public static long getRegChat() {
        try { return prefs().getLong("reg_chat", 0); } catch (Throwable t) { return 0; }
    }
    public static void setRegChat(long id) { prefs().edit().putLong("reg_chat", id).apply(); }

    public static long getLogChat() {
        try { return prefs().getLong("log_chat", 0); } catch (Throwable t) { return 0; }
    }
    public static void setLogChat(long id) { prefs().edit().putLong("log_chat", id).apply(); }

    public static boolean isVoteEnabled() {
        try { return prefs().getBoolean("vote_enabled", true); } catch (Throwable t) { return true; }
    }
    public static void setVoteEnabled(boolean v) { prefs().edit().putBoolean("vote_enabled", v).apply(); }

    public static String getVoteTarget() {
        try { return prefs().getString("vote_target", ""); } catch (Throwable t) { return ""; }
    }
    public static void setVoteTarget(String t) {
        prefs().edit().putString("vote_target", t == null ? "" : t.trim()).apply();
    }

    public static boolean isAutoKill() {
        try { return prefs().getBoolean("auto_kill", true); } catch (Throwable t) { return true; }
    }
    public static void setAutoKill(boolean v) { prefs().edit().putBoolean("auto_kill", v).apply(); }

    public static boolean isAutoRead() {
        try { return prefs().getBoolean("auto_read", true); } catch (Throwable t) { return true; }
    }
    public static void setAutoRead(boolean v) { prefs().edit().putBoolean("auto_read", v).apply(); }

    public static boolean isRolesEnabled() {
        try { return prefs().getBoolean("roles_enabled", true); } catch (Throwable t) { return true; }
    }
    public static void setRolesEnabled(boolean v) { prefs().edit().putBoolean("roles_enabled", v).apply(); }

    public static boolean isTournament() {
        try { return prefs().getBoolean("tournament", false); } catch (Throwable t) { return false; }
    }
    public static void setTournament(boolean v) { prefs().edit().putBoolean("tournament", v).apply(); }

    public static String getColor() {
        try {
            String c = prefs().getString("color", "blue");
            return c == null ? "blue" : c;
        } catch (Throwable t) { return "blue"; }
    }
    public static void setColor(String c) {
        prefs().edit().putString("color", c == null ? "blue" : c).apply();
    }

    /**
     * Аккаунты для текущего режима.
     * solo — только текущий selectedAccount;
     * twins — все активированные (опционально без main, если main_in_twins=false).
     */
    public static ArrayList<Integer> participatingAccounts(int currentAccount) {
        ArrayList<Integer> out = new ArrayList<>();
        String mode = getMode();
        if (MODE_SOLO.equals(mode)) {
            if (UserConfig.getInstance(currentAccount).isClientActivated()) {
                out.add(currentAccount);
            }
            return out;
        }
        // twins
        int main = UserConfig.selectedAccount;
        for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {
            try {
                if (!UserConfig.getInstance(a).isClientActivated()) continue;
                if (!isMainInTwins() && a == main) continue;
                out.add(a);
            } catch (Throwable ignore) {}
        }
        // если main_in_twins и main активирован — добавить в начало
        if (isMainInTwins() && UserConfig.getInstance(main).isClientActivated() && !out.contains(main)) {
            out.add(0, main);
        }
        return out;
    }

    public static String accountsSummary(int currentAccount) {
        ArrayList<Integer> list = participatingAccounts(currentAccount);
        if (list.isEmpty()) return "нет активных аккаунтов";
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < list.size(); i++) {
            int a = list.get(i);
            String name = "acc" + (a + 1);
            try {
                org.telegram.tgnet.TLRPC.User u = UserConfig.getInstance(a).getCurrentUser();
                if (u != null) {
                    name = UserObject.getFirstName(u);
                    if (u.username != null && u.username.length() > 0) {
                        name += " (@" + u.username + ")";
                    }
                }
            } catch (Throwable ignore) {}
            if (i > 0) sb.append("\n");
            sb.append("• ").append(name);
        }
        return sb.toString();
    }
}
'''

JAVA_SETTINGS = r'''package org.telegram.ui;

import android.content.Context;
import android.text.TextUtils;
import android.view.View;
import android.view.ViewGroup;
import android.widget.EditText;
import android.widget.FrameLayout;

import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import org.telegram.messenger.AndroidUtilities;
import org.telegram.messenger.PikmiMafia;
import org.telegram.messenger.R;
import org.telegram.messenger.UserConfig;
import org.telegram.ui.ActionBar.ActionBar;
import org.telegram.ui.ActionBar.BaseFragment;
import org.telegram.ui.ActionBar.Theme;
import org.telegram.ui.Cells.HeaderCell;
import org.telegram.ui.Cells.ShadowSectionCell;
import org.telegram.ui.Cells.TextCheckCell;
import org.telegram.ui.Cells.TextInfoPrivacyCell;
import org.telegram.ui.Cells.TextSettingsCell;
import org.telegram.ui.Components.LayoutHelper;
import org.telegram.ui.Components.RecyclerListView;

public class PikmiMafiaSettingsActivity extends BaseFragment {

    private RecyclerListView listView;
    private ListAdapter adapter;

    private int rowCount;
    private int headerMain;
    private int enabledRow;
    private int modeRow;
    private int mainInTwinsRow;
    private int botModeRow;
    private int trueFreeRow;
    private int botUserRow;
    private int section1;
    private int headerChats;
    private int regChatRow;
    private int logChatRow;
    private int section2;
    private int headerGame;
    private int voteEnRow;
    private int voteTargetRow;
    private int autoKillRow;
    private int autoReadRow;
    private int rolesRow;
    private int tourRow;
    private int colorRow;
    private int section3;
    private int headerAcc;
    private int accountsInfoRow;
    private int section4;
    private int infoRow;

    @Override
    public boolean onFragmentCreate() {
        super.onFragmentCreate();
        updateRows();
        return true;
    }

    private void updateRows() {
        rowCount = 0;
        headerMain = rowCount++;
        enabledRow = rowCount++;
        modeRow = rowCount++;
        mainInTwinsRow = rowCount++;
        botModeRow = rowCount++;
        trueFreeRow = rowCount++;
        botUserRow = rowCount++;
        section1 = rowCount++;
        headerChats = rowCount++;
        regChatRow = rowCount++;
        logChatRow = rowCount++;
        section2 = rowCount++;
        headerGame = rowCount++;
        voteEnRow = rowCount++;
        voteTargetRow = rowCount++;
        autoKillRow = rowCount++;
        autoReadRow = rowCount++;
        rolesRow = rowCount++;
        tourRow = rowCount++;
        colorRow = rowCount++;
        section3 = rowCount++;
        headerAcc = rowCount++;
        accountsInfoRow = rowCount++;
        section4 = rowCount++;
        infoRow = rowCount++;
    }

    @Override
    public View createView(Context context) {
        actionBar.setBackButtonImage(R.drawable.ic_ab_back);
        actionBar.setAllowOverlayTitle(true);
        actionBar.setTitle("Pikmi: Мафия");
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
            if (position == enabledRow) {
                boolean n = !PikmiMafia.isEnabled();
                PikmiMafia.setEnabled(n);
                if (view instanceof TextCheckCell) ((TextCheckCell) view).setChecked(n);
            } else if (position == modeRow) {
                String[] opts = new String[]{"Solo (только текущий)", "Twins (все аккаунты клиента)"};
                int checked = PikmiMafia.MODE_TWINS.equals(PikmiMafia.getMode()) ? 1 : 0;
                new android.app.AlertDialog.Builder(getParentActivity())
                        .setTitle("Режим аккаунтов")
                        .setSingleChoiceItems(opts, checked, (d, which) -> {
                            PikmiMafia.setMode(which == 1 ? PikmiMafia.MODE_TWINS : PikmiMafia.MODE_SOLO);
                            if (adapter != null) adapter.notifyDataSetChanged();
                            d.dismiss();
                        })
                        .setNegativeButton("Отмена", null)
                        .show();
            } else if (position == mainInTwinsRow) {
                boolean n = !PikmiMafia.isMainInTwins();
                PikmiMafia.setMainInTwins(n);
                if (view instanceof TextCheckCell) ((TextCheckCell) view).setChecked(n);
                if (adapter != null) adapter.notifyItemChanged(accountsInfoRow);
            } else if (position == botModeRow) {
                String[] opts = new String[]{"Mafia Baku Black", "True Mafia Black", "Mafioso", "Mafia Combat"};
                String[] keys = new String[]{PikmiMafia.BOT_BAKU, PikmiMafia.BOT_TRUE, PikmiMafia.BOT_MAFIOSO, PikmiMafia.BOT_COMBAT};
                int checked = 0;
                String cur = PikmiMafia.getBotMode();
                for (int i = 0; i < keys.length; i++) if (keys[i].equals(cur)) checked = i;
                new android.app.AlertDialog.Builder(getParentActivity())
                        .setTitle("Игровой бот")
                        .setSingleChoiceItems(opts, checked, (d, which) -> {
                            PikmiMafia.setBotMode(keys[which]);
                            if (adapter != null) adapter.notifyDataSetChanged();
                            d.dismiss();
                        })
                        .setNegativeButton("Отмена", null)
                        .show();
            } else if (position == trueFreeRow) {
                boolean n = !PikmiMafia.isTrueFree();
                PikmiMafia.setTrueFree(n);
                if (view instanceof TextCheckCell) ((TextCheckCell) view).setChecked(n);
                if (adapter != null) adapter.notifyItemChanged(botUserRow);
            } else if (position == botUserRow) {
                showTextDialog("Username бота", PikmiMafia.getBotUsername(), v -> {
                    PikmiMafia.setBotUsername(v);
                    if (adapter != null) adapter.notifyItemChanged(botUserRow);
                });
            } else if (position == regChatRow) {
                showIdDialog("ID чата авторега (0 = не задан)", PikmiMafia.getRegChat(), v -> {
                    PikmiMafia.setRegChat(v);
                    if (adapter != null) adapter.notifyItemChanged(regChatRow);
                });
            } else if (position == logChatRow) {
                showIdDialog("ID лог-чата (0 = Saved Messages)", PikmiMafia.getLogChat(), v -> {
                    PikmiMafia.setLogChat(v);
                    if (adapter != null) adapter.notifyItemChanged(logChatRow);
                });
            } else if (position == voteEnRow) {
                boolean n = !PikmiMafia.isVoteEnabled();
                PikmiMafia.setVoteEnabled(n);
                if (view instanceof TextCheckCell) ((TextCheckCell) view).setChecked(n);
            } else if (position == voteTargetRow) {
                showTextDialog("Ник для голосования", PikmiMafia.getVoteTarget(), v -> {
                    PikmiMafia.setVoteTarget(v);
                    if (adapter != null) adapter.notifyItemChanged(voteTargetRow);
                });
            } else if (position == autoKillRow) {
                boolean n = !PikmiMafia.isAutoKill();
                PikmiMafia.setAutoKill(n);
                if (view instanceof TextCheckCell) ((TextCheckCell) view).setChecked(n);
            } else if (position == autoReadRow) {
                boolean n = !PikmiMafia.isAutoRead();
                PikmiMafia.setAutoRead(n);
                if (view instanceof TextCheckCell) ((TextCheckCell) view).setChecked(n);
            } else if (position == rolesRow) {
                boolean n = !PikmiMafia.isRolesEnabled();
                PikmiMafia.setRolesEnabled(n);
                if (view instanceof TextCheckCell) ((TextCheckCell) view).setChecked(n);
            } else if (position == tourRow) {
                boolean n = !PikmiMafia.isTournament();
                PikmiMafia.setTournament(n);
                if (view instanceof TextCheckCell) ((TextCheckCell) view).setChecked(n);
            } else if (position == colorRow) {
                String[] opts = new String[]{"blue", "red", "orange", "black", "yellow"};
                int checked = 0;
                String cur = PikmiMafia.getColor();
                for (int i = 0; i < opts.length; i++) if (opts[i].equals(cur)) checked = i;
                new android.app.AlertDialog.Builder(getParentActivity())
                        .setTitle("Цвет команды (турнир)")
                        .setSingleChoiceItems(opts, checked, (d, which) -> {
                            PikmiMafia.setColor(opts[which]);
                            if (adapter != null) adapter.notifyItemChanged(colorRow);
                            d.dismiss();
                        })
                        .setNegativeButton("Отмена", null)
                        .show();
            }
        });

        return fragmentView;
    }

    private interface StrCb { void on(String v); }
    private interface LongCb { void on(long v); }

    private void showTextDialog(String title, String cur, StrCb cb) {
        if (getParentActivity() == null) return;
        final EditText input = new EditText(getParentActivity());
        input.setSingleLine(true);
        input.setText(cur == null ? "" : cur);
        input.setPadding(AndroidUtilities.dp(20), AndroidUtilities.dp(16), AndroidUtilities.dp(20), AndroidUtilities.dp(16));
        new android.app.AlertDialog.Builder(getParentActivity())
                .setTitle(title)
                .setView(input)
                .setPositiveButton("OK", (d, w) -> {
                    if (cb != null) cb.on(input.getText().toString().trim());
                })
                .setNegativeButton("Отмена", null)
                .show();
    }

    private void showIdDialog(String title, long cur, LongCb cb) {
        if (getParentActivity() == null) return;
        final EditText input = new EditText(getParentActivity());
        input.setSingleLine(true);
        input.setInputType(android.text.InputType.TYPE_CLASS_NUMBER | android.text.InputType.TYPE_NUMBER_FLAG_SIGNED);
        input.setText(String.valueOf(cur));
        input.setPadding(AndroidUtilities.dp(20), AndroidUtilities.dp(16), AndroidUtilities.dp(20), AndroidUtilities.dp(16));
        new android.app.AlertDialog.Builder(getParentActivity())
                .setTitle(title)
                .setView(input)
                .setPositiveButton("OK", (d, w) -> {
                    try {
                        long v = Long.parseLong(input.getText().toString().trim());
                        if (cb != null) cb.on(v);
                    } catch (Exception ignore) {}
                })
                .setNegativeButton("Отмена", null)
                .show();
    }

    private class ListAdapter extends RecyclerListView.SelectionAdapter {
        private final Context mContext;
        ListAdapter(Context c) { mContext = c; }

        @Override
        public boolean isEnabled(RecyclerView.ViewHolder h) {
            int p = h.getAdapterPosition();
            return p == enabledRow || p == modeRow || p == mainInTwinsRow || p == botModeRow || p == trueFreeRow
                    || p == botUserRow || p == regChatRow || p == logChatRow || p == voteEnRow || p == voteTargetRow
                    || p == autoKillRow || p == autoReadRow || p == rolesRow || p == tourRow || p == colorRow;
        }

        @Override
        public int getItemCount() { return rowCount; }

        @Override
        public int getItemViewType(int position) {
            if (position == headerMain || position == headerChats || position == headerGame || position == headerAcc) return 0;
            if (position == enabledRow || position == mainInTwinsRow || position == trueFreeRow || position == voteEnRow
                    || position == autoKillRow || position == autoReadRow || position == rolesRow || position == tourRow) return 1;
            if (position == section1 || position == section2 || position == section3 || position == section4) return 2;
            if (position == accountsInfoRow || position == infoRow) return 4;
            return 3; // settings
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
                case 3:
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
                    if (position == headerMain) cell.setText("Основное");
                    else if (position == headerChats) cell.setText("Чаты");
                    else if (position == headerGame) cell.setText("Игра");
                    else if (position == headerAcc) cell.setText("Аккаунты в режиме");
                    break;
                }
                case 1: {
                    TextCheckCell cell = (TextCheckCell) holder.itemView;
                    if (position == enabledRow) cell.setTextAndCheck("Модуль включён", PikmiMafia.isEnabled(), true);
                    else if (position == mainInTwinsRow) cell.setTextAndCheck("Основной в twins", PikmiMafia.isMainInTwins(), true);
                    else if (position == trueFreeRow) cell.setTextAndCheck("True: бесплатный бот", PikmiMafia.isTrueFree(), true);
                    else if (position == voteEnRow) cell.setTextAndCheck("Автоголосование", PikmiMafia.isVoteEnabled(), true);
                    else if (position == autoKillRow) cell.setTextAndCheck("Авто-«Убить» комиссара", PikmiMafia.isAutoKill(), true);
                    else if (position == autoReadRow) cell.setTextAndCheck("Автопрочтение бота", PikmiMafia.isAutoRead(), true);
                    else if (position == rolesRow) cell.setTextAndCheck("Список ролей в лог", PikmiMafia.isRolesEnabled(), true);
                    else if (position == tourRow) cell.setTextAndCheck("Турнирный режим", PikmiMafia.isTournament(), false);
                    break;
                }
                case 3: {
                    TextSettingsCell cell = (TextSettingsCell) holder.itemView;
                    cell.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText));
                    if (position == modeRow) {
                        String m = PikmiMafia.MODE_TWINS.equals(PikmiMafia.getMode()) ? "Twins" : "Solo";
                        cell.setTextAndValue("Режим", m, true);
                    } else if (position == botModeRow) {
                        cell.setTextAndValue("Бот", PikmiMafia.botModeLabel(), true);
                    } else if (position == botUserRow) {
                        cell.setTextAndValue("Username бота", "@" + PikmiMafia.getBotUsername(), true);
                    } else if (position == regChatRow) {
                        long id = PikmiMafia.getRegChat();
                        cell.setTextAndValue("Чат авторега", id == 0 ? "не задан" : String.valueOf(id), true);
                    } else if (position == logChatRow) {
                        long id = PikmiMafia.getLogChat();
                        cell.setTextAndValue("Лог-чат", id == 0 ? "Saved Messages" : String.valueOf(id), true);
                    } else if (position == voteTargetRow) {
                        String t = PikmiMafia.getVoteTarget();
                        cell.setTextAndValue("Ник голосования", TextUtils.isEmpty(t) ? "не задан" : t, true);
                    } else if (position == colorRow) {
                        cell.setTextAndValue("Цвет команды", PikmiMafia.getColor(), true);
                    }
                    break;
                }
                case 4: {
                    TextInfoPrivacyCell cell = (TextInfoPrivacyCell) holder.itemView;
                    if (position == accountsInfoRow) {
                        cell.setText("Режим: " + (PikmiMafia.MODE_TWINS.equals(PikmiMafia.getMode()) ? "twins" : "solo") + "\n"
                                + "Участвуют:\n" + PikmiMafia.accountsSummary(currentAccount)
                                + "\n\nАккаунты = все, кто вошёл в этот клиент (до лимита MAX_ACCOUNT). Добавляй твинков через «Добавить аккаунт».");
                    } else {
                        cell.setText("Это меню настроек модуля мафии внутри PikmiGram.\n"
                                + "Авторег, голосование и ночные ходы используют аккаунты клиента (не отдельный userbot).\n"
                                + "Лимит аккаунтов расширяется скриптом pikmi_accounts (по умолчанию до 12).");
                    }
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
        print(hint)
    sys.exit(1)


def main():
    HELPER.parent.mkdir(parents=True, exist_ok=True)
    HELPER.write_text(JAVA_HELPER, encoding="utf-8")
    print("PikmiMafia.java: создан")

    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(JAVA_SETTINGS, encoding="utf-8")
    print("PikmiMafiaSettingsActivity.java: создан")

    if not DA.exists():
        die("DialogsActivity не найден")
    da = DA.read_text(encoding="utf-8")
    if "PG_MAFIA_MENU" in da:
        print("меню мафии: уже есть")
    else:
        inserted = False
        if "PG_GHOST_MENU" in da:
            da = da.replace(
                "presentFragment(new org.telegram.ui.PikmiGhostSettingsActivity());\n        });",
                "presentFragment(new org.telegram.ui.PikmiGhostSettingsActivity());\n        });\n"
                "        io.add(R.drawable.msg_groups, \"PikmiGram: Мафия\", () -> { // PG_MAFIA_MENU\n"
                "            presentFragment(new org.telegram.ui.PikmiMafiaSettingsActivity());\n"
                "        });",
                1
            )
            inserted = "PG_MAFIA_MENU" in da
        if not inserted and "PG_AI_MENU" in da:
            da = da.replace(
                "presentFragment(new org.telegram.ui.PikmiAISettingsActivity());\n        });",
                "presentFragment(new org.telegram.ui.PikmiAISettingsActivity());\n        });\n"
                "        io.add(R.drawable.msg_groups, \"PikmiGram: Мафия\", () -> { // PG_MAFIA_MENU\n"
                "            presentFragment(new org.telegram.ui.PikmiMafiaSettingsActivity());\n"
                "        });",
                1
            )
            inserted = "PG_MAFIA_MENU" in da
        if not inserted:
            rx = re.compile(
                r"(io\.add\(R\.drawable\.outline_groups_24, getString\(R\.string\.NewGroup\), \(\) -> \{\s*"
                r"Bundle args = new Bundle\(\);\s*"
                r"presentFragment\(new GroupCreateActivity\(args\)\);\s*\}\);)"
            )
            if not rx.search(da):
                die("якорь меню не найден")
            da = rx.sub(
                lambda m: m.group(1) + "\n"
                "        io.addGap();\n"
                "        io.add(R.drawable.msg_groups, \"PikmiGram: Мафия\", () -> { // PG_MAFIA_MENU\n"
                "            presentFragment(new org.telegram.ui.PikmiMafiaSettingsActivity());\n"
                "        });",
                da,
                count=1
            )
        DA.write_text(da, encoding="utf-8")
        print("меню мафии: добавлено")

    print("Готово: Pikmi Mafia settings + accounts from client")


if __name__ == "__main__":
    main()
