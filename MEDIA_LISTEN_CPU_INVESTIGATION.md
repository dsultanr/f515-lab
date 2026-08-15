# com.seres.media.listen — разбор нагрузки CPU

Дата: 2026-08-15. Голова: F515, аптайм на момент снятия 2 дня 11 ч, adb через WG (10.8.0.2:5555).
Голова ушла в офлайн в ~11:07, часть данных добрана из дампа на mail.ru WebDAV (`mailru:f515_dump`, 2026-07-29).

## Симптом

`com.seres.media.listen` (pid 3102) держит 42.5% CPU, 476 минут CPU-времени за 2.5 суток
(~13% ядра непрерывно). Музыка при этом **не играет** — все `AudioPlaybackConfiguration` в
состоянии `idle`. `com.seres.settings` (pid 3041) параллельно раздут до 519 МБ RES.

## Что это за приложение

```
codePath    = /system/app/SeresMediaListen
versionName = SAIOS_S1_SeresMediaListen_260107_c2f541ff34_6621
versionCode = 6621   minSdk=29  targetSdk=33
APK         = 127 319 325 байт, 4 dex (~31 МБ кода), 6444 файлов
```

Не голосовой ассистент (проверялась такая гипотеза). `RECORD_AUDIO` и `CAPTURE_AUDIO_OUTPUT`
у него есть (SYSTEM_FIXED, из типового пресета ~385 permissions для системных APK Seres), но
**ни одной записи с микрофона от него нет**. Весь микрофон в логе — от `com.huawei.voice.car`
(`src:VOICE_RECOGNITION`, сессиями по 2–3 часа), вот это и есть ассистент в ожидании
ключевого слова.

## Найдено две независимых причины нагрузки

### 1. Frida-агент iSpace Toolbox, резидентный в процессе

В `/proc/3102/maps`:
```
7bb6642000-7bb7d0e000 r-xp /memfd:frida-agent-64.so (deleted)
```
Стек одного из потоков целиком через `frida-agent-64.so` (`__ppoll` → frida → `__pthread_start`).

Источник — свой, не чужой:
```
6138 root  sh /data/user/0/com.ispace.toolbox/files/frida/frida-resume-watcher.sh
6153 root  sh /data/user/0/com.ispace.toolbox/files/frida/frida-resume-watcher.sh
```
Портов 27042/27043 нет — это локальный inject, не удалённый frida-server.

Заражены ровно три процесса, и это **те же самые**, что аномальны по CPU/памяти:

| PID  | Процесс                    | Агент                  | Статус твика |
|------|----------------------------|------------------------|--------------|
| 1704 | `com.core.system.service`  | `swb-hook.js`          | `status-swb = on` |
| 3041 | `com.seres.settings`       | `tweaks.js`            | `avas=off`, `woman=mute` |
| 3102 | `com.seres.media.listen`   | `local-media-bridge.js`| status-файлов нет |

`com.android.car` / `bms-info.js` — `off`, агент не резидентен, frida в нём отсутствует.

Что делает `local-media-bridge.js` (из бандла, 1889 строк):

- `setInterval(Do, 1000)` — **тик каждую секунду**, лог агента: `installed — polling every 1000ms, source slot=90`
- в тике: чтение status-файла с tmpfs, `Le.getClass().getName()` + `V.use(имя_класса)` —
  резолв Java-класса через JNI на каждом тике (дорогая операция в frida-java-bridge)
- рефлексия `getClass().getMethods()` с перебором — но под однократным guard-флагом
- при обновлении обложки: `Bitmap.compress(PNG, 100, …)` в файл, ротация 4 файлов
  `local_media_bridge_cover_N.png` — PNG-сжатие с качеством 100
- хуки на `handleMediaCardData` в `F515ProjectionCard` / `Sf5ProjectionCard`, на `setMediaWithSource`
- **создаёт собственное оверлейное окно**: `vehicle-info overlay window created on display 1: 600x400 margin=40`
  и рисует в него телеметрию через `Bitmap`/`Canvas`/`Paint`

Из `media-bridge-apply.sh`: выключение твика — это только флаг в status-файле, агент остаётся
в процессе навсегда («Frida has no clean unhook once eternalized») и продолжает тикать,
проверяя флаг «on its own next tick/render».

### 2. Двойная отрисовка в MarqueeTextView (код самого APK)

`com.seres.media.ui.widget.MarqueeTextView`, 375 строк:

```java
public void onDraw(Canvas canvas) {
    restartMarqueeIfNeeded();
    super.onDraw(this.fakeCanvas);   // ← весь TextView.onDraw впустую
    ...
    drawNormal(canvas);              // ← и ещё раз, вручную
}
```

`fakeCanvas` — это `new Canvas()` без bitmap (строки 254, 259). То есть на **каждый кадр**
полный `TextView.onDraw` (layout текста, шейпинг глифов) выполняется в никуда, и следом
текст рисуется второй раз вручную. Плюс `restartMarqueeIfNeeded()` на каждом кадре.

Анимация бегущей строки крутится через `Choreographer.FrameCallback` (три разных callback,
`doFrame` → `textView.invalidate()`), то есть самоподдерживающийся цикл перерисовки, пока
marquee активен. `onVisibilityChanged` → `startMarquee()` — запускается при появлении на экране.

## РАЗВЯЗКА (2026-08-15 12:20, голова вернулась в онлайн)

Снят `simpleperf record -p 3102 -g --duration 30` (3688 семплов, 0 потеряно) —
**обе гипотезы выше оказались не главной причиной**. Профиль по библиотекам:

```
60.40%  [kernel.kallsyms]
11.81%  /system/lib64/libhwui.so
 8.43%  /vendor/lib64/libgsl.so            (Adreno GPU)
 4.65%  libc.so     3.55%  libart.so       1.50%  libGLESv2_adreno.so
 ~2.2%  /data/local/tmp/TemporaryFile-*    (frida-agent)
 0.33%  libminikin.so                      (шейпинг текста)
```

Топ символов:
```
27.83%  _raw_spin_unlock_irqrestore
 7.67%  habhyp_notify                      ← передача кадров через HAB в гипервизор QNX
 6.89%  gsl_command_readtimestamp          ← ожидание GPU-таймстампов
 1.97%  neon::S32_alpha_D32_filter_DX      ← софтверный блиттинг Skia
 1.12%  neon::blit_row_color32
 0.74%  S32_alpha_D32_nofilter_DX
```

### Настоящая причина: окно рендерится на 54 fps непрерывно

Замер за 25 секунд (`gfxinfo reset` → пауза → `gfxinfo`):
```
Total frames rendered: 1351      → 54 fps
Janky frames: 1008 (74.61%)
50th percentile: 21ms            → кадр не укладывается в бюджет 16.7ms
```

Окно `Window{c39ff04 u0 com.seres.media.listen}` живёт на **`mDisplayId=1`** — это
приборная панель (рядом `com.ts.car.clustercomm.projectionservice`), а не центральный экран.
Это штатная projection card приложения (`F515ProjectionCard`), и она перерисовывается
на полной частоте, хотя музыка не играет и содержимое статично.

Механизм: `MarqueeTextView.Marquee` крутит `Choreographer.FrameCallback` → `textView.invalidate()`
каждый кадр → перерисовка всего окна карточки → Skia-блиттинг битмапов + GPU + **передача
кадра на приборку через HAB** (`habhyp_notify`, межгостевой канал к QNX-гипервизору — дорогая
операция, которой на обычном Android нет). Двойная отрисовка через `fakeCanvas` удваивает
часть работы, но сама по себе дёшева: шейпинг текста (`libminikin`) — всего 0.33% профиля.

То есть marquee здесь — **триггер** (заставляет инвалидировать окно 60 раз в секунду),
а стоимость сидит в перерисовке всего содержимого и в HAB-передаче на второй дисплей.

Косвенное подтверждение с более раннего скриншота: подпись в виджете была обрезана слева
(«авайте включим музыку» вместо «Давайте включим музыку») — бегущая строка в процессе прокрутки.

### Корректировка ранних выводов

- **Frida-агент не виновен** в нагрузке: ~2.2% профиля. Он резидентен, тикает раз в секунду,
  но `vehicle-info-status = off` — оверлей не создан, агент только изредка пишет
  `setMediaWithSource` (раз в несколько минут). Всё описанное в разделе 1 про его устройство
  верно, но на CPU он практически не влияет.
- **Двойная отрисовка MarqueeTextView реальна**, но не является главным потребителем.
- Ранняя догадка, что окно media.listen — это виджет плеера в доке центрального экрана,
  **неверна**: окно на display 1, приборка.
- Среднее «2.1 кадра/с» из первого `gfxinfo` — это среднее за 25.7 ч, включая часы,
  когда карточка не показывалась. В активном состоянии частота 54 fps.

### Уточнение 12:36 — рендер вхолостую, источник invalidate не локализован

Замер повторён: 1657 кадров за 30 с = **55 fps**, стабильно, CPU 29.6%. Не артефакт обращений по adb.

Скриншот приборки (`screencap -d 1`) снят дважды с интервалом 1.2 с — **байт-в-байт идентичны**.
На экране статичная карточка «Не воспроизводится» с иконкой ноты. То есть окно перерисовывается
55 раз в секунду, не меняя ни пикселя.

Отсюда:
- **Версия с `anim_loading` не подтвердилась.** В APK это единственная анимация с
  `repeatCount="infinite"` (rotate 360° / 5000 мс), запускается в `showAnimation()` на
  `binding.getRoot()` по событию `ACTION_SHOW_BIG`, отменяется только по `ACTION_HIDE_SMALL`.
  Но если бы она крутилась, за 1.2 с карточка повернулась бы на 86° — картинка идентична.
- **Marquee тоже отпадает как триггер:** текст «Не воспроизводится» короткий, `canMarquee()`
  вернёт false. При этом дефект в коде реальный и остаётся: в оригинальном Android
  `restartMarqueeIfNeeded()` защищён проверкой `if (mRestartMarquee && mEllipsize == MARQUEE)`,
  здесь её выбросили — из каждого `onDraw` безусловно зовётся `startMarquee()`.
  На длинном названии трека это даст постоянный рестарт.

Что известно про источник:
- Главный поток непрерывно принимает vsync — в стеке `NativeDisplayEventReceiver::dispatchVsync`,
  то есть Choreographer подписан на каждый кадр.
- `utm=929784 stm=537193` (HZ=100) → 155 мин user + 89 мин system у главного потока.
- Приложение **не логирует обновлений карточки**: за 6 секунд 2 строки в logcat, ни одного
  `update projection card`. Данные не меняются, кадры генерируются впустую.
- Единственная запись в логе процесса — подозрительная:
  ```
  W Choreographer: Frame time is 0.219509 ms in the future! Check that graphics HAL
                   is generating vsync timestamps using the correct timebase.
  ```
  Кривые vsync-таймстампы от graphics HAL — характерно для Android-гостя под гипервизором,
  и это самостоятельный кандидат в первопричину (Choreographer не может «успокоиться»).

Точную View, которая держит invalidate, без инжекта в процесс установить нельзя.

### Штатного выключателя нет

- `settings list global|system|secure` — ни одного ключа про cluster/projection/marquee.
- `getprop` — пусто по cluster/projection.
- `dumpsys activity service com.ts.car.clustercomm` — `renderer binder: null`, сервис пуст.
- В `AndroidManifest.xml` **нет отдельного компонента проекции** — карточка создаётся
  программно (`BaseProjectionCard.onPresentationCreated`), поэтому `pm disable` компонента
  не применим.

### Артефакты профилирования

`~/f515/logs/media-listen-perf-20260815/` — `ml-perf.data`, `report-by-dso.txt`,
`report-by-symbol.txt`, `agent-trace-live.txt`.

## Чего доказать НЕ удалось (устарело, см. РАЗВЯЗКУ выше)

Точное распределение 476 минут CPU между этими двумя механизмами. Голова ушла в офлайн до того,
как удалось снять `simpleperf`. Косвенные данные из `gfxinfo` (за 25.7 ч активного времени):

```
Total frames rendered: 197348      50th percentile: 5ms     GPU 50th: 1ms
Janky frames: 8908 (4.51%)         Number High input latency: 41202
```

Это ~2.1 кадра/с в среднем и ~16 минут CPU на всю отрисовку по гистограмме — то есть
**рендеринг сам по себе дешёвый и не объясняет 476 минут**. Основное время сидит в главном
потоке между кадрами (239 мин у main, 109 мин у RenderThread), что лучше согласуется
с версией про секундный тик frida-агента, чем с marquee. Но это довод, а не доказательство.

## Как проверить, когда голова вернётся

1. `simpleperf record -p <pid> -g --duration 30` и посмотреть, сколько семплов внутри
   `frida-agent-64.so` против кода приложения. Это закрывает вопрос однозначно.
2. Дешёвая проверка без профайлера: сравнить CPU процесса до и после того, как процесс
   поднимется **без** инжекта (агент не переживает рестарт процесса сам — его возвращает
   `frida-resume-watcher.sh`). Если после чистого старта CPU падает — виноват агент.
3. `cat /data/local/tmp/local-media-bridge-trace.log` — свежие тики и ошибки агента.

## Артефакты

- `~/f515/decompile/SeresMediaListen.apk` — извлечён из `system.img` в дампе через
  `debugfs -R "dump …"` поверх `rclone mount --read-only` (образ 3.84 ГБ целиком не качался,
  локально свободно было 1.5 ГБ). Размер совпадает с оригиналом на устройстве: 127 319 325.
- `~/f515/decompile/SeresLiveWallPaper.apk` — 41 384 078, полный, снят с устройства.
- `~/f515/decompile/ml_card/`, `~/f515/decompile/ml_marquee/` — точечная декомпиляция jadx.
- `~/f515/recon/ispace-frida/frida-dir/` — агенты и apply-скрипты iSpace (JS-бандлы,
  `*-apply.sh`, status-файлы). **Неполно**: `frida-resume-watcher.sh`, `frida-inject`,
  `frida-inject32` не успели скачаться до офлайна.
- `~/f515/recon/ispace-frida/dump-20260729/` — трейс-логи агентов из WebDAV-дампа.

### Не добрано

- `HiVoiceCar.apk` — 588 982 685 байт, скачано 18.7 МБ, pull прерван. Есть в дампе
  (`/system/app/HiVoiceCar/HiVoiceCar.apk` в `system.img`) — достаётся тем же debugfs,
  но нужно ~590 МБ свободного места, а сейчас 1.5 ГБ на всём диске.
- `SeresMediaListen.apk` при первой попытке дошёл до 96% и был снесён прерванным adb pull —
  поэтому и пошли через дамп.

## Патч «убрать карточку с приборки» (2026-08-15 12:49)

Решение: гасить корневой View проекционной карточки, не мешая её инициализации.

Хук добавлен **в конец существующего агента** `local-media-bridge.js` (НЕ отдельным инжектом —
по методологии проекта один агент на процесс, повторный инжект даёт SIGSEGV crash-loop):

```js
C.onCreateView.overload('android.content.Context').implementation = function (ctx) {
    var v = this.onCreateView(ctx);          // оригинал ОБЯЗАТЕЛЕН: в нём инициализируется
    if (v !== null) v.setVisibility(8);      // binding, иначе handleMediaCardData/setUnknown
    return v;                                // падают в throwUninitializedPropertyAccessException
};
```

Классы: `F515ProjectionCard` и `Sf5ProjectionCard` (второй — с запасом, как в самом агенте).
Побочно: `onVisibilityChanged` на GONE останавливает marquee.

Состояние:
- пропатченный агент залит: `/data/user/0/com.ispace.toolbox/files/frida/local-media-bridge.js` (251897 б)
- бэкап на устройстве: `local-media-bridge.js.bak-20260815` (249773 б)
- бэкап локально: `~/f515/recon/ispace-frida/local-media-bridge.js.orig-backup`
- сниппет отдельно: `~/f515/recon/ispace-frida/cluster-card-off.snippet.js`
- синтаксис всего файла проверен `node --check`

Применение требует пересоздания процесса — агент резидентный, «no clean unhook once eternalized».
Переинжект после рестарта гарантирован веткой watcher'а `swb_should_run && ... ensure_agent apply`
(`status-swb = on`; этот же твик и держит агента в процессе при всех выключенных медиа-твиках).

Откат:
```
adb shell cp /data/user/0/com.ispace.toolbox/files/frida/local-media-bridge.js.bak-20260815 \
             /data/user/0/com.ispace.toolbox/files/frida/local-media-bridge.js
adb shell kill $(adb shell pidof com.seres.media.listen)
```

## Попытка убрать нагрузку (2026-08-15 12:50–13:07) — НЕ УДАЛОСЬ, откачено

Три итерации патча в существующий агент. Итог: нагрузку убрать не получилось, система возвращена
в исходное состояние.

**v1 — хук `onCreateView` → `setVisibility(GONE)`.** Полная тишина в трейсе. Две ошибки:
- логгер на Java `FileWriter` не пишет из uid system — нужен Frida File API (`new File(p,'a')`),
  как в самом агенте;
- хук опоздал: карточка создаётся при старте процесса, а watcher инжектит агента ~25 с спустя.
  Их собственный `tryEagerCaptureCardInstance ... via heap walk` существует ровно по этой причине.

**v2 — тот же код с Frida-логгером.** Дал главную диагностику:
```
[cluster-card-off] Java.perform failed: ReferenceError: 'Java' is not defined
```
Бандл собран frida-compile, глобального `Java` нет — мост живёт во внутренней переменной `V`
(28 вызовов `V.use`). Код, дописанный ПОСЛЕ бандла, не имеет к ней доступа.

**v3 — вставка кода ВНУТРЬ бандла** (перед финальным `});})();`, т.е. внутрь `V.perform`-колбэка,
с `V` вместо `Java`). Технически сработало:
```
[cluster-card-off] onCreateView hook installed OK
[cluster-card-off] startup: root views = 1
[cluster-card-off] startup: view #0 display=1 -> GONE
```
Единственный root View процесса — на display 1, он скрыт. **Но fps не изменился: 1317/25с = 53 fps,
CPU 29.6%.** Карточка визуально погасла, рендер продолжился.

**v4 — `Presentation.dismiss()` на display 1.** Сработало (`Presentation on display 1 dismissed`),
и стало **хуже**: 5464 кадра за 25 с = **218 fps**, CPU 37%. Приложение пересоздаёт Presentation
в цикле. Откачено немедленно.

### Что это доказывает

Нагрузка **не зависит от содержимого карточки**: со скрытым корневым View рендер идёт с той же
частотой, а с удалённой Presentation — вчетверо чаще. Значит источник не View и не marquee,
а сам цикл ViewRootImpl/Choreographer на display 1. Это подкрепляет версию с кривыми
vsync-таймстампами гипервизора (`Frame time is 0.219509 ms in the future! Check that graphics HAL
is generating vsync timestamps using the correct timebase`) — Choreographer не «успокаивается».

Практический вывод: точечными хуками в media.listen эту нагрузку не убрать. Осмысленные
направления, если возвращаться: (1) сам graphics HAL / vsync-таймбаза гостя под QNX —
общесистемная проблема, затронет не только это приложение; (2) не давать приложению
подниматься вообще, если карточка на приборке не нужна как функция.

### Состояние после отката (13:07)

- агент восстановлен из `local-media-bridge.js.bak-20260815` (249773 б), инжектирован в pid 16418
- swb-мост (`setMediaWithSource` → `current-media-source`) работает — твик «руль→музыка» цел
- 1357 кадров за 25 с = 54 fps, CPU 33% — исходные значения
- процесс за сессию перезапускался 4 раза; crash-loop guard не срабатывал, твики не отключались

## v5 — блокировка показа Presentation (2026-08-15 14:16). Тоже нет, откачено

Гипотеза: в v4 приложение пересоздавало Presentation потому, что гасился только показ, а сам
`show()` оставался разрешён. v5 закрывает и его: хук на `android.app.Dialog.show()`
(Presentation его не переопределяет, поэтому хукать надо базовый Dialog) с фильтром
`V.cast(this, Presentation).getDisplay().getDisplayId() === 1`, плюс dismiss существующей.

Технически отработало полностью:
```
[cluster-card-off] Dialog.show hook installed OK
[cluster-card-off] startup: existing Presentation on display 1 dismissed
[cluster-card-off] retry-10s: existing Presentation on display 1 dismissed
```
Окно действительно исчезло — на display 1 остался только `com.ts.car.clustercomm.projectionservice`.

**И это не помогло: 6937 кадров за 30 с = 231 fps, CPU 25.8%** — вчетверо больше исходных 53 fps.
Приложение крутит цикл пересоздания проекции, и цикл сам по себе стоит столько же CPU, сколько
и рендер. Тот же результат, что в v4 (218 fps), несмотря на закрытый show().

### Вывод: путь хуков в media.listen исчерпан

Проверены все три уровня — содержимое (v3: View GONE), окно (v4: dismiss), создание окна
(v5: блок show). Нагрузка не убирается ни на одном: приложение либо рендерит статику 53 fps,
либо жжёт столько же в цикле пересоздания. Причина лежит ниже приложения.

Остаются только крупные ходы:
1. **Жить с этим.** ~30-45% одного ядра из шести (load average 4.5-5.0 при 6 ядрах), приборка
   и медиа работают штатно. Практического ущерба нет.
2. **Копать vsync-таймбазу graphics HAL гостя** (`Frame time ... in the future`) — общесистемная
   проблема виртуализованного Android под QNX, заденет не только это приложение.
3. **`pm disable com.seres.media.listen`** — уберёт гарантированно, ценой всей медиасистемы
   (13 активити: DAB, Bluetooth-музыка, USB, радио, коллекция).

### Состояние после отката (14:17)

- агент оригинальный (249773 б), инжектирован в pid 8257, swb-мост цел (1615 записей setMediaWithSource)
- окно карточки вернулось на display 1, 1359 кадров за 25 с = 54 fps — исходные значения
- процесс перезапускался за сессию 6 раз, crash-loop guard не сработал ни разу, твики не отключались

## РЕШЕНИЕ: debug.hwui.fps_divisor (2026-08-15 14:41)

Вместо борьбы с источником invalidate — штатный рычаг HWUI, делящий частоту отрисовки.
Свойство читается процессом при инициализации HWUI, поэтому нужен рестарт процесса.

Замеры (окно на приборке, музыка не играет):

| настройка              | кадров/30с | fps  | CPU      | janky   | load avg |
|------------------------|-----------|------|----------|---------|----------|
| без делителя (исходно) | ~1600     | 54   | 30-45%   | 24-75%  | 4.9      |
| `debug.hwui.fps_divisor 4` | 416   | 13.9 | 11.1%    | 0%      | 3.3      |
| `debug.hwui.fps_divisor 2` | 790   | 26.3 | 10.0%    | 0.4%    | 4.1      |

**CPU у divisor=2 и divisor=4 одинаков (~10-11%)** — значит нелинейность: часть нагрузки
фиксированная, не на кадр. Поэтому divisor=2 строго лучше: вдвое больше кадров за ту же цену.
Итог: **нагрузка втрое-вчетверо меньше, janky практически исчез**.

### Оговорки

- Свойство **глобальное**: его подхватывают все процессы, стартующие ПОСЛЕ установки.
  Уже запущенные (launcher, SystemUI и пр.) не затронуты, пока не перезапустятся.
  При divisor=2 это 30 fps вместо 60 — заметно на анимациях, но терпимо; при 4 (15 fps) — грубо.
- Свойство **не persistent** — сбрасывается при перезагрузке. Для постоянства нужно ставить
  на старте (например, из уже имеющейся автозапускной обвязки в /data/local/tmp).
- Способа применить делитель только к одному приложению нет — свойство читается всем HWUI.

### Команды

```
adb shell setprop debug.hwui.fps_divisor 2      # включить
adb shell kill $(adb shell pidof com.seres.media.listen)   # перечитать в media.listen
adb shell setprop debug.hwui.fps_divisor ""     # вернуть как было (+ рестарт процесса)
```

Текущее состояние: `debug.hwui.fps_divisor = 2`, media.listen pid 15786, 26 fps, CPU 10%.
Агент iSpace — оригинальный, swb-мост цел. Карточка на приборке на месте и работает.

### Уточнение механики fps_divisor (14:50) — делитель применим точечно

Проверено экспериментально:

1. **На уже запущенные процессы не влияет.** `com.seres.launcher` (запущен 2 дня назад):
   528 кадров/20с с делителем и 529 кадров/20с после его снятия — 26.5 fps в обоих случаях.
   Лаунчер сам по себе рисует 26 fps, а не 60. Свойство читается HWUI один раз при
   инициализации процесса.
2. **Делитель живёт внутри процесса.** media.listen (pid 15786, стартовал при divisor=2)
   после снятия свойства продолжил давать 795 кадров/30с = 26.5 fps, CPU 13.3%.

Отсюда рецепт точечного применения к ОДНОМУ приложению (раньше считалось невозможным):
```
setprop debug.hwui.fps_divisor 2
kill $(pidof com.seres.media.listen)      # процесс стартует и "впитывает" делитель
setprop debug.hwui.fps_divisor ""         # снять, чтобы другие процессы не подхватили
```
Дыра рецепта: media.listen часто перезапускается сам и тогда подхватит уже пустое свойство.
Для постоянства нужен сторож (логика уже есть в frida-resume-watcher.sh — он отслеживает
pid media.listen против media-bridge-injpid).

### Текущее состояние (14:52, по решению пользователя)

`debug.hwui.fps_divisor = 2` **оставлено активным** — тогда media.listen подхватывает делитель
и при собственных перезапусках, без сторожа. Плата: все процессы, стартующие после этого
момента, тоже получают 30 fps вместо 60. Свойство не persistent — сбрасывается при ребуте.
