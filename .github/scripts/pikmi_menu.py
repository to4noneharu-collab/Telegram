#!/usr/bin/env python3
"""Переносит пункты PikmiGram (шрифты, список теневого бана, проверка обновлений) в меню
по трём точкам сверху списка чатов (там же, где ночной режим, Избранное, Создать группу).

Запускать после pikmi_fonts.py, shadowban_list.py, pikmi_updater.py. Идемпотентен.
"""
import re
import sys
from pathlib import Path

DA = Path("TMessagesProj/src/main/java/org/telegram/ui/DialogsActivity.java")


def die(msg, hint=None):
    print("ОШИБКА: " + msg)
    if hint:
        print("--- подсказка для разработчика ---")
        print(hint)
    sys.exit(1)


if not DA.exists():
    die("не найден DialogsActivity.java")
da = DA.read_text(encoding="utf-8")
if "PG_CHATS_MENU" in da:
    print("уже применено")
    sys.exit(0)

anchor = re.compile(
    r"(io\.add\(R\.drawable\.outline_groups_24, getString\(R\.string\.NewGroup\), \(\) -> \{\s*"
    r"Bundle args = new Bundle\(\);\s*"
    r"presentFragment\(new GroupCreateActivity\(args\)\);\s*\}\);)"
)
n = len(anchor.findall(da))
if n != 1:
    die("DialogsActivity: не нашёл пункт меню 'Создать группу' в ожидаемом виде",
        __import__("subprocess").run("grep -n 'R.string.NewGroup' %s" % DA, shell=True, capture_output=True, text=True).stdout)

insert = '''
        io.addGap(); // PG_CHATS_MENU
        io.add(R.drawable.msg_edit, "PikmiGram: шрифты", () -> {
            org.telegram.messenger.PikmiFonts.showMenu(DialogsActivity.this);
        });
        io.add(R.drawable.msg_block, "Список теневого бана", () -> {
            org.telegram.messenger.ShadowBan.showList(DialogsActivity.this);
        });
        io.add(R.drawable.msg_edit, "PikmiGram: эквалайзер", () -> {
            org.telegram.messenger.PikmiEqualizer.showDialog(getParentActivity());
        });
        io.add(R.drawable.msg_edit, "PikmiGram: обновления", () -> {
            org.telegram.messenger.PikmiUpdater.check(getParentActivity(), true);
        });'''
da = anchor.sub(lambda m: m.group(1) + insert, da, count=1)
DA.write_text(da, encoding="utf-8")
print("Готово: пункты PikmiGram добавлены в меню чатов")
