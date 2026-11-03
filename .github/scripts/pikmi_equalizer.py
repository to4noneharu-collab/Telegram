#!/usr/bin/env python3
"""Эквалайзер PikmiGram: окно настроек + аудиоэффекты Android.

Создаёт класс PikmiEqualizer (10 пресетов, полосы эквалайзера, усиление басов, виртуализатор,
громкость), сохраняет настройки и применяет их к плееру, как только известен идентификатор
аудиосессии. Окно открывается из меню трёх точек (pikmi_menu.py).
Подключение к плееру (attach) делает отдельный шаг pikmi_equalizer_hook.py.
Идемпотентен.
"""
import sys
from pathlib import Path

PE = Path("TMessagesProj/src/main/java/org/telegram/messenger/PikmiEqualizer.java")

JAVA = r'''package org.telegram.messenger;

import android.app.Activity;
import android.content.Context;
import android.content.DialogInterface;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.media.audiofx.BassBoost;
import android.media.audiofx.Equalizer;
import android.media.audiofx.LoudnessEnhancer;
import android.media.audiofx.Virtualizer;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.Spinner;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;

/** Эквалайзер: полосы, басы, виртуализатор, усиление громкости. Настройки сохраняются. */
public class PikmiEqualizer {

    private static final String PREFS = "pikmigram_eq";

    private static final String[] PRESET_NAMES = {
            "Ровный", "Басы", "Высокие", "Вокал", "Рок", "Поп", "Джаз", "Классика", "Танцы", "Ночной режим"
    };
    // профиль в децибелах для 5 условных точек частотного диапазона (низ ... верх), дальше интерполируется под любое число полос
    private static final float[][] PRESETS = {
            {0, 0, 0, 0, 0},
            {7, 5, 1, 0, 0},
            {0, 0, 1, 5, 7},
            {-2, 0, 5, 3, -1},
            {5, 3, -2, 3, 6},
            {-1, 3, 5, 3, -1},
            {4, 2, -2, 2, 5},
            {5, 3, -2, 3, 5},
            {6, 4, 0, 3, 4},
            {3, 2, 0, -2, -4}
    };

    private static Equalizer eq;
    private static BassBoost bass;
    private static Virtualizer virt;
    private static LoudnessEnhancer loud;
    private static int sessionId = -1;

    private static SharedPreferences prefs() {
        return ApplicationLoader.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public static boolean isEnabled() {
        try {
            return prefs().getBoolean("enabled", false);
        } catch (Throwable e) {
            return false;
        }
    }

    // ---------- подключение к плееру ----------

    /** Подключает эффекты к аудиосессии плеера (вызывать, когда известен sessionId). */
    public static synchronized void attach(int audioSessionId) {
        if (audioSessionId <= 0 || ApplicationLoader.applicationContext == null) {
            return;
        }
        if (audioSessionId == sessionId && eq != null) {
            applyAll();
            return;
        }
        release();
        sessionId = audioSessionId;
        try {
            eq = new Equalizer(0, audioSessionId);
        } catch (Throwable e) {
            eq = null;
        }
        try {
            bass = new BassBoost(0, audioSessionId);
        } catch (Throwable e) {
            bass = null;
        }
        try {
            virt = new Virtualizer(0, audioSessionId);
        } catch (Throwable e) {
            virt = null;
        }
        try {
            loud = new LoudnessEnhancer(audioSessionId);
        } catch (Throwable e) {
            loud = null;
        }
        applyAll();
    }

    /**
     * Подключает эффекты к музыкальному плееру Telegram. Идентификатор аудиосессии берётся у ExoPlayer
     * через рефлексию (чтобы не зависеть от пакета библиотеки), с несколькими повторами.
     */
    public static void attachToPlayer(final org.telegram.ui.Components.VideoPlayer vp, final MessageObject message) {
        if (vp == null || message == null || !message.isMusic()) {
            return;
        }
        final int[] tries = {0};
        final Runnable[] holder = new Runnable[1];
        holder[0] = new Runnable() {
            @Override
            public void run() {
                try {
                    Object p = vp.player;
                    if (p != null) {
                        Object id = p.getClass().getMethod("getAudioSessionId").invoke(p);
                        if (id instanceof Integer && ((Integer) id) > 0) {
                            attach((Integer) id);
                            return;
                        }
                    }
                } catch (Throwable ignore) {
                }
                if (++tries[0] < 8) {
                    AndroidUtilities.runOnUIThread(holder[0], 250);
                }
            }
        };
        AndroidUtilities.runOnUIThread(holder[0], 100);
    }

    public static synchronized void release() {
        try {
            if (eq != null) {
                eq.release();
            }
        } catch (Throwable ignore) {
        }
        try {
            if (bass != null) {
                bass.release();
            }
        } catch (Throwable ignore) {
        }
        try {
            if (virt != null) {
                virt.release();
            }
        } catch (Throwable ignore) {
        }
        try {
            if (loud != null) {
                loud.release();
            }
        } catch (Throwable ignore) {
        }
        eq = null;
        bass = null;
        virt = null;
        loud = null;
        sessionId = -1;
    }

    private static synchronized void applyAll() {
        boolean on = isEnabled();
        SharedPreferences p = prefs();
        try {
            if (eq != null) {
                short bands = eq.getNumberOfBands();
                short min = eq.getBandLevelRange()[0];
                short max = eq.getBandLevelRange()[1];
                for (short i = 0; i < bands; i++) {
                    int level = p.getInt("band" + i, 0);
                    level = Math.max(min, Math.min(max, level));
                    eq.setBandLevel(i, (short) level);
                }
                eq.setEnabled(on);
            }
        } catch (Throwable ignore) {
        }
        try {
            if (bass != null && bass.getStrengthSupported()) {
                bass.setStrength((short) p.getInt("bass", 0));
                bass.setEnabled(on && p.getInt("bass", 0) > 0);
            }
        } catch (Throwable ignore) {
        }
        try {
            if (virt != null && virt.getStrengthSupported()) {
                virt.setStrength((short) p.getInt("virt", 0));
                virt.setEnabled(on && p.getInt("virt", 0) > 0);
            }
        } catch (Throwable ignore) {
        }
        try {
            if (loud != null) {
                loud.setTargetGain(p.getInt("loud", 0));
                loud.setEnabled(on && p.getInt("loud", 0) > 0);
            }
        } catch (Throwable ignore) {
        }
    }

    // ---------- пресеты ----------

    /** Уровень (в милли-децибелах) для полосы i из N по профилю пресета. */
    private static int presetLevel(int preset, int band, int bands, int min, int max) {
        float[] prof = PRESETS[preset];
        float pos = bands <= 1 ? 0 : (float) band / (bands - 1) * (prof.length - 1);
        int lo = (int) Math.floor(pos);
        int hi = Math.min(prof.length - 1, lo + 1);
        float db = prof[lo] + (prof[hi] - prof[lo]) * (pos - lo);
        int mb = Math.round(db * 100f);
        return Math.max(min, Math.min(max, mb));
    }

    // ---------- окно настроек ----------

    private static int dp(Context c, int v) {
        return Math.round(v * c.getResources().getDisplayMetrics().density);
    }

    private static String freqLabel(int milliHz) {
        int hz = milliHz / 1000;
        if (hz >= 1000) {
            float k = hz / 1000f;
            return (k == Math.floor(k) ? String.valueOf((int) k) : String.format("%.1f", k)) + " кГц";
        }
        return hz + " Гц";
    }

    private static String dbLabel(int mb) {
        float db = mb / 100f;
        return (db > 0 ? "+" : "") + String.format("%.1f", db) + " дБ";
    }

    private static TextView label(Context c, String text, int color, int sp) {
        TextView t = new TextView(c);
        t.setText(text);
        t.setTextSize(sp);
        if (color != 0) {
            t.setTextColor(color);
        }
        return t;
    }

    /** Строка состояния: помогает понять, подключены ли эффекты к плееру. */
    public static synchronized String status() {
        return "Сессия плеера: " + (sessionId > 0 ? String.valueOf(sessionId) : "нет (запусти трек)")
                + "\nЭквалайзер: " + (eq != null ? "подключён" : "недоступен")
                + ", басы: " + (bass != null ? "да" : "нет")
                + ", объём: " + (virt != null ? "да" : "нет")
                + ", громкость: " + (loud != null ? "да" : "нет");
    }

    /** Содержимое эквалайзера для страницы и окна. Цвета 0 = по умолчанию. */
    public static View buildContent(final Context ctx, int textColor, int hintColor, int accentColor) {
        final SharedPreferences p = prefs();
        Equalizer probe = eq;
        boolean tmp = false;
        if (probe == null) {
            try {
                probe = new Equalizer(0, 0);
                tmp = true;
            } catch (Throwable e) {
                probe = null;
            }
        }
        final int bands = probe != null ? probe.getNumberOfBands() : 5;
        final int minLvl = probe != null ? probe.getBandLevelRange()[0] : -1500;
        final int maxLvl = probe != null ? probe.getBandLevelRange()[1] : 1500;
        final int[] centers = new int[bands];
        for (int i = 0; i < bands; i++) {
            centers[i] = probe != null ? probe.getCenterFreq((short) i) : (int) (60000 * Math.pow(4, i));
        }
        if (tmp) {
            try {
                probe.release();
            } catch (Throwable ignore) {
            }
        }
        final int fText = textColor;
        final int fHint = hintColor;
        final int fAccent = accentColor;

        final LinearLayout root = new LinearLayout(ctx);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(ctx, 16), dp(ctx, 8), dp(ctx, 16), dp(ctx, 8));

        final Switch sw = new Switch(ctx);
        sw.setText("Эквалайзер включён");
        sw.setTextSize(16);
        if (fText != 0) {
            sw.setTextColor(fText);
        }
        sw.setChecked(isEnabled());
        sw.setOnCheckedChangeListener(new android.widget.CompoundButton.OnCheckedChangeListener() {
            @Override
            public void onCheckedChanged(android.widget.CompoundButton b, boolean checked) {
                p.edit().putBoolean("enabled", checked).apply();
                applyAll();
            }
        });
        root.addView(sw);

        final TextView presetBtn = label(ctx, "", fAccent, 16);
        presetBtn.setPadding(0, dp(ctx, 14), 0, dp(ctx, 10));
        root.addView(presetBtn);

        final SeekBar[] bandBars = new SeekBar[bands];
        final TextView[] bandVals = new TextView[bands];
        for (int i = 0; i < bands; i++) {
            final int idx = i;
            LinearLayout row = new LinearLayout(ctx);
            row.setOrientation(LinearLayout.HORIZONTAL);
            row.setGravity(Gravity.CENTER_VERTICAL);
            row.setPadding(0, dp(ctx, 4), 0, 0);
            TextView name = label(ctx, freqLabel(centers[i]), fText, 14);
            name.setWidth(dp(ctx, 72));
            row.addView(name);
            SeekBar bar = new SeekBar(ctx);
            bar.setMax(maxLvl - minLvl);
            bar.setProgress(p.getInt("band" + i, 0) - minLvl);
            row.addView(bar, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
            TextView val = label(ctx, dbLabel(p.getInt("band" + i, 0)), fHint, 13);
            val.setWidth(dp(ctx, 72));
            val.setGravity(Gravity.END);
            row.addView(val);
            bandBars[i] = bar;
            bandVals[i] = val;
            bar.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
                @Override
                public void onProgressChanged(SeekBar s, int progress, boolean fromUser) {
                    int level = progress + minLvl;
                    bandVals[idx].setText(dbLabel(level));
                    if (fromUser) {
                        p.edit().putInt("band" + idx, level).apply();
                        applyAll();
                    }
                }

                @Override
                public void onStartTrackingTouch(SeekBar s) {
                }

                @Override
                public void onStopTrackingTouch(SeekBar s) {
                }
            });
            root.addView(row);
        }

        presetBtn.setText("Пресет: " + PRESET_NAMES[Math.max(0, Math.min(PRESET_NAMES.length - 1, p.getInt("preset", 0)))] + "  ▾");
        presetBtn.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                new android.app.AlertDialog.Builder(ctx)
                        .setTitle("Пресет")
                        .setItems(PRESET_NAMES, new DialogInterface.OnClickListener() {
                            @Override
                            public void onClick(DialogInterface dialog, int position) {
                                SharedPreferences.Editor ed = p.edit();
                                ed.putInt("preset", position);
                                for (int i = 0; i < bands; i++) {
                                    int level = presetLevel(position, i, bands, minLvl, maxLvl);
                                    ed.putInt("band" + i, level);
                                    bandBars[i].setProgress(level - minLvl);
                                    bandVals[i].setText(dbLabel(level));
                                }
                                ed.apply();
                                presetBtn.setText("Пресет: " + PRESET_NAMES[position] + "  ▾");
                                applyAll();
                            }
                        })
                        .show();
            }
        });

        final SeekBar bassBar = addExtra(ctx, root, p, "bass", "Усиление басов", 1000, fText);
        final SeekBar virtBar = addExtra(ctx, root, p, "virt", "Объёмный звук", 1000, fText);
        final SeekBar loudBar = addExtra(ctx, root, p, "loud", "Усиление громкости", 1500, fText);

        TextView reset = label(ctx, "Сбросить настройки", fAccent, 16);
        reset.setPadding(0, dp(ctx, 18), 0, dp(ctx, 6));
        reset.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                SharedPreferences.Editor ed = p.edit();
                ed.putInt("preset", 0).putInt("bass", 0).putInt("virt", 0).putInt("loud", 0);
                for (int i = 0; i < bands; i++) {
                    ed.putInt("band" + i, 0);
                    bandBars[i].setProgress(0 - minLvl);
                    bandVals[i].setText(dbLabel(0));
                }
                ed.apply();
                bassBar.setProgress(0);
                virtBar.setProgress(0);
                loudBar.setProgress(0);
                presetBtn.setText("Пресет: " + PRESET_NAMES[0] + "  ▾");
                applyAll();
                Toast.makeText(ctx, "Настройки эквалайзера сброшены", Toast.LENGTH_SHORT).show();
            }
        });
        root.addView(reset);

        TextView hint = label(ctx, "Эффекты применяются к музыке, которая играет в приложении. Если звук не меняется, перезапусти трек.", fHint, 12);
        hint.setPadding(0, dp(ctx, 8), 0, 0);
        root.addView(hint);
        return root;
    }

    public static void showDialog(final Activity activity) {
        if (activity == null) {
            return;
        }
        ScrollView sv = new ScrollView(activity);
        sv.addView(buildContent(activity, 0, 0, 0));
        new android.app.AlertDialog.Builder(activity)
                .setTitle("Эквалайзер PikmiGram")
                .setView(sv)
                .setPositiveButton("Готово", null)
                .show();
    }

    private static SeekBar addExtra(Context ctx, LinearLayout root, final SharedPreferences p, final String key, String title, int max, int textColor) {
        TextView t = label(ctx, title, textColor, 14);
        t.setPadding(0, dp(ctx, 14), 0, 0);
        root.addView(t);
        SeekBar bar = new SeekBar(ctx);
        bar.setMax(max);
        bar.setProgress(p.getInt(key, 0));
        bar.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override
            public void onProgressChanged(SeekBar s, int progress, boolean fromUser) {
                if (fromUser) {
                    p.edit().putInt(key, progress).apply();
                    applyAll();
                }
            }

            @Override
            public void onStartTrackingTouch(SeekBar s) {
            }

            @Override
            public void onStopTrackingTouch(SeekBar s) {
            }
        });
        root.addView(bar);
        return bar;
    }
}
'''

if PE.exists() and "PikmiEqualizer" in PE.read_text(encoding="utf-8"):
    print("уже применено")
    sys.exit(0)
PE.parent.mkdir(parents=True, exist_ok=True)
PE.write_text(JAVA, encoding="utf-8")
print("PikmiEqualizer.java: создан")
