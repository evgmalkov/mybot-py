"""DeployBoundaryDetector — детект КРАСНОЙ границы высадки как выпуклого четырёхугольника.

Подход (проверен на реальном кадре): deploy boundary = красная (пунктирная) четырёхугольная линия
вокруг базы. Внутри — forbidden, снаружи — deployable. Зелёный цвет НЕ источник истины.

Алгоритм:
    red mask → HoughLinesP (длинные сегменты) → LINE SUPPORT (доля красных пикселей вдоль линии;
    настоящий redline ~0.96–0.99, ложные от построек ~0.75) → фильтр support+length → dedupe →
    ПЕРЕБОР комбинаций 4 линий → выпуклый quadrilateral → 4 пересечения → polygon [TL,TR,BR,BL].
Центр — из пересечений, не из медианы. Никакого green/static-diamond.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import cv2
import numpy as np

_UI_ZONES = [(0, 0, 240, 270), (1330, 0, 1600, 240), (600, 0, 1010, 120),
             (1300, 600, 1600, 900), (0, 700, 1600, 900)]


@dataclass
class Line:
    x1: int; y1: int; x2: int; y2: int
    angle: float; length: float; support: float


@dataclass
class DeployBoundaryResult:
    detected: bool
    confidence: float = 0.0
    polygon: list = field(default_factory=list)   # [TOP, RIGHT, BOTTOM, LEFT] = [[x,y]*4]
    lines: list = field(default_factory=list)     # выбранные Line (внешняя пара ×2 семейства)
    candidates: list = field(default_factory=list)  # все прошедшие фильтр Hough-линии (для overlay)
    raw_red: object = None
    line_mask: object = None
    reason: str = ''


def _red_mask(img):
    b, g, r = cv2.split(img.astype(int))
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    hue, sat, val = hsv[:, :, 0].astype(int), hsv[:, :, 1].astype(int), hsv[:, :, 2].astype(int)
    # СПЕЦИФИЧНО к redline (оранжево-красный hue), БЕЗ золота стен (hue~22-30). Иначе support
    # перестаёт различать redline (~0.96) и стены (~0.75).
    m = (((hue <= 19) | (hue >= 168)) & (sat > 95) & (val > 100) &
         (r - g > 26) & (r - b > 42)).astype(np.uint8) * 255
    for (x0, y0, x1, y1) in _UI_ZONES:
        m[y0:y1, x0:x1] = 0
    return m


def _support(x1, y1, x2, y2, red_dil):
    """Доля красных пикселей вдоль отрезка (сэмплинг)."""
    n = max(2, int(np.hypot(x2 - x1, y2 - y1)))
    xs = np.linspace(x1, x2, n).astype(int).clip(0, red_dil.shape[1] - 1)
    ys = np.linspace(y1, y2, n).astype(int).clip(0, red_dil.shape[0] - 1)
    return float((red_dil[ys, xs] > 0).mean())


def _line_params(ln: Line):
    """Линия через 2 точки → (a,b,c): a*x+b*y+c=0, нормировано."""
    a, b = ln.y2 - ln.y1, ln.x1 - ln.x2
    c = -(a * ln.x1 + b * ln.y1)
    n = np.hypot(a, b) or 1.0
    return a / n, b / n, c / n


def _intersect(p, q):
    a1, b1, c1 = p; a2, b2, c2 = q
    d = a1 * b2 - a2 * b1
    if abs(d) < 1e-6:
        return None
    return [(b1 * c2 - b2 * c1) / d, (a2 * c1 - a1 * c2) / d]


def _order_apexes(pts):
    """4 вершины изо-ромба → [TOP, RIGHT, BOTTOM, LEFT] по УГЛУ вокруг centroid.

    Не по sum/diff(x,y): у ромба TOP около y≈0 (у края кадра) — sum(x+y) путает TOP и LEFT.
    Циклический порядок по углу устойчив; затем ротируем, чтобы стартовать с верхней (min y)."""
    P = np.array(pts, float)
    cx, cy = P.mean(0)
    ang = np.arctan2(P[:, 1] - cy, P[:, 0] - cx)
    order = np.argsort(ang)                        # по часовой в экранных коорд. (y вниз)
    P = P[order]
    top_i = int(np.argmin(P[:, 1]))                # старт с верхней вершины
    P = np.roll(P, -top_i, axis=0)
    # гарантируем порядок TOP→RIGHT→BOTTOM→LEFT (следующая после TOP — с большим x)
    if P[1][0] < P[-1][0]:
        P = P[[0, 3, 2, 1]]
    return [p.tolist() for p in P]


def _is_convex(poly):
    p = np.array(poly, float); n = len(p); sign = 0
    for i in range(n):
        a, bb, cc = p[i], p[(i + 1) % n], p[(i + 2) % n]
        e1, e2 = bb - a, cc - bb
        cr = float(e1[0] * e2[1] - e1[1] * e2[0])
        if abs(cr) < 1e-6:
            continue
        s = 1 if cr > 0 else -1
        if sign == 0:
            sign = s
        elif s != sign:
            return False
    return True


def _abc(ln: Line):
    """Нормированная прямая (a,b,c) с КОНСИСТЕНТНЫМ знаком (b>=0) — чтобы c был сравним внутри
    семейства параллельных линий (signed perpendicular offset)."""
    a, b, c = _line_params(ln)
    if b < 0 or (abs(b) < 1e-9 and a < 0):
        a, b, c = -a, -b, -c
    return a, b, c


def _outer_pair(fam, min_sep):
    """В семействе ~параллельных линий выбрать ВНЕШНЮЮ пару = крайние по signed-offset c
    (min и max). Требуем разнос >= min_sep (граница шире внутренних стен). Возвращает [lo,hi] или None."""
    if len(fam) < 2:
        return None
    fam = sorted(fam, key=lambda ln: _abc(ln)[2])
    lo, hi = fam[0], fam[-1]
    if _abc(hi)[2] - _abc(lo)[2] < min_sep:
        return None
    return [lo, hi]


def _prep_family(fam, cgap=22.0, topk=16):
    """Подготовить семейство к перебору: dedup близких по c (оставить сильнейшую по support·len),
    затем top-K по support·len (ограничить число комбинаций). Границы обычно среди сильнейших."""
    fam = sorted(fam, key=lambda l: _abc(l)[2])
    dedup = []
    for l in fam:
        if dedup and _abc(l)[2] - _abc(dedup[-1])[2] < cgap:
            if l.support * l.length > dedup[-1].support * dedup[-1].length:
                dedup[-1] = l
        else:
            dedup.append(l)
    dedup.sort(key=lambda l: -l.support * l.length)
    return dedup[:topk]


def detect_deploy_boundary(img, expected_angle=37.0, ang_tol=8.0, min_len=120,
                           min_support=0.85, wh_target=1.321, wh_tol=0.13,
                           apex_margin_px=140) -> DeployBoundaryResult:
    """Красная deploy-граница как изо-ромб: Hough-линии → ДВА семейства (±expected_angle) →
    ВНЕШНЯЯ пара в каждом → 4 пересечения → апексы TOP/RIGHT/BOTTOM/LEFT.

    Угол изо-проекции CoC фиксирован (~±37°), потому семейства задаются заранее — не свободный
    четырёхугольник. Внутренние стены дают те же углы, но лежат ВНУТРИ (c между крайними) →
    берём крайние (внешние) линии. expected_angle можно взять из наклона DRAGON_R."""
    H, W = img.shape[:2]
    red = _red_mask(img)
    red_dil = cv2.dilate(red, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    hl = cv2.HoughLinesP(red, 1, np.pi / 180, threshold=45, minLineLength=min_len, maxLineGap=40)
    if hl is None:
        return DeployBoundaryResult(False, raw_red=red, reason='no lines')

    all_lines, famA, famB = [], [], []
    for x1, y1, x2, y2 in np.asarray(hl).reshape(-1, 4):
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        L = float(np.hypot(x2 - x1, y2 - y1))
        if L < min_len:
            continue
        sup = _support(x1, y1, x2, y2, red_dil)
        if sup < min_support:
            continue
        ang = float(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
        ang = ((ang + 90.0) % 180.0) - 90.0                # → (-90, 90]
        ln = Line(x1, y1, x2, y2, ang, L, sup)
        all_lines.append(ln)
        if abs(ang - expected_angle) <= ang_tol:
            famA.append(ln)                                # +expected (напр. рёбра TR / BL)
        elif abs(ang + expected_angle) <= ang_tol:
            famB.append(ln)                                # -expected (рёбра TL / BR)

    famA, famB = _prep_family(famA), _prep_family(famB)
    if len(famA) < 2 or len(famB) < 2:
        return DeployBoundaryResult(False, raw_red=red, lines=all_lines, candidates=all_lines,
                                    reason=f'families incomplete (A={len(famA)} B={len(famB)})')

    # Geometry-scored выбор: перебор пар в каждом семействе → 4 пересечения → ромб. Держим ТОЛЬКО
    # ромбы с правильным аспектом W/H≈wh_target (жёсткий изо-инвариант: reference OuterDiamond
    # 856/648≈1.32, подобие сохраняет отношение). Песок/декор дают неверный аспект → отсев.
    #
    # SELECTION POLICY (важно): deploy boundary — ВНЕШНЯЯ граница. Раньше выбирали ромб с МАКС.
    # support сторон — но это выбирает наиболее насыщенные красным линии, т.е. ВНУТРЕННИЕ СТЕНЫ
    # (стены дают тот же ±угол и высокий support), а не внешнюю границу. Extreme-c в _outer_pair
    # тоже не гарантирует внешность: ложные Hough-линии от декора могут иметь offset дальше redline.
    # Настоящая внешность определяется ЗАМКНУТОЙ ГЕОМЕТРИЕЙ: среди валидных ромбов с вершинами
    # В КАДРЕ берём САМЫЙ ВНЕШНИЙ (макс. площадь). Но чистая max-area переоценивает: если за
    # redline существует линия того же угла (грунт/декор/баннер «cannot deploy»), она даёт чуть
    # больший ромб и «перехлёстывает» настоящую границу. Ключ — OUTER SCORE = area · min_support²:
    # площадь тянет наружу, а слабый support рёбер (спорная внешняя линия ~0.85 vs настоящий
    # redline ~0.97) гасит перехлёст. Проверено на 2 якорях: decorated-outer и hug-без-overshoot.
    # Лексикографика: (outer_score, min_support, mean_support, -aspect_error).
    # Вершина вне кадра (напр. TOP y<0) — сильный сигнал, что найден не тот quadrilateral → отсев.
    best = None                                  # (key_tuple, [lines], poly, area, sups)
    for a1, a2 in itertools.combinations(famA, 2):
        pa1, pa2 = _line_params(a1), _line_params(a2)
        for b1, b2 in itertools.combinations(famB, 2):
            pb1, pb2 = _line_params(b1), _line_params(b2)
            verts = [_intersect(p, q) for p in (pa1, pa2) for q in (pb1, pb2)]
            if any(v is None for v in verts):
                continue
            # non-finite пересечения (почти параллельные линии) → отсев
            if any((not np.isfinite(v[0])) or (not np.isfinite(v[1])) for v in verts):
                continue
            poly = _order_apexes(verts)
            top, rgt, bot, lft = poly
            w, h = rgt[0] - lft[0], bot[1] - top[1]
            if w < 300 or h < 200:
                continue
            wh = w / h
            if abs(wh - wh_target) > wh_tol or not _is_convex(poly):
                continue
            # Вершины ромба: TOP/BOTTOM у max-зума базы ЛЕГИТИМНО за кадром (истинные пересечения
            # линий границы), поэтому НЕ требуем строго в кадре — допускаем поле apex_margin_px за
            # краями. Это калибровочный контракт (off-screen апексы нужны). Но раздутый/перекошенный
            # ромб уходит ДАЛЕКО за кадр → margin отсекает его, не трогая реальную границу.
            m = apex_margin_px
            if not all(-m <= x < W + m and -m <= y < H + m for x, y in poly):
                continue
            area = cv2.contourArea(np.array(poly, np.float32))
            if not (0.10 * W * H <= area <= 0.85 * W * H):
                continue
            sups = [a1.support, a2.support, b1.support, b2.support]
            # ПЕРВИЧНО — outer score (площадь, гашённая слабым support рёбер), далее качество линий
            outer_score = area * (min(sups) ** 2)
            key = (outer_score, min(sups), sum(sups) / 4.0, -abs(wh - wh_target))
            if best is None or key > best[0]:
                best = (key, [a1, a2, b1, b2], poly, area, sups)
    if best is None:
        return DeployBoundaryResult(False, raw_red=red, lines=all_lines, candidates=all_lines,
                                    reason='no valid in-frame diamond (aspect/geometry)')

    _, selected, poly, _, _ = best
    sups = [l.support for l in selected]
    conf = float(min(1.0, 0.6 * min(sups) + 0.4 * np.mean(sups)))
    return DeployBoundaryResult(True, confidence=conf, polygon=[[int(x), int(y)] for x, y in poly],
                                lines=selected, candidates=all_lines, raw_red=red, line_mask=red_dil, reason='ok')


def render_overlay(img, res: DeployBoundaryResult):
    vis = img.copy()
    if res.raw_red is not None:
        red3 = cv2.cvtColor(res.raw_red, cv2.COLOR_GRAY2BGR)
        vis = cv2.addWeighted(vis, 1.0, (red3 * np.array([0, 1, 1], np.uint8)), 0.5, 0)
    # все кандидаты — тускло-серые (видно, что Hough нашёл и что отбраковано)
    for ln in res.candidates:
        cv2.line(vis, (ln.x1, ln.y1), (ln.x2, ln.y2), (120, 120, 120), 1, cv2.LINE_AA)
    # выбранные 4 стороны — ярко-жёлтые + подпись angle/support/c
    for ln in res.lines:
        cv2.line(vis, (ln.x1, ln.y1), (ln.x2, ln.y2), (0, 255, 255), 2, cv2.LINE_AA)
        _, _, c = _abc(ln)
        cv2.putText(vis, f'{ln.angle:+.0f} s={ln.support:.2f} c={c:.0f}',
                    ((ln.x1 + ln.x2) // 2, (ln.y1 + ln.y2) // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
    if res.detected and res.polygon:
        pts = np.array(res.polygon, np.int32)
        cv2.polylines(vis, [pts], True, (0, 0, 255), 3)
        for i, (x, y) in enumerate(res.polygon):
            cv2.circle(vis, (x, y), 8, (0, 255, 0), -1)
            cv2.putText(vis, f"{['TOP', 'RIGHT', 'BOTTOM', 'LEFT'][i]} ({x},{y})", (x + 10, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.putText(vis, f'detected={res.detected} conf={res.confidence:.2f} {res.reason}',
                (250, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
    return vis
