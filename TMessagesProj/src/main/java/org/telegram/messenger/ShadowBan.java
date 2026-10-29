package org.telegram.messenger;

import android.content.Context;
import android.content.SharedPreferences;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.Set;

/**
 * Локальный "теневой бан": сообщения выбранных пользователей скрываются
 * только на этом устройстве. Сервер Telegram и сам пользователь об этом не знают.
 */
public class ShadowBan {

    private static final String PREFS = "shadow_ban";
    private static final String KEY_IDS = "ids";

    private static volatile Set<Long> cache;

    private static SharedPreferences prefs() {
        return ApplicationLoader.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    private static Set<Long> load() {
        Set<Long> local = cache;
        if (local == null) {
            synchronized (ShadowBan.class) {
                local = cache;
                if (local == null) {
                    local = new HashSet<>();
                    Set<String> raw = prefs().getStringSet(KEY_IDS, null);
                    if (raw != null) {
                        for (String s : raw) {
                            try {
                                local.add(Long.parseLong(s));
                            } catch (NumberFormatException ignore) {
                            }
                        }
                    }
                    cache = local;
                }
            }
        }
        return local;
    }

    private static void save() {
        Set<String> raw = new HashSet<>();
        for (Long id : load()) {
            raw.add(String.valueOf(id));
        }
        prefs().edit().putStringSet(KEY_IDS, raw).apply();
    }

    public static boolean isBanned(long userId) {
        if (userId <= 0) {
            return false;
        }
        synchronized (ShadowBan.class) {
            return load().contains(userId);
        }
    }

    public static boolean isBanned(MessageObject message) {
        if (message == null || message.messageOwner == null || message.isOutOwner()) {
            return false;
        }
        return isBanned(message.getFromChatId());
    }

    /** Возвращает true, если пользователь теперь в теневом бане. */
    public static boolean toggle(long userId) {
        if (userId <= 0) {
            return false;
        }
        boolean nowBanned;
        synchronized (ShadowBan.class) {
            Set<Long> ids = load();
            if (!ids.remove(userId)) {
                ids.add(userId);
                nowBanned = true;
            } else {
                nowBanned = false;
            }
            save();
        }
        return nowBanned;
    }

    /** Удаляет из списка сообщения забаненных пользователей (на месте). Возвращает число скрытых. */
    public static int filter(ArrayList<MessageObject> messages) {
        if (messages == null || messages.isEmpty()) {
            return 0;
        }
        synchronized (ShadowBan.class) {
            if (load().isEmpty()) {
                return 0;
            }
        }
        int removed = 0;
        for (int i = messages.size() - 1; i >= 0; i--) {
            if (isBanned(messages.get(i))) {
                messages.remove(i);
                removed++;
            }
        }
        return removed;
    }
}
