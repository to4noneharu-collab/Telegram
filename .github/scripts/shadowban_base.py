#!/usr/bin/env python3
"""Restores the fork's original ShadowBan integration after syncing upstream.

This is the small, committed ChatActivity.java patch introduced by the
"Add local shadow ban" commit. Other ChatActivity customizations are applied
by their dedicated build scripts. Every insertion is guarded and idempotent.
"""
import sys
from pathlib import Path

CA = Path("TMessagesProj/src/main/java/org/telegram/ui/ChatActivity.java")


def die(message):
    print("ОШИБКА shadowban_base: " + message)
    sys.exit(1)


if not CA.exists():
    die("не найден ChatActivity.java")

ca = CA.read_text(encoding="utf-8")
original = ca

# 1. The option ID used by the message context menu.
constant = "    public final static int OPTION_SHADOW_BAN = 200;"
if constant not in ca:
    anchor = "    public final static int OPTION_COPY = 3;"
    if ca.count(anchor) != 1:
        die("не найден единственный anchor OPTION_COPY; upstream изменил область констант")
    ca = ca.replace(anchor, anchor + "\n" + constant, 1)
elif ca.count(constant) != 1:
    die("OPTION_SHADOW_BAN объявлен более одного раза")

# 2. Filter messages loaded from history.
loaded_filter = "        org.telegram.messenger.ShadowBan.filter(messArr);"
if loaded_filter not in ca:
    anchor = "        ArrayList<MessageObject> messArr = (ArrayList<MessageObject>) args[2];"
    if ca.count(anchor) != 1:
        die("не найден единственный anchor загрузки истории messArr")
    ca = ca.replace(anchor, anchor + "\n" + loaded_filter, 1)
elif ca.count(loaded_filter) != 1:
    die("фильтр загруженной истории встречается более одного раза")

# 3. Filter live messages and stop when all incoming messages are hidden.
live_filter = "        org.telegram.messenger.ShadowBan.filter(arr);"
empty_guard = "        if (arr.isEmpty()) {\n            return;\n        }"
if live_filter not in ca and empty_guard not in ca:
    anchor = "    private void processNewMessages(ArrayList<MessageObject> arr, final boolean animatedFromBottom) {\n"
    if ca.count(anchor) != 1:
        die("не найден единственный метод processNewMessages с ожидаемой сигнатурой")
    ca = ca.replace(anchor, anchor + live_filter + "\n" + empty_guard + "\n", 1)
elif live_filter not in ca or empty_guard not in ca or ca.count(live_filter) != 1 or ca.count(empty_guard) != 1:
    die("частичная или дублированная интеграция фильтра processNewMessages")

# 4. Add the ShadowBan action to the long-press message menu.
menu_block = """            if (!suggestEdit && selectedObject != null && !selectedObject.isOutOwner() && selectedObject.getFromChatId() > 0
                    && selectedObject.getFromChatId() != getUserConfig().getClientUserId()) {
                boolean banned = org.telegram.messenger.ShadowBan.isBanned(selectedObject.getFromChatId());
                items.add(banned ? "Снять теневой бан" : "Теневой бан");
                options.add(OPTION_SHADOW_BAN);
                icons.add(R.drawable.msg_block);
            }"""
if "options.add(OPTION_SHADOW_BAN);" not in ca:
    anchor = "            if (options.isEmpty() && optionsView == null) {"
    if ca.count(anchor) != 1:
        die("не найден единственный anchor вставки пункта теневого бана в меню")
    ca = ca.replace(anchor, menu_block + "\n\n" + anchor, 1)
elif ca.count("options.add(OPTION_SHADOW_BAN);") != 1:
    die("пункт теневого бана встречается более одного раза")

# 5. Handle the selected ShadowBan action.
handler = """            case OPTION_SHADOW_BAN: {
                long bannedId = selectedObject.getFromChatId();
                boolean nowBanned = org.telegram.messenger.ShadowBan.toggle(bannedId);
                if (nowBanned) {
                    for (int i = messages.size() - 1; i >= 0; i--) {
                        MessageObject m = messages.get(i);
                        if (m != null && !m.isOutOwner() && m.getFromChatId() == bannedId) {
                            removeMessageObject(m);
                        }
                    }
                }
                android.widget.Toast.makeText(getParentActivity(), nowBanned ? "Пользователь скрыт локально" : "Теневой бан снят (новые сообщения будут видны)", android.widget.Toast.LENGTH_SHORT).show();
                break;
            }
"""
if "case OPTION_SHADOW_BAN:" not in ca:
    method = "    private void processSelectedOption(int option) {"
    if ca.count(method) != 1:
        die("не найден единственный метод processSelectedOption")
    start = ca.index(method)
    switch = "        switch (option) {\n"
    pos = ca.find(switch, start)
    if pos < 0 or ca.find(switch, pos + len(switch)) >= 0:
        die("не найден однозначный switch(option) внутри processSelectedOption")
    ca = ca[:pos + len(switch)] + handler + ca[pos + len(switch):]
elif ca.count("case OPTION_SHADOW_BAN:") != 1:
    die("обработчик OPTION_SHADOW_BAN встречается более одного раза")

if ca != original:
    CA.write_text(ca, encoding="utf-8")
    print("ChatActivity.java: восстановлены 5 частей базовой интеграции ShadowBan")
else:
    print("ChatActivity.java: базовая интеграция ShadowBan уже присутствует")
