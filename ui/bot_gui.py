import os
import sys
import ctypes
from version import __version__
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass
try:
    import certifi
    import ssl
    CA = certifi.where()
    os.environ.setdefault('SSL_CERT_FILE', CA)
    os.environ.setdefault('REQUESTS_CA_BUNDLE', CA)
except Exception:
    if os.environ.get('MYBOT_ALLOW_INSECURE_SSL') == '1':
        import ssl
        ssl._create_default_https_context = ssl._create_unverified_context
if getattr(sys, 'frozen', False):
    import pyi_splash
os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
app = QApplication(sys.argv)
import glob
import json
import time
import threading
import logging
import warnings
import tempfile
warnings.filterwarnings('ignore', category=FutureWarning)
import traceback
import webbrowser
import atexit
import socket
from pathlib import Path
from updater import Updater
from PyQt5.QtCore import QProcess, QProcessEnvironment, pyqtSignal, QObject, QPropertyAnimation, pyqtProperty, QEvent, QRect, QSize, QTimer, QEasingCurve, QSequentialAnimationGroup, QVariantAnimation
from PyQt5.QtGui import QFont, QPixmap, QTextCursor, QPainter, QColor, QIcon, QBrush
from PyQt5.QtWidgets import QTabBar, QAbstractSpinBox, QMainWindow, QWidget, QLabel, QLineEdit, QSpinBox, QCheckBox, QPushButton, QTextEdit, QComboBox, QVBoxLayout, QHBoxLayout, QGridLayout, QListWidget, QStackedWidget, QMessageBox, QRadioButton, QButtonGroup, QFrame, QGroupBox, QFormLayout, QGraphicsOpacityEffect, QToolButton, QSizePolicy, QSplashScreen, QListWidgetItem, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
from PyQt5.QtWidgets import QGraphicsDropShadowEffect, QDialog
from PyQt5.QtGui import QColor
import main
from main import zero_all_stats_files
from ready_villages import prepare_accounts, save_village_config
from wizard_bridge import bridge
from village_wiz import run_village_wizard
from stats_tab import StatsTab
from ldplayer_manager import list_ld_instances
from memu_manager import list_memu_instances
from paths import BASE_DIR
APP_DIR = BASE_DIR
ATTACK_DIR = os.path.join(APP_DIR, 'attacks')
BG = os.path.join(APP_DIR, 'Templates')
TEMPLATES_DIR = BG
CFG_PATH = os.path.join(APP_DIR, 'settings.json')
profiles_dir = os.path.join(BASE_DIR, 'profiles')
json_paths = glob.glob(os.path.join(profiles_dir, 'Village_*.json'))
MEMU = '127.0.0.1:21503'
BLUESTACKS = '127.0.0.1:5556'
LDPLAYER = '127.0.0.1:5555'












class EmulatorSelectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected = None
        self.setWindowTitle('Select Emulator')
        self.setModal(True)
        self.setFixedSize(820, 260)
        self.setStyleSheet('\n            QDialog {\n                background-color: #2b2b2b;\n                border-radius: 12px;\n                background-image: qradialgradient(\n                    cx:0.5, cy:0.5, radius:1.0,\n                    fx:0.5, fy:0.5,\n                    stop:0 rgba(60,60,60,255),\n                    stop:1 rgba(43,43,43,200)\n                );\n            }\n        ')
        header = QLabel('Choose your emulator', self)
        header.setFont(QFont('Segoe UI', 12, QFont.Bold))
        header.setStyleSheet('color:#FFFFFF;')
        header.setAlignment(Qt.AlignCenter)
        hbox = QHBoxLayout()
        hbox.setContentsMargins(20, 20, 20, 8)
        hbox.setSpacing(28)
        def make_button(name, img_path):
            btn = QToolButton(self)
            btn.setIcon(QIcon(img_path))
            btn.setIconSize(QSize(80, 80))
            btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            btn.setText(name)
            btn.setFont(QFont('Segoe UI', 10, QFont.Bold))
            btn.setMinimumWidth(170)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet('\n                QToolButton { color:#EFEFEF; background:transparent; border:none; }\n                QToolButton:hover { color:#FFD660; }\n                QToolButton:disabled { color:#6A6A6A; }\n            ')
            return btn
        memu_logo = os.path.join(TEMPLATES_DIR, 'memu_logo.png')
        bs_logo = os.path.join(TEMPLATES_DIR, 'bluestacks_logo.png')
        ld_logo = os.path.join(TEMPLATES_DIR, 'ldplayer_logo.png')
        btn_memu = make_button('MEmu', memu_logo)
        btn_memu_mi = make_button('MEmu\nMulti-Instance', memu_logo)
        btn_bs = make_button('BlueStacks', bs_logo)
        btn_ld = make_button('LDPlayer', ld_logo)
        btn_ldmi = make_button('LD\nMulti-Instance', ld_logo)
        btn_memu.clicked.connect(lambda: self._choose('memu'))
        btn_memu_mi.clicked.connect(lambda: self._choose('memu_multi'))
        btn_bs.clicked.connect(lambda: self._choose('bluestacks'))
        btn_ld.clicked.connect(lambda: self._choose('ldplayer'))
        btn_ldmi.clicked.connect(lambda: self._choose('ldplayer_multi'))
        # BlueStacks — в разработке. LDPlayer-кнопки активны только если LDPlayer установлен
        # (быстрый детект без скана диска — иначе всплывал долгий «Scanning LDPlayer»).
        ld_installed = False
        try:
            from ldplayer_manager import find_ldplayer_tools
            _ldc, _ldp = find_ldplayer_tools(allow_deep_scan=False)
            ld_installed = bool(_ldc and _ldp)
        except Exception:
            ld_installed = False
        _disabled = {btn_bs: 'In development — use MEmu or LDPlayer'}
        if not ld_installed:
            _disabled[btn_ld] = 'LDPlayer is not installed'
            _disabled[btn_ldmi] = 'LDPlayer is not installed'
        for _btn, _tip in _disabled.items():
            _btn.setEnabled(False)
            _btn.setCursor(Qt.ArrowCursor)
            _btn.setToolTip(_tip)
        hbox.addWidget(btn_memu)
        hbox.addWidget(btn_memu_mi)
        hbox.addWidget(btn_bs)
        hbox.addWidget(btn_ld)
        hbox.addWidget(btn_ldmi)
        vbox = QVBoxLayout(self)
        vbox.addWidget(header)
        vbox.addLayout(hbox)
        vbox.addStretch()
        self.setLayout(vbox)
    def _choose(self, name):
        self.selected = name
        self.accept()
    def getSelection(self):
        return self.selected





























class AnimatedButton(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._base_geom = None
        self._hovered = False
        self._anim = QPropertyAnimation(self, b'geometry', self)
        self._anim.setDuration(120)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
    def showEvent(self, ev):
        super().showEvent(ev)
        if self._base_geom is None:
            self._base_geom = self.geometry()
            self._orig_font = QFont(self.font())
    def enterEvent(self, ev):
        super().enterEvent(ev)
        self._hovered = True
        f = QFont(self._orig_font)
        f.setPointSizeF(self._orig_font.pointSizeF() * 0.95)
        f.setBold(self._orig_font.bold())
        self.setFont(f)
        self._run_anim(scale=0.95)
    def leaveEvent(self, ev):
        super().leaveEvent(ev)
        self._hovered = False
        self.setFont(self._orig_font)
        self._run_anim(scale=1.0)
    def mousePressEvent(self, ev):
        super().mousePressEvent(ev)
        self._run_anim(scale=1.1)
    def mouseReleaseEvent(self, ev):
        super().mouseReleaseEvent(ev)
        if self._hovered:
            f = QFont(self._orig_font)
            f.setPointSizeF(self._orig_font.pointSizeF() * 0.95)
            f.setBold(self._orig_font.bold())
            self.setFont(f)
            self._run_anim(scale=0.95)
        else:
            self.setFont(self._orig_font)
            self._run_anim(scale=1.0)
    def _run_anim(self, scale: float):
        if not self._base_geom:
            return
        base = self._base_geom
        w0, h0 = base.width(), base.height()
        cx = base.x() + w0 // 2
        cy = base.y() + h0 // 2
        new_w = int(w0 * scale)
        new_h = int(h0 * scale)
        new_x = cx - new_w // 2
        new_y = cy - new_h // 2
        end = QRect(new_x, new_y, new_w, new_h)
        self._anim.stop()
        self._anim.setStartValue(self.geometry())
        self._anim.setEndValue(end)
        self._anim.start()














class ClickBounceButton(AnimatedButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._anim.setDuration(100)
        self._easing = QEasingCurve.OutBack
    def mousePressEvent(self, ev):
        super().mousePressEvent(ev)
        self._anim.setEasingCurve(QEasingCurve.InQuad)
        self._run_anim(scale=0.9)
    def mouseReleaseEvent(self, ev):
        super().mouseReleaseEvent(ev)
        self._anim.setEasingCurve(self._easing)
        self._run_anim(scale=1.05)
        QTimer.singleShot(self._anim.duration(), lambda: (self._anim.setEasingCurve(QEasingCurve.OutQuad), self._run_anim(scale=1.0)))
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
    else:
        traceback.print_exception(exc_type, exc_value, exc_traceback)
        QMessageBox.critical(None, 'Fatal Error', ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
        sys.exit(1)
sys.excepthook = handle_exception






















class TimestampStream(QObject):
    """Qt‑thread‑safe stdout / stderr redirector emitting signal per line."""
    new_line = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self._buf = ''
    def write(self, s: str):
        if not s:
            return
        self._buf += s
        while '\n' in self._buf:
            line, self._buf = self._buf.split('\n', 1)
            if line.strip():
                ts = time.strftime('%H:%M:%S')
                self.new_line.emit(f'{ts} • {line}')
    def flush(self):
        return None
COLOR_TAGS = {'gold': '#FFD700', 'elixir': '#800080', 'warn': 'orange'}
def classify_colour(line: str) -> str:
    lo = line.lower()
    if 'gold' in lo:
        return 'gold'
    else:
        if 'elixir' in lo:
            return 'elixir'
        else:
            if 'warn' in line.upper():
                return 'warn'
            else:
                return 'info'
def load_settings():
    if os.path.exists(CFG_PATH):
        try:
            with open(CFG_PATH, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {'gold_threshold': 650000, 'elixir_threshold': 650000, 'dark_elixir_threshold': 5000, 'upgrade_wall': False, 'wall_level': 5, 'wall_gold_threshold': 5000000, 'wall_elixir_threshold': 5000000, 'enable_clan_games': False, 'enable_multi_account': False, 'request_troops': True, 'attack': 'Dragon_Attack', 'train_mode': 'smart', 'quick_slot': 1, 'enable_stats': False, 'enable_clan_capital': False, 'capital_hall_level': 9}
def save_settings(cfg: dict):
    try:
        with open(CFG_PATH, 'w') as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f'[WARN] could not save settings: {e}')


FARMING_PATH = os.path.join(BASE_DIR, 'config', 'farming.json')
ACCOUNTS_PATH = os.path.join(BASE_DIR, 'config', 'accounts.json')
BOTS_LAYOUT_PATH = os.path.join(BASE_DIR, 'config', 'bots_layout.json')


def load_farming_flags():
    """Флаги «стоп при полном» из config/farming.json (значение >0 → True)."""
    try:
        with open(FARMING_PATH, encoding='utf-8') as f:
            d = json.load(f)
    except Exception:
        d = {}
    return {'gold': int(d.get('gold', 1) or 0) > 0,
            'elixir': int(d.get('elixir', 1) or 0) > 0,
            'dark': int(d.get('dark', 1) or 0) > 0}


def save_farming_flags(gold: bool, elixir: bool, dark: bool):
    """Записать флаги в config/farming.json (сохраняя остальные ключи)."""
    try:
        with open(FARMING_PATH, encoding='utf-8') as f:
            d = json.load(f)
    except Exception:
        d = {}
    d['gold'] = 1 if gold else 0
    d['elixir'] = 1 if elixir else 0
    d['dark'] = 1 if dark else 0
    try:
        with open(FARMING_PATH, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f'[WARN] could not save farming.json: {e}')
def load_attack_assets(name: str):
    """Return (QPixmap | None, description str)."""
    img_path = os.path.join(ATTACK_DIR, f'{name}.png')
    desc_path = os.path.join(ATTACK_DIR, f'{name}.txt')
    pix = None
    if os.path.isfile(img_path):
        pix = QPixmap(img_path)
        if pix.width() > 520:
            pix = pix.scaledToWidth(520, Qt.SmoothTransformation)
    desc = ''
    if os.path.isfile(desc_path):
        with open(desc_path, 'r', encoding='utf-8', errors='ignore') as fh:
            desc = fh.read().strip()
        return (pix, desc)
    return (pix, desc)


































class WoodBackground(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.wood = QPixmap(os.path.join(BG, 'BG.png'))
    def paintEvent(self, ev):
        painter = QPainter(self)
        painter.drawTiledPixmap(self.rect(), self.wood)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 145))
        super().paintEvent(ev)



class InstancePickerDialog(QDialog):
    def __init__(self, parent=None, list_fn=None, title='Select LDPlayer Instance',
                 header='Choose an LDPlayer instance', logo_name='ldplayer_logo.png',
                 name_prefix='LDPlayer', allow_running=True):
        super().__init__(parent)
        self._list_fn = list_fn or list_ld_instances
        self._logo_name = logo_name
        self._name_prefix = name_prefix
        self._allow_running = allow_running   # можно ли выбрать уже запущенный инстанс (attach)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(520, 380)
        self.setStyleSheet('background:#1f1f1f;')
        self.index = None
        self.name = None
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(8)
        hdr = QLabel(header)
        hdr.setAlignment(Qt.AlignCenter)
        hdr.setStyleSheet('color:#eaeaea; font-weight:600; font-size:15px;')
        self.layout.addWidget(hdr)
        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(['Name', 'Status', 'Action'])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet('\n            QTableWidget { background:#1a1a1a; color:#eaeaea; border:1px solid #333; }\n            QHeaderView::section { background:#222; color:#eaeaea; padding:6px; border:none; }\n            QTableWidget::item { background:#1a1a1a; }\n            QTableWidget::item:alternate { background:#202020; }\n            QTableWidget::item:selected { background:#2e2e2e; }\n        ')
        self.table.horizontalHeader().setStretchLastSection(False)
        for c in range(3):
            self.table.horizontalHeader().setSectionResizeMode(c, QHeaderView.Fixed)
        self.layout.addWidget(self.table)
        self._equalize_columns()
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.refresh_btn = QPushButton('Refresh')
        self.refresh_btn.setStyleSheet('QPushButton{background:#444;color:#fff;border:none;border-radius:6px;padding:6px 12px;} QPushButton:hover{background:#666;}')
        self.refresh_btn.clicked.connect(self._populate_table)
        btn_row.addWidget(self.refresh_btn)
        self.layout.addLayout(btn_row)
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)
        self._populate_table()
    def _attach_bounce_icon(self, btn: QPushButton, base_w: int, base_h: int):
        """Shrink icon on press, restore on release (no geometry changes)."""
        def set_scale(s: float):
            w = int(base_w * s)
            h = int(base_h * s)
            w = min(w, btn.width())
            h = min(h, btn.height())
            btn.setIconSize(QSize(w, h))
        def on_press():
            anim = QVariantAnimation(btn)
            anim.setDuration(90)
            anim.setStartValue(1.0)
            anim.setEndValue(0.92)
            anim.valueChanged.connect(set_scale)
            anim.start()
            btn._press_anim = anim
        def on_release():
            back = QVariantAnimation(btn)
            back.setDuration(110)
            back.setStartValue(0.92)
            back.setEndValue(1.0)
            back.valueChanged.connect(set_scale)
            back.start()
            btn._release_anim = back
        btn.pressed.connect(on_press)
        btn.released.connect(on_release)
    def _populate_table(self):
        self.table.setRowCount(0)
        rows = self._list_fn()
        if not rows:
            self.table.setRowCount(1)
            it = QTableWidgetItem(f'No {self._name_prefix} instances found.')
            it.setFlags(it.flags() & ~Qt.ItemIsEnabled & ~Qt.ItemIsSelectable)
            self.table.setItem(0, 0, it)
            self.table.setSpan(0, 0, 1, 3)
            return
        logo_path = os.path.join(TEMPLATES_DIR, self._logo_name)
        icon = QIcon(logo_path) if os.path.exists(logo_path) else QIcon()
        for r in rows:
            self._add_row(r['index'], r['name'], bool(r['started']), icon)
        self._equalize_columns()
    def _add_row(self, idx: int, name: str, started: bool, icon: QIcon):
        row = self.table.rowCount()
        self.table.insertRow(row)
        name_item = QTableWidgetItem(icon, name or f'{self._name_prefix}-{idx}')
        name_item.setData(Qt.UserRole, idx)
        name_item.setData(Qt.UserRole + 1, name)
        name_item.setData(Qt.UserRole + 2, started)
        self.table.setItem(row, 0, name_item)
        status_item = QTableWidgetItem('Running' if started else 'Available')
        status_item.setTextAlignment(Qt.AlignCenter)
        status_item.setForeground(QBrush(QColor('#f0b64c' if started else '#60d394')))
        self.table.setItem(row, 1, status_item)
        btn = QPushButton()
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setFixedSize(120, 40)
        start_png = os.path.join(TEMPLATES_DIR, 'Start.png')
        btn.setIcon(QIcon(start_png))
        btn.setIconSize(QSize(120, 40))
        btn.setStyleSheet('QPushButton{border:none;background:transparent;}')
        btn.setProperty('ld_index', idx)
        btn.setProperty('ld_name', name or f'{self._name_prefix}-{idx}')
        btn.setProperty('ld_started', started)
        btn.clicked.connect(self._on_start_clicked)
        cell = QWidget()
        hl = QHBoxLayout(cell); hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(0)
        hl.addStretch()
        hl.addWidget(btn)
        hl.addStretch()
        self.table.setCellWidget(row, 2, cell)
        self.table.setColumnWidth(2, 140)
        self.table.setRowHeight(row, 44)
        self._attach_bounce_icon(btn, 120, 40)
    def _adjust_button_icons(self):
        for row in range(self.table.rowCount()):
            w = self.table.columnWidth(2)
            h = self.table.rowHeight(row)
            widget = self.table.cellWidget(row, 2)
            if isinstance(widget, QPushButton):
                widget.setIconSize(QSize(w, h))
    def _warn_busy(self):
        m = QMessageBox(self)
        m.setIcon(QMessageBox.Warning)
        m.setWindowTitle('Instance Busy')
        m.setText('This instance is currently in use. Please close it or select a different available instance.')
        m.setStyleSheet('QLabel{ color: white; }')
        m.exec_()
    def _on_start_clicked(self):
        btn = self.sender()
        idx = btn.property('ld_index')
        name = btn.property('ld_name')
        started = bool(btn.property('ld_started'))
        if started and not self._allow_running:
            self._warn_busy()
        else:
            self.index = int(idx)
            self.name = str(name)
            self.accept()
    def _on_row_double_clicked(self, row: int, _col: int):
        item = self.table.item(row, 0)
        if not item:
            return
        started = bool(item.data(Qt.UserRole + 2))
        if started and not self._allow_running:
            self._warn_busy()
            return
        self.index = int(item.data(Qt.UserRole))
        self.name = str(item.data(Qt.UserRole + 1) or f'{self._name_prefix}-{self.index}')
        self.accept()
    def _equalize_columns(self):
        total = max(0, self.table.viewport().width())
        each = max(120, total // 3)
        for c in range(3):
            self.table.setColumnWidth(c, each)
    def resizeEvent(self, e):
        super().resizeEvent(e)
        QTimer.singleShot(0, self._adjust_button_icons)
        QTimer.singleShot(0, self._equalize_columns)


# Обратная совместимость: старое имя = обобщённый пикер (по умолчанию LDPlayer).
LDInstancePickerDialog = InstancePickerDialog



























































class MainWindow(QMainWindow):
    update_available = pyqtSignal(str, str)
    def _apply_image_button(self, btn: QPushButton, filename: str, w: int, h: int):
        btn.setText('')
        btn.setFlat(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setIcon(QIcon(os.path.join(TEMPLATES_DIR, filename)))
        btn.setIconSize(QSize(w, h))
        btn.setFixedSize(w, h)
        btn.setStyleSheet('QPushButton{border:none;background:transparent;}')
    def _bot_pause_path(self, b):
        """Файл-флаг паузы бота = <его профиль>.pause (именно его поллит worker-процесс).
        Привязка к профилю, а не к индексу — устойчиво к закрытию/переносу вкладок."""
        prof = b.get('profile')
        if prof and str(prof).endswith('.json'):
            return str(prof)[:-5] + '.pause'
        return None

    def _update_pause_icon(self):
        """Иконка кнопки паузы = состояние активного бота (play=на паузе, stop=работает)."""
        b = self._bots[self._active_bot]
        name = 'play_button.png' if b.get('paused') else 'stop_button.png'
        self._toggle_btn.setIcon(QIcon(QPixmap(os.path.join(TEMPLATES_DIR, name))))

    def _on_toggle_pause_play(self):
        """Пауза/резюм АКТИВНОГО бота — через файл-флаг (его worker-процесс поллит)."""
        b = self._bots[self._active_bot]
        if not self._proc_alive(b.get('proc')):
            return                                   # нечего ставить на паузу
        path = self._bot_pause_path(b)
        if not path:
            return
        paused = not b.get('paused', False)
        b['paused'] = paused
        try:
            if paused:
                open(path, 'w').close()              # создать флаг → воркер встанет на паузу
            elif os.path.exists(path):
                os.remove(path)                      # снять флаг → воркер продолжит
        except Exception:
            pass
        self._log_to_bot(self._active_bot, '[INFO] Bot paused' if paused else '[INFO] Bot resumed')
        self._update_pause_icon()
    def _stats_file_path(self, village_idx: int) -> Path:
        """\nReturn the Path to “profiles/Village_{village_idx}_stats.json”\n(creating the directory if needed).\n"""
        profiles_dir = Path(BASE_DIR) / 'profiles'
        profiles_dir.mkdir(exist_ok=True)
        return profiles_dir / f'Stats_{village_idx}.json'
    def load_village_stats(self, village_idx: int) -> dict:
        # irreducible cflow, using cdg fallback
        """\nRead and return the JSON‐loaded dict for that village.\nIf the file doesn’t exist or is invalid, return defaults.\n"""
        path = self._stats_file_path(village_idx)
        if not path.exists():
            return {'gold': 0, 'elixir': 0, 'de': 0, 'attacks': 0, 'stars': {'0': 0, '1': 0, '2': 0, '3': 0}}
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception:
            return {'gold': 0, 'elixir': 0, 'de': 0, 'attacks': 0, 'stars': {'0': 0, '1': 0, '2': 0, '3': 0}}
    def _refresh_stats_from_json(self):
        if not self.stats_tab.enable_stats_chk.isChecked():
            return None
        else:
            idx = (self._active_bot + 1) if hasattr(self, '_active_bot') else (self.active_village_idx or 1)
            on_disk = self.load_village_stats(idx)
            self.stats_tab.current_village_idx = idx
            self.stats_tab.set_stats_dict(on_disk)
            self.settings['stats'] = on_disk.copy()
    def on_update_available(self, remote_ver, download_url):
        dlg = QMessageBox(self)
        dlg.setIcon(QMessageBox.Information)
        dlg.setWindowTitle('Update Available')
        dlg.setText(f'A new version ({remote_ver}) is available.')
        dlg.setInformativeText('Download now?')
        dlg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        if dlg.exec_() == QMessageBox.Yes:
            webbrowser.open(download_url)
    def _reload_village_icons(self):
        """\nCalled whenever the wizard finishes cropping new account images.\nReload each account_i.png into its QLabel immediately.\n"""
        for idx, (cb, icon, apply_btn, save_btn) in enumerate(self.mv_village_widgets, start=1):
            img_path = os.path.join(BASE_DIR, 'profiles', f'account_{idx}.png')
            if os.path.isfile(img_path):
                pix = QPixmap(img_path)
                pix = pix.scaledToWidth(95, Qt.SmoothTransformation)
                icon.setPixmap(pix)
            else:
                icon.clear()
    def update_village_fade(self):
        """\nFor each (cb, icon, apply_btn, save_btn) in mv_village_widgets,\ndim or brighten the row based on whether `cb` is checked\nand Multi‐Village is enabled.\n"""
        multi_on = self.mv_enable_chk.isChecked()
        for idx, (cb, icon, apply_btn, save_btn) in enumerate(self.mv_village_widgets, start=1):
            active = multi_on and cb.isChecked()
            cb.setEnabled(multi_on)
            apply_btn.setEnabled(active)
            save_btn.setEnabled(active)
            for w in [cb, icon, apply_btn, save_btn]:
                eff = QGraphicsOpacityEffect(icon)
                eff.setOpacity(1.0 if active else 0.35)
                icon.setGraphicsEffect(eff)
    def _load_bindings_ui(self):
        """Заполнить режим и пер-деревенные привязки из config/accounts.json."""
        try:
            with open(ACCOUNTS_PATH, encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {}
        mode = str(data.get('mode', 'id_switch')).lower()
        self.mv_mode_combo.setCurrentIndex(1 if mode == 'per_instance' else 0)
        binds = data.get('bindings', {}) or {}
        for i, (emu_combo, idx_spin) in self.mv_bindings.items():
            rec = binds.get(str(i)) or {}
            j = emu_combo.findData(str(rec.get('emulator', 'ldplayer')).lower())
            emu_combo.setCurrentIndex(j if j >= 0 else emu_combo.findData('ldplayer'))
            try:
                idx_spin.setValue(int(rec.get('index', 0)))
            except (TypeError, ValueError):
                idx_spin.setValue(0)
        self._on_mode_changed()

    def _on_mode_changed(self):
        """Активировать поля привязки только в режиме per_instance."""
        per = self.mv_mode_combo.currentData() == 'per_instance'
        for emu_combo, idx_spin in getattr(self, 'mv_bindings', {}).values():
            emu_combo.setEnabled(per)
            idx_spin.setEnabled(per)

    def _save_bindings(self):
        """Записать режим + привязки аккаунт↔инстанс в config/accounts.json (остальное сохранить)."""
        try:
            with open(ACCOUNTS_PATH, encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = {}
        data['mode'] = self.mv_mode_combo.currentData() or 'id_switch'
        binds = data.get('bindings', {}) or {}
        for i, (emu_combo, idx_spin) in self.mv_bindings.items():
            binds[str(i)] = {'emulator': emu_combo.currentData(), 'index': int(idx_spin.value())}
        data['bindings'] = binds
        try:
            with open(ACCOUNTS_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, 'Multi-Account', 'Bindings saved to config/accounts.json')
        except Exception as e:
            QMessageBox.warning(self, 'Multi-Account', f'Failed to save: {e}')

    # ── Постоянная верхняя полоса BotInstance (выбор бота; контент ниже меняется) ──
    def _build_bot_bar(self, parent_layout):
        """Верхняя полоса: [Bot 1][Bot 2]…[+]. Всегда видна. Переключение бота меняет контекст
        (пока — запоминаем текущую страницу nav у каждого бота; настройки/runtime — след. шаг)."""
        # состояние каждого BotInstance: страница nav, настройки (cfg), runtime (эмулятор/инстанс/
        # аккаунт/процесс). Settings — data-swap; runtime (proc) — живой объект per-bot.
        # Если сохранён набор (config/bots_layout.json) — восстанавливаем; иначе один бот.
        layout = self._load_bots_layout()
        saved = (layout or {}).get('bots') or []
        self._bots_autostart = bool((layout or {}).get('autostart'))
        if saved:
            self._bots, names = [], []
            for k, sb in enumerate(saved):
                st = self._new_bot_state()
                st.update({'emulator': sb.get('emulator', 'memu'), 'index': int(sb.get('index', 0)),
                           'account': int(sb.get('account', 1)), 'page': int(sb.get('page', 0)),
                           'cfg': sb.get('cfg')})
                self._bots.append(st)
                names.append(sb.get('name') or f'Bot {k + 1}')
        else:
            self._bots, names = [self._new_bot_state()], ['Bot 1']
        self._active_bot = 0
        self.bot_bar = QTabBar()
        self.bot_bar.setExpanding(False)
        self.bot_bar.setDrawBase(False)
        self.bot_bar.setFont(QFont('Segoe UI', 10, QFont.Bold))
        self.bot_bar.setStyleSheet(
            'QTabBar { background: rgba(0,0,0,180); }'
            ' QTabBar::tab { background:#2A2A2A; color:#EFE2BA; padding:6px 16px; margin:4px 2px 0 2px;'
            ' border-top-left-radius:8px; border-top-right-radius:8px; }'
            ' QTabBar::tab:selected { background:#4CAF50; color:#FFF; }')
        self.bot_bar.setTabsClosable(True)                              # крестик закрытия на вкладках
        self.bot_bar.tabCloseRequested.connect(self._close_bot)
        for nm in names:
            self.bot_bar.addTab(nm)
        self.bot_bar.addTab('  +  ')      # последняя «вкладка» = добавить бота
        self._strip_plus_close_btn()      # у «+» крестик не нужен
        self.bot_bar.currentChanged.connect(self._on_bot_bar_changed)   # подключаем ПОСЛЕ addTab
        parent_layout.addWidget(self.bot_bar)
        self._build_bots_controls(parent_layout)
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(0, self._post_bots_restore)   # применить настройки/автозапуск после сборки UI

    def _new_bot_state(self):
        return {'cfg': None, 'emulator': 'memu', 'index': 0, 'profile': None,
                'proc': None, 'stopping': False, 'crashed': False, 'log': []}

    def _build_bots_controls(self, parent_layout):
        """Компактная строка управления НАБОРОМ ботов: Auto-start + Save. Эмулятор/инстанс — выбор
        на нижней кнопке Start (диалог), настройки бота — в меню; статус — цветом вкладки."""
        from PyQt5.QtWidgets import QWidget as _QW
        row = _QW()
        h = QHBoxLayout(row)
        h.setContentsMargins(10, 2, 10, 2)
        h.setSpacing(8)
        h.addStretch()
        self.rt_autostart = QCheckBox('Auto-start on launch')
        self.rt_autostart.setStyleSheet('color:#EFE2BA;')
        self.rt_autostart.setToolTip('On next launch: recreate saved bots and start them automatically')
        h.addWidget(self.rt_autostart)
        save_btn = QPushButton('💾 Save bots')
        save_btn.setToolTip('Save current bots (count + per-bot settings) for next launch')
        save_btn.setStyleSheet('QPushButton{background:#3A6EA5;color:#FFF;border:none;border-radius:6px;'
                               'padding:4px 12px;} QPushButton:hover{background:#4E86C6;}')
        save_btn.clicked.connect(self._save_bots_layout)
        h.addWidget(save_btn)
        parent_layout.addWidget(row)

    def _load_bots_layout(self):
        try:
            with open(BOTS_LAYOUT_PATH, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None

    def _save_bots_layout(self):
        """Сохранить набор ботов (кол-во + настройки) для следующего запуска."""
        try:
            self._bots[self._active_bot]['cfg'] = self._collect_cfg()
        except Exception:
            pass
        bots = []
        for i, b in enumerate(self._bots):
            bots.append({'name': self.bot_bar.tabText(i),
                         'emulator': b.get('emulator', 'memu'), 'index': int(b.get('index', 0)),
                         'cfg': b.get('cfg')})
        data = {'autostart': bool(self.rt_autostart.isChecked()), 'bots': bots}
        try:
            with open(BOTS_LAYOUT_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            note = ('will AUTO-START on next launch.' if data['autostart']
                    else 'will be restored (not auto-started) on next launch.')
            QMessageBox.information(self, 'Save bots', f'Saved {len(bots)} bot(s) — {note}\n'
                                    'Delete config/bots_layout.json to reset to default.')
        except Exception as e:
            QMessageBox.warning(self, 'Save bots', f'Failed to save: {e}')

    def _post_bots_restore(self):
        """После сборки UI: применить настройки активного бота к виджетам + цвета вкладок + автозапуск."""
        if hasattr(self, 'rt_autostart'):
            self.rt_autostart.setChecked(getattr(self, '_bots_autostart', False))
        b = self._bots[self._active_bot]
        if b.get('cfg'):
            self._apply_cfg_to_widgets(b['cfg'])
        for i in range(len(self._bots)):
            self._set_tab_status(i)
        self._update_run_buttons()
        if getattr(self, '_bots_autostart', False):
            print(f'[BOTS] auto-starting {len(self._bots)} saved bot(s)…')
            for i, bb in enumerate(self._bots):
                self._write_bot_profile(bb, i, bb.get('cfg') or {})   # сохранённая cfg + свой стат-бакет
                self._start_bot(bb, i)
            self._update_run_buttons()

    def _set_tab_status(self, idx):
        """Цвет вкладки бота по статусу процесса: зелёный=работает, красный=crashed, обычный=stopped."""
        if not hasattr(self, 'bot_bar') or idx >= len(self._bots):
            return
        b = self._bots[idx]
        running = self._proc_alive(b.get('proc'))
        col = QColor('#7CFC7C') if running else (QColor('#FF7676') if b.get('crashed') else QColor('#EFE2BA'))
        self.bot_bar.setTabTextColor(idx, col)

    def _sync_run_status(self):
        """Периодически: цвета вкладок + Start/End = реальному состоянию процессов. Ловит случаи,
        когда finished-сигнал не пришёл (эмулятор закрыт, воркер убит, свёрнуто в трей с гашением)."""
        if not hasattr(self, 'bot_bar'):
            return
        for i in range(len(self._bots)):
            b = self._bots[i]
            if b.get('proc') is not None and not self._proc_alive(b.get('proc')):
                b['proc'] = None                 # процесс мёртв, а сигнал не дошёл → чистим
            self._set_tab_status(i)
        self._update_run_buttons()

    def _update_run_buttons(self):
        """Нижние Start/End — под АКТИВНЫЙ бот (его статус)."""
        if not hasattr(self, 'start_btn') or not hasattr(self, 'stop_btn'):
            return
        b = self._bots[self._active_bot]
        running = self._proc_alive(b.get('proc'))
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)

    def _write_bot_profile(self, b, idx, cfg):
        """Записать cfg бота во временный профиль profiles/_bot_{idx+1}.json + задать свой стат-бакет.
        Воркер пишет Stats_{current_village_idx}.json по этому индексу, GUI читает Stats_{active+1} →
        у каждой вкладки своя статистика без коллизии. Используется on_start и автозапуском."""
        vidx = idx + 1
        cfg = dict(cfg or {})
        cfg['current_village_idx'] = vidx
        # Режим ротации по деревням (Multi-Village) включён → сохраняем выбранные деревни
        # из GUI, воркер сам крутит ротацию. Иначе одиночный режим: у вкладки только своя
        # деревня (её стат-бакет).
        if not cfg.get('enable_multi_account'):
            cfg['selected_villages'] = [vidx]
        b['village'] = vidx
        prof = os.path.join(str(BASE_DIR), 'profiles', f'_bot_{idx + 1}.json')
        try:
            with open(prof, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            b['profile'] = prof
        except Exception:
            b['profile'] = None

    def _start_bot(self, b, idx):
        """Запустить worker-процесс бота: эмулятор/инстанс из состояния + профиль cfg (из меню)."""
        if self._proc_alive(b.get('proc')):
            return
        emu, ins = b.get('emulator', 'memu'), int(b.get('index', 0))
        tag = f'[Bot {idx + 1} {emu}#{ins}]'
        entry = os.path.join(str(BASE_DIR), 'run_from_source.py')
        args = [entry, '--worker', '--emulator', emu, '--index', str(ins)]
        if b.get('profile'):
            args += ['--profile', str(b['profile'])]
        p = QProcess(self)
        p.setProcessChannelMode(QProcess.MergedChannels)
        p.setWorkingDirectory(str(BASE_DIR))
        env = QProcessEnvironment.systemEnvironment()
        env.insert('PYTHONUNBUFFERED', '1')          # живой вывод в пайп → Logs
        p.setProcessEnvironment(env)
        p.readyReadStandardOutput.connect(lambda pr=p, bb=b: self._drain_bot(pr, bb))
        p.finished.connect(lambda code, st, bb=b: self._bot_finished(bb, code))
        b['proc'] = p
        b['stopping'] = False
        b['crashed'] = False
        b['paused'] = False                          # свежий старт — не на паузе
        try:                                         # снять устаревший флаг паузы
            pf = self._bot_pause_path(b)
            if pf and os.path.exists(pf):
                os.remove(pf)
        except Exception:
            pass
        self._log_to_bot(idx, f'{tag} starting…')
        # GUI обычно под pythonw.exe (sys.stdout=None у детей → print воркера теряется).
        # Запускаем воркер консольным python.exe: Qt ставит CREATE_NO_WINDOW, окно не всплывает,
        # а stdout уходит в пайп QProcess → в Logs.
        exe = str(sys.executable)
        if exe.lower().endswith('pythonw.exe'):
            cand = exe[:-len('pythonw.exe')] + 'python.exe'
            if os.path.exists(cand):
                exe = cand
        p.start(exe, args)
        self._set_tab_status(idx)
        if self._bots[self._active_bot] is b:
            self._update_run_buttons()
            self._update_pause_icon()

    @staticmethod
    def _proc_alive(p):
        """Безопасно: жив ли QProcess. Ловит RuntimeError, когда C++-объект уже удалён (при закрытии)."""
        if p is None:
            return False
        try:
            return p.state() != QProcess.NotRunning
        except RuntimeError:
            return False

    def _stop_active_bot(self):
        b = self._bots[self._active_bot]
        b['stopping'] = True
        p = b.get('proc')
        if p is not None and self._proc_alive(p):
            p.kill()
            p.waitForFinished(3000)          # дождаться смерти → повторный Start сразу сработает

    def _bot_finished(self, b, code):
        b['crashed'] = (not b.get('stopping')) and code != 0
        b['stopping'] = False
        b['proc'] = None                     # чистое состояние → следующий Start не блокируется
        b['paused'] = False
        try:
            pf = self._bot_pause_path(b)     # убрать флаг паузы завершённого бота
            if pf and os.path.exists(pf):
                os.remove(pf)
        except OSError:
            pass
        try:
            i = self._bots.index(b)
            self._set_tab_status(i)
        except ValueError:
            pass
        if self._bots[self._active_bot] is b:
            self._update_run_buttons()
            self._update_pause_icon()

    def _log_to_bot(self, idx, raw):
        """Записать строку в буфер лога бота idx; если он активен — показать во вкладке Logs."""
        if idx < 0 or idx >= len(self._bots):
            return
        entry = f"{time.strftime('%H:%M:%S')} • {raw}"
        buf = self._bots[idx].setdefault('log', [])
        buf.append(entry)
        if len(buf) > 3000:                       # держим последние ~3000 строк
            del buf[:len(buf) - 3000]
        if idx == self._active_bot:
            self._append_log(entry)

    def _drain_bot(self, proc, b):
        try:
            data = bytes(proc.readAllStandardOutput()).decode('utf-8', errors='ignore')
        except Exception:
            return
        try:
            idx = self._bots.index(b)
        except ValueError:
            return
        prefix = f"[Bot {idx + 1} {b.get('emulator', 'memu')}#{int(b.get('index', 0))}]"
        for line in data.splitlines():
            if line.strip():
                self._log_to_bot(idx, f'{prefix} {line}')

    def _plus_index(self):
        return self.bot_bar.count() - 1

    def _on_bot_bar_changed(self, i):
        if i == self._plus_index():
            self._add_bot()               # кликнули по «+»
        else:
            self._switch_bot(i)

    def _add_bot(self):
        n = len(self._bots) + 1
        self._bots.append(self._new_bot_state())
        self.bot_bar.blockSignals(True)
        self.bot_bar.insertTab(self._plus_index(), f'Bot {n}')   # вставить перед «+»
        self.bot_bar.blockSignals(False)
        self._strip_plus_close_btn()
        self.bot_bar.setCurrentIndex(len(self._bots) - 1)        # выбрать нового (→ _switch_bot)

    def _strip_plus_close_btn(self):
        """Убрать крестик у вкладки «+» (её нельзя закрыть — это кнопка добавления)."""
        from PyQt5.QtWidgets import QTabBar as _QTabBar
        pi = self._plus_index()
        for side in (_QTabBar.RightSide, _QTabBar.LeftSide):
            btn = self.bot_bar.tabButton(pi, side)
            if btn is not None:
                btn.deleteLater()
                self.bot_bar.setTabButton(pi, side, None)

    def _close_bot(self, i):
        """Закрыть вкладку бота: погасить его процесс, удалить состояние и вкладку."""
        if i < 0 or i >= len(self._bots):        # клик по «+» игнорируем
            return
        if len(self._bots) <= 1:                 # последний бот не закрываем
            QMessageBox.information(self, 'Bot', 'At least one bot must remain.')
            return
        b = self._bots[i]
        p = b.get('proc')
        if p is not None and self._proc_alive(p):
            b['stopping'] = True
            try:
                p.finished.disconnect()
            except Exception:
                pass
            p.kill()
            p.waitForFinished(3000)
        b['proc'] = None
        try:                                     # убрать флаг паузы закрываемого бота
            pf = self._bot_pause_path(b)
            if pf and os.path.exists(pf):
                os.remove(pf)
        except OSError:
            pass
        self._bots.pop(i)
        target = min(i, len(self._bots) - 1)
        # _active_bot=-1 → _switch_bot не сохранит виджеты закрытого бота в нового активного
        self._active_bot = -1
        self.bot_bar.blockSignals(True)
        self.bot_bar.removeTab(i)
        self.bot_bar.setCurrentIndex(target)
        self.bot_bar.blockSignals(False)
        self._switch_bot(target)                 # покажет данные нового активного
        for k in range(len(self._bots)):         # обновить цвета оставшихся вкладок
            self._set_tab_status(k)

    def _switch_bot(self, i):
        if i < 0 or i >= len(self._bots):
            return
        # Левая навигация НЕ меняется (остаёмся на текущей странице) — меняются только ДАННЫЕ
        # (настройки бота) + нижние Start/End под активного.
        if 0 <= self._active_bot < len(self._bots):
            try:
                self._bots[self._active_bot]['cfg'] = self._collect_cfg()
            except Exception:
                pass
        self._active_bot = i
        saved = self._bots[i].get('cfg')
        if saved:
            self._apply_cfg_to_widgets(saved)
        # лог — свой у каждого бота: перерисовать вкладку Logs из буфера активного
        self.log.clear()
        for entry in self._bots[i].get('log', []):
            self._append_log(entry)
        # статистика активного бота — сразу, не ждать тика таймера
        try:
            self._refresh_stats_from_json()
        except Exception:
            pass
        self._update_run_buttons()
        self._update_pause_icon()

    def _apply_cfg_to_widgets(self, cfg):
        """Применить cfg-словарь к виджетам (обратное к _collect_cfg). Защищённо: отсутствующие
        ключи/виджеты пропускаются. Используется при переключении BotInstance."""
        def _txt(attr, key):
            w = getattr(self, attr, None)
            if w is not None and key in cfg:
                try:
                    w.setText(str(cfg.get(key, '')))
                except Exception:
                    pass

        def _chk(attr, key):
            w = getattr(self, attr, None)
            if w is not None and key in cfg:
                try:
                    w.setChecked(bool(cfg.get(key)))
                except Exception:
                    pass

        def _val(attr, key):
            w = getattr(self, attr, None)
            if w is not None and key in cfg:
                try:
                    w.setValue(int(cfg.get(key)))
                except Exception:
                    pass

        _txt('gold_entry', 'gold_threshold')
        _txt('elixir_entry', 'elixir_threshold')
        _txt('dark_entry', 'dark_elixir_threshold')
        _chk('upgrade_chk', 'upgrade_wall')
        _chk('full_gold_chk', 'full_gold')
        _chk('full_elixir_chk', 'full_elixir')
        _chk('full_dark_chk', 'full_dark')
        _txt('wall_gold_entry', 'wall_gold_threshold')
        _txt('wall_elixir_entry', 'wall_elixir_threshold')
        _val('wall_level_spin', 'wall_level_from' if 'wall_level_from' in cfg else 'wall_level')
        _val('wall_level_to_spin', 'wall_level_to')
        _chk('req_chk', 'request_troops')
        if 'attack' in cfg and hasattr(self, 'attack_combo') and hasattr(self, 'attack_map'):
            inv = {v: k for k, v in self.attack_map.items()}
            t = inv.get(cfg.get('attack'))
            if t:
                self.attack_combo.setCurrentText(t)
        if hasattr(self, 'quick_radio') and hasattr(self, 'smart_radio'):
            (self.quick_radio if cfg.get('train_mode') == 'quick' else self.smart_radio).setChecked(True)
            try:
                self._on_train_mode_toggled()
            except Exception:
                pass
        _val('quick_slot_spin', 'quick_slot')
        _chk('clan_games_toggle', 'enable_clan_games')
        _chk('clan_capital_toggle', 'enable_clan_capital')
        _val('cc_level', 'capital_hall_level')
        _chk('mv_enable_chk', 'enable_multi_account')
        _val('mv_count_spin', 'multi_count')
        _val('mv_interval', 'multi_interval_mins')
        if hasattr(self, 'stats_tab') and hasattr(self.stats_tab, 'enable_stats_chk') and 'enable_stats' in cfg:
            try:
                self.stats_tab.enable_stats_chk.setChecked(bool(cfg['enable_stats']))
            except Exception:
                pass
        if 'selected_villages' in cfg and hasattr(self, 'mv_village_widgets'):
            sel = set(cfg.get('selected_villages') or [])
            for i2, tup in enumerate(self.mv_village_widgets, start=1):
                try:
                    tup[0].setChecked(i2 in sel)
                except Exception:
                    pass

    def _save_village_config(self, idx: int):
        """\nRead all current UI fields and write them out to Village_{idx}.json,\nbut only if that village was just loaded.\n"""
        path = os.path.join(APP_DIR, 'profiles', f'Village_{idx}.json')
        if getattr(self, 'active_village_idx', None) != idx or not os.path.exists(path):
            QMessageBox.warning(self, 'Save Error', 'Cannot save configuration: no configuration has been loaded for this village.')
            return
        cfg = {'gold_threshold': int(self.gold_entry.text()), 'elixir_threshold': int(self.elixir_entry.text()), 'dark_elixir_threshold': int(self.dark_entry.text()), 'upgrade_wall': self.upgrade_chk.isChecked(), 'wall_gold_threshold': int(self.wall_gold_entry.text()), 'wall_elixir_threshold': int(self.wall_elixir_entry.text()), 'wall_level': int(self.wall_level_spin.value()), 'wall_level_from': int(self.wall_level_spin.value()), 'wall_level_to': int(getattr(self, 'wall_level_to_spin', self.wall_level_spin).value()), 'request_troops': self.req_chk.isChecked(), 'attack': self.attack_map[self.attack_combo.currentText()], 'train_mode': 'quick' if self.quick_radio.isChecked() else 'smart', 'quick_slot': self.quick_slot_spin.value()}
        path = os.path.join(APP_DIR, 'profiles', f'Village_{idx}.json')
        with open(path, 'w') as f:
            json.dump(cfg, f, indent=2)
        QMessageBox.information(self, 'Saved', f'Village_{idx} configuration saved!')
    def _load_village_config(self, idx: int):
        """\nRead profiles/Village_{idx}.json and populate\nall General + Army widgets with its values.\n"""
        path = os.path.join(APP_DIR, 'profiles', f'Village_{idx}.json')
        if not os.path.exists(path):
            QMessageBox.warning(self, 'Missing Config', f'No saved settings for Village_{idx}.')
            return
        with open(path, 'r') as f:
            vcfg = json.load(f)
        self.gold_entry.setText(str(vcfg.get('gold_threshold', '')))
        self.elixir_entry.setText(str(vcfg.get('elixir_threshold', '')))
        self.dark_entry.setText(str(vcfg.get('dark_elixir_threshold', '')))
        self.upgrade_chk.setChecked(vcfg.get('upgrade_wall', False))
        self.wall_gold_entry.setText(str(vcfg.get('wall_gold_threshold', '')))
        self.wall_elixir_entry.setText(str(vcfg.get('wall_elixir_threshold', '')))
        self.wall_level_spin.setValue(vcfg.get('wall_level', 8))
        self.req_chk.setChecked(vcfg.get('request_troops', False))
        inv = {v: k for k, v in self.attack_map.items()}
        combo_text = inv.get(vcfg.get('attack', ''), None)
        if combo_text:
            self.attack_combo.setCurrentText(combo_text)
        mode = vcfg.get('train_mode', 'smart')
        if mode == 'quick':
            self.quick_radio.setChecked(True)
        else:
            self.smart_radio.setChecked(True)
        self._on_train_mode_toggled()
        self.quick_slot_spin.setValue(vcfg.get('quick_slot', 1))
    def _confirm_and_load(self, idx: int):
        reply = QMessageBox.question(self, 'Confirm Load', f'Load configuration for Village_{idx}?', QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            path = os.path.join(APP_DIR, 'profiles', f'Village_{idx}.json')
            if not os.path.exists(path):
                QMessageBox.warning(self, 'Missing Config', f'No saved settings for Village_{idx}.')
                return
            self._load_village_config(idx)
            QMessageBox.information(self, 'Loaded', f'Village_{idx} configuration loaded!')
            self.active_village_idx = idx
            _, _, _, save_btn = self.mv_village_widgets[idx - 1]
            save_btn.setEnabled(True)
    def highlight_active_village(self, idx: int):
        for i, (cb, icon, btn, _) in enumerate(self.mv_village_widgets, start=1):
            if i == idx:
                cb.setStyleSheet('color: yellow; font-weight: bold;')
            else:
                cb.setStyleSheet(f'color: {self.mv_colors[i - 1]};')
        self.active_village_idx = idx
        self.stats_tab.current_village_idx = idx
    def _on_request_wizard(self, indices):
        """Мастер настройки деревень убран: конфигурация делается прямо в главном GUI
        (вкладка Multi-Village, кнопки Load/Save на каждую деревню). Отдельный popup
        дублировал функционал и выбивался из стиля. Профили при их отсутствии создаёт
        сам воркер из текущих настроек. Сразу сигналим «готово»."""
        bridge.wizardDone.emit()
    def _toggle_group(self, group: QGroupBox, enabled: bool):
        """\nGray‐out or color the entire group when its toggle is off/on.\n"""
        bg = 'rgba(255,255,255,200)' if enabled else 'rgba(80,80,80,150)'
        group.setStyleSheet(f'\n            QGroupBox {{\n                background: {bg};\n                border: 1px solid #FFFFFF;\n                border-radius: 4px;\n                margin-top: 6px;\n            }}\n            QGroupBox::title {{\n                subcontrol-origin: margin;\n                left: 8px; padding: 0 4px;\n            }}\n        ')
        for w in group.findChildren((QLineEdit, QSpinBox)):
            w.setEnabled(enabled)
    def on_count_changed(self, n: int):
        """\nEnable/check the first n villages, disable/uncheck the rest,\nthen apply fade to all rows accordingly.\n"""
        multi_enabled = self.mv_enable_chk.isChecked()
        for idx, (cb, icon, apply_btn, save_btn) in enumerate(self.mv_village_widgets, start=1):
            is_active = idx <= n and multi_enabled
            cb.setChecked(idx <= n)
            cb.setEnabled(is_active)
            apply_btn.setEnabled(is_active)
            save_btn.setEnabled(is_active)
            for w in (cb, icon, apply_btn, save_btn):
                eff = QGraphicsOpacityEffect(w)
                eff.setOpacity(1.0 if is_active else 0.35)
                w.setGraphicsEffect(eff)
        self.update_village_fade()
    def _on_delete_all(self):
        from PyQt5.QtWidgets import QMessageBox
        import os
        import glob
        ans = QMessageBox.question(self, 'Delete Confirmation', 'Do you want to delete **all** saved settings and images for **every** village?', QMessageBox.Yes | QMessageBox.No)
        if ans!= QMessageBox.Yes:
            return None
        else:
            profiles_dir = os.path.join(BASE_DIR, 'profiles')
            for pattern in ['Village_*.json', 'account_*.png']:
                for path in glob.glob(os.path.join(profiles_dir, pattern)):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
            QMessageBox.information(self, 'Deleted', 'All village configurations and images have been removed.')
            self.mv_enable_chk.setChecked(False)
            self.mv_count_spin.setValue(1)
            for cb, icon, apply_btn, save_btn in self.mv_village_widgets:
                cb.setChecked(False)
                cb.setEnabled(False)
                apply_btn.setEnabled(False)
                save_btn.setEnabled(False)
                icon.clear()
    def choose_emulator(self):
        dlg = EmulatorSelectionDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            choice = dlg.getSelection()
            main.memu_index = None          # сбрасываем: только memu_multi задаёт явный индекс
            if choice == 'memu':
                self.host = MEMU
                main.emulator_key = 'memu'
                main.ld_index = 0
                main.ld_name = None
                port = 6200
            elif choice == 'memu_multi':
                pick = InstancePickerDialog(self, list_fn=list_memu_instances,
                                            title='Select MEmu Instance',
                                            header='Choose a MEmu instance',
                                            logo_name='memu_logo.png', name_prefix='MEmu')
                if pick.exec_() != QDialog.Accepted:
                    return None
                main.emulator_key = 'memu'
                main.ld_index = pick.index
                main.ld_name = pick.name
                main.memu_index = pick.index    # пер-инстансный путь: ensure_memu(index)
                self.host = None
                port = 6300 + pick.index
            else:
                if choice == 'bluestacks':
                    self.host = BLUESTACKS
                    main.emulator_key = 'bluestacks'
                    main.ld_index = 0
                    main.ld_name = None
                    port = 6201
                else:
                    if choice == 'ldplayer':
                        main.emulator_key = 'ldplayer'
                        main.ld_index = 0
                        main.ld_name = 'LDPlayer'
                        self.host = None
                        port = 6202
                    else:
                        if choice == 'ldplayer_multi':
                            pick = LDInstancePickerDialog(self)
                            if pick.exec_()!= QDialog.Accepted:
                                return None
                            else:
                                main.emulator_key = 'ldplayer'
                                main.ld_index = pick.index
                                main.ld_name = pick.name
                                self.host = None
                                port = 6202 + pick.index
            # Занятость инстанса определяем по СВОИМ запущенным ботам (не сокет-локом — лок держит
            # сам worker-процесс; GUI-лок конфликтовал с воркером и с умирающим предшественником).
            sel_key = getattr(main, 'emulator_key', None)
            sel_idx = main.memu_index if sel_key == 'memu' else getattr(main, 'ld_index', 0)
            for j, ob in enumerate(getattr(self, '_bots', [])):
                if j == self._active_bot:
                    continue
                p = ob.get('proc')
                if (p is not None and p.state() != QProcess.NotRunning
                        and ob.get('emulator') == sel_key
                        and int(ob.get('index', 0)) == int(sel_idx or 0)):
                    QMessageBox.warning(self, 'Emulator Busy',
                                        f'{choice.capitalize()} appears to be in use by Bot {j + 1}.\n'
                                        'Choose a different instance or stop that bot first.')
                    main.emulator_key = None
                    return None
            main.host = self.host
            return self.host
    def __init__(self):
        super().__init__()
        self.active_village_idx = None
        self.setWindowTitle(f'MyBotPy   v{__version__}')
        self.host = None
        self.setFixedSize(530, 680)
        self.active_village_idx = None
        self.settings = load_settings()
        self.attack_images = {k: load_attack_assets(k)
            for k in ('Dragon_Attack', 'ElectroDragon_Attack')}
        comic12 = QFont('Comic Sans MS', 12, QFont.Bold)
        comic9 = QFont('Comic Sans MS', 9)
        self.gold_entry = QLineEdit(str(self.settings['gold_threshold']))
        self.elixir_entry = QLineEdit(str(self.settings['elixir_threshold']))
        self.dark_entry = QLineEdit(str(self.settings['dark_elixir_threshold']))
        for w in (self.gold_entry, self.elixir_entry, self.dark_entry):
            w.setFont(comic12)
            w.setFixedWidth(100)
        self.wall_gold_entry = QLineEdit(str(self.settings['wall_gold_threshold']))
        self.wall_elixir_entry = QLineEdit(str(self.settings['wall_elixir_threshold']))
        self.wall_level_spin = QSpinBox()
        self.wall_level_spin.setRange(8, 18)
        self.wall_level_spin.setValue(self.settings['wall_level'])
        for w in (self.wall_gold_entry, self.wall_elixir_entry):
            w.setFont(comic12)
            w.setFixedWidth(100)
        self.wall_level_spin.setFont(comic12)
        self.wall_level_spin.setFixedWidth(70)
        self.req_chk = QCheckBox('Enable Request Troops')
        self.req_chk.setFont(comic12)
        self.req_chk.setChecked(self.settings['request_troops'])
        toggle_font = QFont('Segoe UI', 12, QFont.Bold)
        central = WoodBackground()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.setCentralWidget(central)
        self._build_bot_bar(outer)          # ПОСТОЯННАЯ верхняя полоса BotInstance
        hroot = QHBoxLayout()
        hroot.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(hroot)
        nav = QListWidget()
        nav.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        nav.setSpacing(12)
        nav.addItems(['General', 'Army', 'Multi-Village', 'Clan Games', 'Clan Capital', 'Statistics', 'Logs'])
        self.nav = nav                  # для переключения страницы при смене BotInstance
        nav.setFont(QFont('Segoe UI', 14, QFont.Bold))
        nav.setStyleSheet('\n            QListWidget {\n                background: rgba(0,0,0,180);\n                color: #EFE2BA;\n                border: none;\n            }\n            QListWidget::item:selected { background: rgba(255,255,255,30); color:#FFF; }\n            QListWidget::item:hover    { background: rgba(255,255,255,15); }\n\n            /* hide vertical scrollbar completely */\n            QScrollBar:vertical { width: 0px; background: transparent; }\n            QScrollBar::handle:vertical,\n            QScrollBar::add-line:vertical,\n            QScrollBar::sub-line:vertical { background: transparent; height: 0px; }\n        ')
        nav.setFixedWidth(160)
        nav_container = QWidget()
        nav_container.setFixedWidth(160)
        nav_container.setStyleSheet('background: rgba(0,0,0,180);')
        nav_layout = QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(0)
        nav_layout.addWidget(nav)
        self._toggle_btn = ClickBounceButton()
        self._toggle_btn.setFlat(True)
        self._toggle_btn.setCursor(Qt.PointingHandCursor)
        self._toggle_btn.setIcon(QIcon(os.path.join(TEMPLATES_DIR, 'stop_button.png')))
        self._toggle_btn.setIconSize(QSize(70, 70))
        self._toggle_btn.setFixedSize(80, 80)
        self._toggle_btn.setStyleSheet('background: none; border: none;')
        self._toggle_btn.clicked.connect(self._on_toggle_pause_play)
        nav_layout.addWidget(self._toggle_btn, alignment=Qt.AlignLeft)
        hroot.addWidget(nav_container)
        nav.setStyleSheet('\n        QListWidget {\n            background: rgba(0,0,0,180);\n            color: #EFE2BA;\n            border: none;\n        }\n        QListWidget::item:selected {\n            background: rgba(255,255,255,30);\n            color: #FFFFFF;\n        }\n        QListWidget::item:hover {\n            background: rgba(255,255,255,15);\n        }\n    ')
        right = QVBoxLayout()
        hroot.addLayout(right, 1)
        stack = QStackedWidget()
        right.addWidget(stack, 1)
        gen_tab = QWidget()
        grid = QGridLayout(gen_tab)
        grid.setContentsMargins(15, 15, 15, 15)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(14)
        hdrF = QFont('Segoe UI', 13, QFont.Bold)
        labF = QFont('Segoe UI', 11, QFont.Bold)
        def white_lbl(text, f):
            lbl = QLabel(text)
            lbl.setFont(f)
            lbl.setStyleSheet('color:#FFFFFF;')
            return lbl
        def line():
            l = QFrame(); l.setFrameShape(QFrame.HLine)
            l.setStyleSheet('color:#666;')
            return l
        row = 0
        header_container = QWidget()
        header_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)
        left_lbl = QLabel()
        pix_left = QPixmap(os.path.join(TEMPLATES_DIR, 'icon_siege.png'))
        pix_left = pix_left.scaledToWidth(60, Qt.SmoothTransformation)
        left_lbl.setPixmap(pix_left)
        left_lbl.setFixedSize(pix_left.size())
        left_eff = QGraphicsOpacityEffect(left_lbl)
        left_eff.setOpacity(0.7)
        left_lbl.setGraphicsEffect(left_eff)
        header_layout.addWidget(left_lbl)
        header_layout.addStretch()
        mid_lbl = QLabel()
        pix_mid_orig = QPixmap(os.path.join(TEMPLATES_DIR, 'icon_attack_criteria.png'))
        desired_center_width = 200
        pix_mid = pix_mid_orig.scaledToWidth(desired_center_width, Qt.SmoothTransformation)
        mid_lbl.setPixmap(pix_mid)
        mid_lbl.setFixedSize(pix_mid.size())
        header_layout.addWidget(mid_lbl)
        header_layout.addStretch()
        right_lbl = QLabel()
        pix_right = QPixmap(os.path.join(TEMPLATES_DIR, 'icon_dragon.png'))
        pix_right = pix_right.scaledToWidth(60, Qt.SmoothTransformation)
        right_lbl.setPixmap(pix_right)
        right_lbl.setFixedSize(pix_right.size())
        right_eff = QGraphicsOpacityEffect(right_lbl)
        right_eff.setOpacity(0.7)
        right_lbl.setGraphicsEffect(right_eff)
        header_layout.addWidget(right_lbl)
        grid.addWidget(header_container, row, 0, 1, 2)
        row += 1
        grid.addWidget(line(), row, 0, 1, 2)
        row += 1
        self.gold_entry = QLineEdit(str(self.settings.get('gold_threshold', 650000)))
        self.elixir_entry = QLineEdit(str(self.settings.get('elixir_threshold', 650000)))
        self.dark_entry = QLineEdit(str(self.settings.get('dark_elixir_threshold', 5000)))
        for e in (self.gold_entry, self.elixir_entry, self.dark_entry):
            e.setFont(labF)
            e.setFixedWidth(120)
        icon_gold_lbl = QLabel()
        pix = QPixmap(os.path.join(TEMPLATES_DIR, 'icon_gold.png')).scaledToWidth(24, Qt.SmoothTransformation)
        icon_gold_lbl.setPixmap(pix)
        gold_container = QWidget()
        gold_hlay = QHBoxLayout(gold_container)
        gold_hlay.setContentsMargins(0, 0, 0, 0)
        gold_hlay.setSpacing(6)
        gold_hlay.addWidget(icon_gold_lbl)
        lbl_gold = QLabel('Gold:')
        lbl_gold.setFont(labF)
        lbl_gold.setStyleSheet('color:#FFFFFF;')
        gold_hlay.addWidget(lbl_gold)
        gold_hlay.addStretch()
        grid.addWidget(gold_container, row, 0)
        grid.addWidget(self.gold_entry, row, 1)
        row += 1
        icon_elixir_lbl = QLabel()
        pix2 = QPixmap(os.path.join(TEMPLATES_DIR, 'icon_elixir.png')).scaledToWidth(24, Qt.SmoothTransformation)
        icon_elixir_lbl.setPixmap(pix2)
        elixir_container = QWidget()
        elixir_hlay = QHBoxLayout(elixir_container)
        elixir_hlay.setContentsMargins(0, 0, 0, 0)
        elixir_hlay.setSpacing(6)
        elixir_hlay.addWidget(icon_elixir_lbl)
        lbl_elixir = QLabel('Elixir:')
        lbl_elixir.setFont(labF)
        lbl_elixir.setStyleSheet('color:#FFFFFF;')
        elixir_hlay.addWidget(lbl_elixir)
        elixir_hlay.addStretch()
        grid.addWidget(elixir_container, row, 0)
        grid.addWidget(self.elixir_entry, row, 1)
        row += 1
        icon_de_lbl = QLabel()
        pix3 = QPixmap(os.path.join(TEMPLATES_DIR, 'icon_de.png')).scaledToWidth(24, Qt.SmoothTransformation)
        icon_de_lbl.setPixmap(pix3)
        de_container = QWidget()
        de_hlay = QHBoxLayout(de_container)
        de_hlay.setContentsMargins(0, 0, 0, 0)
        de_hlay.setSpacing(6)
        de_hlay.addWidget(icon_de_lbl)
        lbl_de = QLabel('Dark Elixir:')
        lbl_de.setFont(labF)
        lbl_de.setStyleSheet('color:#FFFFFF;')
        de_hlay.addWidget(lbl_de)
        de_hlay.addStretch()
        grid.addWidget(de_container, row, 0)
        grid.addWidget(self.dark_entry, row, 1)
        row += 1
        # Стоп/сон при ПОЛНЫХ хранилищах — флаги в config/farming.json (по каким ресурсам ждать).
        _farm = load_farming_flags()
        stop_lbl = QLabel('Stop when full:')
        stop_lbl.setFont(labF); stop_lbl.setStyleSheet('color:#FFFFFF;')
        stop_container = QWidget()
        stop_hlay = QHBoxLayout(stop_container)
        stop_hlay.setContentsMargins(0, 0, 0, 0); stop_hlay.setSpacing(12)
        self.full_gold_chk = QCheckBox('Gold')
        self.full_elixir_chk = QCheckBox('Elixir')
        self.full_dark_chk = QCheckBox('Dark')
        self.full_gold_chk.setChecked(_farm['gold'])
        self.full_elixir_chk.setChecked(_farm['elixir'])
        self.full_dark_chk.setChecked(_farm['dark'])
        for c in (self.full_gold_chk, self.full_elixir_chk, self.full_dark_chk):
            c.setFont(labF); c.setStyleSheet('color:#FFFFFF;')
            # сохраняем СРАЗУ при клике — чтобы менялось у уже запущенного бота без рестарта
            c.toggled.connect(lambda _=False: save_farming_flags(
                self.full_gold_chk.isChecked(), self.full_elixir_chk.isChecked(),
                self.full_dark_chk.isChecked()))
            stop_hlay.addWidget(c)
        stop_hlay.addStretch()
        grid.addWidget(stop_lbl, row, 0)
        grid.addWidget(stop_container, row, 1)
        row += 1
        grid.addWidget(line(), row, 0, 1, 2)
        row += 1
        up_container = QWidget()
        up_layout = QHBoxLayout(up_container)
        up_layout.setContentsMargins(0, 0, 0, 0)
        up_layout.setSpacing(6)
        self.upgrade_chk = QCheckBox('Enable Upgrade Wall')
        self.upgrade_chk.setFont(hdrF)
        self.upgrade_chk.setStyleSheet('color:#FFFFFF;')
        self.upgrade_chk.setChecked(self.settings.get('upgrade_wall', False))
        up_layout.addWidget(self.upgrade_chk)
        icon_up_lbl = QLabel()
        pix_up = QPixmap(os.path.join(TEMPLATES_DIR, 'icon_up.png')).scaledToWidth(16, Qt.SmoothTransformation)
        icon_up_lbl.setPixmap(pix_up)
        up_layout.addWidget(icon_up_lbl)
        up_layout.addStretch()
        grid.addWidget(up_container, row, 0, 1, 2)
        row += 1
        self.wall_gold_entry = QLineEdit(str(self.settings.get('wall_gold_threshold', 5000000)))
        self.wall_elixir_entry = QLineEdit(str(self.settings.get('wall_elixir_threshold', 5000000)))
        self.wall_level_spin = QSpinBox()
        self.wall_level_spin.setRange(8, 18)
        self.wall_level_spin.setValue(self.settings.get('wall_level_from', self.settings.get('wall_level', 8)))
        self.wall_level_to_spin = QSpinBox()
        self.wall_level_to_spin.setRange(8, 18)
        self.wall_level_to_spin.setValue(self.settings.get('wall_level_to', self.settings.get('wall_level', 8)))
        for w in (self.wall_gold_entry, self.wall_elixir_entry, self.wall_level_spin, self.wall_level_to_spin):
            w.setFont(labF)
            w.setFixedWidth(120)
        # Пороги Gold/Elixir для стен вытеснены config/wall_prices.json — из GUI убраны.
        # Виджеты оставлены (нужны для enable/disable и сохранения), но скрыты.
        self.wall_gold_entry.setVisible(False)
        self.wall_elixir_entry.setVisible(False)
        icon_wall_level = QLabel()
        pix_wl = QPixmap(os.path.join(TEMPLATES_DIR, 'icon_wall.png')).scaledToWidth(24, Qt.SmoothTransformation)
        icon_wall_level.setPixmap(pix_wl)
        wl_container = QWidget()
        wl_hlay = QHBoxLayout(wl_container)
        wl_hlay.setContentsMargins(0, 0, 0, 0)
        wl_hlay.setSpacing(6)
        wl_hlay.addWidget(icon_wall_level)
        lbl_wl = QLabel('Wall Level From:')
        lbl_wl.setFont(labF)
        lbl_wl.setStyleSheet('color:#FFFFFF;')
        wl_hlay.addWidget(lbl_wl)
        wl_hlay.addStretch()
        grid.addWidget(wl_container, row, 0)
        grid.addWidget(self.wall_level_spin, row, 1)
        row += 1
        wl_to_container = QWidget()
        wl_to_hlay = QHBoxLayout(wl_to_container)
        wl_to_hlay.setContentsMargins(0, 0, 0, 0)
        wl_to_hlay.setSpacing(6)
        icon_wall_level_to = QLabel()
        icon_wall_level_to.setPixmap(pix_wl)
        wl_to_hlay.addWidget(icon_wall_level_to)
        lbl_wl_to = QLabel('Wall Level To:')
        lbl_wl_to.setFont(labF)
        lbl_wl_to.setStyleSheet('color:#FFFFFF;')
        wl_to_hlay.addWidget(lbl_wl_to)
        wl_to_hlay.addStretch()
        grid.addWidget(wl_to_container, row, 0)
        grid.addWidget(self.wall_level_to_spin, row, 1)
        row += 1
        grid.addWidget(line(), row, 0, 1, 2)
        row += 1
        req_container = QWidget()
        req_layout = QHBoxLayout(req_container)
        req_layout.setContentsMargins(0, 0, 0, 0)
        req_layout.setSpacing(6)
        self.req_chk = QCheckBox('Enable Request Troops')
        self.req_chk.setFont(hdrF)
        self.req_chk.setStyleSheet('color:#FFFFFF;')
        self.req_chk.setChecked(self.settings.get('request_troops', False))
        req_layout.addWidget(self.req_chk)
        icon_cc = QLabel()
        pix_cc = QPixmap(os.path.join(TEMPLATES_DIR, 'icon_clan_castle.png')).scaledToWidth(28, Qt.SmoothTransformation)
        icon_cc.setPixmap(pix_cc)
        req_layout.addWidget(icon_cc)
        req_layout.addStretch()
        grid.addWidget(req_container, row, 0, 1, 2)
        row += 1
        grid.addWidget(line(), row, 0, 1, 2)
        row += 1
        row += 1
        grid.addWidget(line(), row, 0, 1, 2)
        def set_opacity(wlist, on):
            for w in wlist: w.setWindowOpacity(1.0 if on else 0.35)
        wall_widgets = [self.wall_gold_entry, self.wall_elixir_entry, self.wall_level_spin]
        req_widgets = []
        def apply_state(enabled: bool, widgets):
            """Enable/disable & dim widgets (0.35 opacity when off)."""
            for w in widgets:
                w.setEnabled(enabled)
                w.setWindowOpacity(1.0 if enabled else 0.35)
        apply_state(self.upgrade_chk.isChecked(), wall_widgets)
        apply_state(self.req_chk.isChecked(), req_widgets)
        self.upgrade_chk.toggled.connect(lambda on: apply_state(on, wall_widgets))
        self.req_chk.toggled.connect(lambda on: apply_state(on, req_widgets))
        set_opacity(wall_widgets, self.upgrade_chk.isChecked())
        set_opacity(req_widgets, self.req_chk.isChecked())
        self.upgrade_chk.toggled.connect(lambda on: set_opacity(wall_widgets, on))
        self.req_chk.toggled.connect(lambda on: set_opacity(req_widgets, on))
        stack.addWidget(gen_tab)
        army_tab = QWidget()
        army_layout = QVBoxLayout(army_tab)
        army_layout.setAlignment(Qt.AlignTop)
        self.attack_img = QLabel()
        self.attack_img.setAlignment(Qt.AlignLeft)
        army_layout.addWidget(self.attack_img)
        ATTACK_CHOICES = {'Dragon Attack': 'Dragon_Attack', 'Electro Dragon Attack': 'ElectroDragon_Attack'}
        self.attack_map = ATTACK_CHOICES
        self.attack_combo = QComboBox()
        self.attack_combo.addItems(ATTACK_CHOICES.keys())
        self.attack_combo.setFont(comic12)
        army_layout.addWidget(self.attack_combo)
        self.attack_desc = QLabel('')
        self.attack_desc.setFont(comic9)
        self.attack_desc.setWordWrap(True)
        self.attack_desc.setStyleSheet('color:#EFE2BA; margin:4px 0;')
        army_layout.addWidget(self.attack_desc)
        self.attack_combo.currentTextChanged.connect(self._update_attack_preview)
        train_box = QVBoxLayout()
        army_layout.addLayout(train_box)
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setStyleSheet('color:#666;')
        train_box.addWidget(sep)
        lbl_train = QLabel('Train')
        toggle_font = QFont('Segoe UI', 12, QFont.Bold)
        lbl_train.setFont(toggle_font)
        lbl_train.setStyleSheet('color:#FFFFFF;')
        train_box.addWidget(lbl_train)
        self.smart_radio = QRadioButton('Smart Train')
        self.quick_radio = QRadioButton('Quick Train')
        for rb in [self.smart_radio, self.quick_radio]:
            rb.setFont(toggle_font)
        self.smart_radio.setStyleSheet('\n            QRadioButton{\n                background:qlineargradient(x1:0,y1:0,x2:0,y2:1,\n                    stop:0 #A5D6A7, stop:1 #66BB6A);\n                color:#FFFFFF; border:2px solid #388E3C;\n                border-radius:4px; padding:4px 8px;\n            }')
        self.quick_radio.setStyleSheet('\n            QRadioButton{\n                background:qlineargradient(x1:0,y1:0,x2:0,y2:1,\n                    stop:0 #81D4FA, stop:1 #29B6F6);\n                color:#FFFFFF; border:2px solid #0277BD;\n                border-radius:4px; padding:4px 8px;\n            }')
        self.train_mode_group = QButtonGroup(self)
        self.train_mode_group.addButton(self.smart_radio)
        self.train_mode_group.addButton(self.quick_radio)
        self.smart_radio.setChecked(True)
        train_box.addWidget(self.smart_radio)
        train_box.addWidget(self.quick_radio)
        slot_row = QHBoxLayout()
        self.quick_slot_label = QLabel('Slot:')
        self.quick_slot_label.setFont(toggle_font)
        self.quick_slot_label.setStyleSheet('color:#FFFFFF;')
        self.quick_slot_spin = QSpinBox()
        self.quick_slot_spin.setRange(1, 2)
        self.quick_slot_spin.setValue(self.settings.get('quick_slot', 1))
        self.quick_slot_spin.setFont(toggle_font)
        self.quick_slot_spin.setFixedWidth(70)
        self.quick_slot_label.setEnabled(False)
        self.quick_slot_spin.setEnabled(False)
        self.quick_slot_spin.setStyleSheet('\n            background: rgba(255,255,255,200);\n            border:1px solid #555; border-radius:4px;\n            color:#000;\n        ')
        slot_row.addWidget(self.quick_slot_label)
        slot_row.addWidget(self.quick_slot_spin)
        train_box.addLayout(slot_row)
        icons_row = QHBoxLayout()
        icons_row.setContentsMargins(0, 8, 0, 0)
        icons_row.setSpacing(20)
        def make_transparent_icon(filename, width):
            lbl = QLabel()
            pix = QPixmap(os.path.join(TEMPLATES_DIR, filename)).scaledToWidth(width, Qt.SmoothTransformation)
            lbl.setPixmap(pix)
            eff = QGraphicsOpacityEffect(lbl)
            eff.setOpacity(0.8)
            lbl.setGraphicsEffect(eff)
            return lbl
        pekka_lbl = make_transparent_icon('icon_pekka.png', 90)
        barb_lbl = make_transparent_icon('icon_rr.png', 70)
        golem_lbl = make_transparent_icon('icon_golem.png', 90)
        icons_row.addWidget(pekka_lbl)
        icons_row.addWidget(barb_lbl)
        icons_row.addWidget(golem_lbl)
        train_box.addLayout(icons_row)
        self.smart_radio.toggled.connect(self._on_train_mode_toggled)
        self.quick_radio.toggled.connect(self._on_train_mode_toggled)
        if self.settings.get('train_mode', 'smart') == 'quick':
            self.quick_radio.setChecked(True)
        multi_tab = QWidget()
        mv_layout = QVBoxLayout(multi_tab)
        mv_layout.setContentsMargins(0, 0, 0, 0)
        mv_layout.setSpacing(20)
        mv_layout.setAlignment(Qt.AlignTop)
        mv_layout.setContentsMargins(0, 0, 0, 0)
        mv_layout.setSpacing(20)
        mv_enable_container = QWidget()
        mv_enable_layout = QHBoxLayout(mv_enable_container)
        mv_enable_layout.setContentsMargins(0, 0, 0, 0)
        mv_enable_layout.setSpacing(0)
        self.mv_enable_chk = QCheckBox('Enable Multi-Village')
        self.mv_enable_chk.setFont(QFont('Segoe UI', 14, QFont.Bold))
        self.mv_enable_chk.setStyleSheet('color: #FFFFFF;')
        self.mv_enable_chk.setChecked(self.settings.get('enable_multi_village', False))
        mv_enable_layout.addWidget(self.mv_enable_chk)
        icon_switch_lbl = QLabel()
        pix_switch = QPixmap(os.path.join(TEMPLATES_DIR, 'icon_switch.png')).scaledToWidth(48, Qt.SmoothTransformation)
        icon_switch_lbl.setPixmap(pix_switch)
        mv_enable_layout.addWidget(icon_switch_lbl)
        mv_enable_layout.addStretch()
        mv_layout.addWidget(mv_enable_container, 0, Qt.AlignTop)
        h1 = QHBoxLayout()
        lbl_accounts = QLabel('How many accounts?')
        lbl_accounts.setFont(QFont('Segoe UI', 12, QFont.Bold))
        lbl_accounts.setStyleSheet('color: #FFFFFF;')
        h1.addWidget(lbl_accounts)
        self.mv_count_spin = QSpinBox()
        self.mv_count_spin.setRange(2, 5)
        self.mv_count_spin.setValue(2)
        self.mv_count_spin.setFont(QFont('Segoe UI', 12, QFont.Bold))
        h1.addWidget(self.mv_count_spin)
        mv_layout.addLayout(h1)
        h2 = QHBoxLayout()
        lbl_interval = QLabel('Switch interval:')
        lbl_interval.setFont(QFont('Segoe UI', 12, QFont.Bold))
        lbl_interval.setStyleSheet('color: #FFFFFF;')
        h2.addWidget(lbl_interval)
        self.mv_interval = QSpinBox()
        self.mv_interval.setFont(QFont('Segoe UI', 12, QFont.Bold))
        self.mv_interval.setRange(5, 720)         # гибкий интервал в минутах (5 мин … 12 ч)
        self.mv_interval.setSingleStep(5)
        self.mv_interval.setSuffix(' min')
        self.mv_interval.setValue(int(self.settings.get('multi_interval_mins', 30)))
        h2.addWidget(self.mv_interval)
        mv_layout.addLayout(h2)
        # --- Мультиаккаунт: модель разведения аккаунтов ---
        h_mode = QHBoxLayout()
        lbl_mode = QLabel('Account mode:')
        lbl_mode.setFont(QFont('Segoe UI', 12, QFont.Bold))
        lbl_mode.setStyleSheet('color: #FFFFFF;')
        h_mode.addWidget(lbl_mode)
        self.mv_mode_combo = QComboBox()
        self.mv_mode_combo.addItem('ID switch (single instance)', 'id_switch')
        self.mv_mode_combo.addItem('Per-instance (account = instance)', 'per_instance')
        self.mv_mode_combo.setFont(QFont('Segoe UI', 11))
        self.mv_mode_combo.currentIndexChanged.connect(lambda _=0: self._on_mode_changed())
        h_mode.addWidget(self.mv_mode_combo)
        h_mode.addStretch()
        mv_layout.addLayout(h_mode)
        self.delete_btn = AnimatedButton('Delete All')
        self.delete_btn.setFont(QFont('Segoe UI', 9, QFont.Bold))
        self.delete_btn.setFixedSize(95, 28)
        self.delete_btn.setStyleSheet('\n            QPushButton {\n                background: qlineargradient(\n                    x1:0,y1:0, x2:0,y2:1,\n                    stop:0 #FF5252, stop:1 #D32F2F\n                );\n                color: #FFF;\n                border: none;\n                border-radius: 8px;\n            }\n            QPushButton:hover { background: #FF867C; }\n        ')
        self.delete_btn.clicked.connect(self._on_delete_all)
        mv_layout.addWidget(self.delete_btn, alignment=Qt.AlignRight)
        vbox = QVBoxLayout()
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(10)
        group = QGroupBox('Villages')
        group.setFont(QFont('Segoe UI', 14, QFont.Bold))
        group.setStyleSheet('\n            QGroupBox {\n                color: #FFFFFF;\n                border: 1px solid #EFE2BA;\n                margin-top: 6px;\n            }\n            QGroupBox::title {\n                subcontrol-origin: margin;\n                left: 8px; padding: 0 4px;\n            }\n        ')
        self.mv_village_widgets = []
        self.mv_bindings = {}          # деревня i → (emulator QComboBox, instance QSpinBox)
        colors = ['#eaecee', '#eaecee', '#eaecee', '#eaecee', '#eaecee']
        self.mv_colors = colors
        for i in range(1, 6):
            row = QHBoxLayout()
            cb = QCheckBox(f'Village_{i}')
            cb.setFont(QFont('Segoe UI', 10, QFont.Bold))
            cb.setStyleSheet(f'color: {colors[i - 1]};')
            pix = QPixmap(os.path.join(BASE_DIR, 'profiles', f'account_{i}.png'))
            icon = QLabel()
            icon.setFixedWidth(95)
            icon.setFixedHeight(60)
            if not pix.isNull():
                icon.setPixmap(pix.scaledToWidth(95, Qt.SmoothTransformation))
            row.addWidget(cb)
            row.addWidget(icon)
            apply_btn = AnimatedButton('Load')
            apply_btn.setFont(QFont('Segoe UI', 8, QFont.Bold))
            apply_btn.setStyleSheet('\n                /* normal state */\n                QPushButton {\n                    background: qlineargradient(\n                        x1:0, y1:0, x2:0, y2:1,\n                        stop:0 #4CAF50,    /* top green */\n                        stop:1 #388E3C     /* bottom darker green */\n                    );\n                    color: #FFFFFF;\n                    border: none;\n                    border-radius: 5px;\n                    padding: 4px 16px;\n                }\n                /* hover state */\n                QPushButton:hover {\n                    background: qlineargradient(\n                        x1:0, y1:0, x2:0, y2:1,\n                        stop:0 #66BB6A,    /* lighter green on hover */\n                        stop:1 #4CAF50\n                    );\n                }\n            ')
            row.addWidget(apply_btn)
            save_btn = AnimatedButton('Save')
            save_btn.setFont(QFont('Segoe UI', 8, QFont.Bold))
            save_btn.setStyleSheet('\n                QPushButton {\n                    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,\n                        stop:0 #2196F3, stop:1 #1976D2);\n                    color: #FFF; border:none; border-radius:8px;\n                    padding:4px 16px;\n                }\n                QPushButton:hover {\n                    background: #42A5F5;\n                }\n            ')
            row.addWidget(save_btn)
            # привязка к инстансу (модель B): эмулятор + индекс инстанса
            arrow = QLabel('→')
            arrow.setFont(QFont('Segoe UI', 10, QFont.Bold))
            arrow.setStyleSheet('color: #EFE2BA;')
            row.addWidget(arrow)
            emu_combo = QComboBox()
            emu_combo.addItem('MEmu', 'memu')
            emu_combo.addItem('LDPlayer', 'ldplayer')
            emu_combo.setFont(QFont('Segoe UI', 8, QFont.Bold))
            emu_combo.setFixedWidth(84)
            row.addWidget(emu_combo)
            idx_spin = QSpinBox()
            idx_spin.setRange(0, 31)
            idx_spin.setPrefix('#')
            idx_spin.setFont(QFont('Segoe UI', 8, QFont.Bold))
            idx_spin.setFixedSize(54, 22)                          # компактно — чтобы строка влезала
            idx_spin.setAlignment(Qt.AlignCenter)
            idx_spin.setStyleSheet('QSpinBox { color:#1b1b1b; background:#EFE2BA; border-radius:4px; }')
            row.addWidget(idx_spin)
            self.mv_bindings[i] = (emu_combo, idx_spin)
            row.addStretch()
            vbox.addLayout(row, 1)
            self.mv_village_widgets.append((cb, icon, apply_btn, save_btn))
            apply_btn.setEnabled(False)
            cb.toggled.connect(lambda checked, b=apply_btn: b.setEnabled(checked))
            apply_btn.clicked.connect(lambda _, idx=i: self._confirm_and_load(idx))
            save_btn.setEnabled(True)
            save_btn.clicked.connect(lambda _, village_idx=i: self._save_village_config(village_idx))
        group.setLayout(vbox)
        mv_layout.addWidget(group, 1)
        save_bind_btn = AnimatedButton('Save bindings')
        save_bind_btn.setFont(QFont('Segoe UI', 9, QFont.Bold))
        save_bind_btn.setToolTip('Save account mode and account↔instance bindings to config/accounts.json')
        save_bind_btn.clicked.connect(self._save_bindings)
        mv_layout.addWidget(save_bind_btn, alignment=Qt.AlignRight)
        self._load_bindings_ui()
        bridge.setActiveVillage.connect(self.highlight_active_village)
        for cb, icon, apply_btn, save_btn in self.mv_village_widgets:
            cb.setEnabled(False)
            apply_btn.setEnabled(False)
            save_btn.setEnabled(True)
            for w in (icon, apply_btn):
                eff = QGraphicsOpacityEffect(w)
                eff.setOpacity(0.35)
                w.setGraphicsEffect(eff)
        def _on_apply_village(self, idx: int):
            """\nCalled when the user clicks “Apply” next to Village_{idx}.\nGathers that village’s current settings, saves them to JSON + PNG,\nand then disables that row so it can’t be applied again.\n"""
            cfg = {'gold_threshold': int(self.gold_entry.text()), 'elixir_threshold': int(self.elixir_entry.text()), 'dark_elixir_threshold': int(self.dark_entry.text()), 'upgrade_wall': self.upgrade_chk.isChecked(), 'wall_level': int(self.wall_level_spin.value()), 'wall_level_from': int(self.wall_level_spin.value()), 'wall_level_to': int(getattr(self, 'wall_level_to_spin', self.wall_level_spin).value()), 'wall_gold_threshold': int(self.wall_gold_entry.text()), 'wall_elixir_threshold': int(self.wall_elixir_entry.text()), 'request_troops': self.req_chk.isChecked(), 'attack': self.attack_map[self.attack_combo.currentText()], 'train_mode': 'quick' if self.quick_radio.isChecked() else 'smart', 'quick_slot': self.quick_slot_spin.value()}
            save_village_config(idx, cfg)
            print(f'[INFO] Village_{idx} configuration saved.')
            cb, icon, apply_btn = self.mv_village_widgets[idx - 1]
            apply_btn.setEnabled(False)
            cb.setEnabled(False)
            from PyQt5.QtWidgets import QGraphicsOpacityEffect
            eff = QGraphicsOpacityEffect(icon)
            eff.setOpacity(0.35)
            icon.setGraphicsEffect(eff)
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(self, f'Village_{idx} Saved', f'Configuration for Village_{idx} has been stored.')
        def apply_mv_state():
            enabled = self.mv_enable_chk.isChecked()
            self.mv_count_spin.setEnabled(enabled)
            self.mv_interval.setEnabled(enabled)
            for cb, icon, apply_btn, save_btn in self.mv_village_widgets:
                active = enabled and cb.isChecked()
                cb.setEnabled(active)
                apply_btn.setEnabled(active)
                if active:
                    apply_btn.graphicsEffect().setOpacity(1.0)
                    icon.graphicsEffect().setOpacity(1.0)
                else:
                    apply_btn.graphicsEffect().setOpacity(0.35)
                    icon.graphicsEffect().setOpacity(0.35)
            self.on_count_changed(self.mv_count_spin.value())
        self.mv_count_spin.valueChanged.connect(self.on_count_changed)
        self.mv_enable_chk.toggled.connect(lambda _: apply_mv_state())
        apply_mv_state()
        self.on_count_changed(self.mv_count_spin.value())
        self.mv_enable_chk.toggled.connect(self.update_village_fade)
        self.mv_count_spin.valueChanged.connect(self.update_village_fade)
        self.update_village_fade()
        stack.addWidget(army_tab)
        logs_tab = QWidget()
        logs_layout = QVBoxLayout(logs_tab)
        logs_layout.setContentsMargins(10, 10, 10, 10)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(comic9)
        self.log.setStyleSheet('background:rgba(0,0,0,200);color:#EFE2BA;border:none;')
        logs_layout.addWidget(self.log)
        stack.addWidget(multi_tab)
        clan_tab = QWidget()
        cg_layout = QVBoxLayout(clan_tab)
        cg_layout.setContentsMargins(15, 15, 15, 15)
        cg_layout.setSpacing(10)
        enable_container = QWidget()
        enable_layout = QHBoxLayout(enable_container)
        enable_layout.setContentsMargins(0, 0, 0, 0)
        enable_layout.setSpacing(6)
        self.clan_games_toggle = QCheckBox('Enable Clan Games')
        self.clan_games_toggle.setFont(QFont('Segoe UI', 12, QFont.Bold))
        self.clan_games_toggle.setStyleSheet('color: #FFFFFF;')
        self.clan_games_toggle.setChecked(self.settings.get('enable_clan_games', False))
        enable_layout.addWidget(self.clan_games_toggle)
        games_icon_lbl = QLabel()
        pix_games = QPixmap(os.path.join(TEMPLATES_DIR, 'icon_games.png')).scaledToWidth(70, Qt.SmoothTransformation)
        games_icon_lbl.setPixmap(pix_games)
        enable_layout.addWidget(games_icon_lbl)
        enable_layout.addStretch()
        cg_layout.addWidget(enable_container)
        self.cg_grid_container = QWidget()
        cg_grid_layout = QGridLayout(self.cg_grid_container)
        cg_grid_layout.setContentsMargins(0, 0, 0, 0)
        cg_grid_layout.setHorizontalSpacing(8)
        cg_grid_layout.setVerticalSpacing(8)
        cg_layout.addWidget(self.cg_grid_container)
        cg_layout.addSpacing(8)
        self.cg_full_img_lbl = QLabel()
        pix = QPixmap(os.path.join(TEMPLATES_DIR, 'Clan Games.png'))
        pix = pix.scaledToWidth(350, Qt.SmoothTransformation)
        self.cg_full_img_lbl.setPixmap(pix)
        self.cg_full_img_lbl.setAlignment(Qt.AlignCenter)
        cg_layout.addWidget(self.cg_full_img_lbl)
        def _on_clan_toggle(on: bool):
            opacity = 1.0 if on else 0.6
            eff = QGraphicsOpacityEffect()
            eff.setOpacity(opacity)
            self.cg_full_img_lbl.setGraphicsEffect(eff)
        self.clan_games_toggle.toggled.connect(_on_clan_toggle)
        _on_clan_toggle(False)
        cg_layout.addStretch()
        stack.addWidget(clan_tab)
        cc_tab = QWidget()
        cc_layout = QVBoxLayout(cc_tab)
        cc_layout.setContentsMargins(15, 15, 15, 15)
        cc_layout.setSpacing(10)
        cc_en_row = QWidget()
        cc_en_h = QHBoxLayout(cc_en_row)
        cc_en_h.setContentsMargins(0, 0, 0, 0)
        cc_en_h.setSpacing(4)
        self.clan_capital_toggle = QCheckBox('Enable Clan Capital')
        self.clan_capital_toggle.setFont(QFont('Segoe UI', 12, QFont.Bold))
        self.clan_capital_toggle.setStyleSheet('color:#FFFFFF;')
        self.clan_capital_toggle.setChecked(self.settings.get('enable_clan_capital', False))
        cc_en_h.addWidget(self.clan_capital_toggle, 0, Qt.AlignLeft | Qt.AlignVCenter)
        logo_path = os.path.join(TEMPLATES_DIR, 'clan_capital_logo.png')
        logo_lbl = QLabel()
        if os.path.exists(logo_path):
            pix = QPixmap(logo_path)
            if not pix.isNull():
                logo_lbl.setPixmap(pix.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo_lbl.setContentsMargins(6, 0, 0, 0)
        cc_en_h.addWidget(logo_lbl, 0, Qt.AlignLeft | Qt.AlignVCenter)
        cc_en_h.addStretch(1)
        cc_layout.addWidget(cc_en_row)
        note_lbl = QLabel('Note: If you enable Clan Capital, please use the default scenery so MyBotPy can detect the Clan Capital boat more reliably.')
        note_lbl.setWordWrap(True)
        note_lbl.setStyleSheet('\n            color: #FFFFFF;\n            font-size: 14px;\n            font-weight: 700;\n            margin-top: 6px;\n        ')
        cc_layout.addWidget(note_lbl)
        cc_lvl_row = QWidget()
        cc_lvl_h = QHBoxLayout(cc_lvl_row)
        cc_lvl_h.setContentsMargins(0, 0, 0, 0)
        cc_lvl_h.setSpacing(8)
        lvl_label = QLabel('Capital Hall level:')
        lvl_label.setStyleSheet('color:#FFFFFF; font-size:18px; font-weight:600;')
        cc_lvl_h.addWidget(lvl_label, 0, Qt.AlignLeft | Qt.AlignVCenter)
        self.cc_level = QSpinBox()
        self.cc_level.setRange(1, 10)
        self.cc_level.setSingleStep(1)
        self.cc_level.setValue(int(self.settings.get('capital_hall_level', 9)))
        self.cc_level.setToolTip('Select your Clan Capital Hall level (1–10).')
        self.cc_level.setFixedSize(110, 40)
        self.cc_level.setFont(QFont('Segoe UI', 16, QFont.DemiBold))
        self.cc_level.setStyleSheet('\n            QSpinBox {\n                color: #111111;\n                background: #FFFFFF;\n                padding: 6px 10px;\n                border: 1px solid rgba(255,255,255,0.30);\n                border-radius: 8px;\n            }\n            QSpinBox::up-button, QSpinBox::down-button {\n                width: 18px; height: 18px;\n                margin: 1px;\n            }\n            QSpinBox:disabled {\n                color: rgba(255,255,255,0.45);     /* dim the number */\n                background: rgba(255,255,255,0.12);\n                border: 1px solid rgba(255,255,255,0.12);\n            }\n        ')
        note_lbl.setStyleSheet('\n            QLabel {\n                color: #FFFFFF;\n                font-size: 14px;\n                font-weight: 700;\n                margin-top: 6px;\n            }\n            QLabel:disabled {\n                color: rgba(255,255,255,0.45);\n            }\n        ')
        lvl_label.setStyleSheet('\n            QLabel {\n                color: #FFFFFF;\n                font-size: 18px;\n                font-weight: 700;\n            }\n            QLabel:disabled {\n                color: rgba(255,255,255,0.45);\n            }\n        ')
        cc_lvl_h.addWidget(self.cc_level, 0, Qt.AlignLeft | Qt.AlignVCenter)
        cc_lvl_h.addStretch(1)
        cc_layout.addWidget(cc_lvl_row)
        cc_layout.addStretch()
        stack.addWidget(cc_tab)
        self.cc_level.setEnabled(self.clan_capital_toggle.isChecked())
        self.clan_capital_toggle.toggled.connect(self.cc_level.setEnabled)
        def _cc_toggle_update(on: bool):
            note_lbl.setEnabled(on)
            lvl_label.setEnabled(on)
            self.cc_level.setEnabled(on)
        _cc_toggle_update(self.clan_capital_toggle.isChecked())
        self.clan_capital_toggle.toggled.connect(_cc_toggle_update)
        self.stats_tab = StatsTab(TEMPLATES_DIR, self.settings, multi_village_cb=self.mv_enable_chk, parent=self)
        stack.addWidget(self.stats_tab)
        self._stats_timer = QTimer(self)
        self._stats_timer.timeout.connect(self._refresh_stats_from_json)
        self._stats_timer.start(2000)
        # синхронизация статуса ботов с реальным состоянием процессов (на случай, если finished-сигнал
        # не дошёл: закрыт эмулятор, убит воркер и т.п.) — цвета вкладок и кнопки Start/End самокорректируются
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._sync_run_status)
        self._status_timer.start(1000)
        stack.addWidget(logs_tab)
        self.stream = TimestampStream()
        self.stream.new_line.connect(self._append_log)
        sys.stdout = self.stream
        sys.stderr = self.stream
        btn_layout = QHBoxLayout()
        right.addLayout(btn_layout)
        self.start_btn = ClickBounceButton()
        self.start_btn.setObjectName('startBtn')
        self._apply_image_button(self.start_btn, 'start.png', 180, 90)
        self.stop_btn = ClickBounceButton()
        self.stop_btn.setObjectName('endBtn')
        self._apply_image_button(self.stop_btn, 'end.png', 180, 90)
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        bridge.requestWizard.connect(self._on_request_wizard)
        bridge.wizardDone.connect(self._reload_village_icons)
        self.start_btn.clicked.connect(self.on_start)
        self.stop_btn.clicked.connect(self.on_end)
        nav.currentRowChanged.connect(stack.setCurrentIndex)
        nav.setCurrentRow(0)
        self._update_attack_preview()
        self._warned = False
        self.updater = Updater(self)
        self.updater.update_available.connect(self.on_update_available)
        QTimer.singleShot(500, self.updater.check_for_update)
    def _lbl(self, text: str, colour: str, font: QFont):
        lbl = QLabel(text)
        font.setBold(True)
        lbl.setFont(font)
        lbl.setStyleSheet(f'\n            color: {colour};\n            border: 1px solid #FFFFFF;\n            background: rgba(0,0,0,120);\n            padding: 2px 4px;\n        ')
        shadow = QGraphicsDropShadowEffect(lbl)
        shadow.setBlurRadius(6)
        shadow.setOffset(1, 1)
        shadow.setColor(QColor(0, 0, 0, 180))
        lbl.setGraphicsEffect(shadow)
        return lbl
    def _on_train_mode_toggled(self):
        """\n• When Quick‑Train ON  → slot enabled, bright background,\n  *number text* dark‑grey.\n• When Quick‑Train OFF → slot disabled and the entire label/box area\n  is dark‑grey.\n"""
        quick = self.quick_radio.isChecked()
        self.quick_slot_label.setEnabled(quick)
        self.quick_slot_spin.setEnabled(quick)
        if quick:
            self.quick_slot_spin.setStyleSheet('\n                QSpinBox {\n                    background: rgba(255,255,255,230);\n                    border: 1px solid #555555;\n                    border-radius: 4px;\n                    color: #444444;            /* dark‑grey text while ON */\n                }\n            ')
            self.quick_slot_label.setWindowOpacity(1.0)
        else:
            self.quick_slot_spin.setStyleSheet('\n                QSpinBox {\n                    background: #2b2b2b;\n                    border: 1px solid #555555;\n                    border-radius: 4px;\n                    color: #888888;\n                }\n            ')
            self.quick_slot_label.setWindowOpacity(0.35)
    def _toggle_wall_inputs(self, enabled: bool):
        policy = Qt.StrongFocus if enabled else Qt.NoFocus
        for w in [self.wall_gold_entry, self.wall_elixir_entry, self.wall_level_spin]:
            w.setEnabled(enabled)
            w.setFocusPolicy(policy)
    def _update_attack_preview(self):
        key = self.attack_combo.currentText()
        sel = self.attack_map[key]
        pix, desc = self.attack_images.get(sel, (None, ''))
        MAX_PREVIEW_W = 380
        if pix and (not pix.isNull()):
            disp = pix.scaledToWidth(MAX_PREVIEW_W, Qt.SmoothTransformation)
            self.attack_img.setPixmap(disp)
        else:
            self.attack_img.clear()
        self.attack_desc.setText(desc or '(no description)')
    def _append_log(self, line: str):
        colour = COLOR_TAGS.get(classify_colour(line), 'info')
        self.log.moveCursor(QTextCursor.End)
        self.log.insertHtml(f'<span class=\'{colour}\'>{line}</span><br>')
        self.log.moveCursor(QTextCursor.End)
    def on_start(self):
        """Нижний Start — запустить АКТИВНЫЙ бот отдельным worker-процессом. Эмулятор/инстанс —
        через диалог (лок держит воркер, не GUI). Настройки бота — из меню (пишем во временный профиль)."""
        try:
            b = self._bots[self._active_bot]
            if self._proc_alive(b.get('proc')):
                return
            main.emulator_key = None                      # сброс: отмена диалога → корректный abort
            self.choose_emulator()                       # выбор эмулятора/инстанса (ставит main.*)
            key = getattr(main, 'emulator_key', None)
            if not key:
                self._log_to_bot(self._active_bot, '[INFO] Start aborted (no emulator selected).')
                return
            if key == 'memu':
                idx = getattr(main, 'memu_index', None)
                idx = idx if idx is not None else 0
            else:
                idx = getattr(main, 'ld_index', 0)
            b['emulator'], b['index'] = key, int(idx or 0)
            # настройки бота (из меню) → временный профиль для воркера (+ свой стат-бакет)
            self._write_bot_profile(b, self._active_bot, self._collect_cfg())
            main.emulator_key = None                      # сбросить, чтобы диалог не залипал на след. боте
            self._start_bot(b, self._active_bot)
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, 'Startup Error', f'An unexpected error occurred when starting:\n\n{e}')

    def on_end(self):
        """Нижний End/Stop — остановить АКТИВНЫЙ бот (его worker-процесс)."""
        self._log_to_bot(self._active_bot, '[INFO] Active bot stopped')
        self._stop_active_bot()
        self._update_run_buttons()           # сразу разблокировать Start (не ждать finished-сигнала)
    def _collect_cfg(self):
        cfg = {
            'gold_threshold': int(self.gold_entry.text()),
            'elixir_threshold': int(self.elixir_entry.text()),
            'dark_elixir_threshold': int(self.dark_entry.text()),
            'upgrade_wall': self.upgrade_chk.isChecked(),
            'wall_level': int(self.wall_level_spin.value()),
            'wall_level_from': int(self.wall_level_spin.value()),
            'wall_level_to': int(getattr(self, 'wall_level_to_spin', self.wall_level_spin).value()),
            'wall_gold_threshold': int(self.wall_gold_entry.text()),
            'wall_elixir_threshold': int(self.wall_elixir_entry.text()),
            'request_troops': self.req_chk.isChecked(),
            'attack': self.attack_map[self.attack_combo.currentText()],
            'train_mode': 'quick' if self.quick_radio.isChecked() else 'smart',
            'quick_slot': self.quick_slot_spin.value(),
            'enable_clan_games': self.clan_games_toggle.isChecked(),
            'enable_clan_capital': self.clan_capital_toggle.isChecked(),
            'capital_hall_level': int(self.cc_level.value()),
            'enable_stats': self.stats_tab.enable_stats_chk.isChecked(),
            'enable_multi_account': self.mv_enable_chk.isChecked(),
            'multi_count': self.mv_count_spin.value(),
            'multi_interval_mins': int(self.mv_interval.value()),
            'selected_villages': [idx for idx, (cb, icon, apply_btn, _) in enumerate(self.mv_village_widgets, start=1) if cb.isChecked()],
            'current_village_idx': 1,
            'enable_stats': self.stats_tab.enable_stats_chk.isChecked(),
            'full_gold': self.full_gold_chk.isChecked(),
            'full_elixir': self.full_elixir_chk.isChecked(),
            'full_dark': self.full_dark_chk.isChecked(),
        }
        # флаги «стоп при полном» — в config/farming.json (по каким ресурсам ждать полноты)
        try:
            save_farming_flags(self.full_gold_chk.isChecked(),
                               self.full_elixir_chk.isChecked(),
                               self.full_dark_chk.isChecked())
        except Exception:
            pass
        return cfg
    def closeEvent(self, event):
        try:
            cfg = self._collect_cfg()
            save_settings(cfg)
            for _b in getattr(self, '_bots', []):     # погасить worker-процессы всех ботов
                pr = _b.get('proc')
                if pr is not None and self._proc_alive(pr):
                    _b['stopping'] = True
                    try:
                        pr.finished.disconnect()      # не ловить колбэки на удаляемых объектах
                    except Exception:
                        pass
                    pr.kill()
        except Exception as e:
            print(f'[ERROR] during shutdown: {e}')
        super().closeEvent(event)
        QApplication.quit()
def main_gui():
    app = QApplication.instance()
    app.setStyleSheet('\n    QToolTip {\n        background: #1E1E1E;\n        color: #EFE2BA;\n        border: 1px solid #5D4037;\n        border-radius: 4px;\n        padding: 4px 6px;\n    }\n    QLineEdit, QSpinBox, QComboBox, QTextEdit {\n        background: rgba(255,255,255,200);\n        border: 1px solid #5D4037;\n        border-radius: 4px;\n    }\n    QPushButton {\n        background: rgba(100, 100, 100, 200);\n        border: 1px solid #4E342E;\n    }\n    QPushButton:hover {\n        background: rgba(120,120,120,200);\n    }\n    \n    QPushButton#startBtn,\n    QPushButton#endBtn {\n        background: transparent;\n        border: none;\n        padding: 0;          /* let the icon be the exact size */\n    }\n\n    /* keep them transparent in all states */\n    QPushButton#startBtn:hover,\n    QPushButton#endBtn:hover,\n    QPushButton#startBtn:disabled,\n    QPushButton#endBtn:disabled {\n        background: transparent;\n        border: none;\n    }\n\n    /* tiny ‘pressed’ nudge */\n    QPushButton#startBtn:pressed,\n    QPushButton#endBtn:pressed {\n        background: transparent;\n        border: none;\n        padding-top: 1px;    /* subtle sink effect */\n    }\n        \n\n    ')
    zero_all_stats_files()
    icon_path = os.path.join(TEMPLATES_DIR, 'app_icon.ico')
    app.setWindowIcon(QIcon(icon_path))
    win = MainWindow()
    win.setWindowIcon(QIcon(icon_path))
    win.show()
    if getattr(sys, 'frozen', False):
        pyi_splash.close()
    sys.exit(app.exec_())
if __name__ == '__main__':
    try:
        main_gui()
    except Exception:
        traceback.print_exc()
        QMessageBox.critical(None, 'Startup Error', 'An error occurred before the UI could start.\n\n' + traceback.format_exc())
