#!/usr/bin/env python3
"""Полноценные страницы клиента вместо окон: шрифты, список теневого бана, эквалайзер, обновления.

Создаёт классы PikmiPage (общая основа: шапка со стрелкой назад, прокрутка, цвета темы),
PikmiFontsPage, PikmiShadowBanPage, PikmiEqualizerPage, PikmiUpdatePage в org.telegram.ui и
перенаправляет пункты меню трёх точек (после pikmi_menu.py) на эти страницы. Идемпотентен.
"""
import sys
from pathlib import Path

UI = Path("TMessagesProj/src/main/java/org/telegram/ui")
DA = UI / "DialogsActivity.java"

BASE = r'''package org.telegram.ui;

import android.content.Context;
import android.graphics.drawable.ColorDrawable;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.telegram.messenger.AndroidUtilities;
import org.telegram.messenger.R;
import org.telegram.ui.ActionBar.ActionBar;
import org.telegram.ui.ActionBar.BaseFragment;
import org.telegram.ui.ActionBar.Theme;

/** Основа страниц PikmiGram: шапка клиента, прокручиваемый список, цвета текущей темы. */
public abstract class PikmiPage extends BaseFragment {

    protected LinearLayout list;
    protected Context ctx;

    protected abstract String pageTitle();

    protected abstract void build();

    @Override
    public View createView(Context context) {
        ctx = context;
        actionBar.setBackButtonImage(R.drawable.ic_ab_back);
        actionBar.setAllowOverlayTitle(true);
        actionBar.setTitle(pageTitle());
        actionBar.setActionBarMenuOnItemClick(new ActionBar.ActionBarMenuOnItemClick() {
            @Override
            public void onItemClick(int id) {
                if (id == -1) {
                    finishFragment();
                }
            }
        });
        FrameLayout frame = new FrameLayout(context);
        frame.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundGray));
        ScrollView scroll = new ScrollView(context);
        list = new LinearLayout(context);
        list.setOrientation(LinearLayout.VERTICAL);
        list.setPadding(0, 0, 0, AndroidUtilities.dp(24));
        scroll.addView(list, new ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        frame.addView(scroll, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        fragmentView = frame;
        build();
        return fragmentView;
    }

    protected int dp(int v) {
        return AndroidUtilities.dp(v);
    }

    protected int cText() {
        return Theme.getColor(Theme.key_windowBackgroundWhiteBlackText);
    }

    protected int cHint() {
        return Theme.getColor(Theme.key_windowBackgroundWhiteGrayText);
    }

    protected int cAccent() {
        return Theme.getColor(Theme.key_windowBackgroundWhiteBlueText);
    }

    protected int cSurface() {
        return Theme.getColor(Theme.key_windowBackgroundWhite);
    }

    /** Серый поясняющий текст между блоками. */
    protected TextView info(String text) {
        TextView t = new TextView(ctx);
        t.setText(text);
        t.setTextSize(13);
        t.setTextColor(cHint());
        t.setPadding(dp(18), dp(12), dp(18), dp(8));
        return t;
    }

    /** Заголовок раздела цветом акцента. */
    protected TextView header(String text) {
        TextView t = new TextView(ctx);
        t.setText(text);
        t.setTextSize(14);
        t.setTextColor(cAccent());
        t.setPadding(dp(18), dp(16), dp(18), dp(6));
        return t;
    }

    /** Белая карточка-контейнер для строк. */
    protected LinearLayout card() {
        LinearLayout c = new LinearLayout(ctx);
        c.setOrientation(LinearLayout.VERTICAL);
        c.setBackgroundColor(cSurface());
        return c;
    }

    /** Строка списка: заголовок, подпись, значение справа. Подпись лежит в getTag() строки. */
    protected LinearLayout row(String title, String subtitle, String right, View.OnClickListener click) {
        LinearLayout r = new LinearLayout(ctx);
        r.setOrientation(LinearLayout.HORIZONTAL);
        r.setGravity(Gravity.CENTER_VERTICAL);
        r.setPadding(dp(18), dp(12), dp(18), dp(12));
        LinearLayout left = new LinearLayout(ctx);
        left.setOrientation(LinearLayout.VERTICAL);
        TextView t = new TextView(ctx);
        t.setText(title);
        t.setTextSize(16);
        t.setTextColor(cText());
        left.addView(t);
        TextView sub = new TextView(ctx);
        sub.setText(subtitle == null ? "" : subtitle);
        sub.setTextSize(13);
        sub.setTextColor(cHint());
        if (subtitle == null || subtitle.length() == 0) {
            sub.setVisibility(View.GONE);
        }
        left.addView(sub);
        r.addView(left, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        TextView val = new TextView(ctx);
        val.setText(right == null ? "" : right);
        val.setTextSize(15);
        val.setTextColor(cAccent());
        r.addView(val);
        r.setTag(new TextView[]{t, sub, val});
        if (click != null) {
            r.setClickable(true);
            r.setBackgroundDrawable(Theme.createSelectorDrawable(Theme.getColor(Theme.key_listSelector), 2, -1));
            r.setOnClickListener(click);
        }
        return r;
    }

    /** Кнопка-строка с акцентным текстом по центру. */
    protected TextView button(String text, View.OnClickListener click) {
        TextView b = new TextView(ctx);
        b.setText(text);
        b.setTextSize(16);
        b.setTextColor(cAccent());
        b.setGravity(Gravity.CENTER);
        b.setPadding(dp(18), dp(14), dp(18), dp(14));
        b.setBackgroundColor(cSurface());
        b.setClickable(true);
        b.setOnClickListener(click);
        return b;
    }

    protected View gap(int heightDp) {
        View v = new View(ctx);
        v.setLayoutParams(new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(heightDp)));
        return v;
    }
}
'''

FONTS = r'''package org.telegram.ui;

import android.view.View;
import android.widget.TextView;
import android.widget.Toast;

import org.telegram.messenger.PikmiFonts;

import java.util.ArrayList;

/** Страница выбора шрифта. */
public class PikmiFontsPage extends PikmiPage {

    @Override
    protected String pageTitle() {
        return "Шрифты";
    }

    @Override
    protected void build() {
        list.removeAllViews();
        list.addView(info("Выбери шрифт. Чтобы он применился во всём приложении, перезапусти его кнопкой внизу."));
        final ArrayList<String> files = new ArrayList<String>();
        files.add("");
        files.addAll(PikmiFonts.available());
        String cur = PikmiFonts.current();
        android.widget.LinearLayout card = card();
        for (int i = 0; i < files.size(); i++) {
            final String f = files.get(i);
            android.widget.LinearLayout r = row(PikmiFonts.nameOf(f), "Привет, милашка ♡ Aa Бб 123", f.equals(cur) ? "✓" : "", new View.OnClickListener() {
                @Override
                public void onClick(View v) {
                    PikmiFonts.select(f);
                    Toast.makeText(ctx, "Шрифт выбран", Toast.LENGTH_SHORT).show();
                    build();
                }
            });
            TextView[] tv = (TextView[]) r.getTag();
            android.graphics.Typeface tf = PikmiFonts.typefaceOf(f);
            tv[0].setTypeface(tf);
            tv[1].setTypeface(tf);
            card.addView(r);
        }
        list.addView(card);
        list.addView(gap(16));
        list.addView(button("Перезапустить приложение", new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                PikmiFonts.restartApp(ctx);
            }
        }));
    }
}
'''

BAN = r'''package org.telegram.ui;

import android.view.View;

import org.telegram.messenger.ShadowBan;
import org.telegram.messenger.UserObject;
import org.telegram.tgnet.TLRPC;

import java.util.ArrayList;

/** Страница со списком теневого бана: нажатие на человека снимает бан. */
public class PikmiShadowBanPage extends PikmiPage {

    @Override
    protected String pageTitle() {
        return "Теневой бан";
    }

    @Override
    protected void build() {
        list.removeAllViews();
        final ArrayList<Long> ids = ShadowBan.getAll();
        if (ids.isEmpty()) {
            list.addView(info("Список пуст. Чтобы добавить человека, нажми и удерживай его сообщение и выбери «Теневой бан»."));
            return;
        }
        list.addView(info("Нажми на человека, чтобы снять теневой бан. После этого переоткрой чат, чтобы увидеть его сообщения."));
        android.widget.LinearLayout card = card();
        for (int i = 0; i < ids.size(); i++) {
            final long id = ids.get(i);
            String name = null;
            try {
                TLRPC.User user = getMessagesController().getUser(id);
                if (user != null) {
                    name = UserObject.getUserName(user);
                }
            } catch (Throwable ignore) {
            }
            if (name == null || name.length() == 0) {
                name = "Пользователь";
            }
            card.addView(row(name, "ID " + id, "Снять", new View.OnClickListener() {
                @Override
                public void onClick(View v) {
                    if (ShadowBan.isBanned(id)) {
                        ShadowBan.toggle(id);
                    }
                    build();
                }
            }));
        }
        list.addView(card);
    }
}
'''

EQ = r'''package org.telegram.ui;

import android.widget.TextView;

import org.telegram.messenger.PikmiEqualizer;

/** Страница эквалайзера. */
public class PikmiEqualizerPage extends PikmiPage {

    @Override
    protected String pageTitle() {
        return "Эквалайзер";
    }

    @Override
    protected void build() {
        list.removeAllViews();
        TextView status = info(PikmiEqualizer.status());
        list.addView(status);
        android.widget.LinearLayout card = card();
        card.addView(PikmiEqualizer.buildContent(ctx, cText(), cHint(), cAccent()));
        list.addView(card);
    }

    @Override
    public void onResume() {
        super.onResume();
    }
}
'''

UPD = r'''package org.telegram.ui;

import android.view.View;
import android.widget.TextView;

import org.telegram.messenger.PikmiUpdater;

/** Страница обновлений: проверка последнего релиза и установка. */
public class PikmiUpdatePage extends PikmiPage {

    private TextView statusView;
    private TextView notesView;
    private TextView installBtn;

    @Override
    protected String pageTitle() {
        return "Обновления";
    }

    @Override
    protected void build() {
        list.removeAllViews();
        list.addView(info("Приложение берёт новые сборки из GitHub Releases вашего репозитория."));
        android.widget.LinearLayout card = card();
        card.addView(row("Текущая сборка", "", String.valueOf(PikmiUpdater.currentBuild()), null));
        card.addView(row("Репозиторий", PikmiUpdater.repo().length() == 0 ? "не задан" : PikmiUpdater.repo(), "", null));
        list.addView(card);

        statusView = info("Проверяю…");
        list.addView(statusView);
        notesView = info("");
        list.addView(notesView);

        installBtn = button("Скачать и установить", null);
        installBtn.setVisibility(View.GONE);
        list.addView(installBtn);
        list.addView(gap(8));
        list.addView(button("Проверить снова", new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                check();
            }
        }));
        check();
    }

    private void check() {
        statusView.setText("Проверяю…");
        notesView.setText("");
        installBtn.setVisibility(View.GONE);
        PikmiUpdater.fetch(getParentActivity(), new PikmiUpdater.Result() {
            @Override
            public void onResult(String error, final String tag, int latest, String body, final String apkUrl) {
                if (statusView == null) {
                    return;
                }
                if (error != null) {
                    statusView.setText("Не удалось проверить: " + error);
                    return;
                }
                if (latest <= PikmiUpdater.currentBuild() || apkUrl == null) {
                    statusView.setText("У тебя последняя версия (сборка " + PikmiUpdater.currentBuild() + ").");
                    return;
                }
                statusView.setText("Доступна новая сборка: " + latest);
                String b = body == null ? "" : body.trim();
                if (b.length() > 1200) {
                    b = b.substring(0, 1200) + "…";
                }
                notesView.setText(b);
                installBtn.setVisibility(View.VISIBLE);
                installBtn.setOnClickListener(new View.OnClickListener() {
                    @Override
                    public void onClick(View v) {
                        PikmiUpdater.install(getParentActivity(), apkUrl, tag);
                    }
                });
            }
        });
    }
}
'''

FILES = {
    "PikmiPage.java": BASE,
    "PikmiFontsPage.java": FONTS,
    "PikmiShadowBanPage.java": BAN,
    "PikmiEqualizerPage.java": EQ,
    "PikmiUpdatePage.java": UPD,
}

REPL = [
    ("org.telegram.messenger.PikmiFonts.showMenu(DialogsActivity.this);", "presentFragment(new PikmiFontsPage());"),
    ("org.telegram.messenger.ShadowBan.showList(DialogsActivity.this);", "presentFragment(new PikmiShadowBanPage());"),
    ("org.telegram.messenger.PikmiEqualizer.showDialog(getParentActivity());", "presentFragment(new PikmiEqualizerPage());"),
    ("org.telegram.messenger.PikmiUpdater.check(getParentActivity(), true);", "presentFragment(new PikmiUpdatePage());"),
]


def die(msg):
    print("ОШИБКА: " + msg)
    sys.exit(1)


if (UI / "PikmiPage.java").exists():
    print("страницы уже созданы")
else:
    UI.mkdir(parents=True, exist_ok=True)
    for name, text in FILES.items():
        (UI / name).write_text(text, encoding="utf-8")
    print("созданы страницы: " + ", ".join(FILES))

if not DA.exists():
    die("не найден DialogsActivity.java")
da = DA.read_text(encoding="utf-8")
done = 0
for old, new in REPL:
    if old in da:
        if da.count(old) != 1:
            die("пункт меню встречается не один раз: " + old)
        da = da.replace(old, new, 1)
        done += 1
if done:
    DA.write_text(da, encoding="utf-8")
print("Готово: пунктов меню переведено на страницы: %d" % done)
if done == 0 and "PikmiFontsPage" not in da:
    die("в DialogsActivity нет пунктов PikmiGram: сначала должен выполниться pikmi_menu.py")
