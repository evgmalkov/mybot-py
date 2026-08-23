"""[LEGACY / NOT USED] Многоэкземплярная панель ботов (вкладки в ОДНОМ окне-платформе).

⚠️ LEGACY: не подключён к GUI. Заменён глобальной верхней BotInstanceBar в bot_gui.py
(QTabBar в общем layout, левая навигация статична). Оставлен как reference для Duplicate/Rename —
после их реализации в новой top-bar удалить файл целиком. Ни один модуль его не импортирует.


Архитектура: единый GUI → вкладки BotInstance → у каждого свой worker-ПРОЦЕСС
(run_from_source.py --worker …). Процессы изолированы (свои main.host/TABS/stop_event) →
никаких конфликтов глобального состояния. HWND не встраиваем.

BotInstanceView — GUI-представление одного экземпляра (эмулятор/инстанс/аккаунт + Start/Stop +
статус + лог), управляет ТОЛЬКО своим процессом. BotsPanel — QTabWidget: +/× добавляет/закрывает.
"""
import os
import sys

from PyQt5.QtCore import QProcess, Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSpinBox,
                             QPushButton, QTextEdit, QTabWidget, QMessageBox)

from paths import BASE_DIR


def _ld_installed() -> bool:
    """Быстрый детект LDPlayer (без скана диска) — прятать пункт, если не установлен."""
    try:
        from ldplayer_manager import find_ldplayer_tools
        c, p = find_ldplayer_tools(allow_deep_scan=False)
        return bool(c and p)
    except Exception:
        return False


class BotInstanceView(QWidget):
    """Один экземпляр бота: выбор эмулятора/инстанса/аккаунта, Start/Stop, статус, лог. Свой процесс."""

    def __init__(self, parent=None, ld_available=True):
        super().__init__(parent)
        self.proc = None
        self._stopping = False
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)

        # --- строка конфигурации ---
        cfg = QHBoxLayout()
        cfg.setSpacing(8)
        cfg.addWidget(self._lbl('Emulator:'))
        self.emu = QComboBox()
        self.emu.addItem('MEmu', 'memu')
        if ld_available:
            self.emu.addItem('LDPlayer', 'ldplayer')
        self.emu.setFixedWidth(110)
        cfg.addWidget(self.emu)
        cfg.addWidget(self._lbl('Instance:'))
        self.idx = QSpinBox()
        self.idx.setRange(0, 31)
        self.idx.setPrefix('#')
        self.idx.setFixedWidth(64)
        cfg.addWidget(self.idx)
        cfg.addWidget(self._lbl('Account:'))
        self.village = QComboBox()
        for i in range(1, 6):
            self.village.addItem(f'Village {i}', i)
        self.village.setFixedWidth(110)
        cfg.addWidget(self.village)
        cfg.addStretch()
        self.status = QLabel('● Stopped')
        self.status.setFont(QFont('Segoe UI', 10, QFont.Bold))
        self.status.setStyleSheet('color:#9A9A9A;')
        cfg.addWidget(self.status)
        v.addLayout(cfg)

        # --- Start / Stop ---
        btns = QHBoxLayout()
        self.start_btn = QPushButton('▶  Start')
        self.start_btn.setFont(QFont('Segoe UI', 11, QFont.Bold))
        self.start_btn.setMinimumHeight(34)
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.setStyleSheet('QPushButton{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,'
                                     'stop:0 #4CAF50,stop:1 #2E7D32);color:#FFF;border:none;'
                                     'border-radius:8px;padding:4px 18px;} QPushButton:hover{background:#5DBF60;}'
                                     ' QPushButton:disabled{background:#3A3A3A;color:#777;}')
        self.start_btn.clicked.connect(self.start)
        self.stop_btn = QPushButton('■  Stop')
        self.stop_btn.setFont(QFont('Segoe UI', 11, QFont.Bold))
        self.stop_btn.setMinimumHeight(34)
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet('QPushButton{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,'
                                    'stop:0 #FF5252,stop:1 #C62828);color:#FFF;border:none;'
                                    'border-radius:8px;padding:4px 18px;} QPushButton:hover{background:#FF7676;}'
                                    ' QPushButton:disabled{background:#3A3A3A;color:#777;}')
        self.stop_btn.clicked.connect(self.stop)
        btns.addWidget(self.start_btn)
        btns.addWidget(self.stop_btn)
        btns.addStretch()
        v.addLayout(btns)

        # --- лог экземпляра ---
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet('QTextEdit{background:#141414;color:#E0E0E0;border:1px solid #333;'
                               'border-radius:6px;font-family:Consolas;font-size:11px;}')
        v.addWidget(self.log, 1)

    @staticmethod
    def _lbl(text):
        lb = QLabel(text)
        lb.setStyleSheet('color:#EFE2BA;')
        lb.setFont(QFont('Segoe UI', 9, QFont.Bold))
        return lb

    # ── статус/лог ──
    def _set_status(self, text, color):
        self.status.setText(f'● {text}')
        self.status.setStyleSheet(f'color:{color};')

    def _append(self, line):
        self.log.append(line)

    def _set_config_enabled(self, on):
        for w in (self.emu, self.idx, self.village):
            w.setEnabled(on)

    def tab_title(self):
        return f'{self.emu.currentText()} #{self.idx.value()}'

    def is_running(self):
        return self.proc is not None and self.proc.state() != QProcess.NotRunning

    def get_config(self):
        """(emulator_key, instance_index, village) — для duplicate/коллизий."""
        return (self.emu.currentData(), int(self.idx.value()), int(self.village.currentData()))

    def set_config(self, emu, idx, village):
        j = self.emu.findData(emu)
        if j >= 0:
            self.emu.setCurrentIndex(j)
        self.idx.setValue(int(idx))
        k = self.village.findData(int(village))
        if k >= 0:
            self.village.setCurrentIndex(k)

    # ── жизненный цикл процесса ──
    def start(self):
        if self.is_running():
            return
        emu = self.emu.currentData()
        idx = int(self.idx.value())
        vil = int(self.village.currentData())
        entry = os.path.join(str(BASE_DIR), 'run_from_source.py')
        self._stopping = False
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.setWorkingDirectory(str(BASE_DIR))
        self.proc.readyReadStandardOutput.connect(self._drain)
        self.proc.finished.connect(self._on_finished)
        self._append(f'[GUI] starting {emu} #{idx}, account Village {vil}…')
        self.proc.start(str(sys.executable), [entry, '--worker', '--emulator', emu,
                                              '--index', str(idx), '--village', str(vil)])
        self._set_status('Running', '#4CAF50')
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._set_config_enabled(False)

    def stop(self):
        self._stopping = True
        if self.proc:
            self.proc.kill()

    def _on_finished(self, code, _status):
        crashed = (not self._stopping) and code != 0
        self._set_status('Crashed' if crashed else 'Stopped', '#FF5252' if crashed else '#9A9A9A')
        if crashed:
            self._append(f'[GUI] runtime exited unexpectedly (code {code}). Press Start to restart.')
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._set_config_enabled(True)
        self._stopping = False

    def _drain(self):
        try:
            data = bytes(self.proc.readAllStandardOutput()).decode('utf-8', errors='ignore')
        except Exception:
            return
        for line in data.splitlines():
            if line.strip():
                self._append(line)


class BotsPanel(QWidget):
    """Головная область: вкладки BotInstance, кнопка + (добавить), × (закрыть с подтверждением)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ld = _ld_installed()
        self._counter = 0
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.tabs.tabBarDoubleClicked.connect(self.rename_bot)          # 2× клик — переименовать
        self.tabs.tabBar().setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabs.tabBar().customContextMenuRequested.connect(self._tab_menu)
        self.tabs.setStyleSheet('QTabBar::tab{background:#2A2A2A;color:#EFE2BA;padding:6px 14px;'
                                'border-top-left-radius:6px;border-top-right-radius:6px;margin-right:2px;}'
                                ' QTabBar::tab:selected{background:#4CAF50;color:#FFF;}')
        add_btn = QPushButton('  +  ')
        add_btn.setFont(QFont('Segoe UI', 12, QFont.Bold))
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setToolTip('Add a bot instance')
        add_btn.setStyleSheet('QPushButton{background:#3A6EA5;color:#FFF;border:none;border-radius:6px;'
                              'padding:2px 10px;} QPushButton:hover{background:#4E86C6;}')
        add_btn.clicked.connect(self.add_bot)
        self.tabs.setCornerWidget(add_btn)
        v.addWidget(self.tabs)
        self.add_bot()   # стартуем с одной вкладкой

    def add_bot(self):
        self._counter += 1
        view = BotInstanceView(self, ld_available=self._ld)
        i = self.tabs.addTab(view, f'Bot {self._counter}')
        self.tabs.setCurrentIndex(i)

    # ── контекст-меню вкладки: New / Duplicate / Rename / Close ──
    def _tab_menu(self, pos):
        from PyQt5.QtWidgets import QMenu
        bar = self.tabs.tabBar()
        i = bar.tabAt(pos)
        m = QMenu(self)
        m.addAction('New bot', self.add_bot)
        if i >= 0:
            m.addAction('Duplicate', lambda: self.duplicate_bot(i))
            m.addAction('Rename…', lambda: self.rename_bot(i))
            m.addSeparator()
            m.addAction('Close', lambda: self._close_tab(i))
        m.exec_(bar.mapToGlobal(pos))

    def _used_instances(self, exclude=None):
        """{(emulator, index)} по всем вкладкам (для детекта коллизий)."""
        used = set()
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if w is None or w is exclude:
                continue
            emu, idx, _ = w.get_config()
            used.add((emu, idx))
        return used

    def _next_free_index(self, emu, start, exclude=None):
        """Ближайший свободный индекс инстанса для эмулятора (>= start), не занятый др. вкладкой."""
        used = self._used_instances(exclude)
        idx = max(0, int(start))
        while (emu, idx) in used and idx < 32:
            idx += 1
        return idx

    def duplicate_bot(self, i):
        """Копия вкладки i с тем же эмулятором/аккаунтом; индекс инстанса — свободный (коллизия → +1)."""
        src = self.tabs.widget(i)
        if src is None:
            return
        emu, idx, vil = src.get_config()
        new_idx = self._next_free_index(emu, idx)
        self._counter += 1
        view = BotInstanceView(self, ld_available=self._ld)
        view.set_config(emu, new_idx, vil)
        j = self.tabs.addTab(view, f'Bot {self._counter}')
        self.tabs.setCurrentIndex(j)
        if new_idx != idx:
            QMessageBox.information(self, 'Duplicate',
                                    f'{emu} #{idx} is already assigned -> using #{new_idx}.')

    def rename_bot(self, i):
        if i < 0:
            return
        from PyQt5.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, 'Rename bot', 'Tab name:', text=self.tabs.tabText(i))
        if ok and name.strip():
            self.tabs.setTabText(i, name.strip())

    def _close_tab(self, i):
        view = self.tabs.widget(i)
        if view is not None and view.is_running():
            r = QMessageBox.question(self, 'Close bot', 'This bot is running. Stop and close?',
                                     QMessageBox.Yes | QMessageBox.No)
            if r != QMessageBox.Yes:
                return
            view.stop()
        self.tabs.removeTab(i)
        if self.tabs.count() == 0:
            self.add_bot()

    def stop_all(self):
        """Остановить все процессы (вызывать при закрытии главного окна)."""
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if w is not None and w.is_running():
                w.stop()
