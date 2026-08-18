"""Кросс-версийный запуск приложения через ADB.

Android 14 / LDPlayer 14 НЕ содержат тула `monkey` (`/system/bin/monkey: No such file` →
exit 127), поэтому основной путь — резолв launcher-активности (`cmd package resolve-activity`)
и `am start -n <activity>`; `monkey` оставлен фолбэком для MEmu/старых сборок.
"""
import subprocess
import sys

from adb_config import ADB_BIN

CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0


def _resolve_launcher(host, pkg):
    """Компонент launcher-активности пакета (`pkg/Activity`) или '' — через cmd package."""
    try:
        out = subprocess.check_output(
            [ADB_BIN, '-s', host, 'shell', 'cmd', 'package', 'resolve-activity',
             '--brief', '-c', 'android.intent.category.LAUNCHER', pkg],
            stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW).decode()
    except (subprocess.CalledProcessError, OSError):
        return ''
    comp = ''
    for line in out.splitlines():
        line = line.strip()
        if line.startswith(pkg + '/'):   # строка вида com.pkg/.Activity
            comp = line
    return comp


def launch_app(host, pkg, check=True):
    """Вывести приложение `pkg` в форграунд. True при успехе.

    1) `am start -n <launcher-activity>` — работает на Android 7+, включая Android 14 без monkey;
    2) фолбэк — `monkey ... LAUNCHER 1` (MEmu/старые). ``check`` → бросить при полном провале.
    """
    comp = _resolve_launcher(host, pkg)
    if comp:
        r = subprocess.run([ADB_BIN, '-s', host, 'shell', 'am', 'start', '-n', comp],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=CREATE_NO_WINDOW)
        if r.returncode == 0:
            return True
    r = subprocess.run([ADB_BIN, '-s', host, 'shell', 'monkey', '-p', pkg, '-c',
                        'android.intent.category.LAUNCHER', '1'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=CREATE_NO_WINDOW)
    if r.returncode != 0 and check:
        raise RuntimeError(f'launch_app: не удалось запустить {pkg} на {host} '
                           f'(нет launcher-активности и нет monkey)')
    return r.returncode == 0
