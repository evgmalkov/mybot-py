"""Измерение точности detect_base против ground-truth (measurement before declaration).

Гоняет detect_base() на кадрах из debug_mbr/ground_truth.json, считает ошибку по 4 вершинам
InnerDiamond (px), сохраняет overlay: GT (зелёный) + detected (красный) + подписи/ошибки.

Запуск:  py -3.13 scripts/mbr_detect_eval.py
DoD детектора: медианная per-vertex ошибка мала на НЕСКОЛЬКИХ разных базах; confidence адекватна;
при низкой уверенности detected=False (без silent fallback).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
for _l in ("core", "emu", "vision", "train", "villages", "ui"):
    sys.path.insert(0, os.path.join(HERE, _l))

import cv2
import numpy as np
import mbr_geometry as mg

DS = os.path.join(HERE, 'debug_mbr')
GT = os.path.join(DS, 'ground_truth.json')
APEXES = ('top', 'right', 'bottom', 'left')


def _poly(dia):
    return np.array([dia['top'], dia['right'], dia['bottom'], dia['left']], np.int32)


def main():
    if not os.path.exists(GT):
        print(f'нет ground_truth: {GT}')
        return 1
    with open(GT, encoding='utf-8') as f:
        frames = json.load(f).get('frames', [])
    if not frames:
        print('ground_truth пуст — соберите кадры (debug_mbr/collect_*.png) и разметьте')
        return 1

    print(f'{"frame":<16}{"detected":<10}{"conf":<7}{"vertex errors (px)":<32}{"mean":<7}')
    print('-' * 72)
    errs_all = []
    for fr in frames:
        path = os.path.join(DS, fr['file'])
        img = cv2.imread(path)
        if img is None:
            print(f'{fr["file"]:<16}NO IMAGE')
            continue
        gt = fr['inner_diamond']
        det = mg.detect_base(img)
        vis = img.copy()
        cv2.polylines(vis, [_poly(gt)], True, (0, 255, 0), 2)          # GT — зелёный
        line = f'{fr["file"]:<16}{str(det.detected):<10}{det.confidence:<7.2f}'
        if det.detected and det.diamond:
            cv2.polylines(vis, [_poly(det.diamond)], True, (0, 0, 255), 2)   # detected — красный
            evals = []
            for k in APEXES:
                dx = det.diamond[k][0] - gt[k][0]
                dy = det.diamond[k][1] - gt[k][1]
                evals.append((dx * dx + dy * dy) ** 0.5)
            errs_all.extend(evals)
            line += f'{" ".join(f"{k[0].upper()}{e:.0f}" for k, e in zip(APEXES, evals)):<32}{np.mean(evals):<7.1f}'
        else:
            line += f'{"(no detection)":<32}{"-":<7}'
        print(line)
        out = os.path.join(DS, os.path.splitext(fr['file'])[0] + '_eval.png')
        cv2.imwrite(out, vis)
    print('-' * 72)
    if errs_all:
        print(f'ИТОГ per-vertex: median={np.median(errs_all):.1f}px  mean={np.mean(errs_all):.1f}px  '
              f'max={np.max(errs_all):.1f}px  (n={len(errs_all)})')
    else:
        print('detect_base ещё не реализован (detected=False у всех) — это ожидаемо на текущем этапе.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
