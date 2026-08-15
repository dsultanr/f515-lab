# f515-lab

Разборы и заметки по головному устройству F515 (Android-гость под QNX-гипервизором, SA8155).

- [LAUNCHER_WIDGET_TWEAKS.md](LAUNCHER_WIDGET_TWEAKS.md) — два твика для виджетов главного
  экрана: разблокировка удаления «несъёмных» плиток и расширение виджета недавних приложений
  с 3 до 5. Готовые агенты, точки хуков, интеграция в iSpace Toolbox.
- [MEDIA_LISTEN_CPU_INVESTIGATION.md](MEDIA_LISTEN_CPU_INVESTIGATION.md) — почему
  `com.seres.media.listen` жёг 30-45% CPU при неиграющей музыке: профилирование, пять
  неудачных попыток починки и рабочий обход через `debug.hwui.fps_divisor`.
