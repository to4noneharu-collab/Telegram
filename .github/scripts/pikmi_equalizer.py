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

    public static void showDialog(final Activity activity) {
        if (activity == null) {
            return;
        }
        final SharedPreferences p = prefs();
        // Для окна нужны параметры полос: берём у живого эффекта или создаём временный на «нулевой» сессии
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
            if (probe != null) {
                centers[i] = probe.getCenterFreq((short) i);
            } else {
                centers[i] = (int) (60000 * Math.pow(4, i));
            }
        }
        if (tmp) {
            try {
                probe.release();
            } catch (Throwable ignore) {
            }
        }

        final LinearLayout root = new LinearLayout(activity);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(activity, 20), dp(activity, 8), dp(activity, 20), dp(activity, 8));

        final Switch sw = new Switch(activity);
        sw.setText("Эквалайзер включён");
        sw.setChecked(isEnabled());
        sw.setTextSize(16);
        root.addView(sw);

        TextView presetLabel = new TextView(activity);
        presetLabel.setText("Пресет");
        presetLabel.setPadding(0, dp(activity, 12), 0, 0);
        root.addView(presetLabel);

        final Spinner spinner = new Spinner(activity);
        ArrayAdapter<String> sa = new ArrayAdapter<String>(activity, android.R.layout.simple_spinner_dropdown_item, PRESET_NAMES);
        spinner.setAdapter(sa);
        spinner.setSelection(Math.max(0, Math.min(PRESET_NAMES.length - 1, p.getInt("preset", 0))));
        root.addView(spinner);

        final SeekBar[] bandBars = new SeekBar[bands];
        final TextView[] bandVals = new TextView[bands];
        for (int i = 0; i < bands; i++) {
            final int idx = i;
            LinearLayout row = new LinearLayout(activity);
            row.setOrientation(LinearLayout.HORIZONTAL);
            row.setGravity(Gravity.CENTER_VERTICAL);
            row.setPadding(0, dp(activity, 6), 0, 0);
            TextView name = new TextView(activity);
            name.setText(freqLabel(centers[i]));
            name.setWidth(dp(activity, 70));
            row.addView(name);
            SeekBar bar = new SeekBar(activity);
            bar.setMax(maxLvl - minLvl);
            bar.setProgress(p.getInt("band" + i, 0) - minLvl);
            row.addView(bar, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
            TextView val = new TextView(activity);
            val.setWidth(dp(activity, 70));
            val.setGravity(Gravity.END);
            val.setText(dbLabel(p.getInt("band" + i, 0)));
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

        final boolean[] presetInit = {true};
        spinner.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                if (presetInit[0]) {
                    presetInit[0] = false;
                    return;
                }
                SharedPreferences.Editor ed = p.edit();
                ed.putInt("preset", position);
                for (int i = 0; i < bands; i++) {
                    int level = presetLevel(position, i, bands, minLvl, maxLvl);
                    ed.putInt("band" + i, level);
                    bandBars[i].setProgress(level - minLvl);
                    bandVals[i].setText(dbLabel(level));
                }
                ed.apply();
                applyAll();
            }

            @Override
            public void onNothingSelected(AdapterView<?> parent) {
            }
        });

        // дополнительные регуляторы: баса, объём, громкость
        addExtra(activity, root, p, "bass", "Усиление басов", 1000, 1000);
        addExtra(activity, root, p, "virt", "Объёмный звук", 1000, 1000);
        addExtra(activity, root, p, "loud", "Усиление громкости", 1500, 1500);

        sw.setOnCheckedChangeListener(new android.widget.CompoundButton.OnCheckedChangeListener() {
            @Override
            public void onCheckedChanged(android.widget.CompoundButton b, boolean checked) {
                p.edit().putBoolean("enabled", checked).apply();
                applyAll();
            }
        });

        TextView hint = new TextView(activity);
        hint.setText("Эффекты применяются к музыке, которая играет в приложении. Если звук не меняется, перезапусти трек.");
        hint.setTextSize(12);
        hint.setPadding(0, dp(activity, 12), 0, 0);
        root.addView(hint);

        ScrollView scroll = new ScrollView(activity);
        scroll.addView(root);

        new android.app.AlertDialog.Builder(activity)
                .setTitle("Эквалайзер PikmiGram")
                .setView(scroll)
                .setNeutralButton("Сбросить", new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface dialog, int which) {
                        SharedPreferences.Editor ed = p.edit();
                        ed.putInt("preset", 0).putInt("bass", 0).putInt("virt", 0).putInt("loud", 0);
                        for (int i = 0; i < bands; i++) {
                            ed.putInt("band" + i, 0);
                        }
                        ed.apply();
                        applyAll();
                        Toast.makeText(activity, "Настройки эквалайзера сброшены", Toast.LENGTH_SHORT).show();
                    }
                })
                .setPositiveButton("Готово", null)
                .show();
    }

    private static void addExtra(Context ctx, LinearLayout root, final SharedPreferences p, final String key, String title, int max, final int scale) {
        TextView t = new TextView(ctx);
        t.setText(title);
        t.setPadding(0, dp(ctx, 12), 0, 0);
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
    }
}
'''

if PE.exists() and "PikmiEqualizer" in PE.read_text(encoding="utf-8"):
    print("уже применено")
    sys.exit(0)
PE.parent.mkdir(parents=True, exist_ok=True)
PE.write_text(JAVA, encoding="utf-8")
print("PikmiEqualizer.java: создан")
