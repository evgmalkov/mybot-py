import io
import os
import re
import shutil
import tempfile
import threading
import zipfile
import requests
from packaging import version
from PyQt5.QtCore import QObject, pyqtSignal
from paths import BASE_DIR
from version import __version__

# Проверка обновлений при запуске GUI (вызов в bot_gui через QTimer). Читаем version.py
# ПРЯМО из raw GitHub нашего репо — без релизов/тегов/GitHub Pages: достаточно запушить
# бамп версии в main. Если удалённая версия выше локальной — сигналим в GUI и подтягиваем
# CHANGELOG.md (секции новее локальной версии), чтобы пользователь видел, ЧТО изменилось.
AUTO_UPDATE = True
VERSION_URL = 'https://raw.githubusercontent.com/evgmalkov/mybot-py/main/version.py'
CHANGELOG_URL = 'https://raw.githubusercontent.com/evgmalkov/mybot-py/main/CHANGELOG.md'
REPO_URL = 'https://github.com/evgmalkov/mybot-py'
ZIP_URL = 'https://github.com/evgmalkov/mybot-py/archive/refs/heads/main.zip'
_VER_RE = re.compile(r"__version__\s*=\s*['\"]([0-9]+(?:\.[0-9]+)*)['\"]")

# Бесшовное обновление: качаем zip репо и накладываем поверх установки. НЕ трогаем данные
# пользователя — эти каталоги верхнего уровня сохраняем как есть, а существующие config/*.json
# не перезаписываем (новые ключи имеют дефолты в коде; новые config-файлы добавляются).
_PRESERVE_TOP = {'profiles', 'runtime', '.git', '__pycache__', '.claude', 'docs'}


def _apply_tree(src, dst):
    """Скопировать распакованное дерево репо (src) поверх установки (dst), сохранив пользовательские
    данные (_PRESERVE_TOP) и существующие config/*.json. Возвращает число скопированных файлов."""
    copied = 0
    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        parts = [] if rel == '.' else rel.split(os.sep)
        if parts and parts[0] in _PRESERVE_TOP:
            dirs[:] = []                          # не спускаемся в сохраняемые каталоги
            continue
        target_dir = os.path.join(dst, *parts) if parts else dst
        os.makedirs(target_dir, exist_ok=True)
        for f in files:
            d = os.path.join(target_dir, f)
            if parts and parts[0] == 'config' and f.endswith('.json') and os.path.exists(d):
                continue                          # настройки юзера не перезаписываем
            try:
                # копируем через temp+replace (атомарно на томе) — не оставить полу-записанный файл
                tmp_d = d + '.upd_tmp'
                shutil.copy2(os.path.join(root, f), tmp_d)
                os.replace(tmp_d, d)
                copied += 1
            except Exception:
                pass
    return copied


def _changelog_since(local_ver, text):
    """Из CHANGELOG.md вернуть секции версий ВЫШЕ локальной (заголовки '## X.Y.Z'),
    чтобы показать в окне обновления только новое. Пустая строка, если ничего/парс не удался."""
    out = []
    for chunk in re.split(r'(?m)^##\s+', text):
        m = re.match(r'([0-9]+(?:\.[0-9]+)*)', chunk)
        if not m:
            continue
        try:
            newer = version.parse(m.group(1)) > version.parse(local_ver)
        except Exception:
            newer = False
        if newer:
            out.append('## ' + chunk.strip())
    return '\n\n'.join(out)


class Updater(QObject):
    # (remote_version, repo_url, changelog_text) — changelog может быть пустым
    update_available = pyqtSignal(str, str, str)
    apply_finished = pyqtSignal(bool, str)        # (успех, сообщение) — итог apply_update

    def __init__(self, parent=None):
        super().__init__(parent)

    def apply_update(self):
        """БЕСШОВНОЕ обновление: скачать main.zip и наложить код/шаблоны поверх установки, сохранив
        config/profiles/runtime. Пользователю НЕ нужен git. Итог — сигнал apply_finished(ok, msg)."""
        def _worker():
            try:
                r = requests.get(ZIP_URL, timeout=120)
                r.raise_for_status()
                tmp = tempfile.mkdtemp(prefix='mybot_upd_')
                try:
                    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                        z.extractall(tmp)
                    roots = [os.path.join(tmp, d) for d in os.listdir(tmp)
                             if os.path.isdir(os.path.join(tmp, d))]
                    if not roots:
                        self.apply_finished.emit(False, 'Downloaded archive was empty.')
                        return
                    n = _apply_tree(roots[0], BASE_DIR)
                    if n <= 0:
                        self.apply_finished.emit(False, 'No files were updated.')
                        return
                    self.apply_finished.emit(
                        True, f'Update applied ({n} files). Close and reopen the app to finish.')
                finally:
                    shutil.rmtree(tmp, ignore_errors=True)
            except Exception as e:
                self.apply_finished.emit(False, f'Update failed: {e}')
        threading.Thread(target=_worker, daemon=True).start()

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
                if version.parse(remote) <= version.parse(__version__):
                    return None
                changelog = ''
                try:                              # changelog — best-effort, окно работает и без него
                    r2 = requests.get(CHANGELOG_URL, timeout=5)
                    r2.raise_for_status()
                    changelog = _changelog_since(__version__, r2.text)
                except Exception:
                    changelog = ''
                self.update_available.emit(remote, REPO_URL, changelog)
            except Exception:
                return None                       # сеть/GitHub недоступны — тихо пропускаем
        threading.Thread(target=_worker, daemon=True).start()
