#!/usr/bin/env python3
"""Добавляет кнопку «Pikmi: Имитация» в контекстное меню голосовых и кружков
(включая одноразовые). Логика как у обычной «Переслать»: выбор чата, но вместо
пересылки — имитация записи (typing record → upload) и отправка медиа как своего
voice_note / video_note (без заголовка пересылки).

Идемпотентен.
"""
import re
import sys
from pathlib import Path

CA = Path("TMessagesProj/src/main/java/org/telegram/ui/ChatActivity.java")
HELPER = Path("TMessagesProj/src/main/java/org/telegram/messenger/PikmiForwardAsOwn.java")

JAVA_HELPER = r'''package org.telegram.messenger;

import org.telegram.tgnet.TLRPC;

import java.io.File;

/**
 * Отправляет чужой кружок / голосовое как своё с имитацией записи.
 * Используется кнопкой «Pikmi: Имитация».
 */
public class PikmiForwardAsOwn {

    public static void send(final int currentAccount, final MessageObject messageObject, final long dialogId, final long topicId) {
        if (messageObject == null || dialogId == 0) {
            return;
        }
        final boolean isRound = messageObject.isRoundVideo();
        final boolean isVoice = messageObject.isVoice();
        if (!isRound && !isVoice) {
            return;
        }

        final TLRPC.Document document = messageObject.getDocument();
        if (document == null) {
            return;
        }

        File src = FileLoader.getInstance(currentAccount).getPathToMessage(messageObject.messageOwner);
        if (src == null || !src.exists() || src.length() == 0) {
            // Пробуем подгрузить
            FileLoader.getInstance(currentAccount).loadFile(document, messageObject, FileLoader.PRIORITY_HIGH, 0);
            src = FileLoader.getInstance(currentAccount).getPathToMessage(messageObject.messageOwner);
            if (src == null || !src.exists() || src.length() == 0) {
                AndroidUtilities.runOnUIThread(() -> {
                    if (ApplicationLoader.applicationContext != null) {
                        android.widget.Toast.makeText(ApplicationLoader.applicationContext,
                                "Файл ещё не скачан, подождите и попробуйте снова", android.widget.Toast.LENGTH_SHORT).show();
                    }
                });
                return;
            }
        }
        final File file = src;
        final String path = file.getAbsolutePath();

        int durationSec = 3;
        if (document.attributes != null) {
            for (int i = 0; i < document.attributes.size(); i++) {
                TLRPC.DocumentAttribute attr = document.attributes.get(i);
                if (attr instanceof TLRPC.TL_documentAttributeAudio) {
                    durationSec = Math.max(1, ((TLRPC.TL_documentAttributeAudio) attr).duration);
                    break;
                } else if (attr instanceof TLRPC.TL_documentAttributeVideo) {
                    durationSec = Math.max(1, (int) ((TLRPC.TL_documentAttributeVideo) attr).duration);
                    break;
                }
            }
        }
        final int durationMs = Math.min(durationSec * 1000, 60000); // safety cap

        final MessagesController mc = MessagesController.getInstance(currentAccount);
        final int recordAction = isRound ? 7 : 1;   // 7 = RecordRound, 1 = RecordAudio
        final int uploadAction = isRound ? 8 : 9;   // 8 = UploadRound, 9 = UploadAudio

        // 1. Имитация записи
        mc.sendTyping(dialogId, topicId, recordAction, 0);

        AndroidUtilities.runOnUIThread(() -> {
            // 2. Имитация выгрузки
            mc.sendTyping(dialogId, topicId, uploadAction, 0);

            AndroidUtilities.runOnUIThread(() -> {
                try {
                    TLRPC.TL_document doc = (TLRPC.TL_document) document;
                    SendMessagesHelper.SendMessageParams params = SendMessagesHelper.SendMessageParams.of(
                            doc,
                            null,           // videoEditedInfo
                            path,
                            dialogId,
                            null,           // replyToMsg
                            null,           // replyToTopMsg
                            null,           // caption
                            null,           // entities
                            null,           // replyMarkup
                            null,           // params
                            true,           // notify
                            0,              // scheduleDate
                            0,              // scheduleRepeatPeriod
                            0,              // ttl
                            null,           // parentObject
                            null,           // sendAnimationData
                            false           // updateStickersOrder
                    );
                    SendMessagesHelper.getInstance(currentAccount).sendMessage(params);
                } catch (Throwable e) {
                    FileLog.e(e);
                    AndroidUtilities.runOnUIThread(() -> {
                        if (ApplicationLoader.applicationContext != null) {
                            android.widget.Toast.makeText(ApplicationLoader.applicationContext,
                                    "Ошибка отправки: " + e.getMessage(), android.widget.Toast.LENGTH_SHORT).show();
                        }
                    });
                }
            }, 600);
        }, Math.max(1200, durationMs));
    }
}
'''


def die(msg, hint=None):
    print("ОШИБКА: " + msg)
    if hint:
        print("--- подсказка для разработчика ---")
        print(hint)
    sys.exit(1)


def main():
    if not CA.exists():
        die("не найден ChatActivity.java")

    ca = CA.read_text(encoding="utf-8")
    if "PG_FORWARD_AS_OWN" in ca or "OPTION_FORWARD_AS_OWN" in ca:
        print("уже применено")
        # всё равно перезапишем хелпер на случай обновления
        HELPER.parent.mkdir(parents=True, exist_ok=True)
        HELPER.write_text(JAVA_HELPER, encoding="utf-8")
        print("PikmiForwardAsOwn.java обновлён")
        return

    # ---------- 1. Константа OPTION ----------
    rx_const = re.compile(r"(public final static int OPTION_SHADOW_BAN = 200;)")
    n = len(rx_const.findall(ca))
    if n != 1:
        die("ChatActivity: не нашёл OPTION_SHADOW_BAN",
            __import__("subprocess").run("grep -n 'OPTION_SHADOW_BAN' %s" % CA, shell=True, capture_output=True, text=True).stdout)
    ca = rx_const.sub(
        r"\1\n    public final static int OPTION_FORWARD_AS_OWN = 201; // PG_FORWARD_AS_OWN",
        ca, count=1
    )

    # ---------- 2. Поле-флаг ----------
    rx_field = re.compile(r"(private MessageObject forwardingMessage;)")
    n = len(rx_field.findall(ca))
    if n != 1:
        die("ChatActivity: не нашёл поле forwardingMessage")
    ca = rx_field.sub(
        r"\1\n    private boolean forwardAsOwnMedia; // PG_FORWARD_AS_OWN",
        ca, count=1
    )

    # ---------- 3. Кнопка в меню (только для voice / round, включая once) ----------
    # Вставляем сразу после блока if (canForward) { ... Forward ... }
    anchor_menu = (
        "                if (canForward) {\n"
        "                    items.add(LocaleController.getString(R.string.Forward));\n"
        "                    options.add(OPTION_FORWARD);\n"
        "                    icons.add(R.drawable.msg_forward);\n"
        "                }"
    )
    if anchor_menu not in ca:
        die("ChatActivity: не нашёл блок canForward + Forward",
            __import__("subprocess").run("grep -n 'canForward' %s | head -5" % CA, shell=True, capture_output=True, text=True).stdout)

    insert_menu = '''
                if (canForward && selectedObject != null && (selectedObject.isVoice() || selectedObject.isRoundVideo())) {
                    items.add("Pikmi: Имитация"); // PG_FORWARD_AS_OWN
                    options.add(OPTION_FORWARD_AS_OWN);
                    icons.add(R.drawable.msg_forward);
                }'''
    ca = ca.replace(anchor_menu, anchor_menu + insert_menu, 1)

    # ---------- 4. Обработка OPTION_FORWARD_AS_OWN в processSelectedOption ----------
    # Вставляем case сразу после case OPTION_FORWARD
    rx_case = re.compile(
        r"(case OPTION_FORWARD: \{\s*"
        r"if \(getMessagesController\(\)\.isFrozen\(\)\) \{\s*"
        r"AccountFrozenAlert\.show\(currentAccount\);\s*"
        r"selectedObject = null;\s*"
        r"selectedObjectToEditCaption = null;\s*"
        r"selectedObjectGroup = null;\s*"
        r"return;\s*"
        r"\}\s*"
        r"forwardingMessage = selectedObject;\s*"
        r"forwardingMessageGroup = selectedObjectGroup;\s*"
        r"Bundle args = new Bundle\(\);\s*"
        r"args\.putBoolean\(\"onlySelect\", true\);\s*"
        r"args\.putInt\(\"dialogsType\", DialogsActivity\.DIALOGS_TYPE_FORWARD\);\s*"
        r"args\.putInt\(\"messagesCount\", 1\);.*?presentFragment\(fragment\);\s*"
        r"break;\s*"
        r"\})",
        re.DOTALL
    )
    m = rx_case.search(ca)
    if not m:
        die("ChatActivity: не нашёл case OPTION_FORWARD целиком",
            __import__("subprocess").run("grep -n 'case OPTION_FORWARD' %s" % CA, shell=True, capture_output=True, text=True).stdout)

    insert_case = '''
            case OPTION_FORWARD_AS_OWN: { // PG_FORWARD_AS_OWN
                if (getMessagesController().isFrozen()) {
                    AccountFrozenAlert.show(currentAccount);
                    selectedObject = null;
                    selectedObjectToEditCaption = null;
                    selectedObjectGroup = null;
                    return;
                }
                if (selectedObject == null || (!selectedObject.isVoice() && !selectedObject.isRoundVideo())) {
                    selectedObject = null;
                    selectedObjectGroup = null;
                    return;
                }
                forwardAsOwnMedia = true;
                forwardingMessage = selectedObject;
                forwardingMessageGroup = null;
                Bundle args = new Bundle();
                args.putBoolean("onlySelect", true);
                args.putInt("dialogsType", DialogsActivity.DIALOGS_TYPE_FORWARD);
                args.putInt("messagesCount", 1);
                args.putBoolean("canSelectTopics", true);
                DialogsActivity fragment = new DialogsActivity(args);
                fragment.setDelegate(this);
                presentFragment(fragment);
                break;
            }'''
    ca = ca[:m.end()] + insert_case + ca[m.end():]

    # ---------- 5. Обработка в didSelectDialogs ----------
    # Вставляем в самое начало метода, сразу после сигнатуры и первой проверки
    rx_did = re.compile(
        r"(public boolean didSelectDialogs\(DialogsActivity fragment, ArrayList<MessagesStorage\.TopicKey> dids, CharSequence message, boolean param, boolean notify, int scheduleDate, int scheduleRepeatPeriod, TopicsFragment topicsFragment\) \{\s*"
        r"if \(\(messagePreviewParams == null && \(!fragment\.isQuote \|\| replyingMessageObject == null\) \|\| fragment\.isQuote && replyingMessageObject == null\) && forwardingMessage == null && selectedMessagesIds\[0\]\.size\(\) == 0 && selectedMessagesIds\[1\]\.size\(\) == 0\) \{\s*"
        r"return false;\s*"
        r"\})"
    )
    m = rx_did.search(ca)
    if not m:
        die("ChatActivity: не нашёл начало didSelectDialogs",
            __import__("subprocess").run("grep -n 'didSelectDialogs' %s" % CA, shell=True, capture_output=True, text=True).stdout)

    insert_did = '''
        if (forwardAsOwnMedia && forwardingMessage != null) { // PG_FORWARD_AS_OWN
            forwardAsOwnMedia = false;
            final MessageObject msg = forwardingMessage;
            forwardingMessage = null;
            forwardingMessageGroup = null;
            for (int i = 0; i < dids.size(); i++) {
                MessagesStorage.TopicKey tk = dids.get(i);
                org.telegram.messenger.PikmiForwardAsOwn.send(currentAccount, msg, tk.dialogId, tk.topicId);
            }
            if (fragment != null && fragment.resetDelegate) {
                fragment.setDelegate(null);
            }
            return true;
        }'''
    ca = ca[:m.end()] + insert_did + ca[m.end():]

    # ---------- 6. Записываем хелпер ----------
    HELPER.parent.mkdir(parents=True, exist_ok=True)
    HELPER.write_text(JAVA_HELPER, encoding="utf-8")
    print("PikmiForwardAsOwn.java: создан")

    CA.write_text(ca, encoding="utf-8")
    print("Готово: кнопка «Pikmi: Имитация» добавлена для голосовых и кружков (включая once)")


if __name__ == "__main__":
    main()
