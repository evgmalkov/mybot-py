"""MBR Coordinate Calibration — мост reference-координат MBR → текущий экран боя.

Милстоун-2 (переформулирован): цель не «идеально найти красную линию», а получить ТРАНСФОРМ

    MBR reference (860×780)  ──H──▶  текущий экран (1600×900)

Красная deploy-граница (detect_deploy_boundary) = КАЛИБРАТОР: её 4 апекса (TOP/RIGHT/BOTTOM/LEFT)
соответствуют 4 апексам OuterDiamond в reference-пространстве MBR (mbr_reference.json). По ним
решаем АФФИННОЕ преобразование reference→screen (изопроекция параллельна → аффинное корректнее и
устойчивее к шуму вершин, чем homography). Дальше любую CSV-точку (в reference) переводим на экран.

Контракт: нет достоверного redline (detect_deploy_boundary.detected=False или низкая confidence) →
калибровка НЕ строится, CSV-атака пропускается. Никакого fallback на статические координаты.

Пайплайн:
    screenshot → detect_deploy_boundary → 4 apex → calibrate_from_redline → IsoGrid(ref→screen)
              → csv_to_screen(grid, csv_pt) → тап.
"""
from __future__ import annotations

import cv2
import numpy as np

import mbr_geometry as mg
from isometric import IsoGrid
import deploy_boundary as db


def calibrate_from_redline(polygon, ref: dict | None = None) -> IsoGrid:
    """4 апекса detected redline [TOP,RIGHT,BOTTOM,LEFT] (экран) → IsoGrid reference→screen.

    polygon — из DeployBoundaryResult.polygon. Соответствия: reference OuterDiamond апексы ↔
    экранные апексы. "Тайл" IsoGrid = reference-координата (0..860 × 0..780)."""
    ref = ref or mg.load_reference()
    ro = mg.reference_outer_apexes(ref)                 # {'left','right','top','bottom'} в reference
    top, right, bottom, left = polygon
    pairs = [
        (ro['top'][0],    ro['top'][1],    top[0],    top[1]),
        (ro['right'][0],  ro['right'][1],  right[0],  right[1]),
        (ro['bottom'][0], ro['bottom'][1], bottom[0], bottom[1]),
        (ro['left'][0],   ro['left'][1],   left[0],   left[1]),
    ]
    return IsoGrid.from_correspondences(pairs, cols=ref['reference']['width'],
                                        rows=ref['reference']['height'])


def csv_to_screen(grid: IsoGrid, x_ref, y_ref):
    """Reference-координата MBR (x,y) → пиксель экрана (int,int)."""
    return grid.to_px_int(x_ref, y_ref)


def calibrate_frame(img, min_confidence=0.6, max_reproj_px=8.0, ref: dict | None = None):
    """Полный вход: кадр → (IsoGrid | None, DeployBoundaryResult). None (CSV НЕ пускать), если
    redline недостоверен (detected/confidence) ИЛИ аффинный фит по 4 апексам плохой (reproj велик —
    признак кривой детекции: перекошенный/раздутый ромб). Никакого fallback на статику."""
    ref = ref or mg.load_reference()
    res = db.detect_deploy_boundary(img)
    if not res.detected or res.confidence < min_confidence:
        return None, res
    grid = calibrate_from_redline(res.polygon, ref)
    if reprojection_error(grid, res.polygon, ref) > max_reproj_px:
        return None, res
    return grid, res


def reprojection_error(grid: IsoGrid, polygon, ref: dict | None = None) -> float:
    """Round-trip: reference outer апексы через grid → пиксель, ошибка vs detected polygon (px, RMS).
    Малое значение = аффинная модель хорошо описывает 4 соответствия (sanity, НЕ конечный DoD)."""
    ref = ref or mg.load_reference()
    ro = mg.reference_outer_apexes(ref)
    top, right, bottom, left = polygon
    errs = []
    for key, scr in (('top', top), ('right', right), ('bottom', bottom), ('left', left)):
        px, py = grid.to_px(*ro[key])
        errs.append((px - scr[0]) ** 2 + (py - scr[1]) ** 2)
    return float(np.sqrt(np.mean(errs)))


def render_overlay(img, grid: IsoGrid, res: db.DeployBoundaryResult,
                   csv_points=None, ref: dict | None = None):
    """Диагностика: detected redline + reference OUTER апексы (round-trip) + reference INNER-ромб +
    решётка reference-точек + опц. CSV DROP-точки — всё через grid на текущем экране."""
    ref = ref or mg.load_reference()
    vis = img.copy()
    # detected redline (красный) + вершины
    if res.polygon:
        cv2.polylines(vis, [np.array(res.polygon, np.int32)], True, (0, 0, 255), 2)
    # reference OUTER апексы через grid (зелёные) — должны лечь на углы redline (round-trip)
    ro = mg.reference_outer_apexes(ref)
    for k in ('top', 'right', 'bottom', 'left'):
        x, y = grid.to_px_int(*ro[k])
        cv2.circle(vis, (x, y), 9, (0, 255, 0), 2)
    # reference INNER-ромб через grid (голубой) — должен обнять СТРУКТУРУ базы
    ri = mg.reference_inner_apexes(ref)
    inner = [grid.to_px_int(*ri[k]) for k in ('top', 'right', 'bottom', 'left')]
    cv2.polylines(vis, [np.array(inner, np.int32)], True, (255, 255, 0), 2)
    # решётка reference-точек (тускло) — визуальная проверка равномерности переноса
    W, Hh = ref['reference']['width'], ref['reference']['height']
    for gx in range(0, W + 1, W // 8):
        for gy in range(0, Hh + 1, Hh // 8):
            x, y = grid.to_px_int(gx, gy)
            cv2.circle(vis, (x, y), 2, (180, 180, 180), -1)
    # CSV DROP-точки (жёлтые)
    for (cx, cy) in (csv_points or []):
        x, y = grid.to_px_int(cx, cy)
        cv2.circle(vis, (x, y), 6, (0, 255, 255), -1)
    cv2.putText(vis, f'calib conf={res.confidence:.2f} reproj={reprojection_error(grid, res.polygon, ref):.1f}px',
                (250, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
    return vis
