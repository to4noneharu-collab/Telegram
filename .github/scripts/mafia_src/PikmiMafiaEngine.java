package org.telegram.messenger;

import android.os.Handler;
import android.os.Looper;
import android.text.TextUtils;
import org.telegram.tgnet.ConnectionsManager;
import org.telegram.tgnet.TLRPC;
import java.util.ArrayList;
import java.util.Locale;
import java.util.concurrent.ConcurrentHashMap;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class PikmiMafiaEngine {
    private static PikmiMafiaEngine Instance;
    private static final Handler main = new Handler(Looper.getMainLooper());
    private static final Pattern START_EQ = Pattern.compile("start(?:group)?=([A-Za-z0-9_\\-]+)");
    private static final Pattern ALLY = Pattern.compile("^\\s*(?:[•·\\-\\*]\\s*)?(.+?)\\s*[-–—]\\s*(.+?)\\s*$");

    private final ConcurrentHashMap<Integer, Boolean> observers = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<String, Long> done = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<Integer, String> accRoles = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<Integer, AccStat> status = new ConcurrentHashMap<>();
    private final ArrayList<RoleEntry> roles = new ArrayList<>();
    private final Object rolesLock = new Object();
    private volatile boolean gameOn;
    private volatile long gameSince, actAt;
    private Runnable nightWarn, nightEnd, voteRun;

    static class AccStat { boolean dead, blocked, killed; String why = ""; }
    static class RoleEntry { String name, role; boolean own, dead; }

    public static synchronized PikmiMafiaEngine getInstance() {
        if (Instance == null) Instance = new PikmiMafiaEngine();
        return Instance;
    }

    public void ensureObservers() {
        for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {
            final int account = a;
            if (observers.putIfAbsent(account, Boolean.TRUE) != null) continue;
            try {
                NotificationCenter.getInstance(account).addObserver((id, account2, args) -> {
                    if (id != NotificationCenter.didReceiveNewMessages || !PikmiMafia.isEnabled()) return;
                    try {
                        if (args == null || args.length < 2) return;
                        if (args.length > 2 && args[2] instanceof Boolean && (Boolean) args[2]) return;
                        ArrayList<MessageObject> messages = (ArrayList<MessageObject>) args[1];
                        if (messages == null) return;
                        for (MessageObject mo : messages) {
                            if (mo != null && mo.messageOwner != null && !mo.isOut()) onMessage(account, mo);
                        }
                    } catch (Throwable e) { FileLog.e(e); }
                }, NotificationCenter.didReceiveNewMessages);
            } catch (Throwable e) { FileLog.e(e); observers.remove(account); }
        }
    }

    private AccStat stat(int a) {
        AccStat st = status.get(a);
        if (st == null) status.put(a, st = new AccStat());
        return st;
    }

    private void startGame() {
        gameOn = true; gameSince = System.currentTimeMillis(); actAt = 0;
        status.clear(); accRoles.clear();
        synchronized (rolesLock) { roles.clear(); }
        cancelNight(); cancelVote();
        log("🎭 Новая игра");
    }

    private void endGame(String footer) {
        gameOn = false; cancelNight(); cancelVote();
        if (PikmiMafia.isRolesEnabled()) publishRoles(footer);
        log("🏁 " + (footer != null ? footer : "Игра окончена"));
    }

    private boolean gameActive() { return gameOn && System.currentTimeMillis() - gameSince < 4L * 3600_000; }

    private void onMessage(int account, MessageObject mo) {
        TLRPC.Message msg = mo.messageOwner;
        if (msg == null) return;
        String text = msg.message != null ? msg.message : "";
        String norm = PikmiMafia.normText(text);
        long dialogId = MessageObject.getDialogId(msg);
        if (!PikmiMafia.participatingAccounts(UserConfig.selectedAccount).contains(account)) return;

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
        if (regChat != 0 && dialogId == regChat) handleChat(account, mo, text, norm, msg);
        if (fromBot && dialogId > 0) handleDm(account, mo, text, norm, msg, sender);
    }

    private void handleChat(int account, MessageObject mo, String text, String norm, TLRPC.Message msg) {
        if (PikmiMafia.hit(PikmiMafia.getRegTrigger(), norm) && once("reg:" + msg.id)) {
            startGame();
            main.postDelayed(() -> doRegisterAll(mo), 400);
        }
        if (PikmiMafia.hit(PikmiMafia.getNightTrigger(), norm) && once("night:" + msg.id)) {
            for (AccStat st : status.values()) { st.blocked = false; if (!st.dead) st.why = ""; st.killed = false; }
            actAt = 0; startNightTimer(); log("🌙 Ночь " + PikmiMafia.getNightSec() + "с");
        }
        if (PikmiMafia.hit(PikmiMafia.getDayTrigger(), norm) && once("day:" + msg.id)) {
            cancelNight(); actAt = 0;
            for (AccStat st : status.values()) st.killed = false;
            log("☀️ День");
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
        if (PikmiMafia.hit(PikmiMafia.getDeadTrigger(), norm)) { st.dead = true; markDead(name(account)); }
        if (PikmiMafia.hit(PikmiMafia.getLoverTrigger(), norm)) { st.blocked = true; st.why = "любовница"; }
        if (PikmiMafia.hit(PikmiMafia.getSwindlerTrigger(), norm)) { st.blocked = true; st.why = "аферист"; }

        if (PikmiMafia.isVoteEnabled() && !TextUtils.isEmpty(PikmiMafia.getVoteTarget())
                && PikmiMafia.hit(PikmiMafia.getVoteTrigger(), norm) && once("vdm:" + account + ":" + msg.id)) {
            scheduleVote(msg.date);
        }
        if (PikmiMafia.isAutoRead() && gameActive() && bot != null) {
            main.postDelayed(() -> {
                try { MessagesController.getInstance(account).markDialogAsRead(bot.id, msg.id, msg.id, msg.date, false, 0, 0, true, 0); }
                catch (Throwable e) { FileLog.e(e); }
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
                if (!r.isEmpty() && r.length() <= 40) { myRole = r; allyMode = false; continue; }
            }
            String rl = extractRole(roleTrig, ln, n);
            if (myRole == null && rl != null) { myRole = rl; allyMode = false; continue; }
            if (myRole == null && headerOnly(roleTrig, n)) { needNext = true; continue; }
            if (!TextUtils.isEmpty(allyTrig) && n.contains(allyTrig)) { allyMode = true; continue; }
            if (allyMode) {
                if (ln.trim().isEmpty()) continue;
                Matcher m = ALLY.matcher(ln.trim());
                if (m.find()) allies.add(new String[]{m.group(1).trim(), m.group(2).trim()});
                else allyMode = false;
            }
        }
        if (myRole == null && allies.isEmpty()) return;
        if (myRole != null) { accRoles.put(account, myRole); setRole(name(account), myRole, true); }
        for (String[] a : allies) setRole(a[0], a[1], false);
        if (PikmiMafia.isRolesEnabled()) main.postDelayed(() -> publishRoles(null), 1500);
    }

    private String extractRole(String trigger, String line, String normLine) {
        for (String part : trigger.split("\\|")) {
            part = part.trim();
            String lead = part.replaceAll("[-–—:\\s]+$", "").trim();
            String nLead = PikmiMafia.normText(lead);
            if (nLead.isEmpty()) continue;
            if (normLine.contains(nLead)) {
                for (int i = 0; i < line.length(); i++) {
                    char c = line.charAt(i);
                    if (c == '-' || c == '–' || c == '—' || c == ':') {
                        String r = line.substring(i + 1).trim().replaceAll("^[\\s\\p{P}]+|[\\s\\p{P}!！]+$", "");
                        if (!r.isEmpty()) return r;
                    }
                }
            }
        }
        return null;
    }

    private boolean headerOnly(String trigger, String normLine) {
        for (String part : trigger.split("\\|")) {
            String n = PikmiMafia.normText(part.replaceAll("[-–—:\\s]+$", ""));
            if (!n.isEmpty() && normLine.endsWith(n)) return true;
        }
        return false;
    }

    private void setRole(String name, String role, boolean own) {
        if (TextUtils.isEmpty(name) || TextUtils.isEmpty(role)) return;
        String key = PikmiMafia.normText(name);
        synchronized (rolesLock) {
            for (RoleEntry e : roles) {
                if (PikmiMafia.normText(e.name).equals(key)) {
                    if (own) e.own = true; e.role = role; return;
                }
            }
            RoleEntry e = new RoleEntry(); e.name = name; e.role = role; e.own = own; roles.add(e);
        }
    }

    private void markDead(String name) {
        String key = PikmiMafia.normText(name);
        synchronized (rolesLock) {
            for (RoleEntry e : roles) if (PikmiMafia.normText(e.name).equals(key)) { e.dead = true; break; }
        }
        if (PikmiMafia.isRolesEnabled()) main.postDelayed(() -> publishRoles(null), 800);
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
        if (PikmiMafia.isRolesEnabled()) main.postDelayed(() -> publishRoles(null), 800);
    }

    private void publishRoles(String footer) {
        StringBuilder sb = new StringBuilder("📋 Роли в игре");
        if (footer != null) sb.append(" · ").append(footer);
        sb.append("\n");
        synchronized (rolesLock) {
            if (roles.isEmpty()) sb.append("пока пусто");
            else for (RoleEntry e : roles) {
                if (e.dead) sb.append("☠️ ");
                else if (e.own) sb.append("🤖 ");
                else sb.append("🤝 ");
                sb.append(e.name).append(" — ").append(e.role).append("\n");
            }
        }
        logRaw(sb.toString().trim());
    }

    private void doRegisterAll(MessageObject mo) {
        String payload = extractParam(mo);
        String botUser = extractBot(mo);
        if (TextUtils.isEmpty(botUser)) botUser = PikmiMafia.getBotUsername();
        final String bot = botUser, param = payload;
        ArrayList<Integer> accs = PikmiMafia.participatingAccounts(UserConfig.selectedAccount);
        log("📝 Регистрация x" + accs.size() + (param != null ? " param=" + param : ""));
        for (int account : accs) {
            final int acc = account;
            Utilities.globalQueue.postRunnable(() -> { try { registerOne(acc, bot, param, mo); } catch (Throwable e) { FileLog.e(e); } });
        }
    }

    private String extractParam(MessageObject mo) {
        try {
            if (!(mo.messageOwner.reply_markup instanceof TLRPC.TL_replyInlineMarkup)) return null;
            TLRPC.TL_replyInlineMarkup mk = (TLRPC.TL_replyInlineMarkup) mo.messageOwner.reply_markup;
            for (TLRPC.TL_keyboardButtonRow row : mk.rows)
                for (TLRPC.KeyboardButton b : row.buttons)
                    if (b instanceof TLRPC.TL_keyboardButtonUrl) {
                        String url = ((TLRPC.TL_keyboardButtonUrl) b).url;
                        if (url == null) continue;
                        Matcher m = START_EQ.matcher(url);
                        if (m.find()) return m.group(1);
                        int i = url.indexOf("start=");
                        if (i >= 0) {
                            String p = url.substring(i + 6);
                            int amp = p.indexOf('&');
                            return amp > 0 ? p.substring(0, amp) : p;
                        }
                    }
        } catch (Throwable e) { FileLog.e(e); }
        return null;
    }

    private String extractBot(MessageObject mo) {
        try {
            if (!(mo.messageOwner.reply_markup instanceof TLRPC.TL_replyInlineMarkup)) return null;
            TLRPC.TL_replyInlineMarkup mk = (TLRPC.TL_replyInlineMarkup) mo.messageOwner.reply_markup;
            for (TLRPC.TL_keyboardButtonRow row : mk.rows)
                for (TLRPC.KeyboardButton b : row.buttons)
                    if (b instanceof TLRPC.TL_keyboardButtonUrl) {
                        String url = ((TLRPC.TL_keyboardButtonUrl) b).url;
                        if (url != null && (url.contains("t.me/") || url.contains("telegram.me/"))) {
                            String path = url.replaceAll("https?://(t\\.me|telegram\\.me)/", "");
                            int q = path.indexOf('?');
                            if (q > 0) path = path.substring(0, q);
                            path = path.replace("@", "").trim();
                            if (!path.isEmpty() && !path.startsWith("c/") && !path.contains("/")) return path;
                        }
                    }
        } catch (Throwable ignore) {}
        return null;
    }

    private void registerOne(int account, String botUsername, String startParam, MessageObject regMsg) {
        MessagesController mc = MessagesController.getInstance(account);
        TLRPC.TL_contacts_resolveUsername req = new TLRPC.TL_contacts_resolveUsername();
        req.username = botUsername;
        ConnectionsManager.getInstance(account).sendRequest(req, (response, error) -> {
            if (!(response instanceof TLRPC.TL_contacts_resolvedPeer)) {
                log("⚠️ resolve @" + botUsername + " acc" + (account + 1)); return;
            }
            TLRPC.TL_contacts_resolvedPeer res = (TLRPC.TL_contacts_resolvedPeer) response;
            mc.putUsers(res.users, false); mc.putChats(res.chats, false);
            if (res.peer == null || res.peer.user_id == 0) return;
            TLRPC.User bot = mc.getUser(res.peer.user_id);
            if (bot == null) return;
            try {
                if (!TextUtils.isEmpty(startParam)) {
                    TLRPC.TL_messages_startBot start = new TLRPC.TL_messages_startBot();
                    start.bot = mc.getInputUser(bot);
                    start.peer = mc.getInputPeer(bot.id);
                    start.start_param = startParam;
                    start.random_id = SendMessagesHelper.getNextRandomId();
                    ConnectionsManager.getInstance(account).sendRequest(start, (r2, e2) ->
                            log(e2 != null ? "⚠️ startBot acc" + (account + 1) : "✅ reg acc" + (account + 1)));
                } else {
                    if (PikmiMafia.isTournament() && pressColor(account, regMsg, PikmiMafia.getColor())) {
                        log("✅ tour acc" + (account + 1)); return;
                    }
                    SendMessagesHelper.getInstance(account).sendMessage(SendMessagesHelper.SendMessageParams.of("/start", bot.id));
                    log("✅ /start acc" + (account + 1));
                }
            } catch (Throwable e) { FileLog.e(e); }
        });
    }

    private boolean pressColor(int account, MessageObject mo, String color) {
        try {
            if (!(mo.messageOwner.reply_markup instanceof TLRPC.TL_replyInlineMarkup)) return false;
            String want = color.toLowerCase(Locale.US);
            TLRPC.TL_replyInlineMarkup mk = (TLRPC.TL_replyInlineMarkup) mo.messageOwner.reply_markup;
            for (TLRPC.TL_keyboardButtonRow row : mk.rows)
                for (TLRPC.KeyboardButton b : row.buttons) {
                    String t = b.text != null ? b.text.toLowerCase(Locale.US) : "";
                    boolean match = t.contains(want)
                            || (want.equals("blue") && (t.contains("син") || t.contains("🔵")))
                            || (want.equals("red") && (t.contains("крас") || t.contains("🔴")))
                            || (want.equals("orange") && (t.contains("оранж") || t.contains("🟠")))
                            || (want.equals("black") && (t.contains("чёрн") || t.contains("черн") || t.contains("⚫")))
                            || (want.equals("yellow") && (t.contains("жёлт") || t.contains("желт") || t.contains("🟡")));
                    if (match && b instanceof TLRPC.TL_keyboardButtonCallback) {
                        pressCb(account, MessageObject.getDialogId(mo.messageOwner), mo.messageOwner.id, ((TLRPC.TL_keyboardButtonCallback) b).data);
                        return true;
                    }
                }
        } catch (Throwable e) { FileLog.e(e); }
        return false;
    }

    private void scheduleVote(int msgDate) {
        cancelVote();
        long delay;
        if ("instant".equals(PikmiMafia.getVoteMode())) delay = 500;
        else {
            long endAt = msgDate * 1000L + PikmiMafia.getVoteTime() * 1000L;
            delay = Math.max(300, endAt - System.currentTimeMillis() - PikmiMafia.getVoteBefore() * 1000L);
        }
        voteRun = this::doVoteAll;
        main.postDelayed(voteRun, delay);
        log("🗳 Голос через " + (delay / 1000) + "с → " + PikmiMafia.getVoteTarget());
    }

    private void cancelVote() { if (voteRun != null) { main.removeCallbacks(voteRun); voteRun = null; } }

    private void doVoteAll() {
        String nick = PikmiMafia.getVoteTarget();
        if (TextUtils.isEmpty(nick)) return;
        String bot = PikmiMafia.getBotUsername();
        for (int account : PikmiMafia.participatingAccounts(UserConfig.selectedAccount)) {
            AccStat st = stat(account);
            if (st.dead || st.blocked) { log("⏭ acc" + (account + 1) + " " + (st.dead ? "мёртв" : st.why)); continue; }
            final int acc = account;
            Utilities.globalQueue.postRunnable(() -> voteOne(acc, bot, nick));
        }
        PikmiMafia.setVoteTarget("");
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
            hist.peer = mc.getInputPeer(botId); hist.limit = 12;
            ConnectionsManager.getInstance(account).sendRequest(hist, (r2, e2) -> {
                if (!(r2 instanceof TLRPC.messages_Messages)) return;
                String want = PikmiMafia.normText(nick);
                for (TLRPC.Message m : ((TLRPC.messages_Messages) r2).messages) {
                    if (!(m.reply_markup instanceof TLRPC.TL_replyInlineMarkup)) continue;
                    for (TLRPC.TL_keyboardButtonRow row : ((TLRPC.TL_replyInlineMarkup) m.reply_markup).rows)
                        for (TLRPC.KeyboardButton b : row.buttons)
                            if (b instanceof TLRPC.TL_keyboardButtonCallback) {
                                String bt = PikmiMafia.normText(b.text);
                                if (bt.contains(want) || want.contains(bt)) {
                                    pressCb(account, botId, m.id, ((TLRPC.TL_keyboardButtonCallback) b).data);
                                    log("✅ голос acc" + (account + 1) + " → " + b.text);
                                    return;
                                }
                            }
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
        try {
            if (!(mo.messageOwner.reply_markup instanceof TLRPC.TL_replyInlineMarkup)) return;
            for (TLRPC.TL_keyboardButtonRow row : ((TLRPC.TL_replyInlineMarkup) mo.messageOwner.reply_markup).rows)
                for (TLRPC.KeyboardButton b : row.buttons)
                    if (b instanceof TLRPC.TL_keyboardButtonCallback && PikmiMafia.normText(b.text).contains(kill)) {
                        st.killed = true;
                        if (nr.contains("сержант")) { accRoles.put(account, "Комиссар"); setRole(name(account), "Комиссар", true); }
                        pressCb(account, bot.id, mo.messageOwner.id, ((TLRPC.TL_keyboardButtonCallback) b).data);
                        log("🔫 Убить acc" + (account + 1));
                        return;
                    }
        } catch (Throwable e) { FileLog.e(e); }
    }

    private void tryPress(int account, MessageObject mo, TLRPC.User bot, String buttonName) {
        String want = PikmiMafia.normText(buttonName);
        if (want.isEmpty() || !once("p:" + account + ":" + mo.getId() + ":" + want)) return;
        try {
            if (!(mo.messageOwner.reply_markup instanceof TLRPC.TL_replyInlineMarkup)) return;
            for (TLRPC.TL_keyboardButtonRow row : ((TLRPC.TL_replyInlineMarkup) mo.messageOwner.reply_markup).rows)
                for (TLRPC.KeyboardButton b : row.buttons)
                    if (b instanceof TLRPC.TL_keyboardButtonCallback && PikmiMafia.normText(b.text).contains(want)) {
                        pressCb(account, bot.id, mo.messageOwner.id, ((TLRPC.TL_keyboardButtonCallback) b).data);
                        log("⚖️ " + buttonName + " acc" + (account + 1));
                        return;
                    }
        } catch (Throwable e) { FileLog.e(e); }
    }

    private void pressLynch(MessageObject mo, boolean like) {
        try {
            if (!(mo.messageOwner.reply_markup instanceof TLRPC.TL_replyInlineMarkup)) return;
            byte[] data = null;
            ArrayList<byte[]> all = new ArrayList<>();
            String want = like ? "👍" : "👎";
            for (TLRPC.TL_keyboardButtonRow row : ((TLRPC.TL_replyInlineMarkup) mo.messageOwner.reply_markup).rows)
                for (TLRPC.KeyboardButton b : row.buttons)
                    if (b instanceof TLRPC.TL_keyboardButtonCallback) {
                        byte[] d = ((TLRPC.TL_keyboardButtonCallback) b).data;
                        all.add(d);
                        if (b.text != null && b.text.contains(want)) data = d;
                    }
            if (data == null && !all.isEmpty()) data = all.get(like ? 0 : Math.min(1, all.size() - 1));
            if (data == null) return;
            long did = MessageObject.getDialogId(mo.messageOwner);
            int mid = mo.messageOwner.id;
            for (int account : PikmiMafia.participatingAccounts(UserConfig.selectedAccount)) {
                AccStat st = stat(account);
                if (st.dead || st.blocked) continue;
                pressCb(account, did, mid, data);
            }
            log(like ? "👍 линч" : "👎 линч");
        } catch (Throwable e) { FileLog.e(e); }
    }

    private void pressCb(int account, long dialogId, int msgId, byte[] data) {
        if (data == null) return;
        try {
            TLRPC.TL_messages_getBotCallbackAnswer req = new TLRPC.TL_messages_getBotCallbackAnswer();
            req.peer = MessagesController.getInstance(account).getInputPeer(dialogId);
            req.msg_id = msgId; req.data = data;
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
        if (nightWarn != null) { main.removeCallbacks(nightWarn); nightWarn = null; }
        if (nightEnd != null) { main.removeCallbacks(nightEnd); nightEnd = null; }
    }

    private boolean once(String key) {
        Long p = done.putIfAbsent(key, System.currentTimeMillis());
        if (done.size() > 400) {
            long now = System.currentTimeMillis();
            done.entrySet().removeIf(e -> now - e.getValue() > 6 * 3600_000L);
        }
        return p == null;
    }

    private void log(String text) { FileLog.d("PikmiMafia: " + text); logRaw(text); }

    private void logRaw(String text) {
        try {
            int account = UserConfig.selectedAccount;
            long did = PikmiMafia.getLogChat();
            if (did == 0) did = UserConfig.getInstance(account).getClientUserId();
            SendMessagesHelper.SendMessageParams params = SendMessagesHelper.SendMessageParams.of(text, did);
            params.notify = false;
            SendMessagesHelper.getInstance(account).sendMessage(params);
        } catch (Throwable e) { FileLog.e(e); }
    }
}
