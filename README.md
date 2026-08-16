# f515-lab

Разборы и заметки по головному устройству F515 (Android-гость под QNX-гипервизором, SA8155).

- [LAUNCHER_WIDGET_TWEAKS.md](LAUNCHER_WIDGET_TWEAKS.md) — три твика для виджетов главного
  экрана: разблокировка удаления «несъёмных» плиток, расширение виджета недавних приложений
  с 3 до 5, и превращение виджета «Поездка» в панель переключения режимов автомобиля
  (Электро/Топливо) и вождения (ЭКО/Спорт). Готовые агенты, точки хуков, ключи
  `SeresPlatformAdapter`, интеграция в iSpace Toolbox.
- [TOOLBOX_APK_INSTALL_FALSE_FAILURE.md](TOOLBOX_APK_INSTALL_FALSE_FAILURE.md) — разбор для
  разработчика iSpace Toolbox: установка APK с флешки проходит, но показывается как
  неудачная. Логи, доказательства успешной установки, три наблюдения (`fixupAppDir` −22 на
  съёмных томах, недоставленный `PACKAGE_ADDED`) и что с этим делать.
- [MEDIA_LISTEN_CPU_INVESTIGATION.md](MEDIA_LISTEN_CPU_INVESTIGATION.md) — почему
  `com.seres.media.listen` жёг 30-45% CPU при неиграющей музыке: профилирование, пять
  неудачных попыток починки и рабочий обход через `debug.hwui.fps_divisor`.
