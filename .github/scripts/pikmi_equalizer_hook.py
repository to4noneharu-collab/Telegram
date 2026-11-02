#!/usr/bin/env python3
"""Подключает эквалайзер к музыкальному плееру: после создания audioPlayer в MediaController
вызывает PikmiEqualizer.attachToPlayer(...). Только для музыки (голосовые не затрагиваются).
Запускать после pikmi_equalizer.py. Идемпотентен.
"""
import re
import sys
from pathlib import Path

MC = Path("TMessagesProj/src/main/java/org/telegram/messenger/MediaController.java")


def die(msg, hint=None):
    print("ОШИБКА: " + msg)
    if hint:
        print("--- подсказка для разработчика ---")
        print(hint)
    sys.exit(1)


if not MC.exists():
    die("не найден MediaController.java")
# в файле есть байты вне UTF-8, поэтому читаем и пишем без потерь
t = MC.read_text(encoding="utf-8", errors="surrogateescape")
if "PikmiEqualizer" in t:
    print("уже применено")
    sys.exit(0)
rx = re.compile(r"(audioPlayer = new VideoPlayer\(\);\s*int tag = \+\+playerNum;)")
n = len(rx.findall(t))
if n != 1:
    die("MediaController: не нашёл создание audioPlayer ровно один раз (найдено %d)" % n,
        __import__("subprocess").run("grep -a -n 'audioPlayer = new VideoPlayer' %s" % MC, shell=True, capture_output=True, text=True).stdout)
t = rx.sub(lambda m: m.group(1) + "\n                org.telegram.messenger.PikmiEqualizer.attachToPlayer(audioPlayer, messageObject); // PG_EQ", t, count=1)
MC.write_text(t, encoding="utf-8", errors="surrogateescape")
print("Готово: эквалайзер подключён к музыкальному плееру")
