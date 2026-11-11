#!/usr/bin/env python3
"""Снимает стандартное ограничение на число аккаунтов (3 без Premium).

По умолчанию (PG_ACCOUNT_LIMIT пусто) разрешает столько аккаунтов, сколько поддерживает сам код
(UserConfig.MAX_ACCOUNT_COUNT), и НЕ уменьшает и не увеличивает размеры массивов и число нативных
экземпляров. Если указано число больше возможностей кода, поднимает константу и переписывает
ConnectionsManager::getInstance (экспериментально).

Переменные: PG_ACCOUNT_LIMIT (число или пусто), PG_SKIP (accjava, accnative).
Идемпотентен. Печатает исходные значения в лог.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

UC = Path("TMessagesProj/src/main/java/org/telegram/messenger/UserConfig.java")
CM = Path("TMessagesProj/jni/tgnet/ConnectionsManager.cpp")
SKIP = os.environ.get("PG_SKIP", "")
RAW = (os.environ.get("PG_ACCOUNT_LIMIT") or "").strip()


def die(msg, hint=None):
    print("ОШИБКА: " + msg)
    if hint:
        print("--- подсказка для разработчика ---")
        print(hint)
    sys.exit(1)


def grep(pattern, target, n=40):
    r = subprocess.run(["grep", "-rn", "-E", pattern, str(target)], capture_output=True, text=True)
    return "\n".join(r.stdout.splitlines()[:n])


NATIVE_RX = re.compile(r"(ConnectionsManager\s*&\s*ConnectionsManager::getInstance\(\s*((?:u?int32_t|int|unsigned int)\s+(\w+))\s*\)\s*\{)(.*?)\n\}", re.S)

# ---------- справка ----------
print("=== ИСХОДНЫЕ ЗНАЧЕНИЯ ЛИМИТА АККАУНТОВ ===")
if not UC.exists():
    die("не найден UserConfig.java")
uc = UC.read_text(encoding="utf-8")
print(grep(r"MAX_ACCOUNT|hasPremiumOnAccounts", UC, 12))
m = re.search(r"public static int getMaxAccountCount\(\)\s*\{.*?\n    \}", uc, re.S)
print(m.group(0) if m else "getMaxAccountCount: не найден")
native_capacity = None
if CM.exists():
    cm = CM.read_text(encoding="utf-8")
    nm = NATIVE_RX.search(cm)
    print("--- native getInstance ---")
    print(nm.group(0) if nm else "getInstance: не найден")
    if nm:
        cases = [int(x) for x in re.findall(r"case\s+(\d+)\s*:", nm.group(4))]
        native_capacity = (max(cases) + 1) if cases else None
print("--- где в коде могут быть зашиты размеры по числу аккаунтов (Java) ---")
print(subprocess.run("grep -rnE 'new [A-Za-z<>]+\\[ *(4|5) *\\]|ACCOUNT.*(\\b4\\b|\\b5\\b)|(\\b4\\b|\\b5\\b).*(accounts|ACCOUNT)' --include=*.java TMessagesProj/src/main/java | grep -vE '^.*(//|\\*)' | head -40", shell=True, capture_output=True, text=True).stdout)
print("--- нативный код: массивы и индексы по instanceNum ---")
print(subprocess.run("grep -rnE 'instanceNum *\\]|\\[ *instanceNum|MAX_ACCOUNT|\\[(4|5)\\];|instances?\\[' TMessagesProj/jni --include=*.cpp --include=*.h | head -40", shell=True, capture_output=True, text=True).stdout)
print("=== КОНЕЦ СПРАВКИ ===")

m_def = re.search(r"MAX_ACCOUNT_DEFAULT_COUNT\s*=\s*(\d+);", uc)
m_max = re.search(r"\bMAX_ACCOUNT_COUNT\s*=\s*(\d+);", uc)
if not m_def or not m_max:
    die("UserConfig: не найдены константы MAX_ACCOUNT_DEFAULT_COUNT / MAX_ACCOUNT_COUNT",
        grep(r"MAX_ACCOUNT|getMaxAccountCount|hasPremiumOnAccounts", UC))
orig_def, orig_max = int(m_def.group(1)), int(m_max.group(1))

if RAW.isdigit():
    want = max(3, min(32, int(RAW)))
else:
    # По умолчанию поднимаем до 12 (с расширением native), чтобы >5 аккаунтов не роняло приложение
    base = max(orig_max, native_capacity or orig_max)
    want = max(base, 12)
new_max = max(orig_max, want)
new_def = min(max(orig_def, want), new_max)
print("Было: DEFAULT=%d, MAX=%d. Станет: DEFAULT=%d, MAX=%d (нативных экземпляров сейчас: %s)" % (
    orig_def, orig_max, new_def, new_max, native_capacity if native_capacity else "?"))

# ---------- Java ----------
if "accjava" in SKIP:
    print("Java: пропущено (PG_SKIP)")
elif "PG_ACCOUNTS" in uc:
    print("Java: уже применено")
else:
    uc = re.sub(r"(MAX_ACCOUNT_DEFAULT_COUNT\s*=\s*)\d+;", lambda x: x.group(1) + "%d; // PG_ACCOUNTS" % new_def, uc, count=1)
    if new_max != orig_max:
        uc = re.sub(r"(\bMAX_ACCOUNT_COUNT\s*=\s*)\d+;", lambda x: x.group(1) + "%d; // PG_ACCOUNTS" % new_max, uc, count=1)
    # getMaxAccountCount() возвращает зашитые числа (5 с Premium, 3 без), именно они и задают лимит
    rx_get = re.compile(r"(public static int getMaxAccountCount\(\)\s*\{)\s*return [^;]*;(\s*\})", re.S)
    if len(rx_get.findall(uc)) != 1:
        die("UserConfig: не нашёл getMaxAccountCount() в ожидаемом виде", grep(r"getMaxAccountCount", UC))
    uc = rx_get.sub(lambda x: x.group(1) + "\n        return MAX_ACCOUNT_COUNT; // PG_ACCOUNTS" + x.group(2), uc, count=1)
    UC.write_text(uc, encoding="utf-8")
    print("Java: готово (getMaxAccountCount теперь возвращает %d)" % new_max)

# ---------- native ----------
if "accnative" in SKIP:
    print("native: пропущено (PG_SKIP)")
    sys.exit(0)
if not CM.exists():
    print("native: ConnectionsManager.cpp не найден, пропуск")
    sys.exit(0)
cm = CM.read_text(encoding="utf-8")
if "PG_ACCOUNTS" in cm:
    print("native: уже применено")
    sys.exit(0)
if native_capacity is not None and new_max <= native_capacity:
    print("native: менять не нужно (экземпляров %d, нужно %d)" % (native_capacity, new_max))
    sys.exit(0)
m = NATIVE_RX.search(cm)
if not m or "static ConnectionsManager" not in m.group(4):
    die("native: не нашёл ConnectionsManager::getInstance в ожидаемом виде",
        grep(r"ConnectionsManager::getInstance|getInstance\(", CM, 20))
param = m.group(3)
cases = ["        case %d:\n            static ConnectionsManager instance%d(%d);\n            return instance%d;" % (i, i, i, i) for i in range(new_max)]
new_func = m.group(1) + """ // PG_ACCOUNTS
    switch (%s) {
%s
        default:
            static ConnectionsManager instanceDefault(%d);
            return instanceDefault;
    }
}""" % (param, "\n".join(cases), new_max - 1)
cm = cm[:m.start()] + new_func + cm[m.end():]
CM.write_text(cm, encoding="utf-8")
print("native: ConnectionsManager::getInstance теперь на %d экземпляров" % new_max)
