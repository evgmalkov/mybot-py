**English** · [Русский](README.ru.md)

# MyBotPy

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/github/license/evgmalkov/mybot-py?style=flat-square" alt="License"></a>
  <a href="https://www.python.org/downloads/release/python-3132/"><img src="https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.13"></a>
  <a href="https://www.memuplay.com/"><img src="https://img.shields.io/badge/emulator-MEmu-4CAF50?style=flat-square" alt="MEmu"></a>
  <a href="https://tronscan.org/#/address/TGVWcdhJkwYw7qhLqSieXjZCsMJxPQKhK4"><img src="https://img.shields.io/badge/USDT-Donate-2EBE74?style=flat-square&logo=tether&logoColor=white" alt="USDT Donate"></a>
</p>

Farming bot for Clash of Clans on the MEmu emulator. Python 3.13, ADB. Open source, MEmu-native,
lightweight template-matching vision, no neural-network dependencies.

Stack: Python 3.13, OpenCV, numpy, PyQt5, uiautomator2, ADB, MEmu / LDPlayer.
Version: 1.3.0 (see [`version.py`](version.py)). Author: E. Malkov.

## Setup
Do this once:

1. Install Python 3.13 — [python.org](https://www.python.org/downloads/release/python-3132/).
   Check "Add python.exe to PATH".
2. Install MEmu — [memuplay.com](https://www.memuplay.com/) (tested on 9.5.3). Launch it once.
   The bot sets the resolution (1600×900), the DirectX renderer and ADB `127.0.0.1:21503` itself
   via `memuc`.
3. Install Clash of Clans in MEmu, sign in, stay on the home base.
4. Download the repo (Code → Download ZIP) or `git clone`.
5. Run [`setup.bat`](setup.bat) — installs the dependencies. Once.
6. Run [`run.bat`](run.bat) — starts the bot. Logs are in the Logs tab.

No venv, no manual paths. Settings go to `settings.json` (from
[`settings.example.json`](settings.example.json)).

## Troubleshooting
- `run.bat` does nothing (a console flashes and closes): run [`run_debug.bat`](run_debug.bat), it
  keeps the console open and shows the error. Usually a missing dependency — run
  [`setup.bat`](setup.bat) again.
- First launch is slow: the GUI loads templates on start, give it ~10 seconds.
- The bot sets MEmu to 1600×900, and that needs admin. Run `run.bat` as administrator once so the
  resolution applies. After that, farming works without admin.

## Features
- Attack (`attacks/attacks.py`): dragons, balloons, siege, heroes, spells, the Duke hero, Stone
  Slammer, x4 speed-up, and it dumps any leftover troops at the end.
  - Hero ability on low HP: watches the hero HP bar and fires the ability when it drops. Grand Warden
    fires proactively (`config/heroes.json`). The spell/troop selection is restored after firing.
  - Won't tap blindly if you interrupt the battle (End Battle / Pause / Stop) — same for MBR-CSV
    strategies.
  - Batched taps (one ADB call per batch) instead of one call per tap.
- Training (`train/`): composition by icon templates, "army full" by fraction matching.
  - Spell composition kept exact by tile count (`config/army.json`), plus a sanity check on the read
    housing so a misread number can't inflate the training count.
- Village (`villages/`): wall upgrades, Clan Games, request troops, multi-account.
  - Wall upgrade by level: reads the "Wall (Level N)" caption and upgrades only walls in the
    `[from..to)` range (`Templates/walls/level_text/`).
- Full storages → sleep or account switch (`config/farming.json`, GUI: Stop when full): dark elixir
  by the bar fill, gold and elixir by "stopped growing". No storage cap value needed.
- Number reading (`vision/digit_ocr.py`): digit-template matching, no OCR library.
- Multi-process multi-bot (v1.3.0): up to N instances in a single GUI window, each an isolated worker
  process (`run_from_source.py --worker`, [`worker_run.py`](worker_run.py)) bound to a distinct
  emulator instance. Process-level isolation of global state (`main.host`/`TABS`/`stop_event`/
  `pause_event`) removes parallel-control conflicts; per-instance collisions are guarded by a lock
  port. Each bot has its own configuration, log buffer, statistics (`Stats_{N}.json`) and
  Start/End/Pause; pause is a file-flag IPC (`profiles/_bot_N.pause`) polled by the worker. The
  session layout is serialized to `config/bots_layout.json` with optional auto-start on next launch.
- Emulators: MEmu (via `memuc`/`.memu`) and LDPlayer 14; the emulator and instance are selected at
  start, instances execute in parallel (one process per bot), running minimized / in the background.
  BlueStacks has an ADB version-conflict workaround (dedicated HD-Adb + reconnect).

## Layout
Flat imports, layers added to `sys.path`:

| directory | purpose |
|---|---|
| `core/` | bot loop, capture/matching, updates |
| `emu/` | emulator managers (MEmu / LDPlayer), ADB, input, screenshots |
| `vision/` | screen recognition |
| `train/` | army training |
| `villages/` | walls, Clan Games, request troops |
| `ui/` | interface (PyQt) |
| `attacks/` | attack logic |
| `Templates/` | matching references (1600×900) |

Each bot runs as a separate worker process ([`worker_run.py`](worker_run.py), launched via
`run_from_source.py --worker`) so instances don't share global state.
Paths — [`paths.py`](paths.py). Version — [`version.py`](version.py).

## Support
Free, MIT. If it's useful and you want to chip in, here's a wallet. Optional — nothing's gated.

- USDT (TRC20 / TRON): `TGVWcdhJkwYw7qhLqSieXjZCsMJxPQKhK4`

## License
See [`LICENSE`](LICENSE).
