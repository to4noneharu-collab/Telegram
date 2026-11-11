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
import java.util.ArrayList;

/**
 * Единое меню Мафии: настройки + живой список ролей + активные ночные кнопки.
 * Никаких сообщений в лог-чат — всё здесь.
 */
public class PikmiMafiaSettingsActivity extends BaseFragment {
    private RecyclerListView listView;
    private ListAdapter adapter;

    // static config rows
    private int rowCount;
    private int hMain, enabledRow, modeRow, mainTwinsRow, botModeRow, trueFreeRow, botUserRow;
    private int sec1, hChat, regChatRow;
    private int sec2, hGame, voteEnRow, voteTargetRow, voteModeRow, voteTimeRow, voteBeforeRow;
    private int nightRow, warnRow, autoKillRow, autoReadRow, tourRow, colorRow, likeRow, lawyerRow;
    private int sec3, hStatus, statusRow;
    private int hRoles;
    private int rolesStart;      // first dynamic role row
    private int rolesCount;      // number of role rows currently
    private int hActive;
    private int activeStart;
    private int activeCount;
    private int sec4, infoRow;

    // live snapshots
    private ArrayList<PikmiMafiaEngine.RoleEntry> rolesSnap = new ArrayList<>();
    private ArrayList<PikmiMafiaEngine.ActiveAcc> activeSnap = new ArrayList<>();
    private String statusLine = "Игра не идёт";

    @Override
    public boolean onFragmentCreate() {
        super.onFragmentCreate();
        PikmiMafiaEngine.getInstance().ensureObservers();
        PikmiMafiaEngine.getInstance().setUiRefresh(this::refreshLive);
        rebuildRows();
        return true;
    }

    @Override
    public void onFragmentDestroy() {
        PikmiMafiaEngine.getInstance().setUiRefresh(null);
        super.onFragmentDestroy();
    }

    @Override
    public void onResume() {
        super.onResume();
        refreshLive();
    }

    private void refreshLive() {
        try {
            if (getParentActivity() == null) return;
            rolesSnap = PikmiMafiaEngine.getInstance().getRolesSnapshot();
            activeSnap = PikmiMafiaEngine.getInstance().getActiveAccounts();
            statusLine = PikmiMafiaEngine.getInstance().getGameStatusLine();
            rebuildRows();
            if (adapter != null) adapter.notifyDataSetChanged();
        } catch (Throwable ignore) {}
    }

    private void rebuildRows() {
        rowCount = 0;
        hMain = rowCount++;
        enabledRow = rowCount++;
        modeRow = rowCount++;
        mainTwinsRow = rowCount++;
        botModeRow = rowCount++;
        trueFreeRow = rowCount++;
        botUserRow = rowCount++;

        sec1 = rowCount++;
        hChat = rowCount++;
        regChatRow = rowCount++;

        sec2 = rowCount++;
        hGame = rowCount++;
        voteEnRow = rowCount++;
        voteTargetRow = rowCount++;
        voteModeRow = rowCount++;
        voteTimeRow = rowCount++;
        voteBeforeRow = rowCount++;
        nightRow = rowCount++;
        warnRow = rowCount++;
        autoKillRow = rowCount++;
        autoReadRow = rowCount++;
        tourRow = rowCount++;
        colorRow = rowCount++;
        likeRow = rowCount++;
        lawyerRow = rowCount++;

        sec3 = rowCount++;
        hStatus = rowCount++;
        statusRow = rowCount++;

        hRoles = rowCount++;
        rolesStart = rowCount;
        rolesCount = Math.max(1, rolesSnap.size()); // at least "пусто"
        rowCount += rolesCount;

        hActive = rowCount++;
        activeStart = rowCount;
        activeCount = Math.max(1, activeSnap.size());
        rowCount += activeCount;

        sec4 = rowCount++;
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
        if (position == enabledRow) {
            boolean n = !PikmiMafia.isEnabled();
            PikmiMafia.setEnabled(n);
            if (n) PikmiMafiaEngine.getInstance().ensureObservers();
            if (view instanceof TextCheckCell) ((TextCheckCell) view).setChecked(n);
        } else if (position == modeRow) {
            pick("Режим", new String[]{"Solo", "Twins"},
                    PikmiMafia.MODE_TWINS.equals(PikmiMafia.getMode()) ? 1 : 0,
                    which -> {
                        PikmiMafia.setMode(which == 1 ? PikmiMafia.MODE_TWINS : PikmiMafia.MODE_SOLO);
                        notifyAll_();
                    });
        } else if (position == mainTwinsRow) {
            boolean n = !PikmiMafia.isMainInTwins();
            PikmiMafia.setMainInTwins(n);
            if (view instanceof TextCheckCell) ((TextCheckCell) view).setChecked(n);
            notifyAll_();
        } else if (position == botModeRow) {
            String[] keys = {PikmiMafia.BOT_BAKU, PikmiMafia.BOT_TRUE, PikmiMafia.BOT_MAFIOSO, PikmiMafia.BOT_COMBAT};
            String[] labs = {"Baku Black", "True Mafia", "Mafioso", "Combat"};
            int ch = 0;
            String cur = PikmiMafia.getBotMode();
            for (int i = 0; i < keys.length; i++) if (keys[i].equals(cur)) ch = i;
            pick("Бот", labs, ch, which -> {
                PikmiMafia.setBotMode(keys[which]);
                notifyAll_();
            });
        } else if (position == trueFreeRow) {
            boolean n = !PikmiMafia.isTrueFree();
            PikmiMafia.setTrueFree(n);
            if (view instanceof TextCheckCell) ((TextCheckCell) view).setChecked(n);
            notifyAll_();
        } else if (position == botUserRow) {
            textDlg("Username бота", PikmiMafia.getBotUsername(), v -> {
                PikmiMafia.setBotUsername(v);
                notifyAll_();
            });
        } else if (position == regChatRow) {
            numDlg("ID чата авторега", PikmiMafia.getRegChat(), v -> {
                PikmiMafia.setRegChat(v);
                notifyAll_();
            });
        } else if (position == voteEnRow) {
            boolean n = !PikmiMafia.isVoteEnabled();
            PikmiMafia.setVoteEnabled(n);
            if (view instanceof TextCheckCell) ((TextCheckCell) view).setChecked(n);
        } else if (position == voteTargetRow) {
            textDlg("Ник голосования", PikmiMafia.getVoteTarget(), v -> {
                PikmiMafia.setVoteTarget(v);
                notifyAll_();
            });
        } else if (position == voteModeRow) {
            pick("Режим голоса", new String[]{"timer", "instant"},
                    "instant".equals(PikmiMafia.getVoteMode()) ? 1 : 0,
                    which -> {
                        PikmiMafia.setVoteMode(which == 1 ? "instant" : "timer");
                        notifyAll_();
                    });
        } else if (position == voteTimeRow) {
            numDlg("Длительность голоса (с)", PikmiMafia.getVoteTime(), v -> {
                PikmiMafia.setVoteTime((int) v);
                notifyAll_();
            });
        } else if (position == voteBeforeRow) {
            numDlg("Голос за N с до конца", PikmiMafia.getVoteBefore(), v -> {
                PikmiMafia.setVoteBefore((int) v);
                notifyAll_();
            });
        } else if (position == nightRow) {
            numDlg("Ночь (с)", PikmiMafia.getNightSec(), v -> {
                PikmiMafia.setNightSec((int) v);
                notifyAll_();
            });
        } else if (position == warnRow) {
            numDlg("Предупреждение (с)", PikmiMafia.getWarnSec(), v -> {
                PikmiMafia.setWarnSec((int) v);
                notifyAll_();
            });
        } else if (position == autoKillRow) {
            boolean n = !PikmiMafia.isAutoKill();
            PikmiMafia.setAutoKill(n);
            if (view instanceof TextCheckCell) ((TextCheckCell) view).setChecked(n);
        } else if (position == autoReadRow) {
            boolean n = !PikmiMafia.isAutoRead();
            PikmiMafia.setAutoRead(n);
            if (view instanceof TextCheckCell) ((TextCheckCell) view).setChecked(n);
        } else if (position == tourRow) {
            boolean n = !PikmiMafia.isTournament();
            PikmiMafia.setTournament(n);
            if (view instanceof TextCheckCell) ((TextCheckCell) view).setChecked(n);
        } else if (position == colorRow) {
            String[] c = {"blue", "red", "orange", "black", "yellow"};
            int ch = 0;
            String cur = PikmiMafia.getColor();
            for (int i = 0; i < c.length; i++) if (c[i].equals(cur)) ch = i;
            pick("Цвет", c, ch, which -> {
                PikmiMafia.setColor(c[which]);
                notifyAll_();
            });
        } else if (position == likeRow) {
            String[] c = {"off", "like", "dis"};
            int ch = 0;
            String cur = PikmiMafia.getLike();
            for (int i = 0; i < c.length; i++) if (c[i].equals(cur)) ch = i;
            pick("Авто 👍/👎", new String[]{"выкл", "лайк", "дизлайк"}, ch, which -> {
                PikmiMafia.setLike(c[which]);
                notifyAll_();
            });
        } else if (position == lawyerRow) {
            boolean n = !PikmiMafia.isAutoLawyer();
            PikmiMafia.setAutoLawyer(n);
            if (view instanceof TextCheckCell) ((TextCheckCell) view).setChecked(n);
        } else if (position >= activeStart && position < activeStart + activeCount) {
            int idx = position - activeStart;
            if (idx >= 0 && idx < activeSnap.size()) {
                PikmiMafiaEngine.ActiveAcc a = activeSnap.get(idx);
                if (a.buttons != null && !a.buttons.isEmpty()) {
                    showButtonsDialog(a);
                }
            }
        }
    }

    private void showButtonsDialog(PikmiMafiaEngine.ActiveAcc a) {
        if (getParentActivity() == null || a.buttons == null || a.buttons.isEmpty()) return;
        String[] opts = a.buttons.toArray(new String[0]);
        String title = a.label + (a.role != null ? " · " + a.role : "");
        new android.app.AlertDialog.Builder(getParentActivity())
                .setTitle(title)
                .setItems(opts, (d, which) -> {
                    PikmiMafiaEngine.getInstance().pressActiveButton(a.account, which);
                    AndroidUtilities.runOnUIThread(this::refreshLive, 600);
                })
                .setNegativeButton("Закрыть", null)
                .show();
    }

    private void notifyAll_() {
        if (adapter != null) adapter.notifyDataSetChanged();
    }

    private interface IntCb { void on(int v); }
    private interface StrCb { void on(String v); }
    private interface LongCb { void on(long v); }

    private void pick(String title, String[] opts, int checked, IntCb cb) {
        if (getParentActivity() == null) return;
        new android.app.AlertDialog.Builder(getParentActivity()).setTitle(title)
                .setSingleChoiceItems(opts, checked, (d, w) -> {
                    cb.on(w);
                    d.dismiss();
                })
                .setNegativeButton("Отмена", null).show();
    }

    private void textDlg(String title, String cur, StrCb cb) {
        if (getParentActivity() == null) return;
        EditText input = new EditText(getParentActivity());
        input.setSingleLine(true);
        input.setText(cur == null ? "" : cur);
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
                .setPositiveButton("OK", (d, w) -> {
                    try {
                        cb.on(Long.parseLong(input.getText().toString().trim()));
                    } catch (Throwable ignore) {}
                })
                .setNegativeButton("Отмена", null).show();
    }

    private class ListAdapter extends RecyclerListView.SelectionAdapter {
        private final Context ctx;

        ListAdapter(Context c) { ctx = c; }

        @Override
        public boolean isEnabled(RecyclerView.ViewHolder h) {
            int p = h.getAdapterPosition();
            if (p == hMain || p == hChat || p == hGame || p == hStatus || p == hRoles || p == hActive
                    || p == sec1 || p == sec2 || p == sec3 || p == sec4 || p == infoRow || p == statusRow)
                return false;
            if (p >= rolesStart && p < rolesStart + rolesCount) return false; // роли только просмотр
            return true;
        }

        @Override
        public int getItemCount() { return rowCount; }

        @Override
        public int getItemViewType(int p) {
            if (p == hMain || p == hChat || p == hGame || p == hStatus || p == hRoles || p == hActive) return 0;
            if (p == enabledRow || p == mainTwinsRow || p == trueFreeRow || p == voteEnRow
                    || p == autoKillRow || p == autoReadRow || p == tourRow || p == lawyerRow) return 1;
            if (p == sec1 || p == sec2 || p == sec3 || p == sec4) return 2;
            if (p == infoRow) return 4;
            return 3; // TextSettingsCell
        }

        @Override
        public RecyclerView.ViewHolder onCreateViewHolder(ViewGroup parent, int viewType) {
            View v;
            switch (viewType) {
                case 0:
                    v = new HeaderCell(ctx);
                    v.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundWhite));
                    break;
                case 1:
                    v = new TextCheckCell(ctx);
                    v.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundWhite));
                    break;
                case 2:
                    v = new ShadowSectionCell(ctx);
                    break;
                case 4:
                    v = new TextInfoPrivacyCell(ctx);
                    break;
                default:
                    v = new TextSettingsCell(ctx);
                    v.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundWhite));
                    break;
            }
            return new RecyclerListView.Holder(v);
        }

        @Override
        public void onBindViewHolder(RecyclerView.ViewHolder h, int p) {
            int t = h.getItemViewType();
            if (t == 0) {
                HeaderCell c = (HeaderCell) h.itemView;
                if (p == hMain) c.setText("Основное");
                else if (p == hChat) c.setText("Чаты");
                else if (p == hGame) c.setText("Игра");
                else if (p == hStatus) c.setText("Статус");
                else if (p == hRoles) c.setText("Роли в игре");
                else if (p == hActive) c.setText("Активные роли");
            } else if (t == 1) {
                TextCheckCell c = (TextCheckCell) h.itemView;
                if (p == enabledRow) c.setTextAndCheck("Модуль включён", PikmiMafia.isEnabled(), true);
                else if (p == mainTwinsRow) c.setTextAndCheck("Основной в twins", PikmiMafia.isMainInTwins(), true);
                else if (p == trueFreeRow) c.setTextAndCheck("True Mafia free", PikmiMafia.isTrueFree(), true);
                else if (p == voteEnRow) c.setTextAndCheck("Автоголос", PikmiMafia.isVoteEnabled(), true);
                else if (p == autoKillRow) c.setTextAndCheck("Авто-килл комиссара", PikmiMafia.isAutoKill(), true);
                else if (p == autoReadRow) c.setTextAndCheck("Авто-чтение ЛС бота", PikmiMafia.isAutoRead(), true);
                else if (p == tourRow) c.setTextAndCheck("Турнир", PikmiMafia.isTournament(), true);
                else if (p == lawyerRow) c.setTextAndCheck("Авто-адвокат", PikmiMafia.isAutoLawyer(), true);
            } else if (t == 3) {
                TextSettingsCell c = (TextSettingsCell) h.itemView;
                if (p == modeRow) c.setTextAndValue("Режим", PikmiMafia.MODE_TWINS.equals(PikmiMafia.getMode()) ? "Twins" : "Solo", true);
                else if (p == botModeRow) c.setTextAndValue("Бот", PikmiMafia.botModeLabel(), true);
                else if (p == botUserRow) c.setTextAndValue("Username", "@" + PikmiMafia.getBotUsername(), true);
                else if (p == regChatRow) {
                    long id = PikmiMafia.getRegChat();
                    c.setTextAndValue("Чат авторега", id == 0 ? "не задан" : String.valueOf(id), true);
                } else if (p == voteTargetRow) {
                    String t2 = PikmiMafia.getVoteTarget();
                    c.setTextAndValue("Ник голоса", TextUtils.isEmpty(t2) ? "—" : t2, true);
                } else if (p == voteModeRow) c.setTextAndValue("Режим голоса", PikmiMafia.getVoteMode(), true);
                else if (p == voteTimeRow) c.setTextAndValue("Длительность (с)", String.valueOf(PikmiMafia.getVoteTime()), true);
                else if (p == voteBeforeRow) c.setTextAndValue("За N с до конца", String.valueOf(PikmiMafia.getVoteBefore()), true);
                else if (p == nightRow) c.setTextAndValue("Ночь (с)", String.valueOf(PikmiMafia.getNightSec()), true);
                else if (p == warnRow) c.setTextAndValue("Предупреждение (с)", String.valueOf(PikmiMafia.getWarnSec()), true);
                else if (p == colorRow) c.setTextAndValue("Цвет команды", PikmiMafia.getColor(), true);
                else if (p == likeRow) {
                    String l = PikmiMafia.getLike();
                    c.setTextAndValue("Авто 👍/👎", "like".equals(l) ? "лайк" : "dis".equals(l) ? "дизлайк" : "выкл", true);
                } else if (p == statusRow) {
                    c.setTextAndValue("Игра", statusLine, false);
                } else if (p >= rolesStart && p < rolesStart + rolesCount) {
                    int idx = p - rolesStart;
                    if (rolesSnap.isEmpty()) {
                        c.setTextAndValue("Роли", "пока пусто", false);
                    } else if (idx < rolesSnap.size()) {
                        PikmiMafiaEngine.RoleEntry e = rolesSnap.get(idx);
                        String prefix = e.dead ? "☠️ " : (e.own ? "🤖 " : "🤝 ");
                        c.setTextAndValue(prefix + e.name, e.role, idx < rolesSnap.size() - 1);
                    }
                } else if (p >= activeStart && p < activeStart + activeCount) {
                    int idx = p - activeStart;
                    if (activeSnap.isEmpty()) {
                        c.setTextAndValue("Аккаунты", "нет участвующих", false);
                    } else if (idx < activeSnap.size()) {
                        PikmiMafiaEngine.ActiveAcc a = activeSnap.get(idx);
                        StringBuilder val = new StringBuilder();
                        if (a.dead) val.append("мёртв");
                        else if (a.blocked) val.append(a.why != null ? a.why : "блок");
                        else if (a.role != null) val.append(a.role);
                        else val.append("—");
                        if (a.buttons != null && !a.buttons.isEmpty()) {
                            val.append(" · ").append(a.buttons.size()).append(" кн.");
                        }
                        String title = a.label + (a.buttons != null && !a.buttons.isEmpty() ? " 🔔" : "");
                        c.setTextAndValue(title, val.toString(), idx < activeSnap.size() - 1);
                    }
                }
            } else if (t == 4) {
                TextInfoPrivacyCell c = (TextInfoPrivacyCell) h.itemView;
                c.setText("Роли и активные кнопки обновляются автоматически. Нажмите на аккаунт с 🔔, чтобы увидеть кнопки бота и нажать их от его имени. Сообщения в лог-чат не отправляются.");
            }
        }
    }
}
