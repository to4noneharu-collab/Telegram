package org.telegram.messenger;

import android.content.Context;
import android.content.SharedPreferences;
import android.text.TextUtils;
import java.util.ArrayList;
import java.util.Locale;

public class PikmiMafia {
    private static final String PREFS = "pikmigram_mafia";
    public static final String MODE_SOLO = "solo", MODE_TWINS = "twins";
    public static final String BOT_BAKU = "baku", BOT_TRUE = "true", BOT_MAFIOSO = "mafioso", BOT_COMBAT = "combat";

    private static SharedPreferences p() {
        return ApplicationLoader.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }
    public static boolean isEnabled() { try { return p().getBoolean("enabled", false); } catch (Throwable t) { return false; } }
    public static void setEnabled(boolean v) { p().edit().putBoolean("enabled", v).apply(); }
    public static String getMode() { try { return MODE_TWINS.equals(p().getString("mode", MODE_SOLO)) ? MODE_TWINS : MODE_SOLO; } catch (Throwable t) { return MODE_SOLO; } }
    public static void setMode(String m) { p().edit().putString("mode", MODE_TWINS.equals(m) ? MODE_TWINS : MODE_SOLO).apply(); }
    public static boolean isMainInTwins() { try { return p().getBoolean("main_in_twins", true); } catch (Throwable t) { return true; } }
    public static void setMainInTwins(boolean v) { p().edit().putBoolean("main_in_twins", v).apply(); }
    public static String getBotMode() {
        try { String m = p().getString("bot_mode", BOT_BAKU);
            if (BOT_TRUE.equals(m) || BOT_MAFIOSO.equals(m) || BOT_COMBAT.equals(m)) return m; return BOT_BAKU;
        } catch (Throwable t) { return BOT_BAKU; }
    }
    public static void setBotMode(String m) {
        if (!BOT_TRUE.equals(m) && !BOT_MAFIOSO.equals(m) && !BOT_COMBAT.equals(m)) m = BOT_BAKU;
        p().edit().putString("bot_mode", m).apply();
        String u = getBotUsername();
        if (TextUtils.isEmpty(u) || isStockBot(u)) setBotUsername(defaultBot(m));
    }
    public static boolean isStockBot(String u) {
        String x = u.toLowerCase(Locale.US);
        return x.contains("mafiabaku") || x.contains("truemafia") || x.contains("mafiosos") || x.contains("combatmafia");
    }
    public static String defaultBot(String mode) {
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
    public static boolean isTrueFree() { try { return p().getBoolean("true_free", false); } catch (Throwable t) { return false; } }
    public static void setTrueFree(boolean v) { p().edit().putBoolean("true_free", v).apply(); if (BOT_TRUE.equals(getBotMode())) setBotUsername(defaultBot(BOT_TRUE)); }
    public static String getBotUsername() {
        try { String u = p().getString("bot", null); if (TextUtils.isEmpty(u)) return defaultBot(getBotMode()); return u.replace("@", "").trim(); }
        catch (Throwable t) { return defaultBot(getBotMode()); }
    }
    public static void setBotUsername(String u) { p().edit().putString("bot", u == null ? "" : u.replace("@", "").trim()).apply(); }
    public static String getBotAlt() {
        try { String a = p().getString("bot_alt", ""); if (TextUtils.isEmpty(a) && BOT_MAFIOSO.equals(getBotMode())) return "MafiososGame"; return a == null ? "" : a; }
        catch (Throwable t) { return ""; }
    }
    public static long getRegChat() { try { return p().getLong("reg_chat", 0); } catch (Throwable t) { return 0; } }
    public static void setRegChat(long id) { p().edit().putLong("reg_chat", id).apply(); }
    public static long getLogChat() { try { return p().getLong("log_chat", 0); } catch (Throwable t) { return 0; } }
    public static void setLogChat(long id) { p().edit().putLong("log_chat", id).apply(); }
    public static boolean isVoteEnabled() { try { return p().getBoolean("vote_enabled", true); } catch (Throwable t) { return true; } }
    public static void setVoteEnabled(boolean v) { p().edit().putBoolean("vote_enabled", v).apply(); }
    public static String getVoteTarget() { try { return p().getString("vote_target", ""); } catch (Throwable t) { return ""; } }
    public static void setVoteTarget(String t) { p().edit().putString("vote_target", t == null ? "" : t.trim()).apply(); }
    public static String getVoteMode() { try { return "instant".equals(p().getString("vote_mode", "timer")) ? "instant" : "timer"; } catch (Throwable t) { return "timer"; } }
    public static void setVoteMode(String m) { p().edit().putString("vote_mode", "instant".equals(m) ? "instant" : "timer").apply(); }
    public static int getVoteTime() { try { return p().getInt("vote_time", 45); } catch (Throwable t) { return 45; } }
    public static void setVoteTime(int s) { p().edit().putInt("vote_time", Math.max(1, Math.min(3600, s))).apply(); }
    public static int getVoteBefore() { try { return p().getInt("vote_before", 5); } catch (Throwable t) { return 5; } }
    public static void setVoteBefore(int s) { p().edit().putInt("vote_before", Math.max(0, Math.min(3600, s))).apply(); }
    public static int getNightSec() { try { return p().getInt("night", 60); } catch (Throwable t) { return 60; } }
    public static void setNightSec(int s) { p().edit().putInt("night", Math.max(1, Math.min(3600, s))).apply(); }
    public static int getWarnSec() { try { return p().getInt("warn", 10); } catch (Throwable t) { return 10; } }
    public static void setWarnSec(int s) { p().edit().putInt("warn", Math.max(0, Math.min(3600, s))).apply(); }
    public static boolean isAutoKill() { try { return p().getBoolean("auto_kill", true); } catch (Throwable t) { return true; } }
    public static void setAutoKill(boolean v) { p().edit().putBoolean("auto_kill", v).apply(); }
    public static boolean isAutoReg() { try { return p().getBoolean("auto_reg", true); } catch (Throwable t) { return true; } }
    public static void setAutoReg(boolean v) { p().edit().putBoolean("auto_reg", v).apply(); }

    public static boolean isAutoRead() { try { return p().getBoolean("auto_read", true); } catch (Throwable t) { return true; } }
    public static void setAutoRead(boolean v) { p().edit().putBoolean("auto_read", v).apply(); }
    public static boolean isRolesEnabled() { try { return p().getBoolean("roles_enabled", true); } catch (Throwable t) { return true; } }
    public static void setRolesEnabled(boolean v) { p().edit().putBoolean("roles_enabled", v).apply(); }
    public static boolean isTournament() { try { return p().getBoolean("tournament", false); } catch (Throwable t) { return false; } }
    public static void setTournament(boolean v) { p().edit().putBoolean("tournament", v).apply(); }
    public static String getColor() { try { String c = p().getString("color", "blue"); return c == null ? "blue" : c; } catch (Throwable t) { return "blue"; } }
    public static void setColor(String c) { p().edit().putString("color", c == null ? "blue" : c).apply(); }
    public static String getLike() { try { String l = p().getString("like", "off"); return l == null ? "off" : l; } catch (Throwable t) { return "off"; } }
    public static void setLike(String l) { p().edit().putString("like", l == null ? "off" : l).apply(); }
    public static boolean isAutoLawyer() { try { return p().getBoolean("auto_lawyer", false); } catch (Throwable t) { return false; } }
    public static void setAutoLawyer(boolean v) { p().edit().putBoolean("auto_lawyer", v).apply(); }
    public static String getLawyerRole() { try { String r = p().getString("lawyer_role", "Мирный житель"); return r == null ? "Мирный житель" : r; } catch (Throwable t) { return "Мирный житель"; } }
    public static void setLawyerRole(String r) { p().edit().putString("lawyer_role", r == null ? "Мирный житель" : r).apply(); }

    public static String getRegTrigger() {
        try { String t = p().getString("reg_trigger", null); if (!TextUtils.isEmpty(t)) return t;
            if (BOT_COMBAT.equals(getBotMode())) return "Регистрация началась|Набор на игру|регистрация";
            if (BOT_TRUE.equals(getBotMode())) return "Ведётся набор в игру|Набор в игру|Регистрация";
            if (BOT_MAFIOSO.equals(getBotMode())) return "Ведётся набор в игру|Набор в игру|Регистрация";
            return "Ведётся набор в игру|Набор в игру|Регистрация началась|регистрация";
        } catch (Throwable t) { return "Ведётся набор в игру|Набор в игру|регистрация"; }
    }
    public static String getVoteTrigger() {
        try { String t = p().getString("vote_trigger", null); if (!TextUtils.isEmpty(t)) return t;
            String m = getBotMode();
            if (BOT_MAFIOSO.equals(m)) return "Пришло время искать виноватых";
            if (BOT_COMBAT.equals(m)) return "Пришло время найти виноватых";
            if (BOT_TRUE.equals(m)) return "Пришло время искать виноватых|Кого ты хочешь повесить";
            return "Пришло время определить и наказать виновных";
        } catch (Throwable t) { return "Пришло время определить и наказать виновных"; }
    }
    public static String getNightTrigger() { try { String t = p().getString("night_trigger", "Наступает ночь"); return TextUtils.isEmpty(t) ? "Наступает ночь" : t; } catch (Throwable t) { return "Наступает ночь"; } }
    public static String getDayTrigger() {
        try { String t = p().getString("day_trigger", null); if (!TextUtils.isEmpty(t)) return t;
            return BOT_COMBAT.equals(getBotMode()) ? "Доброе утро" : "Солнце восходит|Солнце всходит";
        } catch (Throwable t) { return "Солнце восходит|Солнце всходит"; }
    }
    public static String getLynchTrigger() {
        try { String t = p().getString("lynch_trigger", null); if (!TextUtils.isEmpty(t)) return t;
            if (BOT_COMBAT.equals(getBotMode())) return "повесить хотите";
            return "Уверены что хотите линчевать|Вы точно хотите повесить|Вы точно хотите линчевать";
        } catch (Throwable t) { return "Уверены что хотите линчевать"; }
    }
    public static String getRoleTrigger() {
        try { String t = p().getString("role_trigger", null); if (!TextUtils.isEmpty(t)) return t;
            if (BOT_TRUE.equals(getBotMode())) return "Ты -";
            if (BOT_COMBAT.equals(getBotMode())) return "Твоя роль в игре|Твоя роль";
            if (BOT_MAFIOSO.equals(getBotMode())) return "Твоя роль|Ты -";
            return "Твоя роль";
        } catch (Throwable t) { return "Твоя роль"; }
    }
    public static String getAllyTrigger() { try { String t = p().getString("ally_trigger", "Запомни своих союзников"); return TextUtils.isEmpty(t) ? "Запомни своих союзников" : t; } catch (Throwable t) { return "Запомни своих союзников"; } }
    public static String getDeadTrigger() {
        try { String t = p().getString("dead_trigger", null); if (!TextUtils.isEmpty(t)) return t;
            return BOT_COMBAT.equals(getBotMode()) ? "Тебя убили" : "Вас убили";
        } catch (Throwable t) { return "Вас убили"; }
    }
    public static String getLoverTrigger() { try { String t = p().getString("lover_trigger", "Любовница"); return TextUtils.isEmpty(t) ? "Любовница" : t; } catch (Throwable t) { return "Любовница"; } }
    public static String getSwindlerTrigger() { try { String t = p().getString("swindler_trigger", "Аферист"); return TextUtils.isEmpty(t) ? "Аферист" : t; } catch (Throwable t) { return "Аферист"; } }
    public static String getHangTrigger() { try { String t = p().getString("hang_trigger", "линчевали"); return TextUtils.isEmpty(t) ? "линчевали" : t; } catch (Throwable t) { return "линчевали"; } }
    public static String getActionTrigger() { try { String t = p().getString("action_trigger", "Что будем делать"); return TextUtils.isEmpty(t) ? "Что будем делать" : t; } catch (Throwable t) { return "Что будем делать"; } }
    public static String getActTrigger() { try { String t = p().getString("act_trigger", "Пришло время действовать"); return TextUtils.isEmpty(t) ? "Пришло время действовать" : t; } catch (Throwable t) { return "Пришло время действовать"; } }
    public static String getKillButton() { try { String t = p().getString("kill_button", "Убить"); return TextUtils.isEmpty(t) ? "Убить" : t; } catch (Throwable t) { return "Убить"; } }
    public static String getEndTriggers() { try { String t = p().getString("end_triggers", "Игра окончена|Игра остановлена"); return TextUtils.isEmpty(t) ? "Игра окончена|Игра остановлена" : t; } catch (Throwable t) { return "Игра окончена|Игра остановлена"; } }

    public static ArrayList<Integer> participatingAccounts(int currentAccount) {
        ArrayList<Integer> out = new ArrayList<>();
        if (MODE_SOLO.equals(getMode())) {
            if (UserConfig.getInstance(currentAccount).isClientActivated()) out.add(currentAccount);
            return out;
        }
        int main = UserConfig.selectedAccount;
        for (int a = 0; a < UserConfig.MAX_ACCOUNT_COUNT; a++) {
            try {
                if (!UserConfig.getInstance(a).isClientActivated()) continue;
                if (!isMainInTwins() && a == main) continue;
                out.add(a);
            } catch (Throwable ignore) {}
        }
        if (isMainInTwins() && UserConfig.getInstance(main).isClientActivated() && !out.contains(main)) out.add(0, main);
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
                    if (u.username != null && u.username.length() > 0) name += " (@" + u.username + ")";
                }
            } catch (Throwable ignore) {}
            if (i > 0) sb.append("\n");
            sb.append("• ").append(name);
        }
        return sb.toString();
    }
    public static String normText(String s) {
        if (s == null) return "";
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < s.length(); ) {
            int cp = s.codePointAt(i);
            i += Character.charCount(cp);
            if (Character.getType(cp) == Character.NON_SPACING_MARK || Character.isISOControl(cp)) continue;
            cp = Character.toLowerCase(cp);
            if (Character.isLetter(cp) || Character.isDigit(cp)) b.appendCodePoint(cp);
        }
        return b.toString();
    }
    public static boolean hit(String trigger, String norm) {
        if (trigger == null || norm == null) return false;
        for (String part : trigger.split("\\|")) {
            String t = normText(part);
            if (t.length() > 0 && norm.contains(t)) return true;
        }
        return false;
    }
    public static boolean isBotUsername(String username) {
        if (username == null) return false;
        String u = username.replace("@", "").trim();
        if (u.equalsIgnoreCase(getBotUsername())) return true;
        String alt = getBotAlt();
        if (TextUtils.isEmpty(alt)) return false;
        for (String a : alt.split("[,|\\s]+")) {
            a = a.replace("@", "").trim();
            if (a.length() > 0 && a.equalsIgnoreCase(u)) return true;
        }
        return false;
    }
}
