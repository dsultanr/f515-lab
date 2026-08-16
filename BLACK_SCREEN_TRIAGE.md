# Чёрный экран на F515: что снимать в момент сбоя

Чек-лист для случая «экран чёрный, а система жива». Главное здесь — снять состояние
**до** любых действий: перезагрузка, `kill` процесса или просто переключение экрана
уничтожают ровно те следы, по которым причина и определяется. Логи постфактум на этот
вопрос не отвечают.

Повод для заметки: в сборе `logs/blackscreen_investigation_2026-08-06/` (80 МБ логов)
не оказалось ни одного снимка состояния окон и дисплея — только логи. По ним нельзя
проверить самую дешёвую гипотезу: не накрыт ли экран чужим окном.

## Ловушка, с которой всё начинается

Первое, что хочется сделать — посмотреть, какое приложение на переднем плане:

```sh
dumpsys activity activities | grep -m1 mResumedActivity
```

**Этот ответ не значит того, чего от него ждут.** `mResumedActivity` отвечает на вопрос
«чья активность в фокусе», а не «что видно на экране». Оверлейное окно рисуется поверх и
в этом поле не появляется вообще.

Проверенный пример (16.08.2026): на экране был круговой обзор с камер, при этом

```
mResumedActivity: ActivityRecord{... com.seres.launcher/.allapppage.AppListActivity ...}
```

то есть «на переднем плане лаунчер». Картинку рисовало отдельное окно:

```
Window{... com.seres.avm}                appop=NONE
Window{... AutoPark_AvmWindow}           appop=SYSTEM_ALERT_WINDOW
```

Если бы в тот момент экран был чёрным, по `mResumedActivity` мы сделали бы вывод
«Android в порядке, значит дело в железе» — и он был бы необоснован.

## Шаг 0. Разделитель, экономящий часы: `screencap`

`screencap` снимает то, что **нарисовано в буфере**, а не то, что светится на матрице.
Одно это разводит причины по разным веткам:

```sh
screencap -p /data/local/tmp/blackscreen.png
```

| что на снимке | вывод | куда копать |
|---|---|---|
| **чёрный кадр** | чёрное действительно нарисовано | окна и оверлеи (шаг 1), композитор (шаг 3) |
| **нормальный кадр**, а панель тёмная | рисуется всё правильно | подсветка/питание панели (шаг 2) |

## Шаг 1. Что реально на экране: окна и оверлеи

```sh
dumpsys window windows | grep -E "Window #|mAttrs=|isOnScreen|mHasSurface|isReadyForDisplay"
```

Значимые поля:

| поле | смысл |
|---|---|
| `Window #N` | z-порядок, `#0` — самое верхнее |
| `ty=` | тип окна (`APPLICATION_OVERLAY`, `BASE_APPLICATION`, `WALLPAPER`, числовые — смотреть в `WindowManager.LayoutParams`) |
| `fmt=` | `TRANSLUCENT` / `TRANSPARENT` / непрозрачные (`RGBX_8888`) |
| `(fillxfill)` | окно на весь экран |
| `isOnScreen`, `mHasSurface`, `isReadyForDisplay()` | рисуется ли оно на самом деле |

**Признак «экран накрыт»:** окно с маленьким `#N`, размером `fillxfill`, непрозрачным
`fmt`, с `isOnScreen=true` — и это не то приложение, которое ожидается на экране.

Отдельно — кто в системе вправе рисовать поверх всего:

```sh
settings get secure enabled_accessibility_services
```

Окна `TYPE_ACCESSIBILITY_OVERLAY` накрывают в том числе системные бары. На F515 такие
службы есть штатно (`WindowMonitorService`, хуавеевский `FloatViewAccessibilityService`),
а в этом же проекте есть и артефакт, который делает это намеренно —
`ispace-research/artifacts/screen-dimmer/` рисует чёрный слой до 92 % непрозрачности,
вариант `full` — поверх всего экрана. Если такой оверлей завис или уехал в максимум,
картина будет ровно «чёрный экран при живой системе». Проверять его наличие:

```sh
pm list packages | grep -i dimmer
```

## Шаг 2. Дисплей и питание

```sh
dumpsys power | grep -iE "mWakefulness|mScreenOn|brightness"
dumpsys display | grep -iE "mScreenState|mState=|Brightness"
dumpsys window displays
```

Сюда идём, если на скриншоте (шаг 0) картинка нормальная.

## Шаг 3. QNX — здесь живёт композитор

Существенная особенность F515: Android — **гость под QNX-гипервизором**, а HMI-слой и
композитор работают на стороне QNX (Kanzi). Android отдаёт свою поверхность наружу и о
состоянии QNX-слоя ничего не знает. Поэтому перезапуск или падение QNX-HMI даёт чёрный
экран, при котором Android совершенно здоров: ни крашей, ни ANR, а `mResumedActivity`
показывает обычный лаунчер.

В сборе 06.08.2026 в QNX-логе именно это и видно в начале окна инцидента:

```
08:17:53  GVM suspended hence not notified
08:17:55  slay: Unable to find process 'sai_clusterhmi'
08:17:55  slay: Unable to find process 'TTLamp'
08:17:55  slm_hmi: Error while starting component 'RVC': No such file or directory
08:17:56  Background: Window format rgb888 set / Kanzi / on ProjectLoaded
```

(Связь «перезапуск QNX-HMI → чёрный экран» здесь пока не доказана, а предполагается:
снимка состояния экрана в том сборе нет. Именно поэтому шаг 0 и шаг 1 обязательны.)

Что снимать со стороны QNX:

```sh
slog2info | tail -2000                     # или выгрузка за окно инцидента
cat /pps/ivi/...                           # снимок PPS-объектов IVI/HMI
pidin | grep -iE "hmi|kanzi|Background|TTLamp|sai_"
```

## Шаг 4. Падал ли Android

```sh
ls -la /data/tombstones/ /data/anr/ /data/system/dropbox/
logcat -d -b crash | tail -100
```

В сборе 06.08.2026 всё это оказалось пустым — крашей Android не было, что дополнительно
уводит от версии «упал system_server» (та версия относится к **другому** чёрному экрану —
загрузочному, после стирания `/data`, см. `ispace-research/spec/36-adb-data-wipe-findings.md`).

## Готовый сбор одной командой

Снимать в момент сбоя, до перезагрузки:

```sh
D=/data/local/tmp/blackscreen-$(date +%m%d-%H%M 2>/dev/null || echo now); mkdir -p "$D"
screencap -p "$D/screen.png"
dumpsys window windows            > "$D/windows.txt" 2>&1
dumpsys window displays           > "$D/displays.txt" 2>&1
dumpsys power                     > "$D/power.txt" 2>&1
dumpsys display                   > "$D/display.txt" 2>&1
dumpsys SurfaceFlinger --list     > "$D/sf-layers.txt" 2>&1
dumpsys activity activities       > "$D/activities.txt" 2>&1
settings get secure enabled_accessibility_services > "$D/a11y.txt" 2>&1
logcat -d -b all                  > "$D/logcat-all.txt" 2>&1
ls -la /data/tombstones /data/anr > "$D/crashes.txt" 2>&1
echo "собрано в $D"
```

Первым делом смотреть `screen.png` — он один сразу отсекает половину гипотез.

## Чего не хватало в сборе 2026-08-06

Есть: `logcat` всех буферов (32 МБ), `logcat` main/system с загрузки, `dmesg`, листинги
tombstones/ANR/dropbox, QNX `slog2` за окно и целиком, снимок PPS IVI/HMI.

Нет: **скриншота**, `dumpsys window windows`, `dumpsys power`, `dumpsys display`,
`SurfaceFlinger`. То есть ни проверить оверлей, ни отличить «нарисовано чёрное» от
«панель не светится» по тому сбору уже нельзя.
