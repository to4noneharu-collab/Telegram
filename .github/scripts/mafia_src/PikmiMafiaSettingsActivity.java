package org.telegram.ui;

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
import org.telegram.messenger.PikmiMafiaEngine;
import org.telegram.messenger.R;
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
    private int rowCount, hMain, enabledRow, modeRow, mainTwinsRow, botModeRow, trueFreeRow, botUserRow;
    private int sec1, hChat, regChatRow, logChatRow, sec2, hGame, voteEnRow, voteTargetRow, voteModeRow;
    private int voteTimeRow, voteBeforeRow, nightRow, warnRow, autoKillRow, autoReadRow, rolesRow, tourRow, colorRow, likeRow, lawyerRow;
    private int sec3, hAcc, accInfoRow, sec4, infoRow;

    @Override public boolean onFragmentCreate() {
        super.onFragmentCreate();
        PikmiMafiaEngine.getInstance().ensureObservers();
        rowCount = 0;
        hMain = rowCount++; enabledRow = rowCount++; modeRow = rowCount++; mainTwinsRow = rowCount++;
        botModeRow = rowCount++; trueFreeRow = rowCount++; botUserRow = rowCount++;
        sec1 = rowCount++; hChat = rowCount++; regChatRow = rowCount++; logChatRow = rowCount++;
        sec2 = rowCount++; hGame = rowCount++; voteEnRow = rowCount++; voteTargetRow = rowCount++; voteModeRow = rowCount++;
        voteTimeRow = rowCount++; voteBeforeRow = rowCount++; nightRow = rowCount++; warnRow = rowCount++;
        autoKillRow = rowCount++; autoReadRow = rowCount++; rolesRow = rowCount++; tourRow = rowCount++;
        colorRow = rowCount++; likeRow = rowCount++; lawyerRow = rowCount++;
        sec3 = rowCount++; hAcc = rowCount++; accInfoRow = rowCount++; sec4 = rowCount++; infoRow = rowCount++;
        return true;
    }

    @Override public View createView(Context context) {
        actionBar.setBackButtonImage(R.drawable.ic_ab_back);
        actionBar.setAllowOverlayTitle(true);
        actionBar.setTitle("Pikmi: Мафия");
        actionBar.setActionBarMenuOnItemClick(new ActionBar.ActionBarMenuOnItemClick() {
            @Override public void onItemClick(int id) { if (id == -1) finishFragment(); }
        });
        fragmentView = new FrameLayout(context);
        ((FrameLayout) fragmentView).setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundGray));
        listView = new RecyclerListView(context);
        listView.setLayoutManager(new LinearLayoutManager(context, LinearLayoutManager.VERTICAL, false));
        ((FrameLayout) fragmentView).addView(listView, LayoutHelper.createFrame(LayoutHelper.MATCH_PARENT, LayoutHelper.MATCH_PARENT));
        adapter = new ListAdapter(context);
        listView.setAdapter(adapter);
        listView.setOnItemClickListener((view, position) -> onClick(view, position));
        return fragmentView;
    }

    private void onClick(View view, int position) {
        if (position == enabledRow) { boolean n = !PikmiMafia.isEnabled(); PikmiMafia.setEnabled(n); if (n) PikmiMafiaEngine.getInstance().ensureObservers(); if (view instanceof TextCheckCell) ((TextCheckCell) view).setChecked(n); }
        else if (position == modeRow) pick("Режим", new String[]{"Solo", "Twins"}, PikmiMafia.MODE_TWINS.equals(PikmiMafia.getMode()) ? 1 : 0, which -> { PikmiMafia.setMode(which == 1 ? PikmiMafia.MODE_TWINS : PikmiMafia.MODE_SOLO); notifyAll_(); });
        else if (position == mainTwinsRow) { boolean n = !PikmiMafia.isMainInTwins(); PikmiMafia.setMainInTwins(n); if (view instanceof TextCheckCell) ((TextCheckCell) view).setChecked(n); notifyAll_(); }
        else if (position == botModeRow) {
            String[] keys = {PikmiMafia.BOT_BAKU, PikmiMafia.BOT_TRUE, PikmiMafia.BOT_MAFIOSO, PikmiMafia.BOT_COMBAT};
            String[] labs = {"Baku Black", "True Mafia", "Mafioso", "Combat"};
            int ch = 0; String cur = PikmiMafia.getBotMode();
            for (int i = 0; i < keys.length; i++) if (keys[i].equals(cur)) ch = i;
            pick("Бот", labs, ch, which -> { PikmiMafia.setBotMode(keys[which]); notifyAll_(); });
        } else if (position == trueFreeRow) { boolean n = !PikmiMafia.isTrueFree(); PikmiMafia.setTrueFree(n); if (view instanceof TextCheckCell) ((TextCheckCell) view).setChecked(n); notifyAll_(); }
        else if (position == botUserRow) textDlg("Username бота", PikmiMafia.getBotUsername(), v -> { PikmiMafia.setBotUsername(v); notifyAll_(); });
        else if (position == regChatRow) numDlg("ID чата авторега", PikmiMafia.getRegChat(), v -> { PikmiMafia.setRegChat(v); notifyAll_(); });
        else if (position == logChatRow) numDlg("ID лог-чата (0=Saved)", PikmiMafia.getLogChat(), v -> { PikmiMafia.setLogChat(v); notifyAll_(); });
        else if (position == voteEnRow) { boolean n = !PikmiMafia.isVoteEnabled(); PikmiMafia.setVoteEnabled(n); if (view instanceof TextCheckCell) ((TextCheckCell) view).setChecked(n); }
        else if (position == voteTargetRow) textDlg("Ник голосования", PikmiMafia.getVoteTarget(), v -> { PikmiMafia.setVoteTarget(v); notifyAll_(); });
        else if (position == voteModeRow) pick("Режим голоса", new String[]{"timer", "instant"}, "instant".equals(PikmiMafia.getVoteMode()) ? 1 : 0, which -> { PikmiMafia.setVoteMode(which == 1 ? "instant" : "timer"); notifyAll_(); });
        else if (position == voteTimeRow) numDlg("Длительность голоса (с)", PikmiMafia.getVoteTime(), v -> { PikmiMafia.setVoteTime((int) v); notifyAll_(); });
        else if (position == voteBeforeRow) numDlg("Голос за N с до конца", PikmiMafia.getVoteBefore(), v -> { PikmiMafia.setVoteBefore((int) v); notifyAll_(); });
        else if (position == nightRow) numDlg("Ночь (с)", PikmiMafia.getNightSec(), v -> { PikmiMafia.setNightSec((int) v); notifyAll_(); });
        else if (position == warnRow) numDlg("Предупреждение (с)", PikmiMafia.getWarnSec(), v -> { PikmiMafia.setWarnSec((int) v); notifyAll_(); });
        else if (position == autoKillRow) { boolean n = !PikmiMafia.isAutoKill(); PikmiMafia.setAutoKill(n); if (view instanceof TextCheckCell) ((TextCheckCell) view).setChecked(n); }
        else if (position == autoReadRow) { boolean n = !PikmiMafia.isAutoRead(); PikmiMafia.setAutoRead(n); if (view instanceof TextCheckCell) ((TextCheckCell) view).setChecked(n); }
        else if (position == rolesRow) { boolean n = !PikmiMafia.isRolesEnabled(); PikmiMafia.setRolesEnabled(n); if (view instanceof TextCheckCell) ((TextCheckCell) view).setChecked(n); }
        else if (position == tourRow) { boolean n = !PikmiMafia.isTournament(); PikmiMafia.setTournament(n); if (view instanceof TextCheckCell) ((TextCheckCell) view).setChecked(n); }
        else if (position == colorRow) {
            String[] c = {"blue", "red", "orange", "black", "yellow"};
            int ch = 0; String cur = PikmiMafia.getColor();
            for (int i = 0; i < c.length; i++) if (c[i].equals(cur)) ch = i;
            pick("Цвет", c, ch, which -> { PikmiMafia.setColor(c[which]); notifyAll_(); });
        } else if (position == likeRow) {
            String[] c = {"off", "like", "dis"};
            int ch = 0; String cur = PikmiMafia.getLike();
            for (int i = 0; i < c.length; i++) if (c[i].equals(cur)) ch = i;
            pick("Авто 👍/👎", new String[]{"выкл", "лайк", "дизлайк"}, ch, which -> { PikmiMafia.setLike(c[which]); notifyAll_(); });
        } else if (position == lawyerRow) { boolean n = !PikmiMafia.isAutoLawyer(); PikmiMafia.setAutoLawyer(n); if (view instanceof TextCheckCell) ((TextCheckCell) view).setChecked(n); }
    }

    private void notifyAll_() { if (adapter != null) adapter.notifyDataSetChanged(); }
    private interface IntCb { void on(int v); }
    private interface StrCb { void on(String v); }
    private interface LongCb { void on(long v); }

    private void pick(String title, String[] opts, int checked, IntCb cb) {
        if (getParentActivity() == null) return;
        new android.app.AlertDialog.Builder(getParentActivity()).setTitle(title)
                .setSingleChoiceItems(opts, checked, (d, w) -> { cb.on(w); d.dismiss(); })
                .setNegativeButton("Отмена", null).show();
    }
    private void textDlg(String title, String cur, StrCb cb) {
        if (getParentActivity() == null) return;
        EditText input = new EditText(getParentActivity());
        input.setSingleLine(true); input.setText(cur == null ? "" : cur);
        input.setPadding(AndroidUtilities.dp(20), AndroidUtilities.dp(16), AndroidUtilities.dp(20), AndroidUtilities.dp(16));
        new android.app.AlertDialog.Builder(getParentActivity()).setTitle(title).setView(input)
                .setPositiveButton("OK", (d, w) -> cb.on(input.getText().toString().trim()))
                .setNegativeButton("Отмена", null).show();
    }
    private void numDlg(String title, long cur, LongCb cb) {
        if (getParentActivity() == null) return;
        EditText input = new EditText(getParentActivity());
        input.setSingleLine(true);
        input.setInputType(android.text.InputType.TYPE_CLASS_NUMBER | android.text.InputType.TYPE_NUMBER_FLAG_SIGNED);
        input.setText(String.valueOf(cur));
        input.setPadding(AndroidUtilities.dp(20), AndroidUtilities.dp(16), AndroidUtilities.dp(20), AndroidUtilities.dp(16));
        new android.app.AlertDialog.Builder(getParentActivity()).setTitle(title).setView(input)
                .setPositiveButton("OK", (d, w) -> { try { cb.on(Long.parseLong(input.getText().toString().trim())); } catch (Exception ignore) {} })
                .setNegativeButton("Отмена", null).show();
    }

    private class ListAdapter extends RecyclerListView.SelectionAdapter {
        private final Context ctx;
        ListAdapter(Context c) { ctx = c; }
        @Override public boolean isEnabled(RecyclerView.ViewHolder h) {
            int p = h.getAdapterPosition();
            return p != hMain && p != hChat && p != hGame && p != hAcc && p != sec1 && p != sec2 && p != sec3 && p != sec4 && p != accInfoRow && p != infoRow;
        }
        @Override public int getItemCount() { return rowCount; }
        @Override public int getItemViewType(int p) {
            if (p == hMain || p == hChat || p == hGame || p == hAcc) return 0;
            if (p == enabledRow || p == mainTwinsRow || p == trueFreeRow || p == voteEnRow || p == autoKillRow || p == autoReadRow || p == rolesRow || p == tourRow || p == lawyerRow) return 1;
            if (p == sec1 || p == sec2 || p == sec3 || p == sec4) return 2;
            if (p == accInfoRow || p == infoRow) return 4;
            return 3;
        }
        @Override public RecyclerView.ViewHolder onCreateViewHolder(ViewGroup parent, int vt) {
            View v;
            switch (vt) {
                case 0: v = new HeaderCell(ctx); v.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundWhite)); break;
                case 1: v = new TextCheckCell(ctx); v.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundWhite)); break;
                case 2: v = new ShadowSectionCell(ctx); break;
                case 3: v = new TextSettingsCell(ctx); v.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundWhite)); break;
                default: v = new TextInfoPrivacyCell(ctx); break;
            }
            return new RecyclerListView.Holder(v);
        }
        @Override public void onBindViewHolder(RecyclerView.ViewHolder h, int p) {
            switch (h.getItemViewType()) {
                case 0: {
                    HeaderCell c = (HeaderCell) h.itemView;
                    if (p == hMain) c.setText("Основное");
                    else if (p == hChat) c.setText("Чаты");
                    else if (p == hGame) c.setText("Игра");
                    else c.setText("Аккаунты");
                    break;
                }
                case 1: {
                    TextCheckCell c = (TextCheckCell) h.itemView;
                    if (p == enabledRow) c.setTextAndCheck("Модуль включён", PikmiMafia.isEnabled(), true);
                    else if (p == mainTwinsRow) c.setTextAndCheck("Основной в twins", PikmiMafia.isMainInTwins(), true);
                    else if (p == trueFreeRow) c.setTextAndCheck("True: бесплатный бот", PikmiMafia.isTrueFree(), true);
                    else if (p == voteEnRow) c.setTextAndCheck("Автоголосование", PikmiMafia.isVoteEnabled(), true);
                    else if (p == autoKillRow) c.setTextAndCheck("Авто-Убить комиссара", PikmiMafia.isAutoKill(), true);
                    else if (p == autoReadRow) c.setTextAndCheck("Автопрочтение бота", PikmiMafia.isAutoRead(), true);
                    else if (p == rolesRow) c.setTextAndCheck("Список ролей в лог", PikmiMafia.isRolesEnabled(), true);
                    else if (p == tourRow) c.setTextAndCheck("Турнир", PikmiMafia.isTournament(), true);
                    else if (p == lawyerRow) c.setTextAndCheck("Авто-адвокат", PikmiMafia.isAutoLawyer(), false);
                    break;
                }
                case 3: {
                    TextSettingsCell c = (TextSettingsCell) h.itemView;
                    c.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText));
                    if (p == modeRow) c.setTextAndValue("Режим", PikmiMafia.MODE_TWINS.equals(PikmiMafia.getMode()) ? "Twins" : "Solo", true);
                    else if (p == botModeRow) c.setTextAndValue("Бот", PikmiMafia.botModeLabel(), true);
                    else if (p == botUserRow) c.setTextAndValue("Username", "@" + PikmiMafia.getBotUsername(), true);
                    else if (p == regChatRow) c.setTextAndValue("Чат авторега", PikmiMafia.getRegChat() == 0 ? "не задан" : String.valueOf(PikmiMafia.getRegChat()), true);
                    else if (p == logChatRow) c.setTextAndValue("Лог-чат", PikmiMafia.getLogChat() == 0 ? "Saved" : String.valueOf(PikmiMafia.getLogChat()), true);
                    else if (p == voteTargetRow) c.setTextAndValue("Ник голоса", TextUtils.isEmpty(PikmiMafia.getVoteTarget()) ? "—" : PikmiMafia.getVoteTarget(), true);
                    else if (p == voteModeRow) c.setTextAndValue("Режим голоса", PikmiMafia.getVoteMode(), true);
                    else if (p == voteTimeRow) c.setTextAndValue("Длительность голоса", PikmiMafia.getVoteTime() + " с", true);
                    else if (p == voteBeforeRow) c.setTextAndValue("Голос за N с", PikmiMafia.getVoteBefore() + " с", true);
                    else if (p == nightRow) c.setTextAndValue("Ночь", PikmiMafia.getNightSec() + " с", true);
                    else if (p == warnRow) c.setTextAndValue("Предупреждение", PikmiMafia.getWarnSec() + " с", true);
                    else if (p == colorRow) c.setTextAndValue("Цвет", PikmiMafia.getColor(), true);
                    else if (p == likeRow) c.setTextAndValue("Авто 👍/👎", PikmiMafia.getLike(), true);
                    break;
                }
                case 4: {
                    TextInfoPrivacyCell c = (TextInfoPrivacyCell) h.itemView;
                    if (p == accInfoRow) c.setText("Участвуют:\n" + PikmiMafia.accountsSummary(currentAccount));
                    else c.setText("Авторег, голос, роли, ночь, комиссар, линч — без отдельного userbot. Аккаунты = вошедшие в клиент. Прокси не используется.");
                    c.setBackground(Theme.getThemedDrawableByKey(ctx, R.drawable.greydivider, Theme.key_windowBackgroundGrayShadow));
                    break;
                }
            }
        }
    }
}
