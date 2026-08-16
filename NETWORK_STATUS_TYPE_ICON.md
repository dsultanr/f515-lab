# Разбор для разработчика Toolbox: твик «Статус сети» не рисует тип сети (4G)

Твик `network-status` из iSpace Toolbox показывает уровень сигнала, но **иконка типа сети
(4G) не появляется никогда**. Данные при этом читаются правильные и свежие: агент
вычисляет «4G, 4 палочки» — и пишет их не в те `View`.

Коротко: в разметке статус-бара внутри контейнера `ll_mobile_signal` лежат **три**
иконки, а в агенте зашиты id двух соседних — набор смещён на одну позицию. Иконка типа
сети (`mobile_signal_system`) не адресуется вообще, а «уровень» пишется в
`mobile_signal_data`, у которой в разметке стоит `android:visibility="gone"`.

## Окружение

| | |
|---|---|
| ГУ | F515, Android 11 (`RQ3A.211001.001 test-keys`), Android-гость под QNX-гипервизором SA8155 |
| Toolbox | `com.ispace.toolbox`, `versionName=1.44-beta.17`, `versionCode=4417` |
| Агент | `network-status.js`, инжектится в `com.android.systemui` (pid 1511 на момент разбора) |
| SystemUI | `/system/system_ext/priv-app/SeresSystemUI/SeresSystemUI.apk` (47 642 992 байта) |
| Твик | включён: `/data/local/tmp/network-status-status` = `on` |
| TBOX | выключен (`seres.platform.config.tbox` = `0`) — именно тот случай, ради которого мост и нужен |

## Как это устроено

На машине без опции TBOX штатная цепочка `ID_CELLULAR_*` мертва, поэтому уровень сигнала
внешнего модема приходит через tmpfs-мост `/dev/network-status-signal`. Файл пишет
`TboxWire.writeSignalFile` (проект [f515-usb-wwan](https://github.com/dsultanr/f515-usb-wwan)),
формат — четыре числа:

```
reg strength card uptimeSec
```

* `reg` — тип сети: `0` нет сети, `1` 2G, `3` 3G, **`6` 4G**, `10` 5G (`TboxWire.REG_*`);
* `strength` — уровень 0..5;
* `card` — 1, если `strength >= 0`;
* `uptimeSec` — метка времени по `/proc/uptime`, агент считает данные протухшими через 15 с.

Агент читает файл раз в 2 секунды и раскладывает его в два слота статус-бара:
`phone_signal_strength` (палочки) и `phone_signal_system` (тип сети).

## Наблюдение

Живой замер: в файле лежит корректное и свежее значение,

```
$ cat /dev/network-status-signal
6 4 1 2410
$ awk '{print int($1)}' /proc/uptime
2415
```

то есть `reg=6` (4G), `strength=4`, метка на 5 секунд младше текущего uptime — окно
устаревания не при чём. Собственный маппинг агента переводит `reg=6` в категорию `3`, а
наборы иконок в SystemUI — `status_bar_ic_signal_2g/3g/4g/5g` — нумеруются с единицы,
то есть `3` = **4G**. Значение верное.

Трейс агента тоже чистый, ошибок нет:

```
$ tail -3 /data/local/tmp/network-status-trace.log
1786905912318 +148438 agent loaded in pid 1511
1786905912321 +148440 tick loop armed @2000ms
1786905914360 +150479 views found: 1
```

При этом иконка 4G на экране не появляется.

## Причина: id смещены на одну позицию

`res/layout/car_status_bar.xml` из установленной сборки SystemUI — внутри
`ll_mobile_signal` **три** `StateStatusBarIconView`:

```xml
<com.android.keyguard.AlphaOptimizedLinearLayout android:id="@+id/ll_mobile_signal" ...>
  <androidx.constraintlayout.widget.ConstraintLayout ...>
    <com.android.systemui.car.widget.StateStatusBarIconView
        android:id="@+id/mobile_signal_strength"
        android:src="@drawable/status_bar_ic_signal_num_no_service"
        app:slot="@string/status_bar_phone_signal_strength"/>
    <com.android.systemui.car.widget.StateStatusBarIconView
        android:id="@+id/mobile_signal_system"
        app:slot="@string/status_bar_phone_signal_system"/>
    <com.android.systemui.car.widget.StateStatusBarIconView
        android:id="@+id/mobile_signal_data"
        android:visibility="gone"
        android:src="@drawable/status_bar_ic_signal_data"
        app:slot="@string/status_bar_phone_signal_data"/>
  </androidx.constraintlayout.widget.ConstraintLayout>
  ...
```

Числовые id — из `res/values/public.xml` **этой же** сборки:

| id (dec) | id (hex) | имя | роль |
|---|---|---|---|
| 2131362673 | `0x7f0a0371` | `ll_mobile_signal` | контейнер |
| 2131362796 | `0x7f0a03ec` | `mobile_signal_data` | скрыта (`gone`) |
| 2131362797 | `0x7f0a03ed` | `mobile_signal_strength` | палочки |
| **2131362798** | `0x7f0a03ee` | **`mobile_signal_system`** | **тип сети (4G)** |

В агенте (`network-status.js`, минифицированный бандл) зашито:

```js
Ip = 2131362673,   // контейнер            -> ll_mobile_signal        ВЕРНО
Tp = 2131362796,   // используется как "strength" -> mobile_signal_data    (скрыта!)
Cp = 2131362797,   // используется как "system"   -> mobile_signal_strength
qi = "com.android.systemui.car.widget.StateStatusBarIconView",
xp = "phone_signal_strength",
Np = "phone_signal_system",
```

Дальше по этим id ищутся вьюхи и в них пишется состояние:

```js
he.choose(qi, { onMatch: function (p) { if (p.getId() === Tp) d.push(he.retain(p)) },
  onComplete: function () {
    /* ... поднимаемся по родителям до Ip ... */
    var y = _.findViewById(Cp);
    var E = y !== null ? he.retain(he.cast(y, e)) : null;
    p.push({ container: he.retain(_), strength: d[f], system: E });
  }});

/* отрисовка */
var p = n.$new(xp, d.strength, null);   // l1.a("phone_signal_strength", strength, null)
var f = n.$new(Np, d.sys, null);        // l1.a("phone_signal_system",   sys,      null)
_.strength.setStateInfo(p);
_.system !== null && _.system.setStateInfo(f);
```

Итого:

* **уровень** уходит в `mobile_signal_data` — она `gone`, поэтому не видна (агент делает
  видимым только контейнер, саму вьюху — нет);
* **тип сети** уходит в `mobile_signal_strength` — вьюху палочек;
* `mobile_signal_system` (2131362798), единственная, которая рисует 2G/3G/4G/5G,
  не адресуется вообще — отсюда и «тип сети не показывается никогда».

## Фикс

Минимально — сдвинуть оба id на правильные вьюхи:

```js
-Tp = 2131362796,   // mobile_signal_data (gone)
-Cp = 2131362797,   // mobile_signal_strength
+Tp = 2131362797,   // mobile_signal_strength — палочки
+Cp = 2131362798,   // mobile_signal_system   — тип сети (4G)
```

Надёжнее — не хардкодить числа, а резолвить по имени в рантайме: числовые id смещаются
между сборками SystemUI, и это ровно тот способ, которым твик сломается снова после
очередного OTA (он уже сломан именно так).

```js
// один раз, когда есть любой Context из SystemUI (например, view.getContext())
var res = ctx.getResources(), PKG = 'com.android.systemui';
var ID_CONTAINER = res.getIdentifier('ll_mobile_signal',       'id', PKG);
var ID_STRENGTH  = res.getIdentifier('mobile_signal_strength', 'id', PKG);
var ID_SYSTEM    = res.getIdentifier('mobile_signal_system',   'id', PKG);
// getIdentifier вернёт 0, если имя пропало — это и есть сигнал «разметка поменялась,
// рисовать нельзя», лучше залогировать и не трогать статус-бар вслепую.
```

и дальше искать `strength` по `ID_STRENGTH`, а `system` — по `ID_SYSTEM`.

## Что ещё стоит учесть

* **`mobile_signal_data` скрыта разметкой.** Если по замыслу нужна и она (иконка передачи
  данных), одного `setStateInfo` мало — вьюхе нужен `setVisibility(VISIBLE)`.
* **Штатный `SeresStatusBarSignalPolicy` пишет в те же слоты.** Он гоняет их через
  `StatusBarIconController.setSeresIconState` и при `signalSystem <= 0` сбрасывает
  уровень в `-1`. То есть он конкурирует с агентом, который раз в 2 секунды пишет во
  вьюхи напрямую; на машине с выключенным TBOX штатная ветка данных мертва, но сами
  сбросы никуда не деваются.
* **`views found: 1`** в трейсе не означает, что найдено всё нужное: вьюха типа сети
  ищется отдельным `findViewById`, и её отсутствие (`system: null`) нигде не логируется —
  ровно поэтому дефект и выглядел «молчаливым». Одна строка лога про `system === null`
  сэкономила бы весь этот разбор.

## Как проверить после правки

```sh
# что в мосте (reg strength card uptimeSec)
cat /dev/network-status-signal        # напр. 6 4 1 2410  -> 4G, 4 палочки
awk '{print int($1)}' /proc/uptime    # 4-е поле не должно отставать больше чем на 15 с

tail -5 /data/local/tmp/network-status-trace.log
```

На экране в статус-баре должны появиться одновременно палочки уровня и иконка `4G`.
