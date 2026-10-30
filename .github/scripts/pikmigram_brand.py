#!/usr/bin/env python3
"""Брендинг PikmiGram: название приложения и розовая иконка.

Меняет только название на экране и картинки. ID пакета не трогает.
Размеры картинок берёт у существующих файлов. Идемпотентен.
Нужен Pillow (pip install pillow).
"""
import math
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

RES = Path("TMessagesProj/src/main/res")
NAME = "PikmiGram"
PINK_TOP = (255, 143, 191)
PINK_BOTTOM = (255, 79, 147)


def die(msg):
    print("ОШИБКА: " + msg)
    sys.exit(1)


if not RES.exists():
    die("не найдена папка " + str(RES))


# ---------- рисование ----------
def heart_polygon(cx, cy, size):
    pts = []
    for i in range(361):
        t = math.radians(i)
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * size / 34.0, cy - y * size / 34.0))
    return pts


def sparkle(d, cx, cy, r, fill):
    d.polygon([(cx, cy - r), (cx + r * 0.28, cy - r * 0.28), (cx + r, cy), (cx + r * 0.28, cy + r * 0.28),
               (cx, cy + r), (cx - r * 0.28, cy + r * 0.28), (cx - r, cy), (cx - r * 0.28, cy - r * 0.28)], fill=fill)


def draw_heart_layer(px, scale_content):
    """Белое сердечко с бликом и искрами на прозрачном фоне. scale_content: доля холста, занятая сердцем."""
    S = px * 4
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    size = S * scale_content
    cx, cy = S / 2, S / 2 + size * 0.02
    # мягкая тень
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).polygon(heart_polygon(cx, cy + size * 0.03, size), fill=(190, 30, 100, 90))
    shadow = shadow.filter(ImageFilter.GaussianBlur(S * 0.012))
    im = Image.alpha_composite(im, shadow)
    d = ImageDraw.Draw(im)
    d.polygon(heart_polygon(cx, cy, size), fill=(255, 255, 255, 255))
    # розовый внутренний блик
    d.polygon(heart_polygon(cx, cy + size * 0.02, size * 0.74), fill=(255, 226, 238, 255))
    d.polygon(heart_polygon(cx, cy + size * 0.035, size * 0.60), fill=(255, 255, 255, 255))
    # искры
    sparkle(d, cx + size * 0.50, cy - size * 0.46, size * 0.13, (255, 255, 255, 255))
    sparkle(d, cx - size * 0.52, cy + size * 0.30, size * 0.08, (255, 255, 255, 235))
    return im.resize((px, px), Image.LANCZOS)


def gradient(px):
    im = Image.new("RGB", (px, px))
    d = ImageDraw.Draw(im)
    for y in range(px):
        k = y / max(1, px - 1)
        d.line([(0, y), (px, y)], fill=tuple(int(PINK_TOP[i] + (PINK_BOTTOM[i] - PINK_TOP[i]) * k) for i in range(3)))
    return im.convert("RGBA")


def legacy_icon(px, round_shape):
    S = px * 4
    bg = gradient(S)
    mask = Image.new("L", (S, S), 0)
    md = ImageDraw.Draw(mask)
    if round_shape:
        md.ellipse([0, 0, S - 1, S - 1], fill=255)
    else:
        md.rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.22), fill=255)
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.paste(bg, (0, 0), mask)
    out = Image.alpha_composite(out, draw_heart_layer(S, 0.52))
    return out.resize((px, px), Image.LANCZOS)


def png_size(p):
    with Image.open(p) as im:
        return im.size[0]


def save(im, path):
    if path.suffix.lower() == ".webp":
        im.save(path, "WEBP", quality=95)
    else:
        im.save(path, "PNG", optimize=True)


# ---------- 1. название ----------
names = 0
for f in sorted(RES.glob("values*/strings.xml")):
    t = f.read_text(encoding="utf-8")
    n = re.sub(r'(<string name="AppName">)[^<]*(</string>)', r"\g<1>%s\g<2>" % NAME, t)
    n = re.sub(r'(<string name="AppNameBeta">)[^<]*(</string>)', r"\g<1>%s Beta\g<2>" % NAME, n)
    # строки, значение которых ровно "Telegram" (подписи в интерфейсе)
    n = re.sub(r'(<string name="[A-Za-z0-9_]+">)Telegram(</string>)', r"\g<1>%s\g<2>" % NAME, n)
    if n != t:
        f.write_text(n, encoding="utf-8")
        names += 1
if names == 0:
    die("не нашёл строку AppName ни в одном strings.xml")
print("название: обновлено файлов strings.xml: %d" % names)

# ---------- 2. иконки ----------
cache_fg, cache_leg = {}, {}
count = 0
for d in sorted(RES.glob("mipmap-*")):
    if "anydpi" in d.name:
        continue
    for name, kind in (("icon_foreground.png", "fg"), ("icon_foreground_round.png", "fg"), ("icon_foreground_sa.png", "fg"),
                       ("ic_launcher.png", "sq"), ("ic_launcher_round.png", "round")):
        p = d / name
        if not p.exists():
            continue
        px = png_size(p)
        if kind == "fg":
            if px not in cache_fg:
                cache_fg[px] = draw_heart_layer(px, 0.40)  # в безопасной зоне адаптивной иконки (~66%)
            save(cache_fg[px], p)
        else:
            key = (px, kind)
            if key not in cache_leg:
                cache_leg[key] = legacy_icon(px, kind == "round")
            save(cache_leg[key], p)
        count += 1
for d in sorted(RES.glob("drawable-*")):
    p = d / "ic_launcher_dr.webp"
    if p.exists():
        px = png_size(p)
        save(legacy_icon(px, False), p)
        count += 1
print("иконки: заменено файлов: %d" % count)
if count == 0:
    die("не нашёл ни одной иконки для замены")

# ---------- 3. фон адаптивной иконки ----------
bg = RES / "drawable/icon_background_sa.xml"
if bg.exists():
    bg.write_text('''<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android">
    <gradient
        android:type="linear"
        android:angle="90"
        android:startColor="#FF4F93"
        android:endColor="#FF8FBF" />
</shape>''', encoding="utf-8")
    print("фон адаптивной иконки: розовый градиент")
else:
    print("предупреждение: drawable/icon_background_sa.xml не найден, фон не менялся")
# ---------- 4. название из языкового пакета ----------
# Telegram берёт строки сначала из языкового пакета с сервера (там AppName = "Telegram"),
# и только потом из ресурсов. Поэтому подменяем значение прямо при чтении.
import subprocess

LC = Path("TMessagesProj/src/main/java/org/telegram/messenger/LocaleController.java")
if not LC.exists():
    die("не найден LocaleController.java")
lc = LC.read_text(encoding="utf-8")
if "pgBrand(" not in lc:
    rx_class = re.compile(r"(public class LocaleController[^{]*\{)")
    rx_get = re.compile(r"localeValues\.get\((\w+)\)")
    n_get = len(rx_get.findall(lc))
    if len(rx_class.findall(lc)) != 1 or n_get == 0:
        hint = subprocess.run(["grep", "-n", "-E", "localeValues|public class LocaleController|String getString", str(LC)], capture_output=True, text=True).stdout
        print("--- подсказка для разработчика ---")
        print("\n".join(hint.splitlines()[:40]))
        die("LocaleController: не нашёл ожидаемые места (class: %d, localeValues.get: %d)" % (len(rx_class.findall(lc)), n_get))
    helper = """
    private static String pgBrand(String key, String value) {
        if ("AppName".equals(key)) {
            return "%s";
        }
        if ("AppNameBeta".equals(key)) {
            return "%s Beta";
        }
        return value;
    }
""" % (NAME, NAME)
    lc = rx_get.sub(lambda m: "pgBrand(%s, localeValues.get(%s))" % (m.group(1), m.group(1)), lc)
    lc = rx_class.sub(lambda m: m.group(1) + helper, lc, count=1)
    LC.write_text(lc, encoding="utf-8")
    print("название из языкового пакета: подменено мест чтения: %d" % n_get)
else:
    print("название из языкового пакета: уже подменено")
print("Готово: PikmiGram")
