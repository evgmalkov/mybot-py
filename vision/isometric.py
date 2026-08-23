"""Изометрическая проекция игрового поля (тайл ↔ пиксель).

Поле CoC (и подобных base-builder игр) нарисовано ромбом-изометрией: клетка сетки (col, row)
ложится на экран по диагоналям. Этот модуль — ЧИСТАЯ ГЕОМЕТРИЯ (реализована с нуля из математики
аффинного преобразования, без чужого кода): адресация построек/стен по сетке, центр клетки,
точки десанта по контуру. Параметры проекции — ДАННЫЕ профиля (``games/<key>/iso.json``),
поэтому ядро остаётся разрешение-независимым.

Модель — общий аффинный переход (origin + масштаб + поворот + скос):
    px = a·col + b·row + e
    py = d·col + f·row + g
Частный «ромб» (``from_diamond``): +col идёт вправо-вниз, +row — влево-вниз:
    px = origin_x + (col − row)·half_w
    py = origin_y + (col + row)·half_h

Калибровка вживую: снять кадр, отметить пиксели ≥3 известных клеток → ``from_correspondences``.
"""
from dataclasses import dataclass, field


@dataclass
class IsoGrid:
    """Аффинная изосетка. ``m`` = (a, b, e, d, f, g) — прямой переход тайл→пиксель."""
    m: tuple
    cols: int = 44
    rows: int = 44

    # --- прямое/обратное преобразование ---
    def to_px(self, col, row):
        """Тайл (col, row) → пиксель (x, y) как float (центр клетки)."""
        a, b, e, d, f, g = self.m
        return (a * col + b * row + e, d * col + f * row + g)

    def to_px_int(self, col, row):
        """То же, но округлённый (x, y) — под тап/рисование."""
        x, y = self.to_px(col, row)
        return (int(round(x)), int(round(y)))

    def to_tile(self, px, py):
        """Пиксель (x, y) → тайл (col, row) как float (обратное преобразование)."""
        a, b, e, d, f, g = self.m
        det = a * f - b * d
        if abs(det) < 1e-9:
            raise ValueError("degenerate iso grid (det≈0): пересними калибровку")
        dx, dy = px - e, py - g
        col = (f * dx - b * dy) / det
        row = (-d * dx + a * dy) / det
        return (col, row)

    def to_tile_round(self, px, py):
        """Пиксель → ближайшая целочисленная клетка (col, row)."""
        col, row = self.to_tile(px, py)
        return (int(round(col)), int(round(row)))

    # --- служебное ---
    def in_bounds(self, col, row):
        """Клетка внутри игрового поля [0, cols) × [0, rows)?"""
        return 0 <= col < self.cols and 0 <= row < self.rows

    def clamp(self, col, row):
        """Прижать клетку к границам поля."""
        return (min(max(col, 0), self.cols - 1), min(max(row, 0), self.rows - 1))

    def deploy_point(self, side, t, margin=1.0):
        """Точка десанта на КОНТУРЕ поля (снаружи на ``margin`` клеток).

        ``side`` — 'top'|'bottom'|'left'|'right' (грань ромба), ``t`` ∈ [0,1] — позиция вдоль грани.
        Возвращает пиксель (x, y). Полезно для раскладки войск по периметру базы.
        """
        c, r = self.cols - 1, self.rows - 1
        t = min(max(float(t), 0.0), 1.0)
        if side == "top":            # ребро (0,0)→(c,0), сдвиг наружу вверх (−row)
            col, row = t * c, -margin
        elif side == "bottom":       # ребро (0,r)→(c,r), наружу вниз
            col, row = t * c, r + margin
        elif side == "left":         # ребро (0,0)→(0,r), наружу влево (−col)
            col, row = -margin, t * r
        elif side == "right":        # ребро (c,0)→(c,r), наружу вправо
            col, row = c + margin, t * r
        else:
            raise ValueError(f"unknown side: {side!r}")
        return self.to_px_int(col, row)

    # --- сериализация (данные профиля) ---
    def to_dict(self):
        return {"cols": self.cols, "rows": self.rows, "matrix": list(self.m)}

    @classmethod
    def from_dict(cls, d):
        """Из iso.json: либо {'matrix':[6]}, либо {'diamond':{origin,half_w,half_h}}."""
        cols, rows = int(d.get("cols", 44)), int(d.get("rows", 44))
        if "matrix" in d:
            return cls(tuple(float(v) for v in d["matrix"]), cols, rows)
        dia = d["diamond"]
        return cls.from_diamond(dia["origin"], dia["half_w"], dia["half_h"], cols, rows)

    # --- конструкторы ---
    @classmethod
    def from_diamond(cls, origin, half_w, half_h, cols=44, rows=44):
        """Классический ромб: ``origin`` — пиксель клетки (0,0); half_w/half_h — полутайл по осям."""
        ox, oy = float(origin[0]), float(origin[1])
        hw, hh = float(half_w), float(half_h)
        # px = ox + (col−row)·hw ; py = oy + (col+row)·hh
        return cls((hw, -hw, ox, hh, hh, oy), cols, rows)

    @classmethod
    def from_correspondences(cls, pairs, cols=44, rows=44):
        """Решить аффинный переход по ≥3 соответствиям (col,row,px,py) методом наименьших квадратов.

        Так калибруют вживую: кликнуть пиксели нескольких известных клеток на реальном кадре.
        """
        import numpy as np
        if len(pairs) < 3:
            raise ValueError("нужно ≥3 соответствий (col,row,px,py) для калибровки")
        a_rows, bx, by = [], [], []
        for col, row, px, py in pairs:
            a_rows.append([col, row, 1.0])
            bx.append(px)
            by.append(py)
        a = np.asarray(a_rows, float)
        cx, *_ = np.linalg.lstsq(a, np.asarray(bx, float), rcond=None)   # a,b,e
        cy, *_ = np.linalg.lstsq(a, np.asarray(by, float), rcond=None)   # d,f,g
        m = (float(cx[0]), float(cx[1]), float(cx[2]),
             float(cy[0]), float(cy[1]), float(cy[2]))
        return cls(m, cols, rows)
