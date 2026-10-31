#!/usr/bin/env python3
"""Снимает ограничение на число аккаунтов (по умолчанию 3, с Premium 5).

1) Java: UserConfig.MAX_ACCOUNT_DEFAULT_COUNT и MAX_ACCOUNT_COUNT поднимаются до LIMIT.
2) Нативный код: ConnectionsManager::getInstance умеет только несколько экземпляров,
   поэтому переписывается на LIMIT отдельных экземпляров (по одному на аккаунт).
Идемпотентен. Если нужных мест нет, печатает подсказки и завершается с ошибкой.
"""
import re
import subprocess
import sys
from pathlib import Path

import os

# До 5 аккаунтов нативный код Telegram уже поддерживает (как у Premium). Больше 5 экспериментально.
try:
    LIMIT = int(os.environ.get("PG_ACCOUNT_LIMIT") or 5)
except ValueError:
    LIMIT = 5
LIMIT = max(5, min(32, LIMIT))
SKIP = os.environ.get("PG_SKIP", "")

UC = Path("TMessagesProj/src/main/java/org/telegram/messenger/UserConfig.java")
CM = Path("TMessagesProj/jni/tgnet/ConnectionsManager.cpp")


def die(msg, hint=None):
    print("ОШИБКА: " + msg)
    if hint:
        print("--- подсказка для разработчика ---")
        print(hint)
    sys.exit(1)


def grep(pattern, target, n=40):
    r = subprocess.run(["grep", "-rn", "-E", pattern, str(target)], capture_output=True, text=True)
    return "\n".join(r.stdout.splitlines()[:n])


# ---------- Java ----------
if not UC.exists():
    die("не найден UserConfig.java")
uc = UC.read_text(encoding="utf-8")
if "accjava" in SKIP:
    print("Java: пропущено (PG_SKIP)")
elif "PG_ACCOUNTS" in uc:
    print("Java: уже применено")
else:
    rx_def = re.compile(r"(MAX_ACCOUNT_DEFAULT_COUNT\s*=\s*)\d+;")
    rx_max = re.compile(r"(\bMAX_ACCOUNT_COUNT\s*=\s*)\d+;")
    if len(rx_def.findall(uc)) != 1 or len(rx_max.findall(uc)) != 1:
        die("UserConfig: не найдены константы MAX_ACCOUNT_DEFAULT_COUNT / MAX_ACCOUNT_COUNT",
            grep(r"MAX_ACCOUNT|getMaxAccountCount|hasPremiumOnAccounts", UC))
    uc = rx_def.sub(lambda m: m.group(1) + "%d; // PG_ACCOUNTS" % LIMIT, uc, count=1)
    uc = rx_max.sub(lambda m: m.group(1) + "%d; // PG_ACCOUNTS" % LIMIT, uc, count=1)
    UC.write_text(uc, encoding="utf-8")
    print("Java: лимит аккаунтов поднят до %d" % LIMIT)

print("--- где ещё упоминается лимит (для справки) ---")
print(grep(r"getMaxAccountCount|MAX_ACCOUNT_DEFAULT_COUNT|MAX_ACCOUNT_COUNT\s*\)|>= *3\b.*[Aa]ccount", "TMessagesProj/src/main/java", 30))

# ---------- native ----------
if "accnative" in SKIP:
    print("native: пропущено (PG_SKIP)")
    sys.exit(0)
if LIMIT <= 5:
    print("native: не нужно (лимит %d поддерживается штатно)" % LIMIT)
    sys.exit(0)
if not CM.exists():
    die("не найден ConnectionsManager.cpp")
cm = CM.read_text(encoding="utf-8")
if "PG_ACCOUNTS" in cm:
    print("native: уже применено")
    sys.exit(0)

rx = re.compile(r"(ConnectionsManager\s*&\s*ConnectionsManager::getInstance\(\s*((?:u?int32_t|int|unsigned int)\s+(\w+))\s*\)\s*\{)(.*?)\n\}", re.S)
m = rx.search(cm)
if not m or "static ConnectionsManager" not in m.group(4):
    die("native: не нашёл ConnectionsManager::getInstance в ожидаемом виде",
        grep(r"ConnectionsManager::getInstance|getInstance\(", CM, 20))
param = m.group(3)
cases = []
for i in range(LIMIT):
    cases.append("        case %d:\n            static ConnectionsManager instance%d(%d);\n            return instance%d;" % (i, i, i, i))
new_func = m.group(1) + """ // PG_ACCOUNTS
    switch (%s) {
%s
        default:
            static ConnectionsManager instanceDefault(%d);
            return instanceDefault;
    }
}""" % (param, "\n".join(cases), LIMIT - 1)
cm = cm[:m.start()] + new_func + cm[m.end():]
CM.write_text(cm, encoding="utf-8")
print("native: ConnectionsManager::getInstance теперь на %d экземпляров" % LIMIT)
