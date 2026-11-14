"""Rebuild September episode from anonymized HA history; requires matplotlib."""
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ROOT = Path(__file__).resolve().parent
MSK = timezone(timedelta(hours=3))
def at(value):
    return datetime.fromisoformat(value).replace(tzinfo=MSK)

series = {}
with (ROOT / 'telemetry.csv').open() as source:
    for row in csv.DictReader(source):
        value = row['state']
        if row['sensor'] == 'ignition':
            value = {'on': 1, 'off': 0}.get(value, float('nan'))
        try:
            value = float(value)
        except ValueError:
            value = float('nan')
        series.setdefault(row['sensor'], []).append(
            (datetime.fromisoformat(row['time_utc']).astimezone(MSK), value))

plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11})
fig, (ax, ignition) = plt.subplots(2, 1, figsize=(13, 7), sharex=True,
                                 gridspec_kw={'height_ratios': [4, 1]})
fig.suptitle('4–5 сентября: разряд штатного свинцового АКБ 40 А·ч',
             fontsize=17, fontweight='bold', x=.08, ha='left')
for panel, key, color in [(ax, 'battery_voltage', '#1466a5'),
                          (ignition, 'ignition', '#6251a2')]:
    points = series[key] + [(at('2026-09-05T13:00:00'), series[key][-1][1])]
    times, values = zip(*points)
    panel.step(times, values, where='post', color=color, linewidth=1.7)
    panel.grid(alpha=.2)
    panel.spines[['top', 'right']].set_visible(False)
    panel.axvspan(at('2026-09-05T00:54:43'), at('2026-09-05T01:11:36'),
                  color='#e8ad36', alpha=.35)
ax.set_ylabel('Напряжение АКБ, В')
ax.set_ylim(8, 15.5)
ax.set_yticks(range(8, 15))
ax.axhline(9, color='#c33737', alpha=.3, ls=':', linewidth=1)
ax.annotate('00:54–01:11 · 16 мин 53 с\nЗажигание и вентилятор включены',
            xy=(at('2026-09-05T01:00:00'), 13.65),
            xytext=(at('2026-09-04T23:00:00'), 14.65), fontsize=10,
            arrowprops={'arrowstyle': '-', 'color': '#555'})
for timestamp, value, text, label_time, label_value in [
    ('2026-09-05T10:16:59', 8.60, '10:17 · 8,60 В', '2026-09-05T06:40:00', 8.55),
    ('2026-09-05T11:51:32', 8.56, '11:52 · 8,56 В', '2026-09-05T12:45:00', 8.15),
]:
    ax.plot(at(timestamp), value, 'o', color='#c33737', ms=6)
    ax.annotate(text, xy=(at(timestamp), value), xytext=(at(label_time), label_value),
                ha='right' if '11:52' in text else 'left', color='#aa2727', fontsize=10,
                arrowprops={'arrowstyle': '-', 'color': '#aa2727'})
ax.annotate('11:47 · краткий подъём до 13,18 В\nи переход зажигания в on',
            xy=(at('2026-09-05T11:47:26'), 13.18),
            xytext=(at('2026-09-05T08:00:00'), 14.65), fontsize=10,
            arrowprops={'arrowstyle': '-', 'color': '#555'})
ax.annotate('12:24 · 13,66 В', xy=(at('2026-09-05T12:23:58'), 13.66),
            xytext=(at('2026-09-05T12:50:00'), 14.05), ha='right', fontsize=10,
            arrowprops={'arrowstyle': '-', 'color': '#555'})
ignition.set_ylabel('Зажигание')
ignition.set_ylim(-.15, 1.3)
ignition.set_yticks([0, 1], ['off', 'on'])
ignition.xaxis.set_major_locator(mdates.HourLocator(interval=2, tz=MSK))
ignition.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M', tz=MSK))
ignition.set_xlim(at('2026-09-04T21:00:00'), at('2026-09-05T13:00:00'))
ignition.set_xlabel('4 → 5 сентября 2026 · время МСК (UTC+3)')
fig.text(.08, .025, 'Источник: история HA, облачная интеграция Evolute. Ступени — зарегистрированные изменения.'
         '\nТип и ёмкость АКБ — по данным владельца. График не устанавливает причины утренних переключений.',
         fontsize=9, color='#555')
fig.subplots_adjust(left=.08, right=.98, top=.9, bottom=.16, hspace=.13)
fig.savefig(ROOT / 'battery-voltage.png', dpi=160)
fig.savefig(ROOT / 'battery-voltage.svg')
