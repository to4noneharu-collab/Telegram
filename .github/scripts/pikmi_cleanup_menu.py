#!/usr/bin/env python3
"""Убирает из меню долгого нажатия на сообщение пункты 'Список теневого бана',
'PikmiGram: шрифты' и 'PikmiGram: обновления' — они остаются только в меню сверху
списка чатов (три точки). Пункт 'Теневой бан' (бан/разбан автора сообщения) остаётся.

Запускать ПОСЛЕ shadowban_list.py, pikmi_fonts.py и pikmi_updater.py. Идемпотентен:
если блок уже убран (или не создавался), просто пропускает его.
"""
import sys
from pathlib import Path

CA = Path("TMessagesProj/src/main/java/org/telegram/ui/ChatActivity.java")

BLOCKS = [
    ("Список теневого бана", '''
            if (selectedObject != null && org.telegram.messenger.ShadowBan.count() > 0) {
                items.add("Список теневого бана (" + org.telegram.messenger.ShadowBan.count() + ")");
                options.add(OPTION_SHADOW_BAN_LIST);
                icons.add(R.drawable.msg_block);
            }''', '''case OPTION_SHADOW_BAN_LIST: {
                org.telegram.messenger.ShadowBan.showList(this);
                break;
            }
            '''),
    ("PikmiGram: шрифты", '''
            if (selectedObject != null) {
                items.add("PikmiGram: шрифты");
                options.add(OPTION_PIKMI_FONTS);
                icons.add(R.drawable.msg_edit);
            }''', '''case OPTION_PIKMI_FONTS: {
                org.telegram.messenger.PikmiFonts.showMenu(this);
                break;
            }
            '''),
    ("PikmiGram: обновления", '''
            if (selectedObject != null) {
                items.add("PikmiGram: обновления");
                options.add(OPTION_PIKMI_UPDATE);
                icons.add(R.drawable.msg_edit);
            }''', '''case OPTION_PIKMI_UPDATE: {
                org.telegram.messenger.PikmiUpdater.check(getParentActivity(), true);
                break;
            }
            '''),
]


def die(msg):
    print("ОШИБКА: " + msg)
    sys.exit(1)


if not CA.exists():
    die("не найден ChatActivity.java")
ca = CA.read_text(encoding="utf-8")
changed = False
for label, item_block, case_block in BLOCKS:
    present = item_block in ca
    if not present:
        print("пропуск (не найдено или уже убрано): " + label)
        continue
    if ca.count(item_block) != 1:
        die("пункт меню '%s' встречается не один раз, останавливаюсь на всякий случай" % label)
    ca = ca.replace(item_block, "", 1)
    if case_block in ca:
        if ca.count(case_block) != 1:
            die("обработчик '%s' встречается не один раз, останавливаюсь на всякий случай" % label)
        ca = ca.replace(case_block, "", 1)
    changed = True
    print("убрано из меню сообщения: " + label)
if changed:
    CA.write_text(ca, encoding="utf-8")
    print("Готово")
else:
    print("Готово (нечего было убирать)")
