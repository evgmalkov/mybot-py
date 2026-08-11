[English](README.md) · **Русский**

# MyBotPy

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/github/license/evgmalkov/mybot-py?style=flat-square" alt="License"></a>
  <a href="https://www.python.org/downloads/release/python-3132/"><img src="https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.13"></a>
  <a href="https://www.memuplay.com/"><img src="https://img.shields.io/badge/emulator-MEmu-4CAF50?style=flat-square" alt="MEmu"></a>
  <a href="https://tronscan.org/#/address/TGVWcdhJkwYw7qhLqSieXjZCsMJxPQKhK4"><img src="https://img.shields.io/badge/USDT-Donate-2EBE74?style=flat-square&logo=tether&logoColor=white" alt="USDT Donate"></a>
</p>

Бот-фармер для Clash of Clans на эмуляторе MEmu. Python 3.13, ADB. Открытый исходник,
MEmu-нативный, лёгкое зрение на матчинге шаблонов, без нейросетевых зависимостей.

Стек: Python 3.13, OpenCV, numpy, PyQt5, uiautomator2, ADB, MEmu.
Версия: 1.2.0 (см. [`version.py`](version.py)). Автор: E. Malkov.

## Установка
Один раз:

1. Поставь Python 3.13 — [python.org](https://www.python.org/downloads/release/python-3132/).
   Отметь галочку «Add python.exe to PATH».
2. Поставь MEmu — [memuplay.com](https://www.memuplay.com/) (проверено на 9.5.3). Запусти один раз.
   Разрешение (1600×900), рендер DirectX и ADB `127.0.0.1:21503` бот выставит сам через `memuc`.
3. Установи Clash of Clans в MEmu, войди в аккаунт, оставь на домашней базе.
4. Скачай репозиторий (Code → Download ZIP) или `git clone`.
5. Запусти [`setup.bat`](setup.bat) — поставит зависимости. Один раз.
6. Запусти [`run.bat`](run.bat) — стартует бот. Логи — во вкладке Logs.

Без venv и ручных путей. Настройки — в `settings.json` (из
[`settings.example.json`](settings.example.json)).

## Если не запускается
- `run.bat` ничего не делает (консоль мелькнула и закрылась): запусти
  [`run_debug.bat`](run_debug.bat) — он держит консоль открытой и показывает ошибку. Обычно это
  недостающая зависимость, запусти [`setup.bat`](setup.bat) ещё раз.
- Первый запуск долгий: на старте грузятся шаблоны, дай GUI ~10 секунд.
- Бот ставит MEmu в 1600×900, а для этого нужны права админа. Запусти `run.bat` от администратора
  один раз, чтобы применилось разрешение. Дальше для фарма админ не нужен.

## Возможности
- Атака (`attacks/attacks.py`): драконы, шары, осада, герои, заклы, герой Duke, Stone Slammer,
  x4-ускорение, в конце сбрасывает остатки войск.
  - Способность героя при низком HP: следит за HP-полоской и жмёт способность, когда просядет.
    Grand Warden жмётся проактивно (`config/heroes.json`). После активации возвращает выбор на
    текущий закл/войско.
  - Не тапает вслепую, если прервал бой (End Battle / Pause / Stop) — включая стратегии MBR-CSV.
  - Тапы пачками (один adb-вызов на пачку) вместо тапа-на-вызов.
- Тренировка (`train/`): состав по шаблонам иконок, «полна ли армия» по матчингу дробей.
  - Состав заклов держится точным по счёту плиток (`config/army.json`), плюс санити-проверка
    прочитанной вместимости казарм, чтобы сбой OCR не раздул число тренировки.
- Деревня (`villages/`): апгрейд стен, клановые игры, запрос войск, мультиаккаунт.
  - Апгрейд стен по уровню: читает подпись «Wall (Level N)» и улучшает только стены в диапазоне
    `[from..to)` (`Templates/walls/level_text/`).
- Полные хранилища → сон или смена аккаунта (`config/farming.json`, GUI: Stop when full): тёмный
  эликсир — по заливке бара, золото и эликсир — по «перестало расти». Вместимость хранилищ знать
  не нужно.
- Чтение чисел (`vision/digit_ocr.py`): матчинг шаблонов цифр, без OCR-библиотеки.
- Управление MEmu через `memuc` и `.memu` — работает в фоне / свёрнутым. MEmu сейчас единственная
  стабильная платформа; другие эмуляторы в GUI заблокированы (в работе). Для BlueStacks есть фикс
  конфликта версий adb (свой HD-Adb + reconnect).

## Структура
Плоские импорты, слои добавлены в `sys.path`:

| каталог | назначение |
|---|---|
| `core/` | цикл бота, захват/матчинг, обновления |
| `emu/` | эмулятор, ADB, ввод, скриншоты |
| `vision/` | распознавание экрана |
| `train/` | тренировка войска |
| `villages/` | стены, клан-игры, запрос войск |
| `ui/` | интерфейс (PyQt) |
| `attacks/` | логика атак |
| `Templates/` | эталоны для матчинга (1600×900) |

Пути — [`paths.py`](paths.py). Версия — [`version.py`](version.py).

## Поддержать
Бесплатно, MIT. Если полезно и хочешь закинуть на кофе — вот кошелёк. По желанию, ничего за это не
открывается.

- USDT (TRC20 / TRON): `TGVWcdhJkwYw7qhLqSieXjZCsMJxPQKhK4`

## Лицензия
См. [`LICENSE`](LICENSE).
