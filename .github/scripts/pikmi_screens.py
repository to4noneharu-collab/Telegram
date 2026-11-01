#!/usr/bin/env python3
"""Разрешает скриншоты и запись экрана везде, где Telegram их запрещает,
и не отправляет собеседнику служебное сообщение "сделан скриншот" в секретных чатах.

Telegram блокирует скриншоты флагом окна FLAG_SECURE (секретные чаты, чаты с запретом сохранения,
одноразовые медиа, экран с паролем). Скрипт заменяет этот флаг на 0 во всех Java-файлах, поэтому
окно перестаёт быть защищённым, и отключает защищённые поверхности SurfaceView.setSecure(...).
Идемпотентен.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

SRC = Path("TMessagesProj/src/main/java")
if not SRC.exists():
    print("ОШИБКА: не найдена папка " + str(SRC))
    sys.exit(1)

FLAG_RX = re.compile(r"\b(?:android\.view\.)?(?:WindowManager\.)?LayoutParams\.FLAG_SECURE\b")
BARE_RX = re.compile(r"(?<![\w.])FLAG_SECURE\b")
SECURE_RX = re.compile(r"\.setSecure\(\s*(?!false\b)[^)]*\)")
MARK = "/*PG_SCREENS*/"

files = 0
flags = 0
secure = 0
bare = []
for p in sorted(SRC.rglob("*.java")):
    t = p.read_text(encoding="utf-8", errors="replace")
    if "FLAG_SECURE" not in t and ".setSecure(" not in t:
        continue
    n = t
    n, c1 = FLAG_RX.subn("0" + MARK, n)
    n, c2 = SECURE_RX.subn(".setSecure(false)", n)
    if BARE_RX.search(n):
        bare.append(str(p))
    if n != t:
        p.write_text(n, encoding="utf-8")
        files += 1
        flags += c1
        secure += c2
print("Скриншоты: изменено файлов %d, замен FLAG_SECURE: %d, setSecure: %d" % (files, flags, secure))
if bare:
    print("Внимание: остались голые упоминания FLAG_SECURE (статический импорт?):")
    for b in bare:
        print("  " + b)
if files == 0:
    print("Ничего не найдено (возможно, уже применено)")


# ---------- не сообщать собеседнику о скриншоте в секретном чате ----------
if "silentshot" in os.environ.get("PG_SKIP", ""):
    print("Служебное сообщение о скриншоте: оставлено (PG_SKIP)")
    sys.exit(0)
SC = SRC / "org/telegram/messenger/SecretChatHelper.java"
if not SC.exists():
    print("ОШИБКА: не найден SecretChatHelper.java")
    sys.exit(1)
sc = SC.read_text(encoding="utf-8")
if "PG_SILENT_SHOT" in sc:
    print("Служебное сообщение о скриншоте: уже отключено")
    sys.exit(0)
rx = re.compile(r"(public void sendScreenshotMessage\([^)]*\)\s*\{)")
n = len(rx.findall(sc))
if n == 0:
    print("ОШИБКА: не найден метод sendScreenshotMessage")
    print("--- подсказка для разработчика ---")
    print(subprocess.run("grep -rn -E 'sendScreenshotMessage|ScreenshotMessages' TMessagesProj/src/main/java | head -20", shell=True, capture_output=True, text=True).stdout)
    sys.exit(1)
sc = rx.sub(lambda m: m.group(1) + "\n        if (true) { return; } // PG_SILENT_SHOT", sc)
SC.write_text(sc, encoding="utf-8")
print("Служебное сообщение о скриншоте: отключено (методов: %d)" % n)
print(subprocess.run("grep -rn -E 'sendScreenshotMessage' TMessagesProj/src/main/java | head -10", shell=True, capture_output=True, text=True).stdout)
