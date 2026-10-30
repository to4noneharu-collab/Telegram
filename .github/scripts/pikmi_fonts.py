#!/usr/bin/env python3
"""Меню шрифтов PikmiGram.

Добавляет класс PikmiFonts, пункт "PikmiGram: шрифты" в меню долгого нажатия на сообщение
и подмену шрифтов приложения. Запускать из корня репозитория после shadowban_list.py.
Идемпотентен. Если нужного места в коде нет, печатает подсказки и завершается с ошибкой.
"""
import re
import subprocess
import sys
from pathlib import Path

J = Path("TMessagesProj/src/main/java/org/telegram")
CA = J / "ui/ChatActivity.java"
AU = J / "messenger/AndroidUtilities.java"
TH = J / "ui/ActionBar/Theme.java"
PF = J / "messenger/PikmiFonts.java"


def die(msg, hint=None):
    print("ОШИБКА: " + msg)
    if hint:
        print("--- подсказка для разработчика ---")
        print(hint)
    sys.exit(1)


def grep(pattern, path, n=15):
    try:
        out = subprocess.run(["grep", "-n", "-E", pattern, str(path)], capture_output=True, text=True).stdout
        return "\n".join(out.splitlines()[:n])
    except Exception:
        return ""


JAVA = r'''package org.telegram.messenger;

import android.app.Activity;
import android.content.Context;
import android.content.DialogInterface;
import android.content.SharedPreferences;
import android.graphics.Typeface;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.TextView;
import android.widget.Toast;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;

/** Выбор шрифта PikmiGram. Шрифты лежат в assets/fonts с префиксом pg_. */
public class PikmiFonts {

    private static final String PREFS = "pikmigram";
    private static final String KEY = "font_file";
    private static final String DIR = "fonts";
    private static final String PREFIX = "pg_";
    private static final String SAMPLE = "Привет, милашка ♡ Aa Бб 123";

    private static volatile String currentFile;
    private static final HashMap<String, Typeface> cache = new HashMap<>();

    private static SharedPreferences prefs() {
        return ApplicationLoader.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    /** Имя файла выбранного шрифта или пустая строка, если стандартный. */
    public static String current() {
        String c = currentFile;
        if (c == null) {
            try {
                c = prefs().getString(KEY, "");
            } catch (Throwable e) {
                c = "";
            }
            if (c == null) {
                c = "";
            }
            currentFile = c;
        }
        return c;
    }

    public static void setFont(String file) {
        currentFile = file == null ? "" : file;
        try {
            prefs().edit().putString(KEY, currentFile).apply();
        } catch (Throwable ignore) {
        }
    }

    private static Typeface load(String file) {
        if (file == null || file.length() == 0 || ApplicationLoader.applicationContext == null) {
            return null;
        }
        synchronized (cache) {
            Typeface t = cache.get(file);
            if (t != null) {
                return t;
            }
            try {
                t = Typeface.createFromAsset(ApplicationLoader.applicationContext.getAssets(), DIR + "/" + file);
                cache.put(file, t);
                return t;
            } catch (Throwable e) {
                return null;
            }
        }
    }

    /** Шрифт для обычного текста сообщений или null, если выбран стандартный. */
    public static Typeface regular() {
        if (ApplicationLoader.applicationContext == null) {
            return null;
        }
        return load(current());
    }

    private static volatile boolean appWideDone;

    /**
     * Меняет шрифт по умолчанию во всём процессе: и для обычных TextView, и для текста, который
     * Telegram рисует сам через Paint без явного шрифта. Работает через скрытые API (HiddenApiBypass).
     * Если что-то не получилось, приложение просто остаётся на стандартном шрифте.
     */
    @SuppressWarnings({"unchecked", "rawtypes"})
    public static void applyAppWide() {
        if (appWideDone) {
            return;
        }
        Typeface base = regular();
        if (base == null) {
            return;
        }
        try {
            if (android.os.Build.VERSION.SDK_INT >= 28) {
                org.lsposed.hiddenapibypass.HiddenApiBypass.addHiddenApiExemptions("L");
            }
        } catch (Throwable ignore) {
        }
        Typeface bold = Typeface.create(base, Typeface.BOLD);
        Typeface italic = Typeface.create(base, Typeface.ITALIC);
        Typeface boldItalic = Typeface.create(base, Typeface.BOLD_ITALIC);
        boolean ok = false;
        try {
            java.lang.reflect.Method m = Typeface.class.getDeclaredMethod("setDefault", Typeface.class);
            m.setAccessible(true);
            m.invoke(null, base);
            ok = true;
        } catch (Throwable ignore) {
        }
        try {
            java.lang.reflect.Field f = Typeface.class.getDeclaredField("sSystemFontMap");
            f.setAccessible(true);
            Object o = f.get(null);
            if (o instanceof java.util.Map) {
                java.util.HashMap<String, Typeface> copy = new java.util.HashMap<String, Typeface>((java.util.Map) o);
                copy.put("sans-serif", base);
                copy.put("sans-serif-light", base);
                copy.put("sans-serif-thin", base);
                copy.put("sans-serif-regular", base);
                copy.put("sans-serif-medium", bold);
                copy.put("sans-serif-black", bold);
                copy.put("sans-serif-condensed", base);
                f.set(null, copy);
                ok = true;
            }
        } catch (Throwable ignore) {
        }
        String[] names = {"DEFAULT", "SANS_SERIF"};
        for (String n : names) {
            try {
                java.lang.reflect.Field f = Typeface.class.getDeclaredField(n);
                f.setAccessible(true);
                f.set(null, base);
            } catch (Throwable ignore) {
            }
        }
        try {
            java.lang.reflect.Field f = Typeface.class.getDeclaredField("DEFAULT_BOLD");
            f.setAccessible(true);
            f.set(null, bold);
        } catch (Throwable ignore) {
        }
        try {
            java.lang.reflect.Field f = Typeface.class.getDeclaredField("sDefaults");
            f.setAccessible(true);
            Typeface[] arr = (Typeface[]) f.get(null);
            if (arr != null && arr.length >= 4) {
                arr[Typeface.NORMAL] = base;
                arr[Typeface.BOLD] = bold;
                arr[Typeface.ITALIC] = italic;
                arr[Typeface.BOLD_ITALIC] = boldItalic;
            }
        } catch (Throwable ignore) {
        }
        appWideDone = ok;
    }

    /** Подмена шрифтов приложения: вызывается из AndroidUtilities.getTypeface. */
    public static Typeface override(String assetPath) {
        if (assetPath == null || ApplicationLoader.applicationContext == null) {
            return null;
        }
        String cur = current();
        if (cur.length() == 0) {
            return null;
        }
        applyAppWide();
        if (assetPath.contains("mono")) {
            return null;
        }
        Typeface base = load(cur);
        if (base == null) {
            return null;
        }
        String style = null;
        int type = Typeface.NORMAL;
        if (assetPath.contains("medium") || assetPath.contains("bold")) {
            style = "b";
            type = Typeface.BOLD;
        } else if (assetPath.contains("italic")) {
            style = "i";
            type = Typeface.ITALIC;
        }
        if (style == null) {
            return base;
        }
        synchronized (cache) {
            String key = cur + ":" + style;
            Typeface t = cache.get(key);
            if (t == null) {
                t = Typeface.create(base, type);
                cache.put(key, t);
            }
            return t;
        }
    }

    public static ArrayList<String> available() {
        ArrayList<String> out = new ArrayList<>();
        try {
            String[] all = ApplicationLoader.applicationContext.getAssets().list(DIR);
            if (all != null) {
                for (String f : all) {
                    String low = f.toLowerCase();
                    if (f.startsWith(PREFIX) && (low.endsWith(".ttf") || low.endsWith(".otf"))) {
                        out.add(f);
                    }
                }
            }
        } catch (Throwable ignore) {
        }
        Collections.sort(out);
        return out;
    }

    private static String displayName(String file) {
        String b = file.substring(PREFIX.length());
        int dot = b.lastIndexOf('.');
        if (dot > 0) {
            b = b.substring(0, dot);
        }
        switch (b) {
            case "pacifico": return "Pacifico · мягкий рукописный";
            case "marckscript": return "Marck Script · каллиграфия";
            case "caveat": return "Caveat · дневниковый почерк";
            case "lobster": return "Lobster · пухлый плакатный";
            case "amaticsc": return "Amatic SC · тонкий и стильный";
            case "neucha": return "Neucha · детский рисованный";
            case "nunito": return "Nunito · круглый и мягкий";
            case "comfortaa": return "Comfortaa · округлый милый";
            case "philosopher": return "Philosopher · изящный";
            case "marmelad": return "Marmelad · уютный";
            case "badscript": return "Bad Script · скоропись";
            case "pangolin": return "Pangolin · игривый";
            case "kurale": return "Kurale · элегантный";
            case "ruslandisplay": return "Ruslan Display · декоративный";
            case "underdog": return "Underdog · милый мультяшный";
            default:
                return b.length() == 0 ? file : Character.toUpperCase(b.charAt(0)) + b.substring(1);
        }
    }

    public static void showMenu(final org.telegram.ui.ActionBar.BaseFragment fragment) {
        if (fragment == null) {
            return;
        }
        final Activity activity = fragment.getParentActivity();
        if (activity == null) {
            return;
        }
        final ArrayList<String> files = new ArrayList<>();
        files.add("");
        files.addAll(available());
        final String cur = current();
        final ArrayList<String> labels = new ArrayList<>();
        for (String f : files) {
            String name = f.length() == 0 ? "Стандартный шрифт" : displayName(f);
            labels.add((f.equals(cur) ? "✓ " : "") + name + "\n" + SAMPLE);
        }
        ArrayAdapter<String> adapter = new ArrayAdapter<String>(activity, android.R.layout.simple_list_item_1, labels) {
            @Override
            public View getView(int position, View convertView, ViewGroup parent) {
                View v = super.getView(position, convertView, parent);
                if (v instanceof TextView) {
                    TextView tv = (TextView) v;
                    String f = files.get(position);
                    Typeface tf = f.length() == 0 ? Typeface.DEFAULT : load(f);
                    tv.setTypeface(tf != null ? tf : Typeface.DEFAULT);
                    tv.setTextSize(17);
                    tv.setMinHeight(0);
                    tv.setPadding(48, 24, 48, 24);
                }
                return v;
            }
        };
        new android.app.AlertDialog.Builder(activity)
                .setTitle("Шрифт PikmiGram")
                .setAdapter(adapter, new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface dialog, int which) {
                        String f = files.get(which);
                        setFont(f);
                        appWideDone = false;
                        applyAppWide();
                        Toast.makeText(activity, "Шрифт выбран. Чтобы он применился везде, закрой приложение полностью и открой снова", Toast.LENGTH_LONG).show();
                    }
                })
                .setNegativeButton("Закрыть", null)
                .show();
    }
}
'''

if "PikmiFonts" in (CA.read_text(encoding="utf-8") if CA.exists() else ""):
    print("уже применено")
    sys.exit(0)

for p in (CA, AU):
    if not p.exists():
        die("не найден файл " + str(p))

ca = CA.read_text(encoding="utf-8")
if "OPTION_SHADOW_BAN_LIST" not in ca:
    die("в ChatActivity нет OPTION_SHADOW_BAN_LIST: сначала должен выполниться shadowban_list.py")

# ---------- AndroidUtilities.getTypeface ----------
au = AU.read_text(encoding="utf-8")
rx = re.compile(r"(public static Typeface getTypeface\(String assetPath\) \{)")
if len(rx.findall(au)) != 1:
    die("AndroidUtilities.getTypeface не найден в ожидаемом виде",
        grep(r"Typeface (getTypeface|bold)\(|TYPEFACE_ROBOTO", AU))
au = rx.sub(lambda m: m.group(1) + "\n        Typeface pgFont = org.telegram.messenger.PikmiFonts.override(assetPath);\n        if (pgFont != null) {\n            return pgFont;\n        }", au, count=1)
AU.write_text(au, encoding="utf-8")
print("  ok: AndroidUtilities.getTypeface")

# ---------- шрифт текста сообщений ----------
if TH.exists():
    th = TH.read_text(encoding="utf-8")
    rx = re.compile(r"(chat_msgTextPaint = new TextPaint\(Paint\.ANTI_ALIAS_FLAG\);)")
    n = len(rx.findall(th))
    if n:
        th = rx.sub(lambda m: m.group(1) + "\n            {\n                android.graphics.Typeface pgf = org.telegram.messenger.PikmiFonts.regular();\n                if (pgf != null) {\n                    chat_msgTextPaint.setTypeface(pgf);\n                }\n            }", th)
        TH.write_text(th, encoding="utf-8")
        print("  ok: шрифт текста сообщений (мест: %d)" % n)
    else:
        print("  пропуск: chat_msgTextPaint не найден, текст сообщений останется стандартным")
        print(grep(r"chat_msgTextPaint = ", TH, 5))

# ---------- ранний вызов из ApplicationLoader (необязательно) ----------
AL = J / "messenger/ApplicationLoader.java"
if AL.exists():
    al = AL.read_text(encoding="utf-8")
    rx = re.compile(r"(public static void postInitApplication\(\) \{)")
    if len(rx.findall(al)) == 1:
        al = rx.sub(lambda m: m.group(1) + "\n        org.telegram.messenger.PikmiFonts.applyAppWide();", al, count=1)
        AL.write_text(al, encoding="utf-8")
        print("  ok: ApplicationLoader.postInitApplication")
    else:
        print("  пропуск: postInitApplication не найден (шрифт применится при первом запросе шрифта)")

# ---------- класс ----------
PF.write_text(JAVA, encoding="utf-8")
print("  ok: PikmiFonts.java")

# ---------- ChatActivity: пункт меню ----------
def sub1(text, pattern, repl, what):
    rx = re.compile(pattern, re.S)
    if len(rx.findall(text)) != 1:
        die("ChatActivity: " + what + " не найдено ровно один раз")
    return rx.sub(repl, text, count=1)

ca = sub1(ca, r"(public final static int OPTION_SHADOW_BAN_LIST = 201;)",
          lambda m: m.group(1) + "\n    public final static int OPTION_PIKMI_FONTS = 202;", "константа")
ca = sub1(ca, r"(options\.add\(OPTION_SHADOW_BAN_LIST\);\s*icons\.add\(R\.drawable\.msg_block\);\s*\})",
          lambda m: m.group(1) + '''
            if (selectedObject != null) {
                items.add("PikmiGram: шрифты");
                options.add(OPTION_PIKMI_FONTS);
                icons.add(R.drawable.msg_edit);
            }''', "пункт меню")
ca = sub1(ca, r"(case OPTION_SHADOW_BAN_LIST:\s*\{)",
          lambda m: '''case OPTION_PIKMI_FONTS: {
                org.telegram.messenger.PikmiFonts.showMenu(this);
                break;
            }
            ''' + m.group(1), "обработчик")
CA.write_text(ca, encoding="utf-8")
print("Готово: меню шрифтов добавлено")
