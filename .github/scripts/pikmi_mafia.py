#!/usr/bin/env python3
"""Устанавливает модуль Мафия: копирует Java + меню + устойчивый init observers (фон)."""
import re, sys, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CANDIDATES = [
    ROOT / "mafia_src",
    Path(__file__).resolve().parent / "mafia_src",
    Path("mafia_src"),
    Path("/home/workdir/artifacts/mafia_src"),
    Path(".github/scripts/mafia_src"),
]

def find_src():
    for c in CANDIDATES:
        if (c / "PikmiMafia.java").exists() and (c / "PikmiMafiaEngine.java").exists():
            return c
    return None

def main():
    src = find_src()
    if not src:
        print("ОШИБКА: нет mafia_src с Java файлами")
        sys.exit(1)
    dst = Path("TMessagesProj/src/main/java/org/telegram/messenger")
    uid = Path("TMessagesProj/src/main/java/org/telegram/ui")
    dst.mkdir(parents=True, exist_ok=True)
    uid.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src / "PikmiMafia.java", dst / "PikmiMafia.java")
    shutil.copy2(src / "PikmiMafiaEngine.java", dst / "PikmiMafiaEngine.java")
    shutil.copy2(src / "PikmiMafiaSettingsActivity.java", uid / "PikmiMafiaSettingsActivity.java")
    print("Java: скопированы из", src)

    # Защита: старый API кнопок больше не существует в TLRPC
    eng = (dst / "PikmiMafiaEngine.java").read_text(encoding="utf-8")
    bad = [
        "TLRPC.TL_keyboardButtonCallback",
        "TLRPC.TL_keyboardButtonRow",
        "TLRPC.TL_keyboardButtonUrl",
        "TLRPC.KeyboardButton",
    ]
    found = [b for b in bad if b in eng]
    if found:
        print("ОШИБКА: в PikmiMafiaEngine.java остался старый API:", ", ".join(found))
        print("Обнови файл в", src / "PikmiMafiaEngine.java")
        sys.exit(1)
    if "TL_keyboard" not in eng or "forEachButton" not in eng:
        print("ОШИБКА: PikmiMafiaEngine.java без нового TL_keyboard API")
        print("Источник:", src / "PikmiMafiaEngine.java")
        sys.exit(1)
    print("API кнопок: OK (TL_keyboard)")

    da = Path("TMessagesProj/src/main/java/org/telegram/ui/DialogsActivity.java")
    if not da.exists():
        print("ОШИБКА: DialogsActivity")
        sys.exit(1)
    text = da.read_text(encoding="utf-8")
    if "PG_MAFIA_MENU" not in text:
        inserted = False
        for anchor in [
            "presentFragment(new org.telegram.ui.PikmiGhostSettingsActivity());\n        });",
            "presentFragment(new org.telegram.ui.PikmiAISettingsActivity());\n        });",
        ]:
            if anchor in text:
                text = text.replace(anchor, anchor + "\n"
                    "        io.add(R.drawable.msg_groups, \"PikmiGram: Мафия\", () -> { // PG_MAFIA_MENU\n"
                    "            presentFragment(new org.telegram.ui.PikmiMafiaSettingsActivity());\n"
                    "        });", 1)
                inserted = True
                break
        if not inserted:
            rx = re.compile(
                r"(io\.add\(R\.drawable\.outline_groups_24, getString\(R\.string\.NewGroup\), \(\) -> \{\s*"
                r"Bundle args = new Bundle\(\);\s*"
                r"presentFragment\(new GroupCreateActivity\(args\)\);\s*\}\);)"
            )
            if not rx.search(text):
                print("ОШИБКА: якорь меню")
                sys.exit(1)
            text = rx.sub(lambda m: m.group(1) + "\n        io.addGap();\n"
                "        io.add(R.drawable.msg_groups, \"PikmiGram: Мафия\", () -> { // PG_MAFIA_MENU\n"
                "            presentFragment(new org.telegram.ui.PikmiMafiaSettingsActivity());\n"
                "        });", text, count=1)
        da.write_text(text, encoding="utf-8")
        print("меню: добавлено")
    else:
        print("меню: уже есть")

    # ApplicationLoader: ранний + повторный ensureObservers (фон / keepAlive)
    al = Path("TMessagesProj/src/main/java/org/telegram/messenger/ApplicationLoader.java")
    if al.exists():
        t = al.read_text(encoding="utf-8")
        changed = False
        if "PG_MAFIA_OBS" not in t and "applicationInited = true;" in t:
            t = t.replace(
                "applicationInited = true;",
                "applicationInited = true;\n"
                "        AndroidUtilities.runOnUIThread(() -> {\n"
                "            try { org.telegram.messenger.PikmiMafiaEngine.getInstance().ensureObservers(); } catch (Throwable ignore) {}\n"
                "        }, 2500); // PG_MAFIA_OBS\n"
                "        AndroidUtilities.runOnUIThread(() -> {\n"
                "            try { org.telegram.messenger.PikmiMafiaEngine.getInstance().ensureObservers(); } catch (Throwable ignore) {}\n"
                "        }, 15000); // PG_MAFIA_OBS2",
                1,
            )
            changed = True
            print("observers: ApplicationLoader x2")
        # Доп. хук: при onResume приложения (если есть метод)
        if "PG_MAFIA_RESUME" not in t:
            for marker in (
                "public static void startPushService()",
                "public static void startPushService() {",
            ):
                if marker in t:
                    t = t.replace(
                        marker,
                        "public static void pgMafiaEnsure() { // PG_MAFIA_RESUME\n"
                        "        try { org.telegram.messenger.PikmiMafiaEngine.getInstance().ensureObservers(); } catch (Throwable ignore) {}\n"
                        "    }\n\n"
                        + marker,
                        1,
                    )
                    # вызов рядом со startPushService
                    if "startPushService();" in t and "pgMafiaEnsure()" not in t:
                        t = t.replace(
                            "startPushService();",
                            "startPushService();\n"
                            "        try { pgMafiaEnsure(); } catch (Throwable ignore) {} // PG_MAFIA_RESUME_CALL",
                            1,
                        )
                    changed = True
                    print("observers: resume/push hook")
                    break
        if changed:
            al.write_text(t, encoding="utf-8")
        else:
            print("observers: skip/exists")

    # KeepAlive / NotificationsService — подстраховка, если ghost-патч не сработал
    for rel, tag, needle, inject in [
        (
            "TMessagesProj/src/main/java/org/telegram/messenger/NotificationsService.java",
            "PG_MAFIA_NS",
            "public int onStartCommand",
            "        try { org.telegram.messenger.PikmiMafiaEngine.getInstance().ensureObservers(); } catch (Throwable ignore) {} // PG_MAFIA_NS\n",
        ),
    ]:
        p = Path(rel)
        if not p.exists():
            continue
        s = p.read_text(encoding="utf-8")
        if tag in s:
            continue
        if needle in s:
            # вставить сразу после сигнатуры метода — ищем первую '{' после needle
            i = s.find(needle)
            j = s.find("{", i)
            if j > 0:
                s = s[: j + 1] + "\n" + inject + s[j + 1 :]
                p.write_text(s, encoding="utf-8")
                print("observers: NotificationsService")

    print("Готово: Мафия (меню + роли/активные + фон без падений)")

if __name__ == "__main__":
    main()
