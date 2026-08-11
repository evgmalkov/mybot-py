import sys
import os
import json
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QWizard, QWizardPage, QLabel, QLineEdit, QCheckBox, QSpinBox, QFormLayout, QVBoxLayout, QHBoxLayout, QComboBox, QRadioButton, QButtonGroup, QMessageBox
from PyQt5.QtGui import QPixmap, QFont, QWindow
from ready_villages import prepare_accounts, PROFILES_DIR
from wizard_bridge import bridge
from PyQt5.QtCore import Qt
from paths import BASE_DIR
ATTACK_CHOICES = ['Dragon_Attack', 'ElectroDragon_Attack']
INTERVAL_OPTIONS = ['30 minutes', '1 hour', '1.5 hours', '2 hours']


class ConfigPage(QWizardPage):

    def __init__(self, idx: int, parent=None):
        super().__init__(parent)
        self.idx = idx
        self.setTitle(f'Configure Village {idx}')
        layout = QVBoxLayout()
        img_path = PROFILES_DIR / f'account_{idx}.png'
        if img_path.exists():
            lbl = QLabel()
            pix = QPixmap(str(img_path)).scaledToWidth(200)
            lbl.setPixmap(pix)
            layout.addWidget(lbl)
        form = QFormLayout()
        font = QFont('Segoe UI', 10)
        self.gold = QLineEdit('650000')
        self.gold.setFont(font)
        self.elixir = QLineEdit('650000')
        self.elixir.setFont(font)
        self.dark = QLineEdit('1000')
        self.dark.setFont(font)
        self.upgrade = QCheckBox('Upgrade Wall')
        self.upgrade.setFont(font)
        self.wall_level = QSpinBox()
        self.wall_level.setRange(8, 18)
        self.wall_level.setValue(5)
        self.wall_level.setFont(font)
        self.wall_gold = QLineEdit('5000000')
        self.wall_gold.setFont(font)
        self.wall_elixir = QLineEdit('5000000')
        self.wall_elixir.setFont(font)
        self.request_troops = QCheckBox('Enable Request Troops')
        self.request_troops.setFont(font)
        self.attack = QComboBox()
        self.attack.addItems(ATTACK_CHOICES)
        self.attack.setFont(font)
        self.clan_capital = QCheckBox('Enable Clan Capital')
        self.clan_capital.setFont(font)
        self.cc_level = QSpinBox()
        self.cc_level.setRange(1, 10)
        self.cc_level.setValue(9)
        self.cc_level.setFont(font)
        self.cc_level.setEnabled(False)
        self.clan_capital.toggled.connect(self.cc_level.setEnabled)
        self.smart = QRadioButton('Smart Train')
        self.quick = QRadioButton('Quick Train')
        self.smart.setFont(font)
        self.quick.setFont(font)
        self.smart.setChecked(True)
        self.train_group = QButtonGroup()
        self.train_group.addButton(self.smart)
        self.train_group.addButton(self.quick)
        self.quick_slot = QSpinBox()
        self.quick_slot.setRange(1, 2)
        self.quick_slot.setValue(1)
        self.wall_level.setEnabled(False)
        self.wall_gold.setEnabled(False)
        self.wall_elixir.setEnabled(False)
        self.quick_slot.setEnabled(False)
        self.upgrade.toggled.connect(self.on_upgrade_toggled)
        self.quick.toggled.connect(self.quick_slot.setEnabled)
        form.addRow('Gold threshold:', self.gold)
        form.addRow('Elixir threshold:', self.elixir)
        form.addRow('Dark elixir threshold:', self.dark)
        form.addRow(self.upgrade)
        form.addRow('Wall level:', self.wall_level)
        form.addRow('Wall gold threshold:', self.wall_gold)
        form.addRow('Wall elixir threshold:', self.wall_elixir)
        form.addRow(self.request_troops)
        self.clan_games = QCheckBox('Enable Clan Games')
        self.clan_games.setFont(font)
        form.addRow(self.clan_games)
        form.addRow(self.clan_capital)
        form.addRow('Capital Hall level:', self.cc_level)
        self.enable_stats = QCheckBox('Enable Statistics')
        self.enable_stats.setFont(font)
        self.enable_stats.setChecked(True)
        form.addRow(self.enable_stats)
        form.addRow('Attack type:', self.attack)
        train_box = QHBoxLayout(); train_box.addWidget(self.smart)
        train_box.addWidget(self.quick)
        form.addRow(train_box)
        form.addRow('Quick slot:', self.quick_slot)
        layout.addLayout(form)
        self.setLayout(layout)

    def on_upgrade_toggled(self, checked: bool):
        self.wall_level.setEnabled(checked)
        self.wall_gold.setEnabled(checked)
        self.wall_elixir.setEnabled(checked)

    def get_config(self):
        return {'gold_threshold': int(self.gold.text()), 'elixir_threshold': int(self.elixir.text()), 'dark_elixir_threshold': int(self.dark.text()), 'upgrade_wall': self.upgrade.isChecked(), 'wall_level': self.wall_level.value(), 'wall_gold_threshold': int(self.wall_gold.text()), 'wall_elixir_threshold': int(self.wall_elixir.text()), 'request_troops': self.request_troops.isChecked(), 'enable_clan_games': self.clan_games.isChecked(), 'enable_clan_capital': self.clan_capital.isChecked(), 'capital_hall_level': self.cc_level.value(), 'enable_stats': self.enable_stats.isChecked(), 'attack': self.attack.currentText(), 'train_mode': 'quick' if self.quick.isChecked() else 'smart', 'quick_slot': self.quick_slot.value()}


class ConclusionPage(QWizardPage):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle('Finish')
        lbl = QLabel('Click Finish to save all village configurations.')
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(lbl)


def run_village_wizard(start: int, count: int):
    """
1) Crops account images for the needed villages via prepare_accounts.
   If `start` is a list of indices, it will crop a contiguous range
   from min(start) to max(start).
2) Launches a QWizard with one ConfigPage per selected village index.
"""
    if isinstance(start, (list, tuple)):
        indices = sorted(start)
        first_idx = indices[0]
        last_idx = indices[-1]
        crop_count = last_idx - first_idx + 1
        try:
            detected_total = prepare_accounts(start=first_idx, count=crop_count)
        except Exception as e:
            QMessageBox.critical(None, 'Error', f'Could not prepare accounts:\n{e}')
            return
    else:
        first_idx = start
        crop_count = count
        indices = list(range(start, start + count))
        try:
            detected_total = prepare_accounts(start=first_idx, count=crop_count)
        except Exception as e:
            QMessageBox.critical(None, 'Error', f'Could not prepare accounts:\n{e}')
            return
    if detected_total == 1:
        QMessageBox.information(None, 'Single Village Mode', 'Only one village is available—switching to single‐village mode.')
        return
    app = QApplication.instance() or QApplication(sys.argv)
    wizard = QWizard()
    wizard.setWindowTitle('Clash Bot Village Configuration Wizard')
    intro = QWizardPage()
    intro.setTitle('Welcome')
    intro_layout = QVBoxLayout(intro)
    intro_layout.addWidget(QLabel(f'Configuring Village profiles: {indices}'))
    wizard.addPage(intro)
    pages = []
    for idx in indices:
        page = ConfigPage(idx)
        pages.append((idx, page))
        wizard.addPage(page)
    concl = ConclusionPage()
    wizard.addPage(concl)

    def save_all():
        for idx, page in pages:
            cfg = page.get_config()
            path = PROFILES_DIR / f'Village_{idx}.json'
            with open(path, 'w') as f:
                json.dump(cfg, f, indent=2)
        QMessageBox.information(wizard, 'Saved', 'All village configs saved.')
        bridge.wizardDone.emit()
        wizard.close()
    wizard.button(QWizard.FinishButton).clicked.connect(save_all)
    wizard.show()
    wizard.raise_()
    wizard.activateWindow()
    qt_win = QWindow.fromWinId(int(wizard.winId()))
    print(f'[D] Wizard HWND is {qt_win.winId()}')
    wizard.exec_()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    run_village_wizard()
    sys.exit(app.exec_())
