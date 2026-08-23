"""Координатная модель MyBot-MBR для CSV-стратегий (reference-village → экран).

Воспроизводит модель MBR БЕЗ прямого масштабирования 1600/860. Цепочка:

    CSV-координата
        → reference-village 860×780 (config/mbr_reference.json)
        → village transform (аффинно, по детекту InnerDiamond на экране)
        → OuterDiamond = Inner + TH-отступы
        → MakeDropPoints
        → пиксели нашего экрана

`ConvertToVillagePos` у MBR — закрытый нативный DLL; здесь он воспроизводится аффинным
преобразованием reference→screen, решённым по соответствиям (детект InnerDiamond ↔ reference
InnerDiamond). Разрешение/зум в само преобразование CSV НЕ входят.

Этот модуль — ЧИСТАЯ ГЕОМЕТРИЯ + КОНТРАКТ детектора. Сам детектор базы (vision) — отдельный
primitive (`detect_base`), пока заглушка; трансформ тестируется с ручным InnerDiamond.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

from paths import BASE_DIR
from isometric import IsoGrid


# ───────────────────────── контракт detection-primitive ─────────────────────────
# Первый элемент будущего Core Vision SDK. Детектор базы ОБЯЗАН вернуть ровно это.
@dataclass
class BaseDetection:
    """Стандартизированный результат детекта базы на экране (attack view).

    detected — успех (False, если уверенность ниже порога → БЕЗ silent fallback на статику);
    confidence — уверенность [0..1]; center — пиксель центра базы; scale — пикс/reference-единица
    (диагностика); diamond — 4 апекса InnerDiamond В ПИКСЕЛЯХ экрана: {'left','right','top','bottom'},
    каждый = [x, y]. Эти 4 апекса — соответствия для аффинного village-transform.

    ЖЁСТКОЕ правило: при detected==False вызывающий код НЕ падает на статический field_iso —
    CSV-атака пропускается/прерывается с явным логом. Иначе старый костыль тихо вернётся в prod.
    """
    detected: bool
    confidence: float = 0.0
    center: tuple | None = None
    scale: float | None = None
    diamond: dict | None = None            # {'left':[x,y],'right':[x,y],'top':[x,y],'bottom':[x,y]}

    def to_dict(self) -> dict:
        return {'detected': self.detected, 'confidence': self.confidence, 'center': self.center,
                'scale': self.scale, 'diamond': self.diamond}


# ───────────────────────── reference-данные MBR (860×780) ─────────────────────────
def load_reference(path: str | None = None) -> dict:
    """config/mbr_reference.json → {reference:{width,height}, inner_diamond{...}, outer_adjust{...}}."""
    p = path or os.path.join(BASE_DIR, 'config', 'mbr_reference.json')
    with open(p, encoding='utf-8') as f:
        data = json.load(f)
    return data


def reference_inner_apexes(ref: dict) -> dict:
    """Апексы InnerDiamond в reference-пространстве 860×780: left/right/top/bottom = [x,y]."""
    d = ref['inner_diamond']
    midx = (d['left'] + d['right']) / 2.0
    midy = (d['top'] + d['bottom']) / 2.0
    return {
        'left':  [d['left'],  midy],
        'right': [d['right'], midy],
        'top':   [midx, d['top']],
        'bottom':[midx, d['bottom']],
    }


def reference_outer_apexes(ref: dict) -> dict:
    """OuterDiamond = Inner ± outer_adjust (в reference-пространстве). Апексы left/right/top/bottom."""
    d, a = ref['inner_diamond'], ref['outer_adjust']
    left, right = d['left'] - a['left'], d['right'] + a['right']
    top, bottom = d['top'] - a['top'], d['bottom'] + a['bottom']
    midx, midy = (left + right) / 2.0, (top + bottom) / 2.0
    return {
        'left':  [left,  midy], 'right': [right, midy],
        'top':   [midx, top],   'bottom':[midx, bottom],
    }


# ───────────────────────── village transform (reference → screen) ─────────────────────────
def solve_village_transform(inner_screen: dict, ref: dict) -> IsoGrid:
    """Аффинное reference→screen по 4 соответствиям InnerDiamond (reference-апекс ↔ screen-пиксель).

    inner_screen — детект: {'left':[x,y],'right':...,'top':...,'bottom':...} в пикселях экрана.
    Возвращает IsoGrid, где .to_px(ref_x, ref_y) даёт пиксель экрана для ЛЮБОЙ reference-координаты.
    Разрешение экрана в формулу не входит — только соответствия.
    """
    ref_ap = reference_inner_apexes(ref)
    pairs = []
    for key in ('left', 'right', 'top', 'bottom'):
        rx, ry = ref_ap[key]
        sx, sy = inner_screen[key]
        pairs.append((rx, ry, sx, sy))
    # IsoGrid.from_correspondences решает аффинную матрицу (тут «тайл» = reference-координата)
    return IsoGrid.from_correspondences(pairs, cols=ref['reference']['width'],
                                        rows=ref['reference']['height'])


# ───────────────────────── детектор базы (vision) — КОНТРАКТ/заглушка ─────────────────────────
def detect_base(img) -> BaseDetection:
    """Найти InnerDiamond базы на кадре attack view → BaseDetection (контракт выше).

    TODO (Stage 4): реализовать детект (по стенам/структуре/ECD, сценарио-независимо). Пока не
    реализован — трансформ и overlay валидируются с InnerDiamond, заданным вручную. Возвращаем
    detected=False, чтобы вызывающий код явно видел отсутствие детекта (без тихой деградации).
    """
    return BaseDetection(detected=False)
