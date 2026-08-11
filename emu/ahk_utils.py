import subprocess
import time
from pathlib import Path

from paths import BASE_DIR as base_dir

# Бинарь и скрипты AHK могут лежать в корне проекта ИЛИ в AutoHotkey/v2 — ищем в обоих.
_AHK_DIRS = (base_dir, base_dir / 'AutoHotkey' / 'v2')


def _find(name: str):
    for d in _AHK_DIRS:
        p = d / name
        if p.is_file():
            return p
    return None


def run_ahk(script_name: str, wait: float = 2.0) -> bool:
    """Запустить AHK v2 скрипт по имени. Возвращает True/False и НЕ бросает —
    чтобы отсутствие AHK/скрипта не роняло бота (напр. переключение аккаунтов
    деградирует, а не крашится)."""
    ahk_exe = _find('AutoHotkey64.exe')
    if ahk_exe is None:
        print('[AHK] AutoHotkey64.exe not found (root or AutoHotkey/v2) — skip ' + script_name)
        return False
    script_path = _find(script_name)
    if script_path is None:
        print(f'[AHK] script not found: {script_name} — skip')
        return False
    try:
        subprocess.run([str(ahk_exe), str(script_path)], cwd=str(ahk_exe.parent),
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=subprocess.CREATE_NO_WINDOW, check=True)
    except Exception as e:
        print(f'[AHK] run failed for {script_name}: {e}')
        return False
    time.sleep(wait)
    return True
