package org.telegram.messenger;

import android.os.Handler;
import android.os.Looper;
import android.text.TextUtils;
import org.telegram.tgnet.ConnectionsManager;
import org.telegram.tgnet.TLRPC;
import org.telegram.tgnet.tl.TL_keyboard;
import java.util.ArrayList;
import java.util.Locale;
import java.util.concurrent.ConcurrentHashMap;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Движок Мафии.
 * Роли и активные ночные кнопки хранятся здесь и показываются только в меню настроек.
 * В лог-чат ничего не спамим (только FileLog).
 */
public class PikmiMafiaEngine {
    private static PikmiMafiaEngine Instance;
    private static final Handler main = new Handler(Looper.getMainLooper());
    private static final Pattern START_EQ = Pattern.compile("start(?:group)?=([A-Za-z0-9_\\-]+)");
    private static final Pattern ALLY = Pattern.compile("^\\s*(?:[•·\\-\\*]\\s*)?(.+?)\\s*[-–—]\\s*(.+?)\\s*$");

    private final ConcurrentHashMap<Integer, Boolean> observers = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<String, Long> done = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<Integer, String> accRoles = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<Integer, AccStat> status = new ConcurrentHashMap<>();
    /** Последнее сообщение бота с inline-кнопками (для меню «Активные роли»). */
    private final ConcurrentHashMap<Integer, MessageObject> lastPrompt = new ConcurrentHashMap<>();
    private final ArrayList<RoleEntry> roles = new ArrayList<>();
    private final Object rolesLock = new Object();
    private volatile boolean gameOn;
    private volatile long gameSince, actAt;
    private Runnable nightWarn, nightEnd, voteRun, rebindRun;
    private volatile Runnable uiRefresh;
    private volatile long lastEnsureAt;

    public static class AccStat {
        public boolean dead, blocked, killed;
        public String why = "";
    }

    public static class RoleEntry {
        public String name, role;
        public boolean own, dead;
    }

    public static class ActiveAcc {
        public int account;
        public String label;
        public String role;
        public boolean dead, blocked;
        public String why;
        public MessageObject prompt; // last bot msg with buttons
        public ArrayList<String> buttons = new ArrayList<>();
    }

    public static synchronized PikmiMafiaEngine getInstance() {
        if (Instance == null) Instance = new PikmiMafiaEngine();
        return Instance;
    }

    /** UI подписывается, чтобы обновлять список ролей/активных. */
    public void setUiRefresh(Runnable r) { uiRefresh = r; }

    private void notifyUi() {
        final Runnable r = uiRefresh;
        if (r == null) return;
        try {
            main.post(() -> {
                try { r.run(); } catch (Throwable ignore) {}
            });
        } catch (Throwable ignore) {}
    }

    /**
     * Подписка на didReceiveNewMessages для всех аккаунтов.
     * Безопасно вызывать многократно (фон / возврат в приложение / KeepAlive).
     * Ошибки одного аккаунта не снимают подписку и не роняют процесс.
     */
    public void ensureObservers() {
        lastEnsureAt = System.currentTimeMillis();
        int max = 5;
        try { max = Math.max(1, Math.min(UserConfig.MAX_ACCOUNT_COUNT, 32)); } catch (Throwable ignore) {}
        for (int a = 0; a < max; a++) {
            final int account = a;
            try {
                if (!UserConfig.getInstance(account).isClientActivated()) {
                    observers.remove(account);
                    continue;
                }
            } catch (Throwable ignore) {
                continue;
            }
            if (observers.putIfAbsent(account, Boolean.TRUE) != null) continue;
            try {
                NotificationCenter.getInstance(account).addObserver((id, account2, args) -> {
                    try {
                        if (id != NotificationCenter.didReceiveNewMessages) return;
                        if (!PikmiMafia.isEnabled()) return;
                        if (args == null || args.length < 2) return;
                        // isCache — пропускаем кэш, чтобы не дублировать
                        if (args.length > 2 && args[2] instanceof Boolean && (Boolean) args[2]) return;
                        Object raw = args[1];
                        if (!(raw instanceof ArrayList)) return;
                        ArrayList<?> messages = (ArrayList<?>) raw;
                        for (Object o : messages) {
                            if (!(o instanceof MessageObject)) continue;
                            MessageObject mo = (MessageObject) o;
                            if (mo.messageOwner == null || mo.isOut()) continue;
                            try {
                                onMessage(account, mo);
                            } catch (Throwable e) {
                                FileLog.e(e);
                            }
                        }
                    } catch (Throwable e) {
                        // никогда не пробрасываем — иначе падает NotificationCenter в фоне
                        FileLog.e(e);
                    }
                }, NotificationCenter.didReceiveNewMessages);
            } catch (Throwable e) {
                FileLog.e(e);
                // не remove — при следующем ensureObservers попробуем снова через сброс
                observers.remove(account);
            }
        }
        scheduleRebind();
    }

    /** Периодически переподписываемся, пока модуль включён (защита от смерти процесса/GC). */
    private void scheduleRebind() {
        if (rebindRun != null) return;
        rebindRun = () -> {
            rebindRun = null;
            try {
                if (!PikmiMafia.isEnabled()) return;
                // сбрасываем карту, чтобы addObserver снова прошёл для «потерянных» аккаунтов
                if (System.currentTimeMillis() - lastEnsureAt > 50_000) {
                    observers.clear();
                }
                ensureObservers();
            } catch (Throwable e) {
                FileLog.e(e);
            }
        };
        try {
            main.postDelayed(rebindRun, 60_000);
        } catch (Throwable ignore) {}
    }

    // ── публичные снимки для меню ──────────────────────────────────────────

    public boolean isGameOn() { return gameOn && System.currentTimeMillis() - gameSince < 4L * 3600_000; }

    public String getGameStatusLine() {
        if (!isGameOn()) return "Игра не идёт";
        long sec = (System.currentTimeMillis() - gameSince) / 1000;
        String phase = actAt > 0 && System.currentTimeMillis() - actAt < 180_000 ? "ночь/ход" : "день";
        return "Игра · " + phase + " · " + (sec / 60) + "м";
    }

    public ArrayList<RoleEntry> getRolesSnapshot() {
        ArrayList<RoleEntry> out = new ArrayList<>();
        synchronized (rolesLock) {
            for (RoleEntry e : roles) {
                RoleEntry c = new RoleEntry();
                c.name = e.name; c.role = e.role; c.own = e.own; c.dead = e.dead;
                out.add(c);
            }
        }
        return out;
    }

    public ArrayList<ActiveAcc> getActiveAccounts() {
        ArrayList<ActiveAcc> out = new ArrayList<>();
        ArrayList<Integer> accs = PikmiMafia.participatingAccounts(UserConfig.selectedAccount);
        for (int account : accs) {
            ActiveAcc a = new ActiveAcc();
            a.account = account;
            a.label = name(account);
            a.role = accRoles.get(account);
            AccStat st = status.get(account);
            if (st != null) {
                a.dead = st.dead;
                a.blocked = st.blocked;
                a.why = st.why;
            }
            MessageObject mo = lastPrompt.get(account);
            if (mo != null && hasInline(mo.messageOwner)) {
                a.prompt = mo;
                forEachButton(mo.messageOwner, b -> {
                    String tx = btnText(b);
                    if (!TextUtils.isEmpty(tx)) a.buttons.add(tx);
                });
            }
            out.add(a);
        }
        return out;
    }

    /** Нажать кнопку idx у последнего prompt аккаунта (из меню). */
    public void pressActiveButton(int account, int buttonIndex) {
        MessageObject mo = lastPrompt.get(account);
        if (mo == null || mo.messageOwner == null || !hasInline(mo.messageOwner)) return;
        try {
            final int[] idx = {0};
            final boolean[] done = {false};
            forEachButton(mo.messageOwner, b -> {
                if (done[0]) return;
                byte[] data = btnData(b);
                if (data == null) return;
                if (idx[0] == buttonIndex) {
                    pressCb(account, MessageObject.getDialogId(mo.messageOwner), mo.messageOwner.id, data);
                    log("👆 меню: acc" + (account + 1) + " → " + btnText(b));
                    done[0] = true;
                    return;
                }
                idx[0]++;
            });
        } catch (Throwable e) { FileLog.e(e); }
    }

    // ── внутреннее состояние ───────────────────────────────────────────────

    private AccStat stat(int a) {
        AccStat st = status.get(a);
        if (st == null) status.put(a, st = new AccStat());
        return st;
    }

    private void startGame() {
        gameOn = true;
        gameSince = System.currentTimeMillis();
        actAt = 0;
        status.clear();
        accRoles.clear();
        lastPrompt.clear();
        synchronized (rolesLock) { roles.clear(); }
        cancelNight();
        cancelVote();
        log("🎭 Новая игра");
        notifyUi();
    }

    private void endGame(String footer) {
        gameOn = false;
        cancelNight();
        cancelVote();
        log("🏁 " + (footer != null ? footer : "Игра окончена"));
        notifyUi();
    }

    private boolean gameActive() { return gameOn && System.currentTimeMillis() - gameSince < 4L * 3600_000; }

    private void onMessage(int account, MessageObject mo) {
        TLRPC.Message msg = mo.messageOwner;
        if (msg == null) return;
        String text = msg.message != null ? msg.message : "";
        String norm = PikmiMafia.normText(text);
        long dialogId = MessageObject.getDialogId(msg);
        // Участвует ли ЭТОТ аккаунт (не selectedAccount — иначе в solo сообщения с других акков отбрасывались)
        if (!PikmiMafia.participatingAccounts(account).contains(account)) return;

        TLRPC.User sender = null;
        boolean fromBot = false;
        try {
            if (msg.from_id != null && msg.from_id.user_id != 0) {
                sender = MessagesController.getInstance(account).getUser(msg.from_id.user_id);
                if (sender != null && sender.bot && sender.username != null)
                    fromBot = PikmiMafia.isBotUsername(sender.username);
            }
        } catch (Throwable ignore) {}

        long regChat = PikmiMafia.getRegChat();
        if (regChat != 0 && sameChat(regChat, dialogId)) handleChat(account, mo, text, norm, msg);
        if (fromBot && dialogId > 0) handleDm(account, mo, text, norm, msg, sender);
    }

    /** Сравнивает ID из настроек с dialogId (принимает 123, -123, -100123…). */
    private static boolean sameChat(long configured, long dialogId) {
        if (configured == 0) return false;
        if (configured == dialogId) return true;
        if (configured > 0 && dialogId == -configured) return true;
        if (configured < 0 && dialogId == configured) return true;
        // bare channel id vs -100xxxxxxxxxx
        long bareCfg = Math.abs(configured);
        long bareDlg = dialogId < 0 ? -dialogId : dialogId;
        String sCfg = String.valueOf(bareCfg);
        String sDlg = String.valueOf(bareDlg);
        if (sDlg.startsWith("100") && sDlg.length() > 3) {
            try {
                long ch = Long.parseLong(sDlg.substring(3));
                if (ch == bareCfg) return true;
            } catch (Throwable ignore) {}
        }
        if (sCfg.startsWith("100") && sCfg.length() > 3) {
            try {
                long ch = Long.parseLong(sCfg.substring(3));
                if (dialogId == -ch || bareDlg == ch) return true;
                // also full -100 form
                if (dialogId == -bareCfg) return true;
            } catch (Throwable ignore) {}
        }
        return false;
    }

    private void handleChat(int account, MessageObject mo, String text, String norm, TLRPC.Message msg) {
        if (PikmiMafia.isAutoReg() && PikmiMafia.hit(PikmiMafia.getRegTrigger(), norm)
                && once("reg:" + MessageObject.getDialogId(msg) + ":" + msg.id)) {
            log("📝 Рег-триггер did=" + MessageObject.getDialogId(msg));
            main.postDelayed(() -> doRegisterAll(mo), 400);
        }
        if (PikmiMafia.hit(PikmiMafia.getNightTrigger(), norm) && once("night:" + msg.id)) {
            for (AccStat st : status.values()) {
                st.blocked = false;
                if (!st.dead) st.why = "";
                st.killed = false;
            }
            actAt = 0;
            startNightTimer();
            log("🌙 Ночь " + PikmiMafia.getNightSec() + "с");
            notifyUi();
        }
        if (PikmiMafia.hit(PikmiMafia.getDayTrigger(), norm) && once("day:" + msg.id)) {
            cancelNight();
            actAt = 0;
            for (AccStat st : status.values()) st.killed = false;
            log("☀️ День");
            notifyUi();
        }
        if (PikmiMafia.isVoteEnabled() && !TextUtils.isEmpty(PikmiMafia.getVoteTarget())
                && PikmiMafia.hit(PikmiMafia.getVoteTrigger(), norm) && once("vch:" + msg.id)) {
            scheduleVote(msg.date);
        }
        String like = PikmiMafia.getLike();
        if (!"off".equals(like) && PikmiMafia.hit(PikmiMafia.getLynchTrigger(), norm)
                && once("lynch:" + msg.id) && msg.reply_markup != null) {
            main.post(() -> pressLynch(mo, "like".equals(like)));
        }
        if (PikmiMafia.hit(PikmiMafia.getHangTrigger(), norm)) markHang(text);
        if (PikmiMafia.hit(PikmiMafia.getEndTriggers(), norm) && once("end:" + msg.id)) {
            endGame(PikmiMafia.hit("остановлен", norm) ? "Остановлена" : "Игра окончена");
        }
    }

    private void handleDm(int account, MessageObject mo, String text, String norm, TLRPC.Message msg, TLRPC.User bot) {
        parseRole(account, text);
        AccStat st = stat(account);
        if (PikmiMafia.hit(PikmiMafia.getDeadTrigger(), norm)) {
            st.dead = true;
            markDead(name(account));
        }
        if (PikmiMafia.hit(PikmiMafia.getLoverTrigger(), norm)) {
            st.blocked = true;
            st.why = "любовница";
        }
        if (PikmiMafia.hit(PikmiMafia.getSwindlerTrigger(), norm)) {
            st.blocked = true;
            st.why = "аферист";
        }

        // Сохраняем сообщение с кнопками для меню «Активные роли»
        if (msg.reply_markup instanceof TLRPC.TL_replyInlineMarkup && gameActive()) {
            lastPrompt.put(account, mo);
            notifyUi();
        }

        if (PikmiMafia.isVoteEnabled() && !TextUtils.isEmpty(PikmiMafia.getVoteTarget())
                && PikmiMafia.hit(PikmiMafia.getVoteTrigger(), norm) && once("vdm:" + account + ":" + msg.id)) {
            scheduleVote(msg.date);
        }
        if (PikmiMafia.isAutoRead() && gameActive() && bot != null) {
            main.postDelayed(() -> {
                try {
                    MessagesController.getInstance(account).markDialogAsRead(bot.id, msg.id, msg.id, msg.date, false, 0, 0, true, 0);
                } catch (Throwable e) { FileLog.e(e); }
            }, 300);
        }
        if (PikmiMafia.isAutoKill()) {
            String mode = PikmiMafia.getBotMode();
            boolean gate = PikmiMafia.BOT_TRUE.equals(mode) || PikmiMafia.BOT_MAFIOSO.equals(mode);
            if (gate && PikmiMafia.hit(PikmiMafia.getActTrigger(), norm)) actAt = System.currentTimeMillis();
            boolean can = !gate || (actAt > 0 && System.currentTimeMillis() - actAt < 180_000);
            if (can && msg.reply_markup != null && (PikmiMafia.hit(PikmiMafia.getActionTrigger(), norm) || (gate && actAt > 0)))
                tryKill(account, mo, bot);
        }
        if (PikmiMafia.isAutoLawyer() && msg.reply_markup != null) {
            String role = accRoles.get(account);
            if (role != null && PikmiMafia.normText(role).contains("адвокат"))
                tryPress(account, mo, bot, PikmiMafia.getLawyerRole());
        }
        // Combat chemist: авто-нажатие первой кнопки выбора зелья
        if (PikmiMafia.BOT_COMBAT.equals(PikmiMafia.getBotMode()) && msg.reply_markup != null && gameActive()) {
            tryChemist(account, mo, bot);
        }
    }

    private String name(int account) {
        try {
            TLRPC.User u = UserConfig.getInstance(account).getCurrentUser();
            if (u != null) return UserObject.getFirstName(u);
        } catch (Throwable ignore) {}
        return "acc" + (account + 1);
    }

    private void parseRole(int account, String text) {
        if (TextUtils.isEmpty(text)) return;
        String myRole = null;
        ArrayList<String[]> allies = new ArrayList<>();
        String roleTrig = PikmiMafia.getRoleTrigger();
        String allyTrig = PikmiMafia.normText(PikmiMafia.getAllyTrigger());
        boolean allyMode = false, needNext = false;
        for (String ln : text.split("\n")) {
            String n = PikmiMafia.normText(ln);
            if (needNext && myRole == null) {
                if (ln.trim().isEmpty()) continue;
                needNext = false;
                String r = ln.trim().replaceAll("^[\\s\\p{P}]+|[\\s\\p{P}!！]+$", "");
                if (!r.isEmpty() && r.length() <= 40) {
                    myRole = r;
                    allyMode = false;
                    continue;
                }
            }
            String rl = extractRole(roleTrig, ln, n);
            if (myRole == null && rl != null) {
                myRole = rl;
                allyMode = false;
                continue;
            }
            if (myRole == null && headerOnly(roleTrig, n)) {
                needNext = true;
                continue;
            }
            if (n.contains(allyTrig)) {
                allyMode = true;
                continue;
            }
            if (allyMode) {
                Matcher m = ALLY.matcher(ln.trim());
                if (m.find()) allies.add(new String[]{m.group(1).trim(), m.group(2).trim()});
            }
        }
        if (myRole != null) {
            accRoles.put(account, myRole);
            setRole(name(account), myRole, true);
        }
        for (String[] a : allies) setRole(a[0], a[1], false);
        notifyUi();
    }

    private String extractRole(String roleTrig, String ln, String n) {
        for (String part : roleTrig.split("\\|")) {
            String t = PikmiMafia.normText(part);
            if (t.isEmpty()) continue;
            int i = n.indexOf(t);
            if (i >= 0) {
                String after = ln.substring(Math.min(ln.length(), i + part.length())).trim();
                after = after.replaceAll("^[-–—:\\s]+", "").trim();
                after = after.replaceAll("[\\s\\p{P}!！]+$", "").trim();
                if (!after.isEmpty() && after.length() <= 40) return after;
            }
        }
        return null;
    }

    private boolean headerOnly(String roleTrig, String n) {
        for (String part : roleTrig.split("\\|")) {
            String t = PikmiMafia.normText(part);
            if (!t.isEmpty() && (n.equals(t) || n.endsWith(t))) return true;
        }
        return false;
    }

    private void setRole(String name, String role, boolean own) {
        if (TextUtils.isEmpty(name) || TextUtils.isEmpty(role)) return;
        String key = PikmiMafia.normText(name);
        synchronized (rolesLock) {
            for (RoleEntry e : roles) {
                if (PikmiMafia.normText(e.name).equals(key)) {
                    if (own) e.own = true;
                    e.role = role;
                    return;
                }
            }
            RoleEntry e = new RoleEntry();
            e.name = name;
            e.role = role;
            e.own = own;
            roles.add(e);
        }
    }

    private void markDead(String name) {
        String key = PikmiMafia.normText(name);
        synchronized (rolesLock) {
            for (RoleEntry e : roles)
                if (PikmiMafia.normText(e.name).equals(key)) {
                    e.dead = true;
                    break;
                }
        }
        notifyUi();
    }

    private void markHang(String text) {
        String trig = PikmiMafia.normText(PikmiMafia.getHangTrigger());
        for (String ln : text.split("\n")) {
            String n = PikmiMafia.normText(ln);
            int idx = n.indexOf(trig);
            if (idx < 0) continue;
            String before = n.substring(0, idx);
            synchronized (rolesLock) {
                for (RoleEntry e : roles) {
                    String k = PikmiMafia.normText(e.name);
                    if (k.equals(before) || (k.length() >= 3 && before.contains(k))) e.dead = true;
                }
            }
            for (int a : PikmiMafia.participatingAccounts(UserConfig.selectedAccount)) {
                String nm = PikmiMafia.normText(name(a));
                if (nm.equals(before) || (nm.length() >= 3 && before.contains(nm))) stat(a).dead = true;
            }
        }
        notifyUi();
    }

    // ── регистрация / голос / кнопки ───────────────────────────────────────

    private void doRegisterAll(MessageObject mo) {
        String payload = extractParam(mo);
        String botUser = extractBot(mo);
        if (TextUtils.isEmpty(botUser)) botUser = PikmiMafia.getBotUsername();
        final String bot = botUser, param = payload;
        // Участники от текущего selected + все activated в twins; fallback — все activated
        ArrayList<Integer> accs = PikmiMafia.participatingAccounts(UserConfig.selectedAccount);
        if (accs.isEmpty()) {
            for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {
                try {
                    if (UserConfig.getInstance(a).isClientActivated()) accs.add(a);
                } catch (Throwable ignore) {}
            }
        }
        log("📝 Регистрация x" + accs.size()
                + (param != null ? " param=" + param : " (no start-param)")
                + " bot=@" + bot);
        // 1) deep-link /start param для каждого акка
        for (int account : accs) {
            final int acc = account;
            Utilities.globalQueue.postRunnable(() -> {
                try { registerOne(acc, bot, param, mo); } catch (Throwable e) { FileLog.e(e); }
            });
        }
        // 2) если на сообщении есть callback-кнопки регистрации — жмём с каждого акка
        if (mo != null && mo.messageOwner != null && hasInline(mo.messageOwner)) {
            main.postDelayed(() -> pressRegCallbacks(mo, accs), 700);
        }
    }

    /** Жмёт callback-кнопки «рег/играть/join/+» на сообщении набора. */
    private void pressRegCallbacks(MessageObject mo, ArrayList<Integer> accs) {
        if (mo == null || mo.messageOwner == null) return;
        final long did = MessageObject.getDialogId(mo.messageOwner);
        final int mid = mo.messageOwner.id;
        final String[] keys = new String[]{
                "регист", "рег на", "в игр", "играть", "присоед", "join", "play", "вход", "+"
        };
        for (int account : accs) {
            final int acc = account;
            forEachButton(mo.messageOwner, b -> {
                byte[] data = btnData(b);
                if (data == null) return;
                String bt = PikmiMafia.normText(btnText(b));
                if (bt.length() == 0) return;
                boolean match = false;
                for (String k : keys) {
                    if (bt.contains(PikmiMafia.normText(k)) || bt.equals("+")) { match = true; break; }
                }
                // url-кнопки уже обработаны через start=; здесь только callback
                if (!match) return;
                try {
                    pressCb(acc, did, mid, data);
                    log("📝 cb-рег acc" + (acc + 1) + " → " + btnText(b));
                } catch (Throwable e) { FileLog.e(e); }
            });
        }
    }

    private String extractParam(MessageObject mo) {
        if (mo == null || mo.messageOwner == null) return null;
        final String[] out = {null};
        forEachButton(mo.messageOwner, b -> {
            if (out[0] != null) return;
            String url = btnUrl(b);
            if (url == null) return;
            Matcher m = START_EQ.matcher(url);
            if (m.find()) { out[0] = m.group(1); return; }
            int i = url.indexOf("start=");
            if (i >= 0) {
                String p2 = url.substring(i + 6);
                int amp = p2.indexOf('&');
                out[0] = amp > 0 ? p2.substring(0, amp) : p2;
            }
        });
        return out[0];
    }

    private String extractBot(MessageObject mo) {
        if (mo == null || mo.messageOwner == null) return null;
        final String[] out = {null};
        forEachButton(mo.messageOwner, b -> {
            if (out[0] != null) return;
            String url = btnUrl(b);
            if (url == null) return;
            if (url.contains("t.me/") || url.contains("telegram.me/")) {
                String path = url.replaceAll("https?://(t\\.me|telegram\\.me)/", "");
                int q = path.indexOf('?');
                if (q > 0) path = path.substring(0, q);
                path = path.replace("@", "").trim();
                if (!path.isEmpty() && !path.startsWith("c/") && !path.contains("/")) out[0] = path;
            }
        });
        return out[0];
    }


    private void registerOne(int account, String botUsername, String startParam, MessageObject regMsg) {
        MessagesController mc = MessagesController.getInstance(account);
        TLRPC.TL_contacts_resolveUsername req = new TLRPC.TL_contacts_resolveUsername();
        req.username = botUsername;
        ConnectionsManager.getInstance(account).sendRequest(req, (response, error) -> {
            if (!(response instanceof TLRPC.TL_contacts_resolvedPeer)) {
                log("⚠️ resolve @" + botUsername + " acc" + (account + 1));
                return;
            }
            TLRPC.TL_contacts_resolvedPeer res = (TLRPC.TL_contacts_resolvedPeer) response;
            mc.putUsers(res.users, false);
            mc.putChats(res.chats, false);
            if (res.peer == null || res.peer.user_id == 0) return;
            TLRPC.User bot = mc.getUser(res.peer.user_id);
            if (bot == null) return;
            try {
                if (!TextUtils.isEmpty(startParam)) {
                    TLRPC.TL_messages_startBot start = new TLRPC.TL_messages_startBot();
                    start.bot = mc.getInputUser(bot);
                    start.peer = mc.getInputPeer(bot.id);
                    start.start_param = startParam;
                    start.random_id = Utilities.random.nextLong();
                    ConnectionsManager.getInstance(account).sendRequest(start, (r2, e2) -> {
                        if (e2 != null) {
                            log("⚠️ startBot acc" + (account + 1) + ": " + e2.text);
                            // fallback — обычный /start param текстом
                            try {
                                SendMessagesHelper.SendMessageParams p = SendMessagesHelper.SendMessageParams.of(
                                        "/start " + startParam, bot.id);
                                p.notify = false;
                                SendMessagesHelper.getInstance(account).sendMessage(p);
                            } catch (Throwable ignore) {}
                        } else {
                            log("✅ reg acc" + (account + 1) + " param=" + startParam);
                        }
                        if (PikmiMafia.isTournament()) {
                            main.postDelayed(() -> {
                                try { pressColor(account, regMsg, PikmiMafia.getColor()); } catch (Throwable ignore) {}
                            }, 500);
                        }
                    });
                } else {
                    SendMessagesHelper.SendMessageParams p = SendMessagesHelper.SendMessageParams.of("/start", bot.id);
                    p.notify = false;
                    SendMessagesHelper.getInstance(account).sendMessage(p);
                    log("✅ /start acc" + (account + 1) + " (no param)");
                    if (PikmiMafia.isTournament()) {
                        main.postDelayed(() -> {
                            try { pressColor(account, regMsg, PikmiMafia.getColor()); } catch (Throwable ignore) {}
                        }, 500);
                    }
                }
            } catch (Throwable e) { FileLog.e(e); }
        });
    }

    private boolean pressColor(int account, MessageObject mo, String color) {
        if (mo == null || mo.messageOwner == null || !hasInline(mo.messageOwner)) return false;
        String want = PikmiMafia.normText(color);
        final boolean[] ok = {false};
        forEachButton(mo.messageOwner, b -> {
            if (ok[0]) return;
            byte[] data = btnData(b);
            if (data == null) return;
            String bt = PikmiMafia.normText(btnText(b));
            boolean match = bt.contains(want)
                    || ("blue".equals(color) && (bt.contains("син") || bt.contains("blue")))
                    || ("red".equals(color) && (bt.contains("крас") || bt.contains("red")))
                    || ("orange".equals(color) && (bt.contains("оранж") || bt.contains("orange")));
            if (match) {
                pressCb(account, MessageObject.getDialogId(mo.messageOwner), mo.messageOwner.id, data);
                ok[0] = true;
            }
        });
        return ok[0];
    }


    private void scheduleVote(int msgDate) {
        cancelVote();
        long delay;
        if ("instant".equals(PikmiMafia.getVoteMode())) {
            delay = 400;
        } else {
            int before = PikmiMafia.getVoteBefore();
            int total = PikmiMafia.getVoteTime();
            long elapsed = Math.max(0, (int) (System.currentTimeMillis() / 1000) - msgDate);
            delay = Math.max(400, (total - before - elapsed) * 1000L);
        }
        log("🗳 Голос через " + (delay / 1000) + "с → " + PikmiMafia.getVoteTarget());
        voteRun = this::doVoteAll;
        main.postDelayed(voteRun, delay);
    }

    private void cancelVote() {
        if (voteRun != null) {
            main.removeCallbacks(voteRun);
            voteRun = null;
        }
    }

    private void doVoteAll() {
        String nick = PikmiMafia.getVoteTarget();
        if (TextUtils.isEmpty(nick)) return;
        String bot = PikmiMafia.getBotUsername();
        for (int account : PikmiMafia.participatingAccounts(UserConfig.selectedAccount)) {
            AccStat st = stat(account);
            if (st.dead || st.blocked) {
                log("⏭ acc" + (account + 1) + " " + (st.dead ? "мёртв" : st.why));
                continue;
            }
            final int acc = account;
            Utilities.globalQueue.postRunnable(() -> voteOne(acc, bot, nick));
        }
    }

    private void voteOne(int account, String botUsername, String nick) {
        MessagesController mc = MessagesController.getInstance(account);
        TLRPC.TL_contacts_resolveUsername req = new TLRPC.TL_contacts_resolveUsername();
        req.username = botUsername;
        ConnectionsManager.getInstance(account).sendRequest(req, (response, error) -> {
            if (!(response instanceof TLRPC.TL_contacts_resolvedPeer)) return;
            TLRPC.TL_contacts_resolvedPeer res = (TLRPC.TL_contacts_resolvedPeer) response;
            mc.putUsers(res.users, false);
            long botId = res.peer.user_id;
            TLRPC.TL_messages_getHistory hist = new TLRPC.TL_messages_getHistory();
            hist.peer = mc.getInputPeer(botId);
            hist.limit = 12;
            ConnectionsManager.getInstance(account).sendRequest(hist, (r2, e2) -> {
                if (!(r2 instanceof TLRPC.messages_Messages)) return;
                String want = PikmiMafia.normText(nick);
                for (TLRPC.Message m : ((TLRPC.messages_Messages) r2).messages) {
                    if (!hasInline(m)) continue;
                    final boolean[] found = {false};
                    forEachButton(m, b -> {
                        if (found[0]) return;
                        byte[] data = btnData(b);
                        if (data == null) return;
                        String bt = PikmiMafia.normText(btnText(b));
                        if (bt.contains(want) || want.contains(bt)) {
                            pressCb(account, botId, m.id, data);
                            log("✅ голос acc" + (account + 1) + " → " + btnText(b));
                            found[0] = true;
                        }
                    });
                    if (found[0]) return;
                }
                log("⚠️ нет кнопки «" + nick + "» acc" + (account + 1));
            });
        });
    }


    private void tryKill(int account, MessageObject mo, TLRPC.User bot) {
        AccStat st = stat(account);
        if (st.dead || st.killed) return;
        String role = accRoles.get(account);
        if (role == null) role = "";
        String nr = PikmiMafia.normText(role);
        if (!nr.contains("комиссар") && !nr.contains("коммисар") && !nr.contains("сержант")) return;
        String kill = PikmiMafia.normText(PikmiMafia.getKillButton());
        if (mo == null || mo.messageOwner == null || !hasInline(mo.messageOwner)) return;
        forEachButton(mo.messageOwner, b -> {
            if (st.killed) return;
            byte[] data = btnData(b);
            if (data == null) return;
            if (PikmiMafia.normText(btnText(b)).contains(kill)) {
                st.killed = true;
                if (nr.contains("сержант")) {
                    accRoles.put(account, "Комиссар");
                    setRole(name(account), "Комиссар", true);
                }
                pressCb(account, bot.id, mo.messageOwner.id, data);
                log("🔫 Убить acc" + (account + 1));
                notifyUi();
            }
        });
    }


    private void tryPress(int account, MessageObject mo, TLRPC.User bot, String buttonName) {
        String want = PikmiMafia.normText(buttonName);
        if (want.isEmpty() || mo == null || mo.messageOwner == null) return;
        if (!once("p:" + account + ":" + mo.getId() + ":" + want)) return;
        if (!hasInline(mo.messageOwner)) return;
        forEachButton(mo.messageOwner, b -> {
            byte[] data = btnData(b);
            if (data == null) return;
            if (PikmiMafia.normText(btnText(b)).contains(want)) {
                pressCb(account, bot.id, mo.messageOwner.id, data);
                log("⚖️ " + buttonName + " acc" + (account + 1));
            }
        });
    }


    private void tryChemist(int account, MessageObject mo, TLRPC.User bot) {
        if (bot == null || mo == null || mo.messageOwner == null) return;
        if (!once("chem:" + account + ":" + mo.getId())) return;
        String role = accRoles.get(account);
        if (role == null || !PikmiMafia.normText(role).contains("химик")) return;
        if (!hasInline(mo.messageOwner)) return;
        forEachButton(mo.messageOwner, b -> {
            byte[] data = btnData(b);
            if (data == null) return;
            String bt = PikmiMafia.normText(btnText(b));
            if (bt.matches("\\d+") || bt.contains("зелье") || bt.contains("зелие")) {
                pressCb(account, bot.id, mo.messageOwner.id, data);
                log("🧪 химик acc" + (account + 1) + " → " + btnText(b));
            }
        });
    }


    private void pressLynch(MessageObject mo, boolean like) {
        if (mo == null || mo.messageOwner == null || !hasInline(mo.messageOwner)) return;
        try {
            final byte[][] data = {null};
            final ArrayList<byte[]> all = new ArrayList<>();
            String want = like ? "👍" : "👎";
            forEachButton(mo.messageOwner, b -> {
                byte[] d = btnData(b);
                if (d == null) return;
                all.add(d);
                String tx = btnText(b);
                if (tx != null && tx.contains(want)) data[0] = d;
            });
            if (data[0] == null && !all.isEmpty()) data[0] = like ? all.get(0) : all.get(all.size() - 1);
            if (data[0] == null) return;
            long did = MessageObject.getDialogId(mo.messageOwner);
            int mid = mo.messageOwner.id;
            for (int account : PikmiMafia.participatingAccounts(UserConfig.selectedAccount)) {
                pressCb(account, did, mid, data[0]);
            }
            log(like ? "👍 линч" : "👎 линч");
        } catch (Throwable e) { FileLog.e(e); }
    }


    private static boolean hasInline(TLRPC.Message msg) {
        return msg != null && msg.reply_markup instanceof TLRPC.TL_replyInlineMarkup;
    }

    private static TLRPC.TL_replyInlineMarkup markup(TLRPC.Message msg) {
        return (TLRPC.TL_replyInlineMarkup) msg.reply_markup;
    }

    private static String btnText(TL_keyboard.KeyboardButtonProto b) {
        try {
            if (b == null) return "";
            String s = b.getText();
            return s == null ? "" : s;
        } catch (Throwable e) { return ""; }
    }

    private static byte[] btnData(TL_keyboard.KeyboardButtonProto b) {
        try {
            if (b == null) return null;
            // KeyboardButtonProto.getData() сам проверяет TL_inlineButtonTypeCallback
            byte[] d = b.getData();
            return d;
        } catch (Throwable e) { return null; }
    }

    private static String btnUrl(TL_keyboard.KeyboardButtonProto b) {
        try {
            if (b == null) return null;
            TL_keyboard.ButtonTypeProto t = b.getType();
            if (t instanceof TL_keyboard.TL_inlineButtonTypeUrl) {
                return ((TL_keyboard.TL_inlineButtonTypeUrl) t).url;
            }
            if (t instanceof TL_keyboard.TL_inlineButtonTypeUrlAuth) {
                return ((TL_keyboard.TL_inlineButtonTypeUrlAuth) t).url;
            }
            if (t instanceof TL_keyboard.TL_inlineButtonTypeWebView) {
                return ((TL_keyboard.TL_inlineButtonTypeWebView) t).url;
            }
            // fallback через deprecated getUrl()
            return b.getUrl();
        } catch (Throwable e) { return null; }
    }

    private interface BtnVisitor { void visit(TL_keyboard.KeyboardButtonProto b); }

    private static void forEachButton(TLRPC.Message msg, BtnVisitor v) {
        if (!hasInline(msg)) return;
        try {
            TLRPC.TL_replyInlineMarkup mk = markup(msg);
            for (int i = 0; i < mk.rows.size(); i++) {
                TL_keyboard.KeyboardInlineButtonRow row = mk.rows.get(i);
                if (row == null || row.buttons == null) continue;
                for (int j = 0; j < row.buttons.size(); j++) {
                    TL_keyboard.KeyboardInlineButton b = row.buttons.get(j);
                    if (b != null) v.visit(b);
                }
            }
        } catch (Throwable e) { FileLog.e(e); }
    }

    private void pressCb(int account, long dialogId, int msgId, byte[] data) {
        if (data == null) return;
        try {
            TLRPC.TL_messages_getBotCallbackAnswer req = new TLRPC.TL_messages_getBotCallbackAnswer();
            req.peer = MessagesController.getInstance(account).getInputPeer(dialogId);
            req.msg_id = msgId;
            req.data = data;
            ConnectionsManager.getInstance(account).sendRequest(req, (r, e) -> {});
        } catch (Throwable e) { FileLog.e(e); }
    }

    private void startNightTimer() {
        cancelNight();
        int night = PikmiMafia.getNightSec(), warn = PikmiMafia.getWarnSec();
        if (warn > 0 && warn < night) {
            nightWarn = () -> log("⚠️ До дня ~" + warn + "с");
            main.postDelayed(nightWarn, (night - warn) * 1000L);
        }
        nightEnd = () -> log("⏰ Ночь по таймеру");
        main.postDelayed(nightEnd, night * 1000L);
    }

    private void cancelNight() {
        if (nightWarn != null) {
            main.removeCallbacks(nightWarn);
            nightWarn = null;
        }
        if (nightEnd != null) {
            main.removeCallbacks(nightEnd);
            nightEnd = null;
        }
    }

    private boolean once(String key) {
        Long p = done.putIfAbsent(key, System.currentTimeMillis());
        if (done.size() > 400) {
            long now = System.currentTimeMillis();
            done.entrySet().removeIf(e -> now - e.getValue() > 6 * 3600_000L);
        }
        return p == null;
    }

    /** Только в FileLog — в чат ничего не шлём. */
    private void log(String text) {
        FileLog.d("PikmiMafia: " + text);
    }
}
