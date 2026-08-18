
import os
import time
from collections import defaultdict
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPixmap, QColor
from PyQt5.QtWidgets import QWidget, QScrollArea, QVBoxLayout, QLabel, QGridLayout, QGroupBox, QHBoxLayout, QTabWidget, QFrame, QCheckBox, QGraphicsOpacityEffect





class _ResourceRow(QWidget):
    """Icon + numeric label packed in a tiny h‑box."""

    def __init__(self, icon_path: str, font: QFont, colour: str):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        icon_lbl = QLabel()
        icon = QPixmap(icon_path).scaledToWidth(24, Qt.SmoothTransformation)
        icon_lbl.setPixmap(icon)
        self.val_lbl = QLabel('0')
        self.val_lbl.setFont(font)
        self.val_lbl.setStyleSheet(f'color:{colour};')
        h.addWidget(icon_lbl)
        h.addWidget(self.val_lbl)
        h.addStretch()


    def set_value(self, n: int):
        self.val_lbl.setText(f'{n:,}')

    def set_text(self, s: str):
        self.val_lbl.setText(s)


class StatsTab(QWidget):
    """Scrollable statistics panel (Overall → Per‑Village → Attack results)."""

    def __init__(self, templates_dir: str, cfg: dict, multi_village_cb=None, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setStyleSheet('background: transparent;')
        self.templates_dir = templates_dir
        self.multi_village_cb = multi_village_cb
        self.start_ts = time.time()
        self.overall = defaultdict(int)
        self.per_village = defaultdict(lambda: defaultdict(int))
        self.stars = defaultdict(int)
        hdrF = QFont('Segoe UI', 13, QFont.Bold)
        numF = QFont('Segoe UI', 12, QFont.Bold)
        labelF = QFont('Segoe UI', 11, QFont.Bold)
        gold_c = '#EFE2BA'
        elixir_c = '#EFE2BA'
        de_c = '#EFE2BA'
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet('background: transparent; border: none;')
        root = QWidget()
        root.setAttribute(Qt.WA_TranslucentBackground)
        root.setAttribute(Qt.WA_NoSystemBackground)
        root.setStyleSheet('background: transparent;')
        scroll.setWidget(root)
        vroot = QVBoxLayout(root)
        vroot.setContentsMargins(0, 15, 15, 0)
        vroot.setSpacing(15)
        enable_container = QWidget()
        enable_layout = QHBoxLayout(enable_container)
        enable_layout.setContentsMargins(0, 0, 0, 0)
        enable_layout.setSpacing(6)
        self.enable_stats_chk = QCheckBox('Enable Statistics', self)
        self.enable_stats_chk.setFont(QFont('Segoe UI', 13, QFont.Bold))
        self.enable_stats_chk.setStyleSheet('color: #FFFFFF;')
        self.enable_stats_chk.setChecked(self.cfg.get('enable_stats', False))
        enable_layout.addWidget(self.enable_stats_chk)
        shield_lbl = QLabel()
        pix_shield = QPixmap(os.path.join(templates_dir, 'icon_shield.png')).scaledToWidth(36, Qt.SmoothTransformation)
        shield_lbl.setPixmap(pix_shield)
        enable_layout.addWidget(shield_lbl)
        enable_layout.addStretch()
        vroot.addWidget(enable_container)
        self.enable_stats_chk.toggled.connect(lambda on: self.cfg.__setitem__('enable_stats', on))
        gb_overall = QGroupBox('Total Resources Gain')
        gb_overall.setFont(hdrF)
        gb_overall.setStyleSheet('\n            QGroupBox {\n                background: transparent;\n                border: 1px solid #FFFFFF;\n                border-radius: 4px;\n                margin-top: 6px;\n            }\n            QGroupBox::title {\n                subcontrol-origin: margin;\n                left: 8px; padding: 0 4px;\n                color: #FFFFFF;\n            }\n        ')
        grid = QGridLayout(gb_overall)
        grid.setContentsMargins(8, 16, 8, 8)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        self.avg_labels = {}
        self.row_gold = _ResourceRow(os.path.join(templates_dir, 'icon_gold.png'), numF, gold_c)
        self.row_elixir = _ResourceRow(os.path.join(templates_dir, 'icon_elixir.png'), numF, elixir_c)
        self.row_de = _ResourceRow(os.path.join(templates_dir, 'icon_de.png'), numF, de_c)
        grid.addWidget(self.row_gold, 0, 0, 1, 2)
        grid.addWidget(self.row_elixir, 1, 0, 1, 2)
        grid.addWidget(self.row_de, 2, 0, 1, 2)
        att_container = QWidget()
        att_hlay = QHBoxLayout(att_container)
        att_hlay.setContentsMargins(0, 0, 0, 0)
        att_hlay.setSpacing(4)
        att_icon = QLabel()
        pix_atk = QPixmap(os.path.join(templates_dir, 'icon_attack.png')).scaledToWidth(24, Qt.SmoothTransformation)
        att_icon.setPixmap(pix_atk)
        att_hlay.addWidget(att_icon)
        lbl_att = QLabel('Total Attacks:')
        lbl_att.setFont(labelF)
        lbl_att.setStyleSheet('color:#FFFFFF;')
        att_hlay.addWidget(lbl_att)
        att_hlay.addStretch()
        grid.addWidget(att_container, 3, 0)
        self.val_att = QLabel('0')
        self.val_att.setFont(numF)
        self.val_att.setStyleSheet('color:#FFFFFF;')
        grid.addWidget(self.val_att, 3, 1, alignment=Qt.AlignRight)
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet('color:#666;')
        grid.addWidget(line, 4, 0, 1, 2)
        l = QLabel('Avg Gold:')
        l.setFont(labelF)
        l.setStyleSheet('color:#FFFFFF;')
        grid.addWidget(l, 5, 0)
        avg_gold_row = _ResourceRow(os.path.join(templates_dir, 'icon_gold.png'), numF, '#EFE2BA')
        grid.addWidget(avg_gold_row, 5, 1)
        self.avg_labels['avg_gold'] = avg_gold_row
        l = QLabel('Avg Elixir:')
        l.setFont(labelF)
        l.setStyleSheet('color:#FFFFFF;')
        grid.addWidget(l, 6, 0)
        avg_elixir_row = _ResourceRow(os.path.join(templates_dir, 'icon_elixir.png'), numF, '#EFE2BA')
        grid.addWidget(avg_elixir_row, 6, 1)
        self.avg_labels['avg_elixir'] = avg_elixir_row
        l = QLabel('Avg DE:')
        l.setFont(labelF)
        l.setStyleSheet('color:#FFFFFF;')
        grid.addWidget(l, 7, 0)
        avg_de_row = _ResourceRow(os.path.join(templates_dir, 'icon_de.png'), numF, '#EFE2BA')
        grid.addWidget(avg_de_row, 7, 1)
        self.avg_labels['avg_de'] = avg_de_row
        vroot.addWidget(gb_overall)
        gb_attres = QGroupBox('Attack Results')
        gb_attres.setFont(hdrF)
        gb_attres.setStyleSheet('\n            QGroupBox {\n                background: transparent;\n                border: 1px solid #FFFFFF;\n                border-radius: 4px;\n                margin-top: 6px;\n            }\n            QGroupBox::title {\n                subcontrol-origin: margin;\n                left: 8px; padding: 0 4px;\n                color: #FFFFFF;\n            }\n        ')
        grid_ar = QGridLayout(gb_attres)
        grid_ar.setHorizontalSpacing(12)
        grid_ar.setVerticalSpacing(6)
        star_labels = {0: '0 Stars:', 1: '1 Star:', 2: '2 Stars:', 3: '3 Stars:'}
        self.lbl_star = {}
        for i in range(4):
            star_container = QWidget()
            star_hlay = QHBoxLayout(star_container)
            star_hlay.setContentsMargins(0, 0, 0, 0)
            star_hlay.setSpacing(4)
            icon_path = os.path.join(templates_dir, f'icon_{i} star.png')
            star_icon = QLabel()
            pix_star = QPixmap(icon_path).scaledToWidth(48, Qt.SmoothTransformation)
            star_icon.setPixmap(pix_star)
            star_hlay.addWidget(star_icon)
            star_text = QLabel(star_labels[i])
            star_text.setFont(labelF)
            star_text.setStyleSheet('color:#FFFFFF;')
            star_hlay.addWidget(star_text)
            star_hlay.addStretch()
            grid_ar.addWidget(star_container, i, 0)
            v = QLabel('0')
            v.setFont(numF)
            if i == 0:
                colour = '#FF6E40'
            else:
                if i == 1:
                    colour = '#FFB300'
                else:
                    if i == 2:
                        colour = '#FFFF00'
                    else:
                        colour = '#66BB6A'
            v.setStyleSheet(f'color:{colour};')
            grid_ar.addWidget(v, i, 1, alignment=Qt.AlignRight)
            self.lbl_star[i] = v
        for row_idx in range(4):
            grid_ar.setRowStretch(row_idx, 1)
        vroot.addWidget(gb_attres, 1)

        def _on_stats_toggled(on: bool):
            opacity = 1.0 if on else 0.6
            for box in [gb_overall, gb_attres]:
                eff = QGraphicsOpacityEffect()
                eff.setOpacity(opacity)
                box.setGraphicsEffect(eff)
        self.enable_stats_chk.toggled.connect(_on_stats_toggled)
        _on_stats_toggled(self.enable_stats_chk.isChecked())
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        vroot.addStretch()
        session_bottom = QWidget()
        session_layout = QHBoxLayout(session_bottom)
        session_layout.setContentsMargins(0, 0, 0, 0)
        session_layout.setSpacing(4)

    def _refresh_time(self):
        self._refresh_overall_time()
        self._refresh_all()

    def _refresh_overall_time(self):
        elapsed = max(1, int(time.time() - self.start_ts))
        self.session_lbl.setText(self._fmt_secs(elapsed))

    def _refresh_all(self):
        self.row_gold.set_value(self.overall['gold'])
        self.row_elixir.set_value(self.overall['elixir'])
        self.row_de.set_value(self.overall['de'])
        self.val_att.setText(str(self.overall['attacks']))
        # Avg-блок = «среднее на атаку · скорость в час». Скорость в час сглажена: первые
        # SMOOTH_SECS секунд показываем «—/h» (иначе короткая сессия даёт бессмысленные млн/час).
        SMOOTH_SECS = 300
        attacks = self.overall['attacks']
        att = max(1, attacks)
        elapsed_s = time.time() - self.start_ts
        rate_ready = attacks > 0 and elapsed_s >= SMOOTH_SECS
        elapsed_h = elapsed_s / 3600
        for key, res in (('avg_gold', 'gold'), ('avg_elixir', 'elixir'), ('avg_de', 'de')):
            per_att = self.overall[res] // att
            rate = f'{self._fmt_compact(self.overall[res] / elapsed_h)}/h' if rate_ready else '—/h'
            self.avg_labels[key].set_text(f'{per_att:,} · {rate}')
        for s in range(4):
            self.lbl_star[s].setText(str(self.stars[s]))

    @staticmethod
    def _fmt_compact(n: float) -> str:
        """Компактный формат больших чисел: 13172493 → 13.2M."""
        n = float(n)
        for div, suf in ((1e9, 'B'), (1e6, 'M'), (1e3, 'K')):
            if n >= div:
                return f'{n / div:.1f}{suf}'
        return str(int(n))

    def set_stats_dict(self, data: dict):
        """
Called *by MainWindow* once per second with the JSON data
already–loaded from bot_gui.  Copy into self.overall/self.stars,
then refresh the widgets.
"""
        self.overall['gold'] = data.get('gold', 0)
        self.overall['elixir'] = data.get('elixir', 0)
        self.overall['de'] = data.get('de', 0)
        self.overall['attacks'] = data.get('attacks', 0)
        self.stars.clear()
        for star_str, count in data.get('stars', {}).items():
            try:
                i = int(star_str)
                self.stars[i] = count
            except ValueError:
                pass
        self._refresh_all()

    def _create_village_tab(self, idx: int):
        tab = QWidget()
        grid = QGridLayout(tab)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        labelF = QFont('Segoe UI', 11, QFont.Bold)
        numF = QFont('Segoe UI', 12, QFont.Bold)
        colour = '#EFE2BA'
        keys = ['gold', 'elixir', 'de', 'attacks', 'session']
        self.per_village[idx]['session_start'] = time.time()
        self.per_village[idx]['labels'] = {}
        row = 0
        for k in ['Gold', 'Elixir', 'Dark Elixir', 'Attacks', 'Session Duration']:
            l = QLabel(k + ':'); l.setFont(labelF); l.setStyleSheet('color:#FFFFFF;')
            v = QLabel('0'); v.setFont(numF); v.setStyleSheet('color:#FFFFFF;')
            grid.addWidget(l, row, 0)
            grid.addWidget(v, row, 1, alignment=Qt.AlignRight)
            self.per_village[idx]['labels'][k] = v
            row += 1
        line = QFrame(); line.setFrameShape(QFrame.HLine); line.setStyleSheet('color:#666;')
        grid.addWidget(line, row, 0, 1, 2)
        row += 1
        for k in ['Avg Gold/hr', 'Avg Elixir/hr', 'Avg DE/hr']:
            l = QLabel(k + ':')
            l.setFont(labelF)
            l.setStyleSheet('color:#FFFFFF;')
            v = QLabel('0')
            v.setFont(numF)
            v.setStyleSheet('color:#FFFFFF;')
            grid.addWidget(l, row, 0)
            grid.addWidget(v, row, 1, alignment=Qt.AlignRight)
            self.per_village[idx]['labels'][k] = v
            row += 1
        self.tab_vill.addTab(tab, f'Village {idx}')

    def _refresh_village_tab(self, idx: int):
        data = self.per_village[idx]
        labels = data['labels']
        labels['Gold'].setText(f'{data['gold']:,}')
        labels['Elixir'].setText(f'{data['elixir']:,}')
        labels['Dark Elixir'].setText(f'{data['de']:,}')
        labels['Attacks'].setText(str(data['attacks']))
        elapsed = max(1, int(time.time() - data.get('session_start', time.time())))
        labels['Session Duration'].setText(self._fmt_secs(elapsed))
        hours = elapsed / 3600 or 0.0002777777777777778
        labels['Avg Gold/hr'].setText(f'{int(data['gold'] / hours):,}')
        labels['Avg Elixir/hr'].setText(f'{int(data['elixir'] / hours):,}')
        labels['Avg DE/hr'].setText(f'{int(data['de'] / hours):,}')
        att = max(1, data['attacks'])

    @staticmethod
    def _fmt_secs(s: int) -> str:
        h, rem = divmod(s, 3600)
        m, s = divmod(rem, 60)
        return f'{h} h {m:02d} m {s:02d} s'
