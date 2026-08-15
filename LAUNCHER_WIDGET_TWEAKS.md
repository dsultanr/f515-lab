# Три твика для iSpace Toolbox: виджеты главного экрана F515

1. **`widget_unlock_delete`** — разблокировать удаление «несъёмных» виджетов главного экрана.
2. **`recent5`** — расширить виджет недавних приложений с 3 плиток до 5.
3. **`trip_modes`** — превратить виджет «Поездка» в панель переключения режимов автомобиля
   (Электро / Топливо) и режимов вождения (ЭКО / Спорт).

Все три проверены вживую на F515 15.08.2026. Твики независимы, но на практике связаны:
пять плиток недавних влезают только после того, как с дока убраны лишние виджеты.

Первые два живут в процессе `com.seres.launcher`, третий — в `com.seres.settings`
(там уже резидентен `tweaks.js`, поэтому третий твик встраивается в него, без второго инжекта).

## Окружение, на котором проверено

| | |
|---|---|
| ГУ | F515, Android 11 (`RQ3A.211001.001 test-keys`), Android-гость под QNX-гипервизором SA8155 |
| Лаунчер | `com.seres.launcher`, `versionCode=658`, `versionName=SAIOS_SeresLauncher_7901201-PH01_251104_03719402_658`, targetSdk 30 |
| APK | `/system/app/SeresLauncher/SeresLauncher.apk` (15 811 487 байт) |
| Frida | 17.15.3 (`frida-inject`, уже staged в `/data/local/tmp/frida-inject`) |

Твики 1 и 2 нацелены на `com.seres.launcher` — раньше проект в него не инжектил, конфликтов с
`tweaks.js` / `local-media-bridge.js` / `swb-hook.js` нет; их логично свести в **один агент на
процесс** (модель проекта: inject-once-per-pid, свой inject-pid файл), разведя гейтами по
status-файлам. Твик 3 нацелен на `com.seres.settings`, где `tweaks.js` уже резидентен, поэтому
он встраивается в него — второй инжект в тот же процесс недопустим.

## Общее: сборка агента под Frida 17

В Frida 17 глобальный `Java` удалён — «голый» скрипт падает с `ReferenceError: 'Java' is not
defined`. Нужен `frida-java-bridge` и бандл в формате **iife** (тот же формат, в котором
собраны существующие агенты проекта):

```bash
npm install frida-compile frida-java-bridge
npx frida-compile agent.src.js -o agent.js -B iife -S
```

Логировать только через Frida File API (`new File(path, 'a')`). Java-`FileWriter` из процесса
с uid `system` в `/data/local/tmp` молча не пишет; файл лога надо заранее создавать в
apply-скрипте и `chmod 666` — как это уже делается для остальных агентов.

---

# Твик 1: `widget_unlock_delete`

## Проблема

Часть плиток главного экрана помечена в БД лаунчера как несъёмные, и в режиме редактирования
у них нет крестика удаления. Состояние по умолчанию (`seres_assembly_database`, таблица
`AssemblyModel`):

| id | label | className | canDelete |
|---|---|---|---|
| 4 | Настройки | `...settings.widgetprovider.SettingsSmartWidgetService` | 0 |
| 9 | Приложения | `localIconAppList` | 0 |
| 6 | навигация | `com.kika.car.library.widget.NaviSmartWidgetService` | 0 |
| 7 | Аудио | `...media.listen.launcherwidget.MediaSmartWidgetService` | 0 |
| 5 | Недавние | `com.seres.launcher.service.NearTaskSmartWidgetService` | 0 |
| 1 | Популярные | `...dialer.widgetservice.DialerSmartWidgetService` | 1 |
| 2 | Энергия | `...EnergyConsumeSmartWidgetService` | 1 |
| 3 | Поездка | `...TripDataSmartWidgetService` | 1 |
| 8 | Видео | `...media.vision.launcherwidget.VisionSmartWidgetService` | 1 |

## Где это решается в коде

`com.seres.launcher.assembly.AssemblyView`, расчёт видимости кнопки удаления:

```java
int i2 = (!(assemblyInfo != null && assemblyInfo.getEdit())
          || !assemblyInfo.getCanDelete()
          || assemblyInfo.getDraging()
          || c.x(assemblyInfo)) ? 8 : 0;      // 8 = GONE
```

`c.x(assemblyInfo)` — это всего лишь `className == "VPA"` (голосовой ассистент), то есть
единственный реальный барьер — `getCanDelete()`.

## Хук

```js
const Info = Java.use('com.seres.launcher.assembly.database.AssemblyInfo');
Info.getCanDelete.implementation = function () {
  return true;
};
```

## Почему этого достаточно и агент нужен только один раз

Удаление выполняет сам лаунчер своим штатным кодом и сохраняет результат в свою БД —
у виджета выставляется `isBound = 0`, строка в `AssemblyModel` остаётся (виджет
остаётся доступен для обратного добавления через каталог «Все услуги»). То есть **эффект
переживает перезапуск лаунчера и перезагрузку**, сторож не нужен: заинжектили, пользователь
удалил нужные плитки, агент можно выгружать (`kill` процесса лаунчера).

Проверено: после удаления «навигация» и «Аудио» получили `isBound=0` при сохранённых строках,
на главном экране осталось три плитки.

## Побочные эффекты, о которых надо знать

- Пока агент в процессе, крестик появляется у **всех** плиток, включая «Настройки» и
  «Приложения». Если пользователь удалит их, вернуть можно только через каталог добавления
  (или правкой БД). Стоит либо предупреждать в UI тулбокса, либо сузить хук белым списком
  className, разрешив удаление только выбранных плиток.
- Наблюдалось, что после работы с плиткой лаунчер сохраняет модель обратно в БД уже
  с `canDelete = 1` (значение берётся из объекта, где геттер подменён). То есть твик
  частично «залипает» в БД. Ущерба нет, но восстановление исходных флагов потребует
  правки БД, если это принципиально.

---

# Твик 2: `recent5`

## Что ограничивает количество плиток

Ограничений два, править надо оба.

**1. Константа в коде.** `com.seres.launcher.service.NearTaskSmartWidgetService.setIcons`:

```java
int min = Math.min(list.size(), 3);
for (int i2 = 0; i2 < min; i2++) {
    View childAt = itemSmartNearTaskerBinding.d.getChildAt(i2);   // ← слоты из разметки
    LinearLayout linearLayout = childAt instanceof LinearLayout ? (LinearLayout) childAt : null;
    if (linearLayout == null) return;
    AppInfoModel appInfoModel = list.get(i2);
    View childAt2 = linearLayout.getChildAt(0);   // ImageView
    View childAt3 = linearLayout.getChildAt(1);   // SeresAutoSizeTextView
    b.a((ImageView) childAt2, appInfoModel.getIconRes(), appInfoModel.getProcess());
    seresAutoSizeTextView.setText(appInfoModel.getLabel());
    linearLayout.setTag(C0134R.id.ll, appInfoModel);
    linearLayout.setVisibility(0);
}
if (min < 3) {
    for (int i4 = min; i4 < 3; i4++) itemSmartNearTaskerBinding.d.getChildAt(i4).setVisibility(8);
}
```

**2. Разметка.** `res/layout/item_smart_near_tasker.xml`: внутри контейнера `@+id/ll`
(`SeresLinearLayout`, horizontal, `wrap_content`) ровно **три** дочерних `SeresLinearLayout`,
каждый — `SeresAppIconImageView` + `SeresAutoSizeTextView`.

Поэтому **замена `3` на `5` сама по себе не работает**: `getChildAt(3)` вернёт `null`,
и метод выйдет по `if (linearLayout == null) return;`.

Данных хватает: `NearTaskStateFlow` список не обрезает — в живом замере было
`filled 5 of 18 recent apps`, то есть система держала 18 недавних задач.

## Решение

1. Достроить контейнер до нужного числа слотов: инфлейтить ту же разметку
   `item_smart_near_tasker`, взять из её `@id/ll` первый дочерний View, `removeViewAt(0)`
   и `addView` в рабочий контейнер. Так гарантированно совпадают типы (`getChildAt(1)`
   жёстко кастуется к `SeresAutoSizeTextView`) и стили.
2. Заполнить слоты самостоятельно по образцу оригинала, с лимитом `WANT` вместо 3.
3. Лишние слоты гасить `setVisibility(8)`.

Ширину трогать не нужно: контейнер `wrap_content`, плитка растягивается сама.

## Агент

```js
import Java from 'frida-java-bridge';

const LOG = '/data/local/tmp/recent5-trace.log';
function log(m) {
  try { const f = new File(LOG, 'a'); f.write(Date.now() + ' [recent5] ' + m + '\n'); f.close(); } catch (e) {}
}

const WANT = 5;

Java.perform(function () {
  const Svc          = Java.use('com.seres.launcher.service.NearTaskSmartWidgetService');
  const LinearLayout = Java.use('android.widget.LinearLayout');
  const ImageView    = Java.use('android.widget.ImageView');
  const AutoSize     = Java.use('com.seres.commonui.widget.textview.autosize.SeresAutoSizeTextView');
  const TextView     = Java.use('android.widget.TextView');
  const Inflater     = Java.use('android.view.LayoutInflater');
  const IconHelper   = Java.use('j1.b');                                  // b.a(ImageView, iconRes, process)
  const AppInfoModel = Java.use('com.seres.launcher.database.AppInfoModel');

  Svc.setIcons.implementation = function (list, binding) {
    try {
      const container = binding.d.value;                                   // SeresLinearLayout @id/ll
      const ctx  = container.getContext();
      const res  = ctx.getResources();
      const pkg  = ctx.getPackageName();
      const llId = res.getIdentifier('ll', 'id', pkg);

      // 1) достроить недостающие слоты инфлейтом той же разметки
      if (container.getChildCount() < WANT) {
        const layoutId = res.getIdentifier('item_smart_near_tasker', 'layout', pkg);
        const inflater = Inflater.from(ctx);
        let guard = 0;
        while (container.getChildCount() < WANT && guard++ < 10) {
          const tmpRoot = inflater.inflate(layoutId, null);
          const tmpLl   = Java.cast(tmpRoot.findViewById(llId), LinearLayout);
          const slot    = tmpLl.getChildAt(0);
          tmpLl.removeViewAt(0);                                           // отвязать от временного родителя
          container.addView(slot);
        }
        log('slots: ' + container.getChildCount());
      }

      // 2) заполнить, лимит WANT вместо 3
      const total = list.size();
      const n = Math.min(total, WANT);
      for (let i = 0; i < n; i++) {
        const slot = Java.cast(container.getChildAt(i), LinearLayout);
        const iv   = Java.cast(slot.getChildAt(0), ImageView);
        const tv   = Java.cast(slot.getChildAt(1), AutoSize);
        const tvb  = Java.cast(slot.getChildAt(1), TextView);
        const m    = Java.cast(list.get(i), AppInfoModel);
        tv.setUseAutoSize(true);
        IconHelper.a(iv, m.getIconRes(), m.getProcess());
        tvb.setText.overload('java.lang.CharSequence').call(tvb, m.getLabel());
        slot.setTag(llId, m);
        slot.setVisibility(0);
      }
      for (let i = n; i < WANT; i++) {
        const extra = container.getChildAt(i);
        if (extra !== null) extra.setVisibility(8);
      }
      binding.getRoot().setVisibility(n > 0 ? 0 : 8);
      log('filled ' + n + ' of ' + total);
    } catch (e) {
      log('custom setIcons failed, falling back: ' + e);
      return this.setIcons(list, binding);                                 // страховка: отдать оригиналу
    }
  };
  log('setIcons hook installed OK');
});
```

## Грабли

- `tv.setText(m.getLabel())` падает с `argument types do not match`: у `TextView` несколько
  перегрузок `setText`, `SeresAutoSizeTextView` их наследует. Нужен явный
  `Java.cast(view, TextView)` + `.setText.overload('java.lang.CharSequence')`.
- `Java.cast(m.getLabel(), CharSequence)` делает только хуже — `String` передавайте как есть.
- `setIcons` вызывается не в момент инжекта, а при обновлении списка недавних задач.
  После инжекта виджет перерисуется сам при первом запуске/закрытии приложения; для проверки
  достаточно `am start ... ; input keyevent KEYCODE_HOME`.

## Сторож обязателен

В отличие от твика 1, расширение **нигде не персистится**: количество слотов зашито в
разметку, подходящего поля в `AssemblyModel` нет. Любой перезапуск лаунчера возвращает три
плитки. Нужна ветка в `frida-resume-watcher.sh` рядом с `media_listen_active`:

```sh
recent5_should_run() { [ "$(cat "$DIR/status-recent5" 2>/dev/null)" = "on" ]; }
launcher_pid() { pidof com.seres.launcher; }

if recent5_should_run; then
    lcur=$(launcher_pid); linj=$(cat "$RECENT5_INJPID" 2>/dev/null)
    if [ -n "$lcur" ] && [ "$lcur" != "$linj" ]; then
        if [ -n "$linj" ] && crashloop_record_and_tripped launcher; then
            log "launcher crash-loop guard tripped -> disable recent5"
            disable_group recent5
        else
            log "launcher recreated (pid=$lcur injpid='$linj') -> re-inject recent5"
            sh "$RECENT5_APPLY" recent5 apply >> "$TRACE" 2>&1
        fi
    fi
fi
```

`recent5-apply.sh` — по образцу `media-bridge-apply.sh`:

```sh
TARGET=com.seres.launcher
JS=recent5.js
INJPID=$TMP/recent5-injpid
AGENT_PID_MARK=$TMP/recent5-agent-pid
STATUS_FILE="$DIR/status-recent5"          # persistent
TMP_STATUS=$TMP/recent5-status             # tmpfs

setenforce 0 2>/dev/null
[ -f "$TMP/recent5-trace.log" ] || : > "$TMP/recent5-trace.log"
chmod 666 "$TMP/recent5-trace.log" 2>/dev/null
```

## Ограничения и риски

- **Ширина дока.** Пять плиток влезают, если освобождено место (у нас были удалены
  «навигация» и «Аудио» — то есть твик 1 применён). При полном доке пять могут не поместиться:
  либо ограничиться четырьмя, либо считать доступную ширину.
- **Привязка к версии.** Хуки завязаны на `NearTaskSmartWidgetService.setIcons`, поле
  биндинга `d`, хелпер `j1.b.a`, `AssemblyInfo.getCanDelete` и структуру разметки — всё это
  обфусцированные имена конкретной сборки `_658`. После OTA лаунчера нужна перепроверка.
- **Fallback безопасен:** при любой ошибке агент отдаёт управление оригинальному `setIcons`,
  худший случай — привычные три плитки, а не сломанный лаунчер.

## Проверка

```sh
# инжект
/data/local/tmp/frida-inject -e -p $(pidof com.seres.launcher) -s /data/local/tmp/recent5.js

# триггернуть обновление списка
am start -n com.seres.settings/.main.MainActivity; sleep 3; input keyevent KEYCODE_HOME

tail -3 /data/local/tmp/recent5-trace.log
#   [recent5] setIcons hook installed OK
#   [recent5] slots: 5
#   [recent5] filled 5 of 18
```

## Откат

```sh
kill $(pidof com.seres.launcher)     # выгружает агента, состояние штатное
```

Для твика 1 откат означает лишь исчезновение крестиков: уже удалённые виджеты
возвращаются через каталог «Все услуги» на главном экране.


---

# Твик 3: `trip_modes`

Виджет «Поездка» (сетка 2×2 с пробегом, средним расходом и средней скоростью) превращается
в панель из четырёх кнопок:

```
Электро | Топливо     ← режим автомобиля
ЭКО     | Спорт       ← режим вождения
```

Активный режим подсвечивается белым, неактивный — серым. Значения читаются из машины,
а не запоминаются в твике, поэтому подсветка не врёт даже когда режим сменился сам
(например, автомобиль уходит с «только электро» при включении Спорта).

## Как машина переключает режимы

Оба действия делаются одним API — `com.seres.adapter.SeresPlatformAdapter` (клиентская
библиотека вкомпилирована в приложения-клиенты, ходит по binder в `com.seres.publicadapter`;
отдельного framework-jar нет):

```java
SeresPlatformAdapter.getInstance().setValue(key, value);   // value — строка
SeresPlatformAdapter.getInstance().getValueSync(key);
```

| Действие | Ключ | Значение | Как проверено |
|---|---|---|---|
| Только электро | `ID_VCH_POWER_MODE` | `1` | запись + скриншот UI |
| Приоритет электродвигателя | `ID_VCH_POWER_MODE` | `2` | наблюдалось |
| Умный | `ID_VCH_POWER_MODE` | `3` | не проверялось |
| Приоритет топлива | `ID_VCH_POWER_MODE` | `4` | запись + скриншот UI |
| Режим ЭКО | `ID_SETTING_DRIVE_MODE` | `3` | запись + скриншот UI |
| Комфорт | `ID_SETTING_DRIVE_MODE` | `2` | не проверялось |
| Спорт | `ID_SETTING_DRIVE_MODE` | `1` | запись + скриншот UI |

Значения идут в порядке кнопок в UI слева направо. **Осторожно с массивами из
`FeatureConfig`**: `rangModeCanArray = {2,4,3,1}` — это порядок циклического перебора
плитки в шторке, а не соответствие значений режимам; если читать его как маппинг,
получится неверная таблица (мы на этом ошиблись).

Оригинал (`DriveViewModel.runSetDriveMode`) после записи режима вождения ждёт 600 мс
и сверяет результат через `getValueSync("ID_SETTING_CHECK_DRIVE_MODE")` — при успехе
возвращается заданное значение.

Read-only соседи, которые легко принять за нужный ключ: `ID_VCH_ENGRE_MODE` (заданный режим,
запись игнорируется) и `ID_VCH_ACTUAL_MODE`.

## Куда встраиваться

Виджет реализован в `com.seres.settings.widgetprovider.TripDataSmartWidgetService`
(`extends WidgetService`). В `createView()` инфлейтится разметка, из неё достаются четыре
ячейки, в каждой — три `AppCompatTextView`:

| Что | id ячейки |
|---|---|
| Пробег | `2131362092` |
| Средний расход электро | `2131362125` |
| Средний расход топлива | `2131362680` |
| Средняя скорость | `2131362928` |

Внутри ячейки: значение `2131363364`, название `2131363365`, единица `2131363366`
(последних двух в некоторых ячейках может не быть — обязательно проверять на null).

## Агент

Код встраивается в существующий `tweaks.js` (перед закрывающим `})();`, внутрь IIFE,
где доступен java-мост `V`):

```js
;try{(function(){
function tlog(m){try{var f=new File('/data/local/tmp/trip-modes.log','a');f.write(Date.now()+' [trip-modes] '+m+'\n');f.close()}catch(e){}}

// id из разметки виджета "Поездка" (TripDataSmartWidgetService.createView)
var CELL_DISTANCE=2131362092, CELL_ELE=2131362125, CELL_OIL=2131362680, CELL_SPEED=2131362928;
var TV_VALUE=2131363364, TV_NAME=2131363365, TV_UNIT=2131363366;

var KEY_POWER='ID_VCH_POWER_MODE';      // 1=только электро, 4=приоритет топлива
var KEY_DRIVE='ID_SETTING_DRIVE_MODE';  // 3=ЭКО, 1=Спорт

// ячейка -> [подпись, ключ, значение, название группы]
var CELLS=[
  [CELL_DISTANCE,'Электро', KEY_POWER,'1','Режим авто'],
  [CELL_ELE,     'Топливо', KEY_POWER,'4','Режим авто'],
  [CELL_OIL,     'ЭКО',     KEY_DRIVE,'3','Вождение'],
  [CELL_SPEED,   'Спорт',   KEY_DRIVE,'1','Вождение']
];

var ACTIVE=0xffffffff|0, IDLE=0xff8a8a8a|0;
var adapter=null;
function ad(){ if(adapter===null){adapter=V.use('com.seres.adapter.SeresPlatformAdapter').getInstance()} return adapter }
function readKey(k){ try{ return ('' + ad().getValueSync(k)).trim() }catch(e){ tlog('read '+k+' failed: '+e); return null } }

var TextView=null, ViewCls=null, Clicker=null;

function paint(root){
  try{
    var pw=readKey(KEY_POWER), dr=readKey(KEY_DRIVE);
    for(var i=0;i<CELLS.length;i++){
      var c=CELLS[i], cell=root.findViewById(c[0]);
      if(cell===null){ tlog('cell '+c[1]+' not found'); continue }
      tlog('paint cell '+c[1]);
      var cellV=V.cast(cell, ViewCls);
      function tv(id){ var r=cellV.findViewById(id); return (r===null)?null:V.cast(r, TextView) }
      function put(t, s){ if(t!==null){ t.setText.overload('java.lang.CharSequence').call(t, s) } }
      var val=tv(TV_VALUE), nam=tv(TV_NAME), uni=tv(TV_UNIT);
      put(val, c[1]); put(nam, c[4]); put(uni, '');
      if(val===null){ tlog('  cell '+c[1]+': value tv missing'); continue }
      var cur = (c[2]===KEY_POWER) ? pw : dr;
      val.setTextColor(cur===c[3] ? ACTIVE : IDLE);
    }
  }catch(e){ tlog('paint failed: '+e) }
}

function decorate(root){
  if(TextView===null){ TextView=V.use('android.widget.TextView'); ViewCls=V.use('android.view.View') }
  var OCL=V.use('android.view.View$OnClickListener');
  for(var i=0;i<CELLS.length;i++){
    (function(c, idx){
      try{
        var cell=root.findViewById(c[0]);
        if(cell===null){ tlog('cell '+c[1]+' not found'); return }
        var cellV=V.cast(cell, ViewCls);
        var Klass=V.registerClass({
          name:'su.dsr.f515.TripClick'+idx,
          implements:[OCL],
          methods:{ onClick:function(v){
            try{
              tlog('click -> '+c[2]+'='+c[3]);
              ad().setValue(c[2], c[3]);
              // машина применяет режим не мгновенно (оригинал ждёт 600 мс перед сверкой)
              setTimeout(function(){
                V.scheduleOnMainThread(function(){ try{ paint(root) }catch(e){ tlog('repaint failed: '+e) } });
              }, 1200);
            }catch(e){ tlog('click failed: '+e) }
          }}
        });
        cellV.setClickable(true);
        cellV.setOnClickListener(Klass.$new());
        tlog('cell '+c[1]+' wired');
      }catch(e){ tlog('wire '+c[1]+' failed: '+e) }
    })(CELLS[i], i);
  }
  paint(root);
  tlog('widget decorated');
}

try{
  var Svc=V.use('com.seres.settings.widgetprovider.TripDataSmartWidgetService');
  try{ Svc.updateUI.implementation=function(){ /* off: иначе перезапишет наши подписи */ }; tlog('updateUI disabled') }
  catch(e){ tlog('updateUI hook failed: '+e) }
  Svc.createView.implementation=function(){
    var root=this.createView();
    try{ if(root!==null) decorate(root) }catch(e){ tlog('decorate failed: '+e) }
    return root;
  };
  tlog('TripDataSmartWidgetService hooks installed OK');
  // агент инжектится позже, чем лаунчер успевает запросить createView -> берём живой экземпляр
  V.scheduleOnMainThread(function(){
    try{
      V.choose('com.seres.settings.widgetprovider.TripDataSmartWidgetService',{
        onMatch:function(inst){
          try{
            var cls=inst.getClass(), fs=cls.getDeclaredFields(), root=null, names='';
            for(var k=0;k<fs.length;k++){
              var f=fs[k]; names+=f.getName()+':'+f.getType().getName()+' ';
              if(f.getType().getName()==='android.view.View'){
                f.setAccessible(true);
                var cand=f.get(inst);
                if(cand!==null){ root=cand }
              }
            }
            tlog('fields: '+names);
            if(root!==null){ decorate(V.cast(root, V.use('android.view.View'))); tlog('existing instance decorated via heap walk') }
            else tlog('no non-null View field found');
          }catch(e){ tlog('heap decorate failed: '+e) }
        },
        onComplete:function(){}
      });
    }catch(e){ tlog('choose failed: '+e) }
  });
}catch(e){ tlog('service hook FAILED: '+e) }
})()}catch(e){}
```

## Грабли

- **Хук `createView` опаздывает.** Лаунчер биндится к сервису и получает View раньше, чем
  watcher успевает инжектировать агента, поэтому одного хука мало — нужен heap walk по живому
  экземпляру (`V.choose` + рефлексия по полю типа `android.view.View`; имя поля `contentView`
  совпадает с декомпилированным, но надёжнее искать по типу).
- **`updateUI()` обязательно глушить**, иначе он перезапишет подписи данными поездки.
- **`V.registerClass` с `fields` не заработал** — пришлось делать отдельный listener-класс
  на ячейку с замыканием (`su.dsr.f515.TripClick0..3`).
- **Перерисовка сразу после клика показывает старое состояние** — машина применяет режим
  с задержкой; ставим repaint через ~1200 мс.
- **`findViewById` на «сыром» объекте из рефлексии** даёт `TypeError: not a function` —
  результат надо привести `V.cast(obj, View)`.

## Ограничения

- Плитка перестаёт показывать данные поездки — она целиком становится панелью режимов.
  Если это нежелательно, разумнее сделать отдельный виджет вместо подмены существующего.
- Твик живёт в `tweaks.js`; при обновлении тулбокса файл перезапишется. Именно поэтому
  его стоит внести в проект штатно — своим `status-trip_modes` и веткой в watcher
  (переинжект после пересоздания `com.seres.settings` уже работает через существующую
  логику tweaks-агента).
- Имена и id привязаны к сборке Настроек `SAIOS_S1_SeresSettings` этой прошивки;
  после OTA нужна перепроверка.

## Проверка

```sh
tail -f /data/local/tmp/trip-modes.log
#   [trip-modes] TripDataSmartWidgetService hooks installed OK
#   [trip-modes] cell Электро wired ... cell Спорт wired
#   [trip-modes] widget decorated
#   [trip-modes] click -> ID_SETTING_DRIVE_MODE=1
```
