"""Системный конфиг (плееры/ADB/таймауты/отладка) — читает config/system.json.

Значения снаружи, логика в коде (правило проекта). Отсутствие файла/ключа → дефолт
(= прежнее захардкоженное значение), поэтому подключение не ломающее. Игровые параметры —
в отдельных config/*.json (antiban/farming/army/…), тут ТОЛЬКО системное.

Плоский импорт: ``import syscfg`` (корень в sys.path). НЕ называть модуль ``sysconfig`` —
это имя стандартной библиотеки.
"""
import json
import os

from paths import BASE_DIR

_PATH = os.path.join(BASE_DIR, "config", "system.json")


def _load():
    try:
        with open(_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


_CFG = _load()


def resolution():
    """(width, height, dpi) как int из system.json (дефолт 1600×900@300)."""
    r = _CFG.get("resolution", {}) or {}
    return int(r.get("width", 1600)), int(r.get("height", 900)), int(r.get("dpi", 300))


def emu(name, key, default):
    """Параметр эмулятора `name` (memu/ldplayer/bluestacks) → key, или default."""
    return (_CFG.get("emulators", {}) or {}).get(name, {}).get(key, default)


def timeout(key, default):
    """Таймаут по ключу из секции timeouts, или default."""
    return (_CFG.get("timeouts", {}) or {}).get(key, default)


def debug(key, default=False):
    """Флаг отладки из секции debug, или default."""
    return (_CFG.get("debug", {}) or {}).get(key, default)
