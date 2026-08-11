import re
import threading
import requests
from packaging import version
from PyQt5.QtCore import QObject, pyqtSignal
from version import __version__

# Проверка обновлений при запуске GUI (вызов в bot_gui через QTimer). Читаем version.py
# ПРЯМО из raw GitHub нашего репо — без релизов/тегов/GitHub Pages: достаточно запушить
# бамп версии в main. Если удалённая версия выше локальной — сигналим в GUI.
AUTO_UPDATE = True
VERSION_URL = 'https://raw.githubusercontent.com/evgmalkov/mybot-py/main/version.py'
REPO_URL = 'https://github.com/evgmalkov/mybot-py'
_VER_RE = re.compile(r"__version__\s*=\s*['\"]([0-9]+(?:\.[0-9]+)*)['\"]")


class Updater(QObject):
    update_available = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def check_for_update(self):
        if not AUTO_UPDATE:
            return None

        def _worker():
            try:
                resp = requests.get(VERSION_URL, timeout=5)
                resp.raise_for_status()
                m = _VER_RE.search(resp.text)
                if not m:
                    return None
                remote = m.group(1)
                if version.parse(remote) > version.parse(__version__):
                    self.update_available.emit(remote, REPO_URL)
            except Exception:
                return None                       # сеть/GitHub недоступны — тихо пропускаем
        threading.Thread(target=_worker, daemon=True).start()
