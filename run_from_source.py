"""MyBotPy — точка входа (запуск из исходников).

Настраивает пути к рантайму зависимостей и слоям проекта, затем передаёт
управление GUI (bot_gui.main_gui).

Запуск:   python run_from_source.py   (или run.bat — через pythonw, без консоли)
Проверка: python run_from_source.py --import-only
"""
import os
import sys
import pathlib

HERE = pathlib.Path(__file__).resolve().parent

# Опциональное вендоренное дерево зависимостей (DLL: OpenCV/numpy/pywin32 + win32/lib).
# Для обычной установки через pip/venv НЕ нужно. Путь можно задать переменной окружения
# MYBOTPY_RUNTIME либо положить папку `runtime` рядом с этим файлом. Если её нет — берём
# пакеты активного интерпретатора (venv / системный Python).
_rt = os.environ.get("MYBOTPY_RUNTIME")
RUNTIME = pathlib.Path(_rt) if _rt else (HERE / "runtime")

if sys.version_info[:2] != (3, 13):
    sys.exit(f"needs CPython 3.13 (bytecode is 3.13); running {sys.version.split()[0]}")

# extension modules resolve their DLLs from the runtime dirs (если дерево присутствует)
if RUNTIME.is_dir():
    for d in (RUNTIME, RUNTIME / "pywin32_system32"):
        if d.is_dir():
            os.add_dll_directory(str(d))

# bot's own modules first, then the vendored dependency tree.
# Модули разложены по каталогам-слоям, но импортируются ПЛОСКО (import main,
# from screenshot_utils import ...) — поэтому каждый слой добавляем в sys.path.
# Весь код открыт (.py); ensure_home_base и ldplayer_manager лежат в корне и
# импортятся плоско.
LAYERS = ("core", "emu", "vision", "train", "villages", "ui")
sys.path.insert(0, str(HERE))
for _layer in LAYERS:
    sys.path.insert(0, str(HERE / _layer))
if RUNTIME.is_dir():
    sys.path += [str(RUNTIME), str(RUNTIME / "win32"), str(RUNTIME / "win32" / "lib")]

os.chdir(HERE)

if "--import-only" in sys.argv:
    import importlib
    mods = ["ensure_home_base", "ldplayer_manager", "main", "bot_gui", "mods",
            "attacks.attacks"]
    ok = bad = 0
    for m in mods:
        try:
            importlib.import_module(m)
            print(f"OK   {m}")
            ok += 1
        except SystemExit as e:
            print(f"EXIT {m} -> sys.exit({e.code})")
            bad += 1
        except Exception as e:
            print(f"FAIL {m} -> {type(e).__name__}: {str(e)[:100]}")
            bad += 1
    print(f"\n{ok} imported, {bad} failed")
    sys.exit(0 if bad == 0 else 1)

# import as a normal module so the `if __name__ == "__main__"` block stays put,
# patch it, then start the GUI ourselves exactly as that block would
import main          # first, to settle a circular import between main/*_manager
import bot_gui
import mods

mods.apply()
bot_gui.main_gui()
