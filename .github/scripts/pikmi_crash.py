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

import android.app.ActivityManager;
import android.app.ApplicationExitInfo;
import android.content.ContentValues;
import android.content.Context;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.MediaStore;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.util.List;

/**
 * Сохраняет в "Загрузки" данные о падениях, чтобы их можно было отправить разработчику:
 * 1) трассировку Java-падения (сразу);
 * 2) причину прошлого вылета процесса, в том числе нативного (при следующем запуске, Android 11+).
 */
public class PikmiCrash {

    public static void install(final Context ctx) {
        try {
            final Thread.UncaughtExceptionHandler prev = Thread.getDefaultUncaughtExceptionHandler();
            Thread.setDefaultUncaughtExceptionHandler(new Thread.UncaughtExceptionHandler() {
                @Override
                public void uncaughtException(Thread t, Throwable e) {
                    try {
                        StringWriter sw = new StringWriter();
                        PrintWriter pw = new PrintWriter(sw);
                        pw.println("PikmiGram Java crash " + new java.util.Date());
                        pw.println(device());
                        pw.println("Thread: " + (t == null ? "?" : t.getName()));
                        pw.println();
                        e.printStackTrace(pw);
                        pw.flush();
                        save(ctx, "PikmiGram-crash-" + System.currentTimeMillis() + ".txt", sw.toString().getBytes("UTF-8"));
                    } catch (Throwable ignore) {
                    }
                    if (prev != null) {
                        prev.uncaughtException(t, e);
                    }
                }
            });
        } catch (Throwable ignore) {
        }
        if (Build.VERSION.SDK_INT >= 30) {
            try {
                readLastExit(ctx);
            } catch (Throwable ignore) {
            }
        }
    }

    private static String device() {
        return "Device: " + Build.MANUFACTURER + " " + Build.MODEL + ", Android " + Build.VERSION.RELEASE + " (API " + Build.VERSION.SDK_INT + ")";
    }

    private static void readLastExit(Context ctx) throws Exception {
        ActivityManager am = (ActivityManager) ctx.getSystemService(Context.ACTIVITY_SERVICE);
        if (am == null) {
            return;
        }
        List<ApplicationExitInfo> list = am.getHistoricalProcessExitReasons(ctx.getPackageName(), 0, 5);
        if (list == null) {
            return;
        }
        SharedPreferences prefs = ctx.getSharedPreferences("pikmigram_crash", Context.MODE_PRIVATE);
        long lastSeen = prefs.getLong("last_exit_ts", 0);
        long newest = lastSeen;
        for (ApplicationExitInfo info : list) {
            long ts = info.getTimestamp();
            if (ts <= lastSeen) {
                continue;
            }
            if (ts > newest) {
                newest = ts;
            }
            int reason = info.getReason();
            if (reason != ApplicationExitInfo.REASON_CRASH
                    && reason != ApplicationExitInfo.REASON_CRASH_NATIVE
                    && reason != ApplicationExitInfo.REASON_ANR
                    && reason != ApplicationExitInfo.REASON_SIGNALED
                    && reason != ApplicationExitInfo.REASON_INITIALIZATION_FAILURE
                    && reason != ApplicationExitInfo.REASON_LOW_MEMORY) {
                continue;
            }
            StringBuilder sb = new StringBuilder();
            sb.append("PikmiGram: причина прошлого вылета\n");
            sb.append(device()).append('\n');
            sb.append("Время: ").append(new java.util.Date(ts)).append('\n');
            sb.append("Причина (код): ").append(reason).append(" (4=Java crash, 5=native crash, 6=ANR, 2=signaled, 3=low memory, 7=init failure)\n");
            sb.append("Статус: ").append(info.getStatus()).append('\n');
            sb.append("Описание: ").append(info.getDescription()).append("\n\n");
            try {
                InputStream is = info.getTraceInputStream();
                if (is != null) {
                    ByteArrayOutputStream bos = new ByteArrayOutputStream();
                    byte[] buf = new byte[8192];
                    int n;
                    int total = 0;
                    while ((n = is.read(buf)) > 0 && total < 600000) {
                        bos.write(buf, 0, n);
                        total += n;
                    }
                    is.close();
                    sb.append("--- текстовые фрагменты трассировки ---\n");
                    byte[] data = bos.toByteArray();
                    StringBuilder run = new StringBuilder();
                    for (int i = 0; i <= data.length; i++) {
                        int b = i < data.length ? (data[i] & 0xff) : 0;
                        if (b >= 32 && b < 127) {
                            run.append((char) b);
                        } else {
                            if (run.length() >= 4) {
                                sb.append(run).append('\n');
                            }
                            run.setLength(0);
                        }
                    }
                }
            } catch (Throwable ignore) {
            }
            save(ctx, "PikmiGram-exit-" + ts + ".txt", sb.toString().getBytes("UTF-8"));
        }
        if (newest > lastSeen) {
            prefs.edit().putLong("last_exit_ts", newest).apply();
        }
    }

    private static void save(Context ctx, String name, byte[] data) throws Exception {
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
