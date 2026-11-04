#!/usr/bin/env python3
"""Показывает секунды во всех местах, где отображается время (HH:mm:ss).

Строковые ресурсы (formatterDay24H и т.д.) содержат "HH:mm" и перекрывают
fallback. Поэтому патчер:
  1. В getFormatterDay() и getFormatterConstDay() подставляет паттерн
     с секундами напрямую (игнорируя ресурс).
  2. Добавляет секунды в остальные fallback-паттерны (stats, schedule…).

Идемпотентен.
"""
import re
import sys
from pathlib import Path

LC = Path("TMessagesProj/src/main/java/org/telegram/messenger/LocaleController.java")


def die(msg, hint=None):
    print("ОШИБКА: " + msg)
    if hint:
        print("--- подсказка для разработчика ---")
        print(hint)
    sys.exit(1)


def main():
    if not LC.exists():
        die("не найден LocaleController.java")

    text = LC.read_text(encoding="utf-8")
    if "PG_TIME_SECONDS" in text:
        print("уже применено")
        return

    original = text

    # ---------- 1. getFormatterDay() — главный форматтер сообщений ----------
    # Передаём паттерн с секундами и как format, и как defaultFormat → ресурс игнорируется
    old_day = (
        'formatterDay = createFormatter(lang.toLowerCase().equals("ar") || lang.toLowerCase().equals("ko") ? locale : Locale.US, '
        'is24HourFormat ? getStringInternal("formatterDay24H", R.string.formatterDay24H) : getStringInternal("formatterDay12H", R.string.formatterDay12H), '
        'is24HourFormat ? "HH:mm" : "h:mm a");'
    )
    new_day = (
        'formatterDay = createFormatter(lang.toLowerCase().equals("ar") || lang.toLowerCase().equals("ko") ? locale : Locale.US, '
        'is24HourFormat ? "HH:mm:ss" : "h:mm:ss a", '
        'is24HourFormat ? "HH:mm:ss" : "h:mm:ss a"); // PG_TIME_SECONDS'
    )
    if old_day not in text:
        rx = re.compile(
            r'formatterDay\s*=\s*createFormatter\(\s*'
            r'lang\.toLowerCase\(\)\.equals\("ar"\)\s*\|\|\s*lang\.toLowerCase\(\)\.equals\("ko"\)\s*\?\s*locale\s*:\s*Locale\.US\s*,\s*'
            r'is24HourFormat\s*\?\s*getStringInternal\("formatterDay24H"[^)]+\)\s*:\s*getStringInternal\("formatterDay12H"[^)]+\)\s*,\s*'
            r'is24HourFormat\s*\?\s*"HH:mm"\s*:\s*"h:mm a"\s*\)\s*;',
            re.DOTALL
        )
        if not rx.search(text):
            die("LocaleController: не нашёл вызов createFormatter для formatterDay",
                __import__("subprocess").run(
                    "grep -n 'formatterDay = createFormatter' %s" % LC, shell=True,
                    capture_output=True, text=True).stdout)
        text = rx.sub(new_day, text, count=1)
    else:
        text = text.replace(old_day, new_day, 1)

    # ---------- 2. getFormatterConstDay() ----------
    old_const = (
        'formatterConstDay = createFormatter(lang.toLowerCase().equals("ar") || lang.toLowerCase().equals("ko") ? locale : Locale.US, '
        'is24HourFormat ? "HH:mm" : "h:mm a", is24HourFormat ? "HH:mm" : "h:mm a");'
    )
    new_const = (
        'formatterConstDay = createFormatter(lang.toLowerCase().equals("ar") || lang.toLowerCase().equals("ko") ? locale : Locale.US, '
        'is24HourFormat ? "HH:mm:ss" : "h:mm:ss a", is24HourFormat ? "HH:mm:ss" : "h:mm:ss a"); // PG_TIME_SECONDS'
    )
    if old_const in text:
        text = text.replace(old_const, new_const, 1)
    else:
        text = text.replace(
            'is24HourFormat ? "HH:mm" : "h:mm a", is24HourFormat ? "HH:mm" : "h:mm a");',
            'is24HourFormat ? "HH:mm:ss" : "h:mm:ss a", is24HourFormat ? "HH:mm:ss" : "h:mm:ss a"); // PG_TIME_SECONDS',
            1
        )

    # ---------- 3. Stats / BannedUntil ----------
    text = text.replace(
        'is24HourFormat ? "MMM dd yyyy, HH:mm" : "MMM dd yyyy, h:mm a"',
        'is24HourFormat ? "MMM dd yyyy, HH:mm:ss" : "MMM dd yyyy, h:mm:ss a"'
    )
    text = text.replace(
        'is24HourFormat ? "MMM dd, HH:mm" : "MMM dd, h:mm a"',
        'is24HourFormat ? "MMM dd, HH:mm:ss" : "MMM dd, h:mm:ss a"'
    )

    # ---------- 4. Schedule formatters ----------
    text = re.sub(
        r"(createFormatter\(\s*locale\s*,\s*getStringInternal\([^)]+\)\s*,\s*['\"][^'\"]*?)HH:mm(?!:ss)",
        lambda m: m.group(1) + "HH:mm:ss",
        text
    )
    text = re.sub(
        r"(MMM d(?: yyyy)?(?:,|\',) )HH:mm(?!:ss)",
        r"\1HH:mm:ss",
        text
    )
    text = re.sub(
        r"('Today,' )HH:mm(?!:ss)",
        r"\1HH:mm:ss",
        text
    )

    if text == original:
        die("LocaleController: ничего не изменилось",
            __import__("subprocess").run(
                "grep -n 'formatterDay = createFormatter' %s" % LC, shell=True,
                capture_output=True, text=True).stdout)

    if "PG_TIME_SECONDS" not in text:
        text = text.replace(
            'is24HourFormat ? "HH:mm:ss" : "h:mm:ss a");',
            'is24HourFormat ? "HH:mm:ss" : "h:mm:ss a"); // PG_TIME_SECONDS',
            1
        )

    LC.write_text(text, encoding="utf-8")
    print("Готово: секунды принудительно включены (ресурсы игнорируются)")


if __name__ == "__main__":
    main()
