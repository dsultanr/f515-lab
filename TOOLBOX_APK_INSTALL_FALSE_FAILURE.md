# iSpace Toolbox: установка APK проходит, но показывается как неудачная

Разбор для разработчика тулбокса. Пользователь трижды подряд ставил APK с флешки через
Toolbox, каждый раз получал сообщение о неудаче — а пакет при этом устанавливался. Ниже
логи, доказательства того, что установка состоялась, и три независимых наблюдения, из
которых складывается объяснение.

Снято вживую на F515 16.08.2026, время в логах — MSK.

## Окружение

| | |
|---|---|
| ГУ | F515, Android 11 (`RQ3A.211001.001 test-keys`), security patch 2022-10-05, Android-гость под QNX-гипервизором SA8155 |
| Toolbox | `com.ispace.toolbox`, `versionName=1.44-beta.17`, `versionCode=4417`, targetSdk 34 |
| Хост-процесс установщика | `com.seres.engineeringmode` (`versionCode=1`), pid 3468 — Toolbox работает в нём через JVMTI-инъекцию, оттуда же идут строки `ApkInstallBiz` |
| Штатный установщик | `com.android.packageinstaller` 4.5.0.0, targetSdk 30 |
| Устанавливаемый пакет | `su.dsr.f515usbwwan` 3.2 (`versionCode=23`), 845 555 Б, подписан v2, minSdk 26 / targetSdk 29 |
| Источник APK | съёмный exFAT-том `/storage/19FF-0859-0008-0017` (он же `/mnt/media_rw/...`) |

## Что наблюдает пользователь

Toolbox → установка APK с флешки → сообщение о неудаче. Три попытки подряд, все три
«неудачные». Точный текст сообщения в этом разборе не зафиксирован — если он будет, его
стоит сюда добавить: он покажет, на каком именно шаге тулбокс считает операцию проваленной.

## Что показывают факты: установка прошла

Сразу после третьей «неудачной» попытки:

```
$ adb shell dumpsys package su.dsr.f515usbwwan | grep -E "versionName|versionCode|lastUpdateTime"
    versionCode=23 minSdk=26 targetSdk=29
    versionName=3.2
    lastUpdateTime=2026-08-16 12:54:55
```

И установленный APK совпадает с исходным байт в байт:

```
$ adb shell md5sum $(adb shell pm path su.dsr.f515usbwwan | sed 's/package://')
8610d4abcd7817f24c42edeae039b5b5  /data/app/~~1BQKsHGAJ2ANejy2ur4rdw==/su.dsr.f515usbwwan-.../base.apk

$ adb shell md5sum /mnt/media_rw/19FF-0859-0008-0017/F515UsbWwanApp.apk
8610d4abcd7817f24c42edeae039b5b5
```

То есть APK скопирован, разобран, установлен и активен. Ошибка — только в том, что видит
пользователь.

## Хронология по логу

Строки ниже — из `logcat -d`, вычищены только посторонние теги (`RadioServer`, `MM_OSAL`,
`GlRenderControl` и подобный шум).

```
12:54:55.494  3468  9215 W engineeringmod: Openjdkjvmti plugin was loaded on a non-debuggable
                                            Runtime. Plugin was loaded too late to change
                                            runtime state to DEBUGGABLE...
12:54:55.574  3468  9215 E ApkInstallBiz: start copy install
12:54:55.662   864  1280 W RuleEvaluation: Integrity rule files are not available.
12:54:55.670   864  1041 W PackageManager: No IntentFilter verification will not be done as
                                            there is no IntentFilterVerifier available!
12:54:55.671   864   982 E ActivityManager: Killing 2930:su.dsr.f515usbwwan/u0a38 (adj 945):
                                            stop su.dsr.f515usbwwan due to installPackageLI
12:54:55.769   273   285 E vold    : Failed to find mounted volume for /Android/obb/su.dsr.f515usbwwan/
12:54:55.769   864  1041 E StorageManagerService: Failed to fixup app dir for su.dsr.f515usbwwan
12:54:55.769   864  1041 E StorageManagerService: android.os.ServiceSpecificException:  (code -22)
        at android.os.IVold$Stub$Proxy.fixupAppDir(IVold.java:2067)
        at com.android.server.StorageManagerService$StorageManagerInternalImpl
              .prepareAppDataAfterInstall(StorageManagerService.java:4770)
        at com.android.server.pm.PackageManagerService.prepareAppDataAfterInstallLIF(...:23059)
        at com.android.server.pm.PackageManagerService.executePostCommitSteps(...:17101)
        at com.android.server.pm.PackageManagerService.installPackagesLI(...:17033)
        ...
        (то же самое повторяется ещё раз — по одному разу на каждый смонтированный
         съёмный том)
12:54:56.176   768  1188 E installd: Couldn't opendir /data/app/vmdl367373448.tmp: No such file
                                     or directory
12:54:56.176   768  1188 E installd: Failed to delete /data/app/vmdl367373448.tmp: No such file
                                     or directory
12:54:56.265   864   982 W BroadcastQueue: Background execution not allowed: receiving Intent
                                     { act=android.intent.action.PACKAGE_ADDED
                                       dat=package:su.dsr.f515usbwwan flg=0x4000010 (has extras) }
                                     to com.android.packageinstaller/.PackageInstalledReceiver
```

Дальше от pid 3468 (тулбокс) идут только `AdapterManager.bindAdapterService` раз в 3.5
секунды — то есть **о результате установки `ApkInstallBiz` не пишет в лог ничего**: ни
успеха, ни ошибки. Единственная его строка за всю операцию — `start copy install`.

## Три независимых наблюдения

**1. Установка завершена штатно.** `installPackagesLI` дошёл до `executePostCommitSteps`,
процесс старой версии убит по `installPackageLI`, `PACKAGE_ADDED` разослан. Всё, что после
этого падает, к самому пакету отношения не имеет.

**2. `fixupAppDir` падает с `-22` (EINVAL) на съёмных томах.** `vold` не может найти
смонтированный том для `/Android/obb/su.dsr.f515usbwwan/`. Это post-commit шаг подготовки
каталогов приложения на внешнем хранилище: на голове смонтированы два съёмных exFAT-тома,
и на каждом из них создать `Android/obb/<пакет>` не выходит. На установленный пакет это не
влияет (см. пункт 1 и совпадение md5), но в логе выглядит громко — четыре стектрейса
уровня `E` подряд.

**3. `PACKAGE_ADDED` не доставлен штатному приёмнику установщика.**
`com.android.packageinstaller/.PackageInstalledReceiver` не получил broadcast: «Background
execution not allowed». Это обычное для Android 8+ поведение — неявные broadcast'ы не
будят фоновые приёмники, — но именно из этого приёмника штатная цепочка узнаёт, что
установка удалась.

## Гипотеза о причине сообщения

Кода тулбокса у меня нет, поэтому это гипотеза, а не вывод: `ApkInstallBiz` судит об успехе
не по результату сессии установки, а по внешнему признаку — либо ждёт broadcast
`PACKAGE_ADDED` (который не приходит, пункт 3), либо ловит ошибку post-commit шага (пункт 2)
и трактует её как провал всей операции. Оба признака на этой голове ложные.

Проверяемое следствие гипотезы: сообщение об ошибке появляется **не сразу**, а после
таймаута ожидания — если это так, дело в broadcast'е; если сразу, то в исключении от
post-commit.

## Что предлагается сделать

1. **Определять исход по PackageManager, а не по broadcast.** После коммита сессии
   достаточно `getPackageInfo(pkg, 0)` и сравнения `versionCode`/`lastUpdateTime` с тем, что
   ставили. Это работает независимо от того, дошёл ли broadcast и что случилось с
   `Android/obb`.
2. **Если используется `PackageInstaller.Session` — брать результат из `IntentSender`**,
   который передаётся в `commit()`: он доставляется адресно и запретом фоновых broadcast'ов
   не режется, в отличие от неявного `PACKAGE_ADDED`. Статус приходит в
   `EXTRA_STATUS`/`EXTRA_STATUS_MESSAGE`.
3. **Не считать `fixupAppDir`/`obb` фатальными.** Ошибка относится к каталогам на съёмных
   томах и не мешает ни установке, ни запуску приложения.
4. **Логировать исход.** Сейчас `ApkInstallBiz` пишет только `start copy install`. Одна
   строка с кодом результата в конце операции сняла бы весь этот разбор — по логу сейчас
   невозможно отличить «тулбокс решил, что не вышло» от «тулбокс не дождался ответа».
5. **Показывать в сообщении об ошибке, на каком шаге оно случилось** (копирование /
   коммит сессии / ожидание подтверждения) — тогда пользователь не будет ставить одно и то
   же по три раза.

## Как проверить, что установка на самом деле прошла

```sh
adb shell dumpsys package <пакет> | grep -E "versionName|versionCode|lastUpdateTime"
adb shell md5sum $(adb shell pm path <пакет> | sed 's/package://')
```

Если `versionCode` уже новый — переставлять не нужно, что бы ни показал экран.

## Что осталось невыясненным

* Точный текст сообщения тулбокса и задержка до его появления (см. проверяемое следствие
  выше).
* Логи двух более ранних попыток: буфер `logcat` на этой голове держит около двух минут
  (`RadioServer` пишет `dealFmRsq` по несколько строк в секунду и вытесняет всё остальное),
  поэтому в дампе остался только третий заход. Логи снимать сразу после воспроизведения.
* Что именно делает шаг `copy install` — копирует ли тулбокс APK во внутреннее хранилище
  перед установкой, и не связан ли отказ `fixupAppDir` с тем, что источник лежал на exFAT.
