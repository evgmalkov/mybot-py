"""Единый источник путей проекта.

Все модули берут пути отсюда (`from paths import BASE_DIR`), а не вычисляют из
`__file__`. Это (1) убирает дублированный `BASE_DIR`-бойлерплейт из ~17 модулей и
(2) делает будущую раскладку файлов по папкам безопасной: корень проекта ищется
по маркеру (`Templates/` или `.git`), а не по месту конкретного модуля.

BASE_DIR — `pathlib.Path`; совместим и с `os.path.join(BASE_DIR, ...)`, и с
оператором `BASE_DIR / '...'`, поэтому годится как для str-, так и для Path-модулей.
"""
import os
import sys
from pathlib import Path

# Диагностика: писать ли debug-кропы (gold_crop_debug.png и т.п.) на диск.
# По умолчанию выключено (в проде I/O не тратится); включить: MYBOT_DEBUG=1.
DEBUG = os.environ.get('MYBOT_DEBUG', '') == '1'


def _find_root(start: Path) -> Path:
    p = start
    for _ in range(6):
        if (p / 'Templates').is_dir() or (p / '.git').is_dir():
            return p
        if p.parent == p:
            break
        p = p.parent
    return start


if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = _find_root(Path(__file__).resolve().parent)

# Отладочные/рабочие кадры и кропы — в отдельную папку, чтобы не засорять корень.
# Папка создаётся лениво при первом обращении; целиком в .gitignore.
DEBUG_DIR = BASE_DIR / 'debug'


def debug_path(name):
    """Полный путь для отладочного/рабочего файла в DEBUG_DIR (создаёт папку).

    Если в `name` уже есть каталог — возвращаем как есть (путь задан явно).
    """
    if os.path.dirname(str(name)):
        return str(name)
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    return str(DEBUG_DIR / name)


# Производные пути (для новых модулей; существующие пока выводят свои сами).
APP_DIR = BASE_DIR
ADB_DIR = BASE_DIR
TEMPLATES_DIR = BASE_DIR / 'Templates'
ATTACK_DIR = BASE_DIR / 'attacks'
PROFILES_DIR = BASE_DIR / 'profiles'
CFG_PATH = BASE_DIR / 'settings.json'
AHK_DIR = BASE_DIR / 'AutoHotkey' / 'v2'
TEMPLATE_ROOT = TEMPLATES_DIR / 'Smart_Auto_train'
