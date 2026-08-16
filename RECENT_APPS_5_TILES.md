# Твик для iSpace Toolbox: «Недавние приложения — 5 плиток вместо 3»

Рецепт реализации твика, расширяющего смарт-виджет недавних приложений на главном экране
с трёх плиток до пяти. Проверено вживую на F515 15.08.2026.

## Окружение, на котором проверено

| | |
|---|---|
| ГУ | F515, Android 11 (`RQ3A.211001.001 test-keys`), Android-гость под QNX-гипервизором SA8155 |
| Лаунчер | `com.seres.launcher`, `versionCode=658`, `versionName=SAIOS_SeresLauncher_7901201-PH01_251104_03719402_658`, targetSdk 30 |
| APK | `/system/app/SeresLauncher/SeresLauncher.apk` (15 811 487 байт) |
| Frida | 17.15.3 (`frida-inject`, уже staged в `/data/local/tmp/frida-inject`) |
| TBOX | **выключен** с 16.08.2026: системный параметр стенда `seres.platform.config.tbox` = `0` |

## Что ограничивает количество плиток

Два независимых ограничения — важно, что править надо оба.

**1. Жёсткая константа в коде.** `com.seres.launcher.service.NearTaskSmartWidgetService.setIcons`:

```java
int min = Math.min(list.size(), 3);
for (int i2 = 0; i2 < min; i2++) {
    View childAt = itemSmartNearTaskerBinding.d.getChildAt(i2);   // ← слоты берутся из разметки
    LinearLayout linearLayout = childAt instanceof LinearLayout ? (LinearLayout) childAt : null;
    if (linearLayout == null) return;
    AppInfoModel appInfoModel = list.get(i2);
    View childAt2 = linearLayout.getChildAt(0);   // ImageView
    View childAt3 = linearLayout.getChildAt(1);   // SeresAutoSizeTextView
    ...
    b.a((ImageView) childAt2, appInfoModel.getIconRes(), appInfoModel.getProcess());
    seresAutoSizeTextView.setText(appInfoModel.getLabel());
    linearLayout.setTag(C0134R.id.ll, appInfoModel);
    linearLayout.setVisibility(0);
}
if (min < 3) {
    for (int i4 = min; i4 < 3; i4++) itemSmartNearTaskerBinding.d.getChildAt(i4).setVisibility(8);
}
```

**2. Количество слотов в разметке.** `res/layout/item_smart_near_tasker.xml` — внутри контейнера
`@+id/ll` (`SeresLinearLayout`, horizontal, `wrap_content`) ровно **три** дочерних
`SeresLinearLayout`, каждый из которых содержит `SeresAppIconImageView` + `SeresAutoSizeTextView`.

Поэтому **простая замена `3` на `5` не работает**: `getChildAt(3)` вернёт `null`, и метод выйдет
по `if (linearLayout == null) return;`.

Данных при этом хватает с запасом — источник (`NearTaskStateFlow`) список не обрезает,
в логе живого замера было `filled 5 of 18 recent apps`.

## Решение

В хуке на `setIcons`:

1. Достроить контейнер до нужного числа слотов: инфлейтить ту же разметку
   `item_smart_near_tasker`, взять из её `@id/ll` первый дочерний View, `removeViewAt(0)`
   и `addView` в рабочий контейнер. Так гарантированно совпадают типы (`getChildAt(1)`
   жёстко кастуется к `SeresAutoSizeTextView`) и стили.
2. Заполнить слоты самостоятельно по образцу оригинала, с лимитом 5 вместо 3.
3. Лишние слоты гасить `setVisibility(8)`.

Ширину трогать не надо: контейнер `wrap_content`, плитка растягивается сама.

## Агент

Сборка обязательно под Frida 17: глобального `Java` в ней больше нет, нужен
`frida-java-bridge` и бандл в формате **iife** (тот же формат, что у существующих агентов
проекта).

```bash
npm install frida-compile frida-java-bridge
npx frida-compile recent5.js -o recent5.js.bundle -B iife -S
```

`recent5.src.js`:

```js
import Java from 'frida-java-bridge';

const LOG = '/data/local/tmp/recent5-trace.log';
function log(m) {
  try { const f = new File(LOG, 'a'); f.write(Date.now() + ' [recent5] ' + m + '\n'); f.close(); } catch (e) {}
}

const WANT = 5;   // сколько плиток показывать

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

### Грабли, на которые мы наступили

- `tv.setText(m.getLabel())` — падает с `argument types do not match`: у `TextView` несколько
  перегрузок `setText`, а `SeresAutoSizeTextView` их наследует. Нужен явный
  `Java.cast(view, TextView)` + `.setText.overload('java.lang.CharSequence')`.
- `Java.cast(m.getLabel(), CharSequence)` делает только хуже — строку приводить не надо,
  передавайте `String` как есть.
- Логирование через Java `FileWriter` из процесса с uid `system` в `/data/local/tmp` молча
  не работает. Пишите через Frida File API (`new File(path, 'a')`), как в остальных агентах
  проекта; файл лога предварительно создавать в apply-скрипте с `chmod 666`.

## Интеграция в инфраструктуру iSpace

По той же модели, что и остальные твики: **один агент на процесс, inject-once-per-pid**.

Целевой процесс — `com.seres.launcher`, ранее в него никто не инжектил, конфликтов с
`tweaks.js` / `local-media-bridge.js` / `swb-hook.js` нет. Повторный инжект в уже хукнутый
процесс, как обычно, недопустим (стек хуков → SIGSEGV), поэтому нужен свой inject-pid файл.

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

Ветка в `frida-resume-watcher.sh` (рядом с `media_listen_active`):

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

**Сторож здесь обязателен, а не желателен.** В отличие от удаления виджетов (лаунчер
сохраняет это в своей БД `seres_assembly_database`, поле `isBound`), пятая и четвёртая плитки
нигде не персистятся: количество слотов зашито в разметку, подходящего поля в
`AssemblyModel` нет. Любой перезапуск лаунчера возвращает три плитки.

### Момент применения

`setIcons` вызывается не при инжекте, а при обновлении списка недавних задач. После инжекта
виджет перерисуется сам при первом же запуске/закрытии приложения. Для немедленного эффекта
в apply-скрипте можно дёрнуть обновление, но проще этого не делать — эффект появится
в течение обычной работы.

## Ограничения и риски

- **Ширина.** Пять плиток влезают, если на главном экране освобождено место (у нас были
  удалены виджеты «навигация» и «Аудио»). При полном доке пять плиток могут не поместиться —
  стоит либо ограничиться четырьмя, либо проверять доступную ширину.
- **Не переживает перезапуск лаунчера** без сторожа (см. выше).
- **Привязка к версии.** Хук завязан на имена `NearTaskSmartWidgetService.setIcons`,
  поле биндинга `d`, хелпер `j1.b.a` и структуру разметки. Всё это обфусцированные имена
  конкретной сборки `_658` — после OTA лаунчера нужно перепроверять (у проекта уже есть
  практика проверки твиков после OTA).
- **Fallback безопасен:** при любой ошибке агент отдаёт управление оригинальному `setIcons`,
  то есть худший случай — привычные три плитки, а не сломанный лаунчер.

## Проверка

```sh
# инжект
/data/local/tmp/frida-inject -e -p $(pidof com.seres.launcher) -s /data/local/tmp/recent5.js

# триггернуть обновление списка
am start -n com.seres.settings/.main.MainActivity; sleep 3; input keyevent KEYCODE_HOME

# ожидаемо в логе
tail -3 /data/local/tmp/recent5-trace.log
#   [recent5] setIcons hook installed OK
#   [recent5] slots: 5
#   [recent5] filled 5 of 18
```

## Откат

Перезапуск процесса лаунчера убирает агента целиком, состояние возвращается к штатному:

```sh
kill $(pidof com.seres.launcher)
```
