#!/usr/bin/env python3
"""Встроенный апдейтер PikmiGram (обновления из GitHub Releases этого репозитория).

- создаёт класс PikmiUpdater (проверка релиза, диалог, загрузка и установка APK);
- пункт "PikmiGram: обновления" в меню долгого нажатия на сообщение;
- автопроверка при открытии приложения (не чаще раза в 6 часов), если находится LaunchActivity.onResume;
- разрешение REQUEST_INSTALL_PACKAGES в манифестах.
Номер сборки и репозиторий берутся из GITHUB_RUN_NUMBER и GITHUB_REPOSITORY.
Запускать после pikmi_fonts.py. Идемпотентен.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

J = Path("TMessagesProj/src/main/java/org/telegram")
CA = J / "ui/ChatActivity.java"
LA = J / "ui/LaunchActivity.java"
PU = J / "messenger/PikmiUpdater.java"
MANIFESTS = [Path("TMessagesProj/config/release/AndroidManifest_SDK23.xml"),
             Path("TMessagesProj/config/release/AndroidManifest.xml"),
             Path("TMessagesProj/config/release/AndroidManifest_standalone.xml")]


def die(msg, hint=None):
    print("ОШИБКА: " + msg)
    if hint:
        print("--- подсказка для разработчика ---")
        print(hint)
    sys.exit(1)


repo = os.environ.get("GITHUB_REPOSITORY", "")
build = os.environ.get("GITHUB_RUN_NUMBER", "0")
if not build.isdigit():
    build = "0"

JAVA = r'''package org.telegram.messenger;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.DialogInterface;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.Settings;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;

/** Апдейтер PikmiGram: ищет новый релиз в GitHub Releases и ставит APK. */
public class PikmiUpdater {

    private static final String REPO = "@REPO@";
    private static final int BUILD = @BUILD@;
    private static final String PREFS = "pikmigram_update";
    private static final long CHECK_INTERVAL = 6L * 60 * 60 * 1000;
    private static final String FILE_NAME = "PikmiGram-update.apk";

    private static SharedPreferences prefs(Context c) {
        return c.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    /** Тихая проверка при запуске: не чаще раза в несколько часов. */
    public static void autoCheck(Activity a) {
        try {
            if (a == null || REPO.length() == 0) {
                return;
            }
            SharedPreferences p = prefs(a);
            long now = System.currentTimeMillis();
            if (now - p.getLong("last_check", 0) < CHECK_INTERVAL) {
                return;
            }
            p.edit().putLong("last_check", now).apply();
            check(a, false);
        } catch (Throwable ignore) {
        }
    }

    private static int parseBuild(String tag) {
        if (tag == null) {
            return 0;
        }
        int end = tag.length();
        int start = end;
        while (start > 0 && Character.isDigit(tag.charAt(start - 1))) {
            start--;
        }
        if (start == end) {
            return 0;
        }
        try {
            return Integer.parseInt(tag.substring(start, end));
        } catch (Throwable e) {
            return 0;
        }
    }

    /** Проверка обновления. manual = true: показывать результат, даже если новых версий нет. */
    public static void check(final Activity a, final boolean manual) {
        if (a == null) {
            return;
        }
        if (REPO.length() == 0) {
            if (manual) {
                Toast.makeText(a, "Обновления не настроены в этой сборке", Toast.LENGTH_LONG).show();
            }
            return;
        }
        if (manual) {
            Toast.makeText(a, "Проверяю обновления…", Toast.LENGTH_SHORT).show();
        }
        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    HttpURLConnection c = (HttpURLConnection) new URL("https://api.github.com/repos/" + REPO + "/releases/latest").openConnection();
                    c.setConnectTimeout(10000);
                    c.setReadTimeout(15000);
                    c.setRequestProperty("Accept", "application/vnd.github+json");
                    c.setRequestProperty("User-Agent", "PikmiGram");
                    int code = c.getResponseCode();
                    if (code != 200) {
                        throw new IOException("HTTP " + code);
                    }
                    StringBuilder sb = new StringBuilder();
                    BufferedReader r = new BufferedReader(new InputStreamReader(c.getInputStream(), "UTF-8"));
                    String line;
                    while ((line = r.readLine()) != null) {
                        sb.append(line).append('\n');
                    }
                    r.close();
                    JSONObject o = new JSONObject(sb.toString());
                    final String tag = o.optString("tag_name", "");
                    final String body = o.optString("body", "");
                    final int latest = parseBuild(tag);
                    String apk = null;
                    JSONArray assets = o.optJSONArray("assets");
                    if (assets != null) {
                        for (int i = 0; i < assets.length(); i++) {
                            JSONObject as = assets.getJSONObject(i);
                            if (as.optString("name", "").toLowerCase().endsWith(".apk")) {
                                apk = as.optString("browser_download_url", null);
                                break;
                            }
                        }
                    }
                    final String apkUrl = apk;
                    a.runOnUiThread(new Runnable() {
                        @Override
                        public void run() {
                            onResult(a, manual, tag, latest, body, apkUrl);
                        }
                    });
                } catch (final Throwable e) {
                    if (manual) {
                        a.runOnUiThread(new Runnable() {
                            @Override
                            public void run() {
                                Toast.makeText(a, "Не удалось проверить обновления: " + e.getMessage(), Toast.LENGTH_LONG).show();
                            }
                        });
                    }
                }
            }
        }).start();
    }

    private static void onResult(final Activity a, boolean manual, final String tag, int latest, String body, final String apkUrl) {
        if (a.isFinishing()) {
            return;
        }
        if (latest <= BUILD || apkUrl == null) {
            if (manual) {
                Toast.makeText(a, "У тебя последняя версия (сборка " + BUILD + ")", Toast.LENGTH_LONG).show();
            }
            return;
        }
        if (!manual && tag.equals(prefs(a).getString("skip_tag", ""))) {
            return;
        }
        String text = "Новая сборка: " + latest + "\nУ тебя: " + BUILD;
        if (body != null && body.trim().length() > 0) {
            String b = body.trim();
            if (b.length() > 800) {
                b = b.substring(0, 800) + "…";
            }
            text += "\n\n" + b;
        }
        new AlertDialog.Builder(a)
                .setTitle("Доступно обновление PikmiGram")
                .setMessage(text)
                .setPositiveButton("Обновить", new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface dialog, int which) {
                        download(a, apkUrl, tag);
                    }
                })
                .setNeutralButton("Пропустить версию", new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface dialog, int which) {
                        prefs(a).edit().putString("skip_tag", tag).apply();
                    }
                })
                .setNegativeButton("Позже", null)
                .show();
    }

    private static void download(final Activity a, String url, String tag) {
        try {
            if (Build.VERSION.SDK_INT >= 26 && !a.getPackageManager().canRequestPackageInstalls()) {
                Toast.makeText(a, "Разреши установку из этого приложения, затем снова нажми «Обновить»", Toast.LENGTH_LONG).show();
                Intent i = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + a.getPackageName()));
                a.startActivity(i);
                return;
            }
            final Context ctx = a.getApplicationContext();
            final DownloadManager dm = (DownloadManager) ctx.getSystemService(Context.DOWNLOAD_SERVICE);
            File old = new File(ctx.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS), FILE_NAME);
            if (old.exists()) {
                old.delete();
            }
            DownloadManager.Request req = new DownloadManager.Request(Uri.parse(url));
            req.setTitle("PikmiGram " + tag);
            req.setDescription("Загрузка обновления");
            req.setMimeType("application/vnd.android.package-archive");
            req.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            req.setDestinationInExternalFilesDir(ctx, Environment.DIRECTORY_DOWNLOADS, FILE_NAME);
            final long[] ids = new long[1];
            final BroadcastReceiver receiver = new BroadcastReceiver() {
                @Override
                public void onReceive(Context context, Intent intent) {
                    long id = intent.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1);
                    if (id != ids[0]) {
                        return;
                    }
                    try {
                        context.getApplicationContext().unregisterReceiver(this);
                    } catch (Throwable ignore) {
                    }
                    Uri uri = dm.getUriForDownloadedFile(id);
                    if (uri == null) {
                        Toast.makeText(context, "Не удалось скачать обновление", Toast.LENGTH_LONG).show();
                        return;
                    }
                    Intent install = new Intent(Intent.ACTION_VIEW);
                    install.setDataAndType(uri, "application/vnd.android.package-archive");
                    install.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
                    context.startActivity(install);
                }
            };
            IntentFilter filter = new IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE);
            if (Build.VERSION.SDK_INT >= 33) {
                ctx.registerReceiver(receiver, filter, Context.RECEIVER_EXPORTED);
            } else {
                ctx.registerReceiver(receiver, filter);
            }
            ids[0] = dm.enqueue(req);
            Toast.makeText(a, "Скачиваю обновление, смотри уведомление", Toast.LENGTH_LONG).show();
        } catch (Throwable e) {
            Toast.makeText(a, "Ошибка загрузки: " + e.getMessage(), Toast.LENGTH_LONG).show();
        }
    }
}
'''


def grep(pattern, path, n=15):
    r = subprocess.run(["grep", "-n", "-E", pattern, str(path)], capture_output=True, text=True)
    return "\n".join(r.stdout.splitlines()[:n])


if not CA.exists():
    die("не найден ChatActivity.java")
ca = CA.read_text(encoding="utf-8")
if "PikmiUpdater" in ca:
    print("уже применено")
    sys.exit(0)
if "OPTION_PIKMI_FONTS" not in ca:
    die("в ChatActivity нет OPTION_PIKMI_FONTS: сначала должен выполниться pikmi_fonts.py")

# ---------- класс ----------
PU.write_text(JAVA.replace("@REPO@", repo).replace("@BUILD@", build), encoding="utf-8")
print("PikmiUpdater.java: репозиторий '%s', сборка %s" % (repo, build))


def sub1(text, pattern, repl, what):
    rx = re.compile(pattern, re.S)
    if len(rx.findall(text)) != 1:
        die("ChatActivity: %s не найдено ровно один раз" % what)
    return rx.sub(repl, text, count=1)


ca = sub1(ca, r"(public final static int OPTION_PIKMI_FONTS = 202;)",
          lambda m: m.group(1) + "\n    public final static int OPTION_PIKMI_UPDATE = 203;", "константа")
ca = sub1(ca, r"(options\.add\(OPTION_PIKMI_FONTS\);\s*icons\.add\(R\.drawable\.msg_edit\);\s*\})",
          lambda m: m.group(1) + '''
            if (selectedObject != null) {
                items.add("PikmiGram: обновления");
                options.add(OPTION_PIKMI_UPDATE);
                icons.add(R.drawable.msg_edit);
            }''', "пункт меню")
ca = sub1(ca, r"(case OPTION_PIKMI_FONTS:\s*\{)",
          lambda m: '''case OPTION_PIKMI_UPDATE: {
                org.telegram.messenger.PikmiUpdater.check(getParentActivity(), true);
                break;
            }
            ''' + m.group(1), "обработчик")
CA.write_text(ca, encoding="utf-8")
print("ChatActivity: пункт 'PikmiGram: обновления' добавлен")

# ---------- автопроверка при запуске (необязательно) ----------
if LA.exists():
    la = LA.read_text(encoding="utf-8")
    rx = re.compile(r"(protected void onResume\(\) \{\s*super\.onResume\(\);)")
    if len(rx.findall(la)) == 1:
        la = rx.sub(lambda m: m.group(1) + "\n        org.telegram.messenger.PikmiUpdater.autoCheck(this);", la, count=1)
        LA.write_text(la, encoding="utf-8")
        print("LaunchActivity.onResume: автопроверка добавлена")
    else:
        print("пропуск автопроверки: LaunchActivity.onResume не найден (проверка останется ручной)")
        print(grep(r"void onResume\(", LA, 5))
else:
    print("пропуск автопроверки: LaunchActivity.java не найден")

# ---------- разрешение на установку APK ----------
PERM = '<uses-permission android:name="android.permission.REQUEST_INSTALL_PACKAGES" />'
patched = 0
for mf in MANIFESTS:
    if not mf.exists():
        continue
    t = mf.read_text(encoding="utf-8")
    if "REQUEST_INSTALL_PACKAGES" in t:
        continue
    m = re.search(r"(\n[ \t]*)<application\b", t)
    if not m:
        print("предупреждение: в %s нет <application>, разрешение не добавлено" % mf)
        continue
    t = t[:m.start()] + m.group(1) + PERM + t[m.start():]
    mf.write_text(t, encoding="utf-8")
    patched += 1
print("манифесты: разрешение добавлено в %d файл(ов)" % patched)
print("Готово: апдейтер")
