#!/usr/bin/env python3
"""Сохраняет одноразовые фото/видео в галерею (Pictures/PikmiGram), не меняя поведение
для отправителя: просмотр засчитывается и удаление у него срабатывает как обычно.

Перехватывает момент прямо перед SecretMediaViewer.openMedia(...): к этому моменту файл
уже скачан и будет показан, поэтому копия snapshot'ится в тот же миг, без влияния на
исходную логику показа/удаления. Идемпотентен.
"""
import re
import sys
from pathlib import Path

CA = Path("TMessagesProj/src/main/java/org/telegram/ui/ChatActivity.java")

JAVA = r'''package org.telegram.messenger;

import android.content.ContentValues;
import android.content.Context;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.MediaStore;

import org.telegram.tgnet.TLRPC;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.OutputStream;

/** Сохраняет одноразовые фото/видео в галерею в момент просмотра. */
public class PikmiSaveMedia {

    public static void save(final int currentAccount, final TLRPC.Message message) {
        if (message == null || ApplicationLoader.applicationContext == null) {
            return;
        }
        Utilities.globalQueue.postRunnable(new Runnable() {
            @Override
            public void run() {
                try {
                    File src = FileLoader.getInstance(currentAccount).getPathToMessage(message);
                    if (src == null || !src.exists() || src.length() == 0) {
                        return;
                    }
                    boolean isVideo = MessageObject.isVideoMessage(message) || MessageObject.isGifMessage(message) || MessageObject.isRoundVideoMessage(message);
                    String ext = isVideo ? "mp4" : "jpg";
                    String name = "PikmiGram_" + message.dialog_id + "_" + message.id + "_" + System.currentTimeMillis() + "." + ext;
                    copyToGallery(ApplicationLoader.applicationContext, src, name, isVideo);
                } catch (Throwable ignore) {
                }
            }
        });
    }

    private static void copyToGallery(Context ctx, File src, String name, boolean isVideo) throws Exception {
        if (Build.VERSION.SDK_INT >= 29) {
            ContentValues v = new ContentValues();
            v.put(MediaStore.MediaColumns.DISPLAY_NAME, name);
            v.put(MediaStore.MediaColumns.MIME_TYPE, isVideo ? "video/mp4" : "image/jpeg");
            v.put(MediaStore.MediaColumns.RELATIVE_PATH, (isVideo ? Environment.DIRECTORY_MOVIES : Environment.DIRECTORY_PICTURES) + "/PikmiGram");
            Uri collection = isVideo ? MediaStore.Video.Media.EXTERNAL_CONTENT_URI : MediaStore.Images.Media.EXTERNAL_CONTENT_URI;
            Uri uri = ctx.getContentResolver().insert(collection, v);
            if (uri != null) {
                OutputStream os = ctx.getContentResolver().openOutputStream(uri);
                if (os != null) {
                    copy(src, os);
                    return;
                }
            }
        }
        File dir = new File(Environment.getExternalStoragePublicDirectory(isVideo ? Environment.DIRECTORY_MOVIES : Environment.DIRECTORY_PICTURES), "PikmiGram");
        dir.mkdirs();
        FileOutputStream fo = new FileOutputStream(new File(dir, name));
        copy(src, fo);
    }

    private static void copy(File src, OutputStream os) throws Exception {
        FileInputStream is = new FileInputStream(src);
        byte[] buf = new byte[65536];
        int n;
        while ((n = is.read(buf)) > 0) {
            os.write(buf, 0, n);
        }
        is.close();
        os.close();
    }
}
'''


def die(msg, hint=None):
    print("ОШИБКА: " + msg)
    if hint:
        print("--- подсказка для разработчика ---")
        print(hint)
    sys.exit(1)


if not CA.exists():
    die("не найден ChatActivity.java")
ca = CA.read_text(encoding="utf-8")
if "PikmiSaveMedia" in ca:
    print("уже применено")
    sys.exit(0)

PERM = Path("TMessagesProj/src/main/java/org/telegram/messenger/PikmiSaveMedia.java")
PERM.parent.mkdir(parents=True, exist_ok=True)
PERM.write_text(JAVA, encoding="utf-8")
print("PikmiSaveMedia.java: создан")

rx = re.compile(
    r"(SecretMediaViewer\.getInstance\(\)\.setParentActivity\(getParentActivity\(\)\);\s*"
    r"SecretMediaViewer\.getInstance\(\)\.openMedia\(message, photoViewerProvider, openAction, closeAction\);)"
)
n = len(rx.findall(ca))
if n != 1:
    die("ChatActivity: не нашёл вызов SecretMediaViewer.openMedia в ожидаемом виде",
        __import__("subprocess").run("grep -n 'SecretMediaViewer' %s" % CA, shell=True, capture_output=True, text=True).stdout)
ca = rx.sub(lambda m: "org.telegram.messenger.PikmiSaveMedia.save(currentAccount, message.messageOwner); // PG_SAVE_MEDIA\n                " + m.group(1), ca, count=1)
CA.write_text(ca, encoding="utf-8")
print("Готово: одноразовые фото/видео сохраняются при просмотре (Pictures/PikmiGram, Movies/PikmiGram)")

# ---------- кружки и голосовые (round/voice once) ----------
ca2 = CA.read_text(encoding="utf-8")
anchor2 = (
    "                secretVoicePlayer = new SecretVoicePlayer(getContext());\n"
    "                secretVoicePlayer.setCell("
)
if anchor2 not in ca2:
    die("ChatActivity: не нашёл точку воспроизведения кружка/голосового once",
        __import__("subprocess").run("grep -n 'SecretVoicePlayer' %s" % CA, shell=True, capture_output=True, text=True).stdout)
if ca2.count(anchor2) != 1:
    die("ChatActivity: точка воспроизведения кружка/голосового once встречается не один раз")
ca2 = ca2.replace(
    anchor2,
    "                org.telegram.messenger.PikmiSaveMedia.save(currentAccount, messageObject.messageOwner); // PG_SAVE_MEDIA\n" + anchor2,
    1,
)
CA.write_text(ca2, encoding="utf-8")
print("Готово: одноразовые кружки и голосовые тоже сохраняются при просмотре")
