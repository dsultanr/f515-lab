"""Rebuild the figure from exported HA state changes; requires matplotlib."""
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ROOT = Path(__file__).resolve().parent
MSK = timezone(timedelta(hours=3))
series = {}
with (ROOT / 'telemetry.csv').open() as source:
    for row in csv.DictReader(source):
        time = datetime.fromisoformat(row['time_utc']).astimezone(MSK)
        try:
            value = float(row['state'])
        except ValueError:
            value = float('nan')
        series.setdefault(row['sensor'], []).append((time, value))

def at(value):
    return datetime.fromisoformat(value).replace(tzinfo=MSK)

plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11})
fig, (ax, current) = plt.subplots(2, 1, figsize=(13, 7), sharex=True,
                                gridspec_kw={'height_ratios': [3, 1]})
fig.suptitle('После подготовки через облако Evolute: разряд АКБ 12 В',
             fontsize=17, fontweight='bold', x=.08, ha='left')
for panel, key, color in [(ax, 'battery_voltage', '#1466a5'),
                          (current, 'hv_battery_current', '#6251a2')]:
    points = series[key] + [(at('2026-11-12T12:00:00'), series[key][-1][1])]
    times, values = zip(*points)
    panel.step(times, values, where='post', color=color, linewidth=1.7)
    panel.grid(alpha=.2)
    panel.spines[['top', 'right']].set_visible(False)
    panel.axvspan(at('2026-11-11T21:38:04'), at('2026-11-11T21:55:11'),
                  color='#e8ad36', alpha=.35)
    panel.axvline(at('2026-11-12T08:12:17'), color='#328257', alpha=.6, ls='--')
ax.set_ylabel('Напряжение АКБ, В')
ax.set_ylim(8, 15.3)
ax.set_yticks(range(8, 15))
ax.annotate('21:38–21:55 · 17 минут\nЗажигание и климат включены',
            xy=(at('2026-11-11T21:46:00'), 13.65),
            xytext=(at('2026-11-11T21:20:00'), 14.55), fontsize=10,
            arrowprops={'arrowstyle': '-', 'color': '#555'})
ax.plot(at('2026-11-12T02:11:20'), 8.58, 'o', color='#c33737', ms=6)
ax.annotate('02:11 · минимум 8,58 В', xy=(at('2026-11-12T02:11:20'), 8.58),
            xytext=(at('2026-11-12T02:45:00'), 8.65), color='#aa2727', fontsize=11,
            arrowprops={'arrowstyle': '-', 'color': '#aa2727'})
ax.axhline(9, color='#c33737', alpha=.3, ls=':', linewidth=1)
ax.text(at('2026-11-12T11:45:00'), 9.1, 'Порог защиты 9 В — по данным владельца',
        color='#995050', fontsize=9, ha='right')
ax.annotate('Защита отключила потребителей\nВосстановление до 10,2–10,3 В',
            xy=(at('2026-11-12T02:38:35'), 10.28),
            xytext=(at('2026-11-12T03:10:00'), 10.85), fontsize=10,
            arrowprops={'arrowstyle': '-', 'color': '#555'})
ax.annotate('08:12–08:14 · 12,76 → 13,5 В\nПризнаки включения DC-DC',
            xy=(at('2026-11-12T08:13:53'), 13.5),
            xytext=(at('2026-11-12T07:10:00'), 14.55), fontsize=10,
            arrowprops={'arrowstyle': '-', 'color': '#328257'})
ax.annotate('', xy=(at('2026-11-12T02:11:20'), 11.65),
            xytext=(at('2026-11-12T08:12:17'), 11.65),
            arrowprops={'arrowstyle': '<->', 'color': '#666'})
ax.text(at('2026-11-12T05:10:00'), 11.85, '6 ч 01 мин после минимума',
        ha='center', color='#555', fontsize=10)
current.set_ylabel('Ток ВВБ, А')
current.set_ylim(-1, 24)
current.set_yticks([0, 10, 20])
current.xaxis.set_major_locator(mdates.HourLocator(interval=2, tz=MSK))
current.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M', tz=MSK))
current.set_xlim(at('2026-11-11T21:00:00'), at('2026-11-12T12:00:00'))
current.set_xlabel('11 → 12 ноября 2026 · время МСК (UTC+3)')
fig.text(.08, .025, 'Источник: история HA, прямая телеметрия Vega. Ступени — зарегистрированные изменения;'
         '\nнедоступные значения показаны разрывами. После 21:55 датчик зажигания — off (есть краткий пропуск).',
         fontsize=9, color='#555')
fig.subplots_adjust(left=.08, right=.98, top=.9, bottom=.16, hspace=.13)
fig.savefig(ROOT / 'battery-voltage.png', dpi=160)
fig.savefig(ROOT / 'battery-voltage.svg')
