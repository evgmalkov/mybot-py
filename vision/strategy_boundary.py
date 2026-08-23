"""StrategyGuidedBoundaryDetector — уточнение линии высадки по PRIOR из стратегии.

Идея (в отличие от deploy_boundary.py, который ищет весь четырёхугольник): для НАТИВНЫХ атак
у нас уже есть приблизительная линия высадки — hardcoded точки стратегии (attacks.DRAGON_L/R,
одно ребро ромба на сторону). Задача узкая: найти РЕАЛЬНУЮ красную deploy-границу рядом с prior
и уточнить её положение. Это проще и надёжнее, чем детект всей базы.

Сигнал: красная deploy-граница = UI-оверлей игры (см. память mbr-csv-geometry), тема-независим по
цвету. Ярче всего в pre/ранней-deploy фазе. Метод:
    fade-guard (отсев выцветших transition-кадров)
      → redline-маска (оранжево-красный, без золота стен)
      → коридор ±R вокруг prior-линии
      → RANSAC прямой ПАРАЛЛЕЛЬНО prior (длинное ребро = крупнейший коллинеарный набор)
      → среди кандидатов берём ВНЕШНЮЮ (боундари снаружи внутренних стен) с покрытием сегмента
      → offset (перпендикуляр fitted↔prior) + confidence.

Контракт: при недостоверном детекте detected=False (БЕЗ silent fallback — правило проекта).
Для НАТИВНОЙ атаки вызывающий код может откатиться на статические DRAGON_L/R (у них есть
безопасный дефолт); для CSV — строгий скип. Сам этот модуль fallback НЕ делает.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

_UI_ZONES = [(0, 0, 240, 270), (1330, 0, 1600, 240), (600, 0, 1010, 120),
             (1300, 600, 1600, 900), (0, 700, 1600, 900)]


@dataclass
class StrategyEdge:
    """Уточнённое ребро высадки для одной стороны."""
    detected: bool
    confidence: float = 0.0
    offset: float = 0.0                 # перпендикуляр fitted↔prior (px); <0 = наружу от базы
    line: tuple | None = None           # (a,b,c) нормированной прямой a*x+b*y+c=0
    p1: tuple | None = None             # концы fitted-сегмента [x,y]
    p2: tuple | None = None
    support: float = 0.0                # доля красного вдоль fitted-сегмента
    span: float = 0.0                   # покрытие сегмента инлайерами [0..1]
    reason: str = ''


def _red_mask(img):
    """Redline-маска: оранжево-красный (hue≈0/180), R доминирует; золото стен (hue~22-30) исключено."""
    b, g, r = cv2.split(img.astype(int))
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    hue, sat, val = hsv[:, :, 0].astype(int), hsv[:, :, 1].astype(int), hsv[:, :, 2].astype(int)
    m = (((hue <= 19) | (hue >= 168)) & (sat > 95) & (val > 100) &
         (r - g > 26) & (r - b > 42)).astype(np.uint8) * 255
    for (x0, y0, x1, y1) in _UI_ZONES:
        m[y0:y1, x0:x1] = 0
    return m


def is_fade_frame(img, v_hi=190, s_lo=60) -> bool:
    """Выцветший transition-кадр (fade-in при входе в атаку): очень светлый и малонасыщенный.
    На таких цвета ненадёжны → детект пропускаем."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    return bool(hsv[:, :, 2].mean() > v_hi and hsv[:, :, 1].mean() < s_lo)


def _prior_line(points):
    """Prior-точки одного ребра → нормированная прямая (a,b,c) + концы сегмента."""
    P = np.array(points, float)
    k, bb = np.polyfit(P[:, 0], P[:, 1], 1)
    a, b, c = k, -1.0, bb
    n = math.hypot(a, b)
    return a / n, b / n, c / n, P[0], P[-1]


def refine_edge(img, prior_points, red=None, red_dil=None, radius=110, min_len=110,
                max_ang_diff=7.0, min_support=0.80, min_out_span=0.45) -> StrategyEdge:
    """Уточнить ОДНО ребро высадки рядом с prior_points через Hough-линии в коридоре.

    Логика: deploy-граница = длинная красная линия СНАРУЖИ внутренних стен. В коридоре ±radius
    вокруг prior берём Hough-сегменты, ~параллельные prior, с высоким support (доля красного вдоль),
    и выбираем САМЫЙ ВНЕШНИЙ (минимальный offset — дальше от базы). Стены дают такие же линии, но
    ВНУТРИ; декор/шум — короткие (отсекаются min_len). red/red_dil — предвыч. маски."""
    H, W = img.shape[:2]
    if red is None:
        red = _red_mask(img)
    if red_dil is None:
        red_dil = cv2.dilate(red, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    a0, b0, c0, p1, p2 = _prior_line(prior_points)
    prior_ang = math.degrees(math.atan2(p2[1] - p1[1], p2[0] - p1[0]))
    # маска коридора: |dist до prior| <= radius и в пределах охвата сегмента (+поле)
    yy, xx = np.indices((H, W))
    d = np.abs(a0 * xx + b0 * yy + c0)
    xlo, xhi = min(p1[0], p2[0]) - 40, max(p1[0], p2[0]) + 40
    ylo, yhi = min(p1[1], p2[1]) - 40, max(p1[1], p2[1]) + 40
    corr = ((d <= radius) & (xx >= xlo) & (xx <= xhi) & (yy >= ylo) & (yy <= yhi)).astype(np.uint8)
    red_c = cv2.bitwise_and(red, red, mask=corr)
    hl = cv2.HoughLinesP(red_c, 1, np.pi / 180, threshold=40, minLineLength=min_len, maxLineGap=35)
    if hl is None:
        return StrategyEdge(False, reason='no hough lines in corridor')
    dirx, diry = -b0, a0
    cands = []
    for x1, y1, x2, y2 in hl.reshape(-1, 4):
        ang = math.degrees(math.atan2(y2 - y1, x2 - x1))
        da = abs(((ang - prior_ang + 90) % 180) - 90)
        if da > max_ang_diff:                              # только ~параллельно prior
            continue
        sup = _support((x1, y1), (x2, y2), red_dil)
        if sup < min_support:
            continue
        # прямая сегмента → offset относительно prior + проекция концов prior
        na, nb = (y2 - y1), (x1 - x2)
        nn = math.hypot(na, nb) or 1.0
        na, nb = na / nn, nb / nn
        nc = -(na * x1 + nb * y1)
        # ориентируем нормаль как у prior (a0,b0), offset = значение prior-нормали на середине сег.
        mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        offset = a0 * mx + b0 * my + c0
        length = math.hypot(x2 - x1, y2 - y1)
        cands.append((offset, sup, length, (na, nb, nc)))
    if not cands:
        return StrategyEdge(False, reason='no parallel red line (support/len)')
    # САМАЯ ВНЕШНЯЯ линия (min offset) среди длинных — это граница (стены остаются внутри).
    best = min(cands, key=lambda c: c[0])
    offset, sup, length, (na, nb, nc) = best
    qa, qb, qc = _norm(na, nb, nc)
    q1 = _project(p1, qa, qb, qc); q2 = _project(p2, qa, qb, qc)
    span = length / max(1.0, math.hypot(p2[0] - p1[0], p2[1] - p1[1]))
    detected = sup >= min_support and span >= min_out_span
    conf = float(min(1.0, 0.6 * sup + 0.4 * min(1.0, span)))
    return StrategyEdge(detected, conf, float(offset), (qa, qb, qc),
                        [float(q1[0]), float(q1[1])], [float(q2[0]), float(q2[1])],
                        float(sup), float(span),
                        'ok' if detected else f'weak (sup={sup:.2f} span={span:.2f})')


def _norm(a, b, c):
    n = math.hypot(a, b) or 1.0
    return a / n, b / n, c / n


def _project(pt, a, b, c):
    """Проекция точки на прямую a*x+b*y+c=0 (нормированную)."""
    x, y = pt
    dd = a * x + b * y + c
    return [x - a * dd, y - b * dd]


def _support(q1, q2, red_dil):
    n = max(2, int(math.hypot(q2[0] - q1[0], q2[1] - q1[1])))
    xs = np.linspace(q1[0], q2[0], n).astype(int).clip(0, red_dil.shape[1] - 1)
    ys = np.linspace(q1[1], q2[1], n).astype(int).clip(0, red_dil.shape[0] - 1)
    return float((red_dil[ys, xs] > 0).mean())


def detect(img, prior_points, **kw) -> StrategyEdge:
    """Публичный вход: fade-guard + refine_edge для одной стороны (prior_points = DRAGON_L или R)."""
    if is_fade_frame(img):
        return StrategyEdge(False, reason='fade/transition frame')
    return refine_edge(img, prior_points, **kw)


def generate_drop_points(edge: StrategyEdge, count=12, out_offset=0.0):
    """Точки высадки вдоль уточнённого ребра (edge.p1..p2), опц. сдвиг наружу на out_offset px."""
    if not edge.detected or edge.p1 is None:
        return None
    p1, p2 = np.array(edge.p1, float), np.array(edge.p2, float)
    a, b, _ = edge.line
    pts = np.linspace(p1, p2, count) - np.array([a, b]) * out_offset   # (a,b) — внешняя нормаль
    return [(int(round(x)), int(round(y))) for x, y in pts]


def render_overlay(img, prior_points, edge: StrategyEdge, color=(255, 0, 0)):
    vis = img.copy()
    red = _red_mask(img)
    vis[red > 0] = (0, 255, 255)
    a0, b0, c0, p1, p2 = _prior_line(prior_points)
    cv2.line(vis, tuple(map(int, p1)), tuple(map(int, p2)), (0, 0, 255), 1)   # prior — красный
    if edge.p1 and edge.p2:
        cv2.line(vis, tuple(map(int, edge.p1)), tuple(map(int, edge.p2)), color, 2)
    cv2.putText(vis, f'det={edge.detected} conf={edge.confidence:.2f} off={edge.offset:+.0f} '
                f'sup={edge.support:.2f} cov={edge.span:.2f} {edge.reason}',
                (250, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    return vis
