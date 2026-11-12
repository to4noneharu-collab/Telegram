#!/usr/bin/env python3
"""Поднимает лимит аккаунтов как в AyuGram/exteraGram: 16 без Premium / 32 с Premium.

Патчит:
  - UserConfig.MAX_ACCOUNT_DEFAULT_COUNT = 16
  - UserConfig.MAX_ACCOUNT_COUNT = 32
  - getMaxAccountCount() → hasPremium ? 32 : 16
  - jni/tgnet/ConnectionsManager.cpp — static instance0..instance31
  - jni/tgnet/Defines.h MAX_ACCOUNT_COUNT (если есть)

Без native-патча при MAX>5 приложение падает при старте.
Идемпотентен (маркер PG_ACCOUNTS).
"""
import os
import re
import sys
from pathlib import Path

UC = Path("TMessagesProj/src/main/java/org/telegram/messenger/UserConfig.java")
CM = Path("TMessagesProj/jni/tgnet/ConnectionsManager.cpp")
DH = Path("TMessagesProj/jni/tgnet/Defines.h")

# 16 без Premium / 32 с Premium
DEFAULT_COUNT = 16
MAX_COUNT = 32

SKIP = os.environ.get("PG_SKIP", "")


def die(msg):
    print("ОШИБКА:", msg)
    sys.exit(1)


def main():
    if not UC.exists():
        die("не найден UserConfig.java")

    uc = UC.read_text(encoding="utf-8")

    # --- Java ---
    if "accjava" in SKIP:
        print("Java: пропущено (PG_SKIP)")
    else:
        uc2, n1 = re.subn(
            r"(public\s+static\s+final\s+int\s+MAX_ACCOUNT_DEFAULT_COUNT\s*=\s*)\d+(\s*;)",
            r"\g<1>%d\2 // PG_ACCOUNTS" % DEFAULT_COUNT,
            uc,
            count=1,
        )
        uc2, n2 = re.subn(
            r"(public\s+static\s+final\s+int\s+MAX_ACCOUNT_COUNT\s*=\s*)\d+(\s*;)",
            r"\g<1>%d\2 // PG_ACCOUNTS" % MAX_COUNT,
            uc2,
            count=1,
        )
        if n1 == 0:
            uc2, n1 = re.subn(
                r"(MAX_ACCOUNT_DEFAULT_COUNT\s*=\s*)\d+(\s*;)",
                r"\g<1>%d\2 // PG_ACCOUNTS" % DEFAULT_COUNT,
                uc2,
                count=1,
            )
        if n2 == 0:
            uc2, n2 = re.subn(
                r"(MAX_ACCOUNT_COUNT\s*=\s*)\d+(\s*;)",
                r"\g<1>%d\2 // PG_ACCOUNTS" % MAX_COUNT,
                uc2,
                count=1,
            )

        rx_get = re.compile(
            r"(public\s+static\s+int\s+getMaxAccountCount\s*\(\s*\)\s*\{)(.*?)(\n\s*\})",
            re.S,
        )
        m = rx_get.search(uc2)
        if not m:
            die("не найден getMaxAccountCount()")
        body = m.group(2)
        if "PG_ACCOUNTS" in body:
            print("Java getMaxAccountCount: уже применено")
        else:
            new_body = (
                "\n        // PG_ACCOUNTS: как AyuGram — 32 с Premium, 16 без\n"
                "        return hasPremiumOnAccounts() ? %d : %d;\n    "
                % (MAX_COUNT, DEFAULT_COUNT)
            )
            uc2 = uc2[: m.start()] + m.group(1) + new_body + m.group(3) + uc2[m.end() :]
            print("Java getMaxAccountCount: %d / %d" % (DEFAULT_COUNT, MAX_COUNT))

        if n1 or n2 or "PG_ACCOUNTS" in uc2:
            UC.write_text(uc2, encoding="utf-8")
            print("Java: MAX_ACCOUNT_DEFAULT_COUNT=%d MAX_ACCOUNT_COUNT=%d" % (DEFAULT_COUNT, MAX_COUNT))
        else:
            print("Java: константы не найдены в ожидаемом виде — проверь UserConfig.java")

    # --- Defines.h ---
    if DH.exists() and "accnative" not in SKIP:
        dh = DH.read_text(encoding="utf-8")
        if "PG_ACCOUNTS" in dh:
            print("Defines.h: уже применено")
        else:
            dh2, n = re.subn(
                r"(#\s*define\s+MAX_ACCOUNT_COUNT\s+)\d+",
                r"\g<1>%d // PG_ACCOUNTS" % MAX_COUNT,
                dh,
                count=1,
            )
            if n:
                DH.write_text(dh2, encoding="utf-8")
                print("Defines.h: MAX_ACCOUNT_COUNT=%d" % MAX_COUNT)
            else:
                print("Defines.h: MAX_ACCOUNT_COUNT define не найден (ок, если нет)")

    # --- native ConnectionsManager.cpp ---
    if "accnative" in SKIP:
        print("native: пропущено (PG_SKIP)")
        return
    if not CM.exists():
        print("native: ConnectionsManager.cpp не найден — пропуск")
        return

    cm = CM.read_text(encoding="utf-8")
    if "PG_ACCOUNTS" in cm:
        print("native: уже применено")
        return

    rx = re.compile(
        r"(ConnectionsManager\s*&\s*ConnectionsManager::getInstance\s*\(\s*"
        r"((?:u?int32_t|int|unsigned\s+int)\s+(\w+))\s*\)\s*\{)"
        r"(.*?)\n\}",
        re.S,
    )
    m = rx.search(cm)
    if not m:
        die("native: не найден ConnectionsManager::getInstance")

    param = m.group(3)
    cases = []
    for i in range(MAX_COUNT):
        cases.append(
            "        case %d:\n"
            "            static ConnectionsManager instance%d(%d);\n"
            "            return instance%d;" % (i, i, i, i)
        )
    new_func = (
        m.group(1)
        + " // PG_ACCOUNTS\n"
        + "    switch (%s) {\n" % param
        + "\n".join(cases)
        + "\n        default:\n"
        + "            static ConnectionsManager instanceDefault(%d);\n" % (MAX_COUNT - 1)
        + "            return instanceDefault;\n"
        + "    }\n"
        + "}"
    )
    cm = cm[: m.start()] + new_func + cm[m.end() :]
    CM.write_text(cm, encoding="utf-8")
    print("native: ConnectionsManager::getInstance → %d инстансов (0..%d)" % (MAX_COUNT, MAX_COUNT - 1))
    print("Готово. Лимит: %d без Premium / %d с Premium." % (DEFAULT_COUNT, MAX_COUNT))


if __name__ == "__main__":
    main()
