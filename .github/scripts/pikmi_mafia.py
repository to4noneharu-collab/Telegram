#!/usr/bin/env python3
"""Устанавливает модуль Мафия: копирует Java + меню + init observers."""
import re, sys, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# sources рядом со скриптом или в mafia_src /
CANDIDATES = [
    ROOT / "mafia_src",
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
    print("Java: скопированы")

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

    al = Path("TMessagesProj/src/main/java/org/telegram/messenger/ApplicationLoader.java")
    if al.exists():
        t = al.read_text(encoding="utf-8")
        if "PG_MAFIA_OBS" not in t and "applicationInited = true;" in t:
            t = t.replace(
                "applicationInited = true;",
                "applicationInited = true;\n"
                "        AndroidUtilities.runOnUIThread(() -> {\n"
                "            try { org.telegram.messenger.PikmiMafiaEngine.getInstance().ensureObservers(); } catch (Throwable ignore) {}\n"
                "        }, 4000); // PG_MAFIA_OBS",
                1,
            )
            al.write_text(t, encoding="utf-8")
            print("observers: ApplicationLoader")
        else:
            print("observers: skip")
    print("Готово: Мафия (рег/голос/роли/ночь/комиссар/линч)")

if __name__ == "__main__":
    main()
