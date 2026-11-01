#!/usr/bin/env python3
"""Снимает запрет на пересылку/копирование уровня всего чата/канала (настройка
'Запретить сохранение контента' на весь чат, а не на отдельное сообщение).

Обе точки, откуда это проверяется во всём интерфейсе, переводятся в "всегда разрешено":
ChatActivity.isPeerNoForwards() и MessagesController.isPeerNoForwards(long). Вместе с
pikmi_noforwards.py (запрет уровня сообщения) это закрывает все места в коде, которые
читают оба флага. Запускать отдельно от pikmi_noforwards.py, порядок не важен. Идемпотентен.
"""
import re
import sys
from pathlib import Path

CA = Path("TMessagesProj/src/main/java/org/telegram/ui/ChatActivity.java")
MC = Path("TMessagesProj/src/main/java/org/telegram/messenger/MessagesController.java")


def die(msg, hint=None):
    print("ОШИБКА: " + msg)
    if hint:
        print("--- подсказка для разработчика ---")
        print(hint)
    sys.exit(1)


def patch(path, rx, what, grep_pattern):
    if not path.exists():
        die("не найден " + str(path))
    t = path.read_text(encoding="utf-8")
    n = len(rx.findall(t))
    if n == 0:
        print("пропуск (не найдено, возможно уже применено): " + what)
        return False
    if n != 1:
        die("%s: найдено %d совпадений вместо одного" % (what, n),
            __import__("subprocess").run("grep -n -E '%s' %s" % (grep_pattern, path), shell=True, capture_output=True, text=True).stdout)
    t = rx.sub(lambda m: m.group(1) + "\n        if (true) { return false; } // PG_NOFORWARDS_CHANNEL", t, count=1)
    path.write_text(t, encoding="utf-8")
    print("готово: " + what)
    return True


ca_marker = "PG_NOFORWARDS_CHANNEL" in (CA.read_text(encoding="utf-8") if CA.exists() else "")
mc_marker = "PG_NOFORWARDS_CHANNEL" in (MC.read_text(encoding="utf-8") if MC.exists() else "")
if ca_marker and mc_marker:
    print("уже применено")
    sys.exit(0)

if not ca_marker:
    patch(
        CA,
        re.compile(r"(public boolean isPeerNoForwards\(\) \{)"),
        "ChatActivity.isPeerNoForwards()",
        r"public boolean isPeerNoForwards\(",
    )
if not mc_marker:
    patch(
        MC,
        re.compile(r"(public boolean isPeerNoForwards\(long dialogId\) \{)"),
        "MessagesController.isPeerNoForwards(long)",
        r"public boolean isPeerNoForwards\(",
    )
print("Готово: запрет пересылки/копирования уровня чата/канала снят")
