"""Лёгкое распознавание чисел фиксированного шрифта CoC матчингом шаблонов цифр.

Замена easyocr для ЧИСЛОВЫХ чтений (ресурсы/лут/счётчики): CoC рисует числа
фиксированным растровым шрифтом (белые глифы с тёмным контуром), поэтому пошаблонный
матчинг цифр точнее универсального OCR и в разы легче — без torch (~0 доп. RAM/потоков
против ~450 МБ и ~50 потоков easyocr).

Шаблоны: Templates/digits/<d>_<k>.png — мульти-сэмпл бинарные маски цифр 0-9.
Матчер: изолируем белое (min-канал), режем на глифы по колоночной проекции, каждый
глиф нормализуем в канвас 22x20 и сравниваем с сэмплами (nearest-neighbour).
"""
import os
import glob
import cv2
import numpy as np
from paths import TEMPLATES_DIR

_CH, _CW = 22, 20
_SAMPLES = None


def _canvas(mask):
    """Бинарный глиф → нормализованный канвас 22x20 (высота по аспекту, центр по ширине)."""
    ys, xs = np.where(mask > 0)
    if len(ys) == 0:
        return None
    m = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    w = min(_CW, max(1, round(m.shape[1] * _CH / m.shape[0])))
    m = cv2.resize(m, (w, _CH), interpolation=cv2.INTER_NEAREST)
    out = np.zeros((_CH, _CW), np.float32)
    x0 = (_CW - w) // 2
    out[:, x0:x0 + w] = (m > 0)
    return out


def _load_samples():
    global _SAMPLES
    if _SAMPLES is None:
        _SAMPLES = []
        d = os.path.join(str(TEMPLATES_DIR), 'digits')
        for path in glob.glob(os.path.join(d, '*.png')):
            try:
                n = int(os.path.basename(path).split('_')[0].split('.')[0])
            except ValueError:
                continue
            c = _canvas(cv2.imread(path, cv2.IMREAD_GRAYSCALE))
            if c is not None:
                _SAMPLES.append((n, c))
    return _SAMPLES


def _segment(roi_bgr, thr=200):
    # thr высокий: цифры — чистый белый (~225+), серая заливка ресурс-бара (~150-190)
    # отсекается. Фильтр высоты — ОТНОСИТЕЛЬНЫЙ (по медиане глифов): адаптируется к
    # любому масштабу шрифта (HUD ~19px, экран результата ~27px), отсекая выбросы
    # (полоса бара, иконки, пунктуация).
    white = (roi_bgr.min(axis=2) > thr).astype('uint8') * 255
    cols = (white > 0).sum(axis=0) > 0
    segs, s = [], None
    for i, v in enumerate(cols):
        if v and s is None:
            s = i
        if (not v) and s is not None:
            segs.append((s, i)); s = None
    if s is not None:
        segs.append((s, len(cols)))
    boxes = []
    for a, b in segs:
        if b - a < 3:
            continue
        gl = white[:, a:b]
        ys = np.where(gl.max(axis=1) > 0)[0]
        if not len(ys):
            continue
        h = ys.max() - ys.min() + 1
        if h < 8:
            continue
        boxes.append((gl[ys.min():ys.max() + 1], h))
    if not boxes:
        return []
    med = sorted(h for _, h in boxes)[len(boxes) // 2]
    return [g for g, h in boxes if 0.6 * med <= h <= 1.4 * med]


def _match(glyph):
    c = _canvas(glyph)
    if c is None:
        return None, -1.0
    best, bs = None, -1.0
    for n, t in _load_samples():
        sc = 1.0 - float(np.abs(c - t).mean())
        if sc > bs:
            bs, best = sc, n
    return best, bs


_SLASH = None


def _slash():
    global _SLASH
    if _SLASH is None:
        p = os.path.join(str(TEMPLATES_DIR), 'digits', 'slash.png')
        m = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
        _SLASH = _canvas(m) if m is not None else None
    return _SLASH


def _components(roi_bgr, thr=150):
    # Компонентная сегментация (для дробей): '/' обычно склеивается с соседями при
    # колоночной проекции, а как связная компонента отделяется. Медианный фильтр
    # высоты убирает мусор (края иконок).
    white = (roi_bgr.min(axis=2) > thr).astype('uint8')
    n, lab, st, _c = cv2.connectedComponentsWithStats(white, connectivity=8)
    out = []
    for i in range(1, n):
        x, y, w, h, area = st[i]
        if area < 12 or h < 7:
            continue
        out.append((x, h, ((lab[y:y + h, x:x + w] == i) * 255).astype('uint8')))
    out.sort()
    if not out:
        return []
    med = sorted(h for _, h, _ in out)[len(out) // 2]
    return [m for _, h, m in out if 0.6 * med <= h <= 1.4 * med]


def read_fraction(roi_bgr, thr=150):
    """Прочитать «N/M» → (N, M) или (None, None). Разделитель '/' — по шаблону slash."""
    slash = _slash()
    toks = []
    for m in _components(roi_bgr, thr):
        c = _canvas(m)
        if c is None:
            continue
        dn, dsc = None, -1.0
        for n, t in _load_samples():
            sc = 1.0 - float(np.abs(c - t).mean())
            if sc > dsc:
                dsc, dn = sc, n
        ssc = 1.0 - float(np.abs(c - slash).mean()) if slash is not None else -1.0
        toks.append('/' if ssc > dsc else str(dn))
    s = ''.join(toks)
    if '/' not in s:
        return (None, None)
    a, b = s.split('/', 1)
    return (int(a) if a.isdigit() else None, int(b) if b.isdigit() else None)


def read_int(roi_bgr, thr=200, min_score=0.70):
    """Целое из ROI с белыми цифрами; None если сегментов нет или уверенность низкая."""
    digits = []
    for gl in _segment(roi_bgr, thr):
        d, sc = _match(gl)
        if d is None or sc < min_score:
            return None
        digits.append(str(d))
    if not digits:
        return None
    return int(''.join(digits))
