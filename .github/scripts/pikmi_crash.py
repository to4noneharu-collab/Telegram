#!/usr/bin/env python3
"""Лог падений PikmiGram.

Если приложение вылетает из-за ошибки в Java-коде, трассировка сохраняется файлом
PikmiGram-crash-<время>.txt в папку "Загрузки" телефона. Нативные падения (SIGSEGV) так не поймать.
Запускать из корня репозитория. Идемпотентен, не падает, если место вставки не найдено.
"""
import re
import sys
from pathlib import Path

J = Path("TMessagesProj/src/main/java/org/telegram")
AL = J / "messenger/ApplicationLoader.java"
PC = J / "messenger/PikmiCrash.java"

JAVA = r'''package org.telegram.messenger;

import android.content.ContentValues;
import android.content.Context;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.MediaStore;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;
import java.io.PrintWriter;
import java.io.StringWriter;

/** Сохраняет трассировку падения в Загрузки, чтобы её можно было отправить разработчику. */
public class PikmiCrash {

    public static void install(final Context ctx) {
        try {
            final Thread.UncaughtExceptionHandler prev = Thread.getDefaultUncaughtExceptionHandler();
            Thread.setDefaultUncaughtExceptionHandler(new Thread.UncaughtExceptionHandler() {
                @Override
                public void uncaughtException(Thread t, Throwable e) {
                    try {
                        write(ctx, t, e);
                    } catch (Throwable ignore) {
                    }
                    if (prev != null) {
                        prev.uncaughtException(t, e);
                    }
                }
            });
        } catch (Throwable ignore) {
        }
    }

    private static void write(Context ctx, Thread t, Throwable e) throws Exception {
        StringWriter sw = new StringWriter();
        PrintWriter pw = new PrintWriter(sw);
        pw.println("PikmiGram crash " + new java.util.Date());
        pw.println("Device: " + Build.MANUFACTURER + " " + Build.MODEL + ", Android " + Build.VERSION.RELEASE + " (API " + Build.VERSION.SDK_INT + ")");
        pw.println("Thread: " + (t == null ? "?" : t.getName()));
        pw.println();
        e.printStackTrace(pw);
        pw.flush();
        byte[] data = sw.toString().getBytes("UTF-8");
        String name = "PikmiGram-crash-" + System.currentTimeMillis() + ".txt";
        if (Build.VERSION.SDK_INT >= 29) {
            ContentValues v = new ContentValues();
            v.put(MediaStore.MediaColumns.DISPLAY_NAME, name);
            v.put(MediaStore.MediaColumns.MIME_TYPE, "text/plain");
            v.put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS);
            Uri uri = ctx.getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, v);
            if (uri != null) {
                OutputStream os = ctx.getContentResolver().openOutputStream(uri);
                if (os != null) {
                    os.write(data);
                    os.close();
                    return;
                }
            }
        }
        File dir = ctx.getExternalFilesDir(null);
        if (dir == null) {
            dir = ctx.getFilesDir();
        }
        FileOutputStream fo = new FileOutputStream(new File(dir, name));
        fo.write(data);
        fo.close();
    }
}
'''

if not AL.exists():
    print("пропуск: нет ApplicationLoader.java")
    sys.exit(0)
al = AL.read_text(encoding="utf-8")
if "PikmiCrash" in al:
    print("уже применено")
    sys.exit(0)
rx = re.compile(r"(public void onCreate\(\) \{\s*super\.onCreate\(\);)")
if len(rx.findall(al)) != 1:
    print("предупреждение: ApplicationLoader.onCreate не найден, лог падений не включён")
    sys.exit(0)
PC.write_text(JAVA, encoding="utf-8")
al = rx.sub(lambda m: m.group(1) + "\n        org.telegram.messenger.PikmiCrash.install(this);", al, count=1)
AL.write_text(al, encoding="utf-8")
print("Лог падений включён (файл появится в Загрузках после вылета)")
