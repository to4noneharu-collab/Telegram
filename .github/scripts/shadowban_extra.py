#!/usr/bin/env python3
"""Теневой бан: скрывает забаненных в "печатает", "просмотрели", реакциях и превью ответов.

Запускается из корня репозитория после shadowban_list.py. Идемпотентен.
Если ожидаемый код не найден, завершается с ошибкой сразу (до долгой сборки).
"""
import re
import sys
from pathlib import Path

J = Path("TMessagesProj/src/main/java/org/telegram")
MC = J / "messenger/MessagesController.java"
MO = J / "messenger/MessageObject.java"
SEEN = J / "ui/MessageSeenView.java"
RHEAD = J / "ui/Components/ReactedHeaderView.java"
RLIST = J / "ui/Components/ReactedUsersListView.java"
SB = J / "messenger/ShadowBan.java"

MARK = "SHADOWBAN_EXTRA_APPLIED"
BAN = "org.telegram.messenger.ShadowBan"


def die(msg):
    print("ОШИБКА: " + msg)
    sys.exit(1)


def read(p):
    if not p.exists():
        die("не найден файл " + str(p))
    return p.read_text(encoding="utf-8")


def sub(text, pattern, repl, what, expect=1, optional=False):
    """Заменяет по regex; ожидает ровно expect совпадений (или >=1, если expect=None)."""
    rx = re.compile(pattern, re.S)
    n = len(rx.findall(text))
    if n == 0 and optional:
        print("  пропуск (не найдено): " + what)
        return text
    if n == 0 or (expect is not None and n != expect):
        die("%s: найдено %d совпадений, ожидалось %s" % (what, n, expect if expect is not None else ">=1"))
    print("  ok: " + what)
    return rx.sub(repl, text)


sb = read(SB)
if "count()" not in sb:
    die("в ShadowBan.java нет count(): сначала должен выполниться shadowban_list.py")
mo = read(MO)
if MARK in mo:
    print("уже применено")
    sys.exit(0)

# ---------- 1. "Печатает..." ----------
print("MessagesController (печатает)")
mc = read(MC)
mc = sub(
    mc,
    r"(importingActions\.put\(uid, importAction\.progress\);\s*\}\s*else if \(userId != getUserConfig\(\)\.getClientUserId\(\))\) \{",
    lambda m: m.group(1) + " && !" + BAN + ".isBanned(userId)) {",
    "typing: пропуск забаненных",
)
MC.write_text(mc, encoding="utf-8")

# ---------- 2. "Просмотрели" ----------
print("MessageSeenView (просмотрели)")
seen = read(SEEN)
seen = sub(
    seen,
    r"if \(finalFromId == peerId\) \{",
    "if (finalFromId == peerId || " + BAN + ".isBanned(peerId)) {",
    "seen: пропуск забаненных",
    expect=2,
)
SEEN.write_text(seen, encoding="utf-8")

print("ReactedHeaderView (просмотрели/реакции в меню)")
rh = read(RHEAD)
rh = sub(rh, r"if \(fromId != l\) \{", "if (fromId != l && !" + BAN + ".isBanned(l)) {", "header: Long id")
rh = sub(rh, r"if \(fromId != userId\) \{", "if (fromId != userId && !" + BAN + ".isBanned(userId)) {", "header: participant id")
rh = sub(
    rh,
    r"(for \(TLRPC\.User u : list\.users\) \{\s*if \(message\.messageOwner\.from_id != null && u\.id != message\.messageOwner\.from_id\.user_id)\) \{",
    lambda m: m.group(1) + " && !" + BAN + ".isBanned(u.id)) {",
    "header: реакции пользователей",
)
RHEAD.write_text(rh, encoding="utf-8")

print("ReactedUsersListView (список реакций)")
rl = read(RLIST)
rl = sub(
    rl,
    r"(for \(int i = 0; i < res\.reactions\.size\(\); i\+\+\) \{)(\s*)(userReactions\.add\(res\.reactions\.get\(i\)\);)",
    lambda m: m.group(1) + m.group(2) + "if (" + BAN + ".isBanned(MessageObject.getPeerId(res.reactions.get(i).peer_id))) {" + m.group(2) + "    continue;" + m.group(2) + "}" + m.group(2) + m.group(3),
    "reactions list: пропуск забаненных",
)
RLIST.write_text(rl, encoding="utf-8")

# ---------- 3. MessageObject: ответы и реакции ----------
print("MessageObject (ответы, реакции)")
mo = sub(
    mo,
    r"return !\(replyMessageObject != null && replyMessageObject\.messageOwner instanceof TLRPC\.TL_messageEmpty\) && messageOwner\.reply_to != null && \(messageOwner\.reply_to\.reply_to_msg_id != 0",
    lambda m: "return !" + BAN + ".isBanned(replyMessageObject) && " + m.group(0)[len("return "):],
    "isReply(): не показывать ответ на забаненного",
)
mo = sub(
    mo,
    r"return !\(replyMessageObject == null \|\| replyMessageObject\.messageOwner instanceof TLRPC\.TL_messageEmpty \|\|",
    "return !(replyMessageObject == null || " + BAN + ".isBanned(replyMessageObject) || replyMessageObject.messageOwner instanceof TLRPC.TL_messageEmpty ||",
    "hasValidReplyMessageObject()",
)
mo = sub(
    mo,
    r"if \(replyMessageObject == null \|\| replyMessageObject\.messageOwner instanceof TLRPC\.TL_messageEmpty \|\| replyMessageObject\.messageOwner\.action instanceof TLRPC\.TL_messageActionHistoryClear\) \{",
    "if (replyMessageObject == null || " + BAN + ".isBanned(replyMessageObject) || replyMessageObject.messageOwner instanceof TLRPC.TL_messageEmpty || replyMessageObject.messageOwner.action instanceof TLRPC.TL_messageActionHistoryClear) {",
    "текст закрепа: не показывать текст забаненного",
    optional=True,
)

method = '''public MessageObject replyMessageObject;

    // SHADOWBAN_EXTRA_APPLIED: убирает реакции забаненных пользователей и их вклад в счётчики
    private static boolean shadowSameReaction(TLRPC.Reaction a, TLRPC.Reaction b) {
        if (a instanceof TLRPC.TL_reactionEmoji && b instanceof TLRPC.TL_reactionEmoji) {
            String x = ((TLRPC.TL_reactionEmoji) a).emoticon;
            String y = ((TLRPC.TL_reactionEmoji) b).emoticon;
            return x != null && x.equals(y);
        }
        if (a instanceof TLRPC.TL_reactionCustomEmoji && b instanceof TLRPC.TL_reactionCustomEmoji) {
            return ((TLRPC.TL_reactionCustomEmoji) a).document_id == ((TLRPC.TL_reactionCustomEmoji) b).document_id;
        }
        return false;
    }

    public void shadowSanitizeReactions() {
        if (messageOwner == null || messageOwner.reactions == null || org.telegram.messenger.ShadowBan.count() == 0) {
            return;
        }
        java.util.List<TLRPC.MessagePeerReaction> recent = messageOwner.reactions.recent_reactions;
        java.util.List<TLRPC.ReactionCount> results = messageOwner.reactions.results;
        if (recent != null && results != null) {
            for (int i = recent.size() - 1; i >= 0; i--) {
                TLRPC.MessagePeerReaction pr = recent.get(i);
                if (!org.telegram.messenger.ShadowBan.isBanned(MessageObject.getPeerId(pr.peer_id))) {
                    continue;
                }
                recent.remove(i);
                for (int k = 0; k < results.size(); k++) {
                    TLRPC.ReactionCount rc = results.get(k);
                    if (shadowSameReaction(rc.reaction, pr.reaction)) {
                        rc.count--;
                        if (rc.count <= 0) {
                            results.remove(k);
                        }
                        break;
                    }
                }
            }
        }
        long did = messageOwner.dialog_id != 0 ? messageOwner.dialog_id : getDialogId();
        if (results != null && did > 0 && org.telegram.messenger.ShadowBan.isBanned(did)) {
            // личный чат с забаненным: убираем его реакции, оставляем только наши
            for (int i = results.size() - 1; i >= 0; i--) {
                TLRPC.ReactionCount rc = results.get(i);
                if (!rc.chosen) {
                    results.remove(i);
                } else if (rc.count > 1) {
                    rc.count = 1;
                }
            }
        }
    }'''
mo = sub(mo, r"public MessageObject replyMessageObject;", lambda m: method, "метод shadowSanitizeReactions")
mo = sub(
    mo,
    r"(wasUnread = !messageOwner\.out && messageOwner\.unread;)",
    lambda m: m.group(1) + "\n        shadowSanitizeReactions();",
    "вызов в конструкторе",
    expect=None,
)
MO.write_text(mo, encoding="utf-8")
print("Готово: скрытие забаненных применено")
