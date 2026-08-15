# f515-lab

Разборы и заметки по головному устройству F515 (Android-гость под QNX-гипервизором, SA8155).

- [MEDIA_LISTEN_CPU_INVESTIGATION.md](MEDIA_LISTEN_CPU_INVESTIGATION.md) — почему `com.seres.media.listen`
  жёг 30-45% CPU при неиграющей музыке: профилирование, пять неудачных попыток починки
  и рабочий обход через `debug.hwui.fps_divisor`.
