#!/usr/bin/env python3
"""Снимает запрет на пересылку/копирование/сохранение, который Telegram ставит на
сообщение (флаг noforwards — то, что сервер присылает в message.noforwards для чатов
и сообщений с включённым 'Запретить сохранение контента').

Сбрасывает флаг сразу при создании MessageObject, поэтому все проверки в интерфейсе
(кнопки «Переслать», «Копировать», контекстное меню) видят сообщение как обычное —
автор пересылки не виден, текст и медиа копируются как из любого другого чата.

Это первая часть: закрывает запрет уровня сообщения. Запрет уровня целого канала
(когда он полностью закрыт на пересылку) добавляется отдельным скриптом позже.
Запускать после shadowban_extra.py (использует тот же, уже проверенный якорь). Идемпотентен.
"""
import re
import sys
from pathlib import Path

MO = Path("TMessagesProj/src/main/java/org/telegram/messenger/MessageObject.java")


def die(msg, hint=None):
    print("ОШИБКА: " + msg)
    if hint:
        print("--- подсказка для разработчика ---")
        print(hint)
    sys.exit(1)


if not MO.exists():
    die("не найден MessageObject.java")
mo = MO.read_text(encoding="utf-8")
if "PG_NOFORWARDS" in mo:
    print("уже применено")
    sys.exit(0)

rx = re.compile(r"(wasUnread = !messageOwner\.out && messageOwner\.unread;)")
n = len(rx.findall(mo))
if n == 0:
    die("MessageObject: не нашёл якорь конструктора (wasUnread = ...)",
        __import__("subprocess").run("grep -n 'wasUnread = ' %s" % MO, shell=True, capture_output=True, text=True).stdout)
mo = rx.sub(
    lambda m: m.group(1) + "\n        if (messageOwner != null) { messageOwner.noforwards = false; } // PG_NOFORWARDS",
    mo,
    count=1,
)
MO.write_text(mo, encoding="utf-8")
print("Готово: запрет пересылки/копирования уровня сообщения снят")
