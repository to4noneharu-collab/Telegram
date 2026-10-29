#!/usr/bin/env python3
"""Добавляет к теневому бану меню со списком забаненных и кнопкой "снять".

Запускается из корня репозитория ПОСЛЕ применения shadowban.patch.
Идемпотентен: повторный запуск ничего не меняет.
При несовпадении ожидаемого кода завершается с ошибкой сразу, до долгой сборки.
"""
import re
import sys
from pathlib import Path

SB = Path("TMessagesProj/src/main/java/org/telegram/messenger/ShadowBan.java")
CA = Path("TMessagesProj/src/main/java/org/telegram/ui/ChatActivity.java")


def die(msg):
    print("ОШИБКА: " + msg)
    sys.exit(1)


if not SB.exists() or not CA.exists():
    die("не найден ShadowBan.java или ChatActivity.java: сначала примени shadowban.patch")

# ---------- ShadowBan.java ----------
sb = SB.read_text(encoding="utf-8")
if "showList" not in sb:
    extra = '''
    /** Сколько пользователей в теневом бане. */
    public static int count() {
        synchronized (ShadowBan.class) {
            return load().size();
        }
    }

    /** Копия списка id забаненных пользователей. */
    public static ArrayList<Long> getAll() {
        synchronized (ShadowBan.class) {
            return new ArrayList<>(load());
        }
    }

    /** Диалог со списком забаненных: нажатие на пользователя снимает бан. */
    public static void showList(final org.telegram.ui.ActionBar.BaseFragment fragment) {
        if (fragment == null) {
            return;
        }
        final android.app.Activity activity = fragment.getParentActivity();
        if (activity == null) {
            return;
        }
        final ArrayList<Long> ids = getAll();
        if (ids.isEmpty()) {
            android.widget.Toast.makeText(activity, "Список теневого бана пуст", android.widget.Toast.LENGTH_SHORT).show();
            return;
        }
        final CharSequence[] names = new CharSequence[ids.size()];
        for (int i = 0; i < ids.size(); i++) {
            long id = ids.get(i);
            String name = null;
            try {
                org.telegram.tgnet.TLRPC.User user = fragment.getMessagesController().getUser(id);
                if (user != null) {
                    name = UserObject.getUserName(user);
                }
            } catch (Throwable ignore) {
            }
            if (name == null || name.length() == 0) {
                name = "Пользователь";
            }
            names[i] = name + " (ID " + id + ")";
        }
        new android.app.AlertDialog.Builder(activity)
                .setTitle("Теневой бан: нажми на пользователя, чтобы снять")
                .setItems(names, new android.content.DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(android.content.DialogInterface dialog, int which) {
                        long id = ids.get(which);
                        if (isBanned(id)) {
                            toggle(id);
                        }
                        android.widget.Toast.makeText(activity, "Бан снят: " + names[which] + ". Переоткрой чат, чтобы увидеть сообщения", android.widget.Toast.LENGTH_LONG).show();
                    }
                })
                .setNegativeButton("Закрыть", null)
                .show();
    }
'''
    i = sb.rstrip().rfind("}")
    if i < 0:
        die("ShadowBan.java: не нашёл закрывающую скобку класса")
    sb = sb[:i].rstrip("\n") + "\n" + extra + "}\n"
    SB.write_text(sb, encoding="utf-8")
    print("ShadowBan.java: добавлен список")
else:
    print("ShadowBan.java: уже обновлён")

# ---------- ChatActivity.java ----------
ca = CA.read_text(encoding="utf-8")
if "OPTION_SHADOW_BAN_LIST" in ca:
    print("ChatActivity.java: уже обновлён")
    sys.exit(0)

# 1) константа
pat1 = re.compile(r"(public final static int OPTION_SHADOW_BAN = 200;)")
if len(pat1.findall(ca)) != 1:
    die("ChatActivity: не найдена константа OPTION_SHADOW_BAN (патч применён не полностью?)")
ca = pat1.sub(r"\1\n    public final static int OPTION_SHADOW_BAN_LIST = 201;", ca, count=1)

# 2) пункт меню после блока "Теневой бан"
pat2 = re.compile(r"(options\.add\(OPTION_SHADOW_BAN\);\s*icons\.add\(R\.drawable\.msg_block\);\s*\})")
if len(pat2.findall(ca)) != 1:
    die("ChatActivity: не найден блок добавления пункта 'Теневой бан' в меню")
menu_item = '''
            if (selectedObject != null && org.telegram.messenger.ShadowBan.count() > 0) {
                items.add("Список теневого бана (" + org.telegram.messenger.ShadowBan.count() + ")");
                options.add(OPTION_SHADOW_BAN_LIST);
                icons.add(R.drawable.msg_block);
            }'''
ca = pat2.sub(lambda m: m.group(1) + menu_item, ca, count=1)

# 3) обработчик
pat3 = re.compile(r"(case OPTION_SHADOW_BAN:\s*\{)")
if len(pat3.findall(ca)) != 1:
    die("ChatActivity: не найден обработчик case OPTION_SHADOW_BAN")
handler = '''case OPTION_SHADOW_BAN_LIST: {
                org.telegram.messenger.ShadowBan.showList(this);
                break;
            }
            '''
ca = pat3.sub(lambda m: handler + m.group(1), ca, count=1)

CA.write_text(ca, encoding="utf-8")
print("ChatActivity.java: добавлен пункт 'Список теневого бана'")
