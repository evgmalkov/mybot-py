"""Движок совместимости со стратегиями MyBot-MBR (формат CSV).

Позволяет запускать чужие MBR-стратегии (`CSV/Attack/*.csv`) на нашей механике
БЕЗ переделок: пользователь кладёт .csv в папку `strategies/`, выбирает её в GUI.

Что поддержано из формата MBR:
  • секции NOTE / SIDE / SIDEB / MAKE / DROP / WAIT (разделитель «|»);
  • MAKE — именованные векторы высадки (сторона + число точек + сдвиг тайлов);
  • DROP — шаги высадки (вектор(ы), индексы точек, количество, имя войска,
    диапазоны задержек DELAY_DROP / SLEEPAFTER в мс);
  • WAIT — пауза (мс);
  • справочник имён войск/заклов/героев MBR → наши табы (см. NAME_MAP);
  • относительные стороны FRONT/BACK/LEFT/RIGHT → физические полурёбра алмаза
    через ту же таблицу алиасов, что и у MBR (__apply_mainside_aliases).

Геометрия: redline MBR (динамический контур зоны высадки) заменён честной
СТАТИЧЕСКОЙ аппроксимацией «алмаза» базы для 1600×900 (константы APEX_* ниже —
их можно подстроить под свою базу). Точность высадки — «на правильном ребре»,
не пиксель-в-пиксель к MBR.

Неподдержанные войска (нет иконки/таба у нас) — логируются и пропускаются;
по мере добавления шаблонов войск покрытие растёт.
"""
from __future__ import annotations
import json
import os
import re
import time
import random

from paths import BASE_DIR

STRATEGIES_DIR = os.path.join(BASE_DIR, 'strategies')

# ───────────────────── изометрия поля + параметры высадки ─────────────────────
# Точки десанта строятся на изосетке поля (vision/isometric.py): позиции на КОНТУРЕ поля в
# ТАЙЛОВЫХ координатах (deploy_point) → масштабируются с зумом/разрешением (модель как у MBR,
# ConvertToVillagePos). Сетка — config/field_iso.json; MBR-параметры — config/mbr_csv.json.
from isometric import IsoGrid

_MBR_DEFAULTS = {'base_margin': 1.5, 'addtiles_dir': -1, 'debug_overlay': False,
                 'use_calibration': False, 'min_confidence': 0.6, 'max_reproj_px': 8.0}


def _load_json(rel_path: str) -> dict:
    """Прочитать JSON из корня проекта. Никогда не бросает."""
    try:
        with open(os.path.join(BASE_DIR, rel_path), encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f'[MBR-CSV] config load failed ({rel_path}): {e}')
        return {}


def _load_grid() -> IsoGrid:
    """Изосетка поля из config/field_iso.json (diamond/matrix); дефолт — под 1600×900."""
    data = _load_json('config/field_iso.json')
    if data:
        try:
            return IsoGrid.from_dict(data)
        except Exception as e:
            print(f'[MBR-CSV] field_iso.json invalid: {e} — using default diamond')
    return IsoGrid.from_diamond(origin=(800, 40), half_w=17.4, half_h=7.9)


_MBR = dict(_MBR_DEFAULTS)
_MBR.update({k: v for k, v in _load_json('config/mbr_csv.json').items() if k in _MBR_DEFAULTS})
BASE_MARGIN = float(_MBR['base_margin'])       # тайлов наружу от края поля (базовый отступ линии)
ADDTILES_DIR = int(_MBR['addtiles_dir'])       # знак ADDTILES из CSV (-1 = отрицательный → наружу)
DEBUG_OVERLAY = bool(_MBR['debug_overlay'])
USE_CALIBRATION = bool(_MBR['use_calibration'])  # динамическая геометрия из redline (см. config)
CALIB_MIN_CONF = float(_MBR['min_confidence'])
CALIB_MAX_REPROJ = float(_MBR['max_reproj_px'])
GRID = _load_grid()


# 8 полурёбер MBR → (грань изосетки, t_start, t_end) вдоль контура поля 44×44.
# Грани изосетки и их направление t (0→1 = апекс→апекс):
#   top:    (0,0)→(43,0)   [TOP→RIGHT]      left:  (0,0)→(0,43)  [TOP→LEFT]
#   right:  (43,0)→(43,43) [RIGHT→BOTTOM]   bottom:(0,43)→(43,43)[LEFT→BOTTOM]
_EDGE_MAP = {
    'TOP-RIGHT-UP':      ('top',    0.0, 0.5),
    'TOP-RIGHT-DOWN':    ('top',    0.5, 1.0),
    'TOP-LEFT-UP':       ('left',   0.5, 0.0),
    'TOP-LEFT-DOWN':     ('left',   1.0, 0.5),
    'BOTTOM-LEFT-UP':    ('bottom', 0.0, 0.5),
    'BOTTOM-LEFT-DOWN':  ('bottom', 0.5, 1.0),
    'BOTTOM-RIGHT-UP':   ('right',  0.5, 0.0),
    'BOTTOM-RIGHT-DOWN': ('right',  1.0, 0.5),
}

# ───────────────────── таблица алиасов сторон (как в MBR ParseAttackCSV) ─────────────────────
# MAINSIDE (какое ребро атакуем) → перевод относительных CSV-имён в физические полурёбра.
_MAINSIDE_ALIASES = {
    'BOTTOM-RIGHT': {
        'FRONT-LEFT': 'BOTTOM-RIGHT-DOWN', 'FRONT-RIGHT': 'BOTTOM-RIGHT-UP',
        'RIGHT-FRONT': 'TOP-RIGHT-DOWN', 'RIGHT-BACK': 'TOP-RIGHT-UP',
        'LEFT-FRONT': 'BOTTOM-LEFT-DOWN', 'LEFT-BACK': 'BOTTOM-LEFT-UP',
        'BACK-LEFT': 'TOP-LEFT-DOWN', 'BACK-RIGHT': 'TOP-LEFT-UP',
    },
    'BOTTOM-LEFT': {
        'FRONT-LEFT': 'BOTTOM-LEFT-UP', 'FRONT-RIGHT': 'BOTTOM-LEFT-DOWN',
        'RIGHT-FRONT': 'BOTTOM-RIGHT-DOWN', 'RIGHT-BACK': 'BOTTOM-RIGHT-UP',
        'LEFT-FRONT': 'TOP-LEFT-DOWN', 'LEFT-BACK': 'TOP-LEFT-UP',
        'BACK-LEFT': 'TOP-RIGHT-UP', 'BACK-RIGHT': 'TOP-RIGHT-DOWN',
    },
    'TOP-LEFT': {
        'FRONT-LEFT': 'TOP-LEFT-UP', 'FRONT-RIGHT': 'TOP-LEFT-DOWN',
        'RIGHT-FRONT': 'BOTTOM-LEFT-UP', 'RIGHT-BACK': 'BOTTOM-LEFT-DOWN',
        'LEFT-FRONT': 'TOP-RIGHT-UP', 'LEFT-BACK': 'TOP-RIGHT-DOWN',
        'BACK-LEFT': 'BOTTOM-RIGHT-UP', 'BACK-RIGHT': 'BOTTOM-RIGHT-DOWN',
    },
    'TOP-RIGHT': {
        'FRONT-LEFT': 'TOP-RIGHT-DOWN', 'FRONT-RIGHT': 'TOP-RIGHT-UP',
        'RIGHT-FRONT': 'TOP-LEFT-UP', 'RIGHT-BACK': 'TOP-LEFT-DOWN',
        'LEFT-FRONT': 'BOTTOM-RIGHT-UP', 'LEFT-BACK': 'BOTTOM-RIGHT-DOWN',
        'BACK-LEFT': 'BOTTOM-LEFT-DOWN', 'BACK-RIGHT': 'BOTTOM-LEFT-UP',
    },
}
# BOTTOM-LEFT/RIGHT из CSV трактуем как FRONT-LEFT/RIGHT (нижние рёбра).
_SIDE_SYNONYMS = {'BOTTOM-LEFT': 'FRONT-LEFT', 'BOTTOM-RIGHT': 'FRONT-RIGHT'}

MAINSIDES = ('BOTTOM-LEFT', 'BOTTOM-RIGHT', 'TOP-LEFT', 'TOP-RIGHT')


def _resolve_side(csv_side: str, mainside: str) -> str | None:
    """CSV-имя стороны (относительное) → физическое полуребро при данном MAINSIDE."""
    s = csv_side.strip().upper()
    s = _SIDE_SYNONYMS.get(s, s)
    if s == 'RANDOM':
        return random.choice(list(_HALF_EDGES))
    return _MAINSIDE_ALIASES.get(mainside, {}).get(s)


def make_points(csv_side: str, qty: int, addtiles: int, mainside: str,
                rx: int = 0, ry: int = 0, grid: IsoGrid | None = None):
    """Точки десанта вдоль полуребра поля (изосетка, как MBR MakeDropPoints).

    Позиции берутся на КОНТУРЕ поля в тайлах: side + t∈[t0,t1] → deploy_point. ADDTILES из CSV
    трактуем как сдвиг линии высадки наружу/внутрь в ТАЙЛАХ (margin), rx/ry — джиттер в пикселях.
    grid — калиброванная изосетка из redline (иначе статическая GRID)."""
    g = grid or GRID
    phys = _resolve_side(csv_side, mainside)
    if phys is None or phys not in _EDGE_MAP:
        return []
    side, t0, t1 = _EDGE_MAP[phys]
    qty = max(1, int(qty))
    margin = BASE_MARGIN + ADDTILES_DIR * int(addtiles or 0)   # тайлов наружу от края поля
    if margin < 0.2:
        margin = 0.2
    pts = []
    for i in range(qty):
        t = t0 if qty == 1 else t0 + (t1 - t0) * (i / (qty - 1))
        px, py = g.deploy_point(side, t, margin=margin)
        jx = random.randint(-abs(rx), abs(rx)) if rx else 0
        jy = random.randint(-abs(ry), abs(ry)) if ry else 0
        pts.append((int(px) + jx, int(py) + jy))
    return pts


# ───────────────────── справочник имён MBR → наши табы ─────────────────────
# Ключи — как в MBR (регистр игнорируем). Значение — наш tab-ключ из attacks.TABS,
# спец-значение 'REMAIN' (добить остатки) или None (нет у нас → пропустить+лог).
NAME_MAP = {
    # войска, что у нас есть
    'ball': 'balloon', 'balloon': 'balloon',
    'edrag': 'e_drag',
    'drag': 'dragon', 'sdrag': 'dragon', 'gdrag': 'dragon', 'babyd': 'dragon',
    # осадные машины / подкреп — все в наш единый siege
    'wallw': 'siege_machine', 'battleb': 'siege_machine', 'stones': 'siege_machine',
    'siegeb': 'siege_machine', 'logl': 'siege_machine',
    # герои
    'king': 'bk', 'queen': 'queen', 'warden': 'warden', 'rc': 'rc',
    'champion': 'rc', 'prince': 'prince', 'duke': 'duke',
    # заклинания, что у нас есть
    'rspell': 'rage', 'fspell': 'freeze',
    # добить остатки
    'remain': 'REMAIN',
    # ── неподдержанные (нет иконки/таба) → None: пропустить с логом ──
    'castle': None, 'tspell': None, 'haspell': None, 'espell': None,
    'heal': None, 'hspell': None, 'jspell': None, 'lspell': None,
    'pspell': None, 'cspell': None, 'skspell': None, 'btspell': None,
    'anys': None, 'arch': None, 'barb': None, 'wiza': None, 'bowl': None,
    'giant': None, 'valk': None, 'hogs': None, 'mini': None, 'lava': None,
    'pekk': None, 'witc': None, 'gobl': None, 'gole': None, 'mine': None,
    'iceh': None, 'iceg': None, 'smini': None, 'swall': None, 'skyw': None,
    'throw': None, 'meteorg': None, 'wall': None,
}


def _troop_key(mbr_name: str):
    """MBR-имя войска → (наш tab-ключ | 'REMAIN' | None). None = пропустить."""
    return NAME_MAP.get(mbr_name.strip().lower(), None)


# ───────────────────── парсер CSV ─────────────────────
def _cells(line: str):
    """Разбить строку MBR-CSV на ячейки по «|», обрезать хвостовой «,,,»-мусор."""
    line = line.rstrip('\r\n')
    # хвостовые пустые CSV-колонки (,,,) и обрамляющие пробелы/кавычки
    if '|' not in line:
        return []
    parts = line.split('|')
    return [p.strip().strip('"').strip() for p in parts]


def _parse_range_ms(text: str, default=(0, 0)):
    """«50-70» → (50, 70) мс; «100» → (100, 100); пусто → default."""
    text = (text or '').strip()
    if not text:
        return default
    m = re.match(r'^(\d+)\s*-\s*(\d+)$', text)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    if text.isdigit():
        return (int(text), int(text))
    return default


def _expand_indices(text: str):
    """«5,3,1» → [5,3,1]; «1-7» → [1..7]; «6,1» → [6,1]."""
    out = []
    for tok in (text or '').split(','):
        tok = tok.strip()
        if not tok:
            continue
        m = re.match(r'^(\d+)\s*-\s*(\d+)$', tok)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            out.extend(range(a, b + 1) if a <= b else range(a, b - 1, -1))
        elif tok.isdigit():
            out.append(int(tok))
    return out


def _expand_vectors(text: str):
    """«A» → [A]; «A-B» → [A,B]; «E-F» → [E,F]; «A-B» многобуквенно по алфавиту."""
    text = (text or '').strip().upper()
    if '-' in text:
        a, b = [t.strip() for t in text.split('-', 1)]
        if len(a) == 1 and len(b) == 1 and a.isalpha() and b.isalpha():
            lo, hi = ord(a), ord(b)
            return [chr(c) for c in range(lo, hi + 1)] if lo <= hi else [a, b]
    return [text] if text else []


class MBRStrategy:
    """Разобранная MBR-стратегия: notes + MAKE-векторы (сырьё) + DROP/WAIT-шаги."""

    def __init__(self, path: str):
        self.path = path
        self.name = os.path.splitext(os.path.basename(path))[0]
        self.notes = []
        self.makes = []   # список dict: name, side, points, addtiles, versus, rx, ry
        self.steps = []   # список ('DROP', {...}) / ('WAIT', (lo,hi))
        self._parse()

    def _parse(self):
        with open(self.path, 'r', encoding='utf-8', errors='ignore') as fh:
            for raw in fh:
                c = _cells(raw)
                if not c:
                    continue
                cmd = c[0].strip().upper()
                if cmd == 'NOTE':
                    self.notes.append('|'.join(c[1:]).strip(' ,|'))
                elif cmd == 'MAKE' and len(c) >= 6:
                    self.makes.append({
                        'name': c[1].strip().upper(),
                        'side': c[2].strip().upper(),
                        'points': _int(c[3], 10),
                        'addtiles': _int(c[4], 0),
                        'versus': c[5].strip().upper() or 'INT-EXT',
                        'rx': _int(c[6] if len(c) > 6 else '0', 0),
                        'ry': _int(c[7] if len(c) > 7 else '0', 0),
                    })
                elif cmd == 'DROP' and len(c) >= 5:
                    self.steps.append(('DROP', {
                        'vectors': c[1], 'index': c[2], 'qty': _int(c[3], 1),
                        'troop': c[4].strip(),
                        'delay': _parse_range_ms(c[5] if len(c) > 5 else ''),
                        'sleep_after': _parse_range_ms(c[7] if len(c) > 7 else ''),
                    }))
                elif cmd == 'WAIT':
                    self.steps.append(('WAIT', _parse_range_ms(c[1] if len(c) > 1 else '')))


def _int(text, default):
    try:
        return int(str(text).strip())
    except (ValueError, TypeError):
        return default


def list_strategies():
    """Список доступных .csv-стратегий из strategies/ (имена без расширения)."""
    if not os.path.isdir(STRATEGIES_DIR):
        return []
    return sorted(os.path.splitext(f)[0] for f in os.listdir(STRATEGIES_DIR)
                  if f.lower().endswith('.csv'))


def strategy_path(name: str):
    return os.path.join(STRATEGIES_DIR, name + '.csv')


def _grab_bgr():
    """Свежий кадр экрана как BGR ndarray (или None). capture_array УЖЕ возвращает BGR
    (см. screenshot_utils) — НЕ конвертировать (иначе R↔B, красное→синее, маска пуста)."""
    try:
        import cv2
        from screenshot_utils import capture_array
    except Exception:
        return None
    img = capture_array()
    if img is None:
        return None
    if img.ndim == 3 and img.shape[2] == 4:      # защитно: BGRA → BGR (не RGBA)
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return img                                    # уже BGR


def _calibrate_field_grid():
    """Динамическая изосетка поля 44×44 из detected redline (calibration gate).

    None → калибровка не удалась → CSV не исполнять (no-fallback). Углы поля ↔ апексы redline:
    (0,0)=TOP, (43,0)=RIGHT, (0,43)=LEFT, (43,43)=BOTTOM (см. _EDGE_MAP)."""
    try:
        import deploy_boundary as db          # noqa: F401 (через mbr_calibration)
        import mbr_calibration as mc
    except Exception as e:
        print(f'[MBR-CSV] calibration deps missing: {e}')
        return None
    # retry: несколько кадров за ~3с (redline может дорисоваться на пару кадров позже входа)
    grid_ref, res = None, None
    for attempt in range(5):
        img = _grab_bgr()
        if img is None:
            time.sleep(0.6)
            continue
        grid_ref, res = mc.calibrate_frame(img, min_confidence=CALIB_MIN_CONF,
                                           max_reproj_px=CALIB_MAX_REPROJ)
        if grid_ref is not None:
            break
        time.sleep(0.6)
    if grid_ref is None:
        conf = getattr(res, 'confidence', 0.0) if res is not None else 0.0
        reason = res.reason if res is not None else 'no screenshot'
        print(f'[MBR-CSV] redline calibration FAILED (detected={getattr(res, "detected", False)} '
              f'conf={conf:.2f} {reason}) — CSV NOT executed (no fallback)')
        return None
    top, rgt, bot, lft = res.polygon
    field = IsoGrid.from_correspondences(
        [(0, 0, *top), (43, 0, *rgt), (0, 43, *lft), (43, 43, *bot)], cols=44, rows=44)
    print(f'[MBR-CSV] redline calibrated (conf={res.confidence:.2f}) → dynamic field grid')
    return field


def _save_debug_overlay(vectors, mainside, grid=None):
    """Наложить на кадр боя контур поля (изосетка) + точки высадки → PNG для калибровки геометрии."""
    try:
        import cv2
        import numpy as np
        from screenshot_utils import capture_array
    except Exception as e:
        print(f'[MBR-CSV][debug] overlay deps missing: {e}')
        return
    try:
        img = capture_array()
        if img is None:
            print('[MBR-CSV][debug] capture failed — no overlay')
            return
        img = np.ascontiguousarray(img)
        if img.ndim == 3 and img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        elif img.ndim == 3 and img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        # сбор ЧИСТОГО кадра базы в датасет ground-truth (для разработки detect_base)
        try:
            ds = os.path.join(BASE_DIR, 'debug_mbr')
            if os.path.isdir(ds):
                n = sum(1 for f in os.listdir(ds) if f.startswith('collect_') and f.endswith('.png'))
                clean = os.path.join(ds, f'collect_{n + 1:03d}.png')
                cv2.imwrite(clean, img)
                print(f'[MBR-CSV][debug] clean frame -> {clean}')
        except Exception:
            pass
        # контур поля 44×44 по апексам изосетки — жёлтый (калиброванный grid, иначе статический)
        g = grid or GRID
        corners = [g.to_px_int(0, 0), g.to_px_int(43, 0),
                   g.to_px_int(43, 43), g.to_px_int(0, 43)]
        cv2.polylines(img, [np.array(corners, np.int32)], True, (0, 255, 255), 2)
        # точки всех векторов — красные, подпись имени — зелёная
        for name, pts in vectors.items():
            for (px, py) in pts:
                cv2.circle(img, (int(px), int(py)), 6, (0, 0, 255), -1)
            if pts:
                x0, y0 = pts[0]
                cv2.putText(img, name, (int(x0) + 6, int(y0) - 6),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        out = os.path.join(BASE_DIR, 'mbr_csv_debug.png')
        cv2.imwrite(out, img)
        print(f'[MBR-CSV][debug] overlay saved -> {out} (MAINSIDE={mainside})')
    except Exception as e:
        print(f'[MBR-CSV][debug] overlay failed: {e}')


def _save_selected_frame(attacks):
    """M2-A: тапнуть карточку войска → red area (граница высадки) проявляется ярко → снять кадр.
    Именно так detector должен получать вход (как MBR: select troop → redline виден)."""
    try:
        import cv2
        from screenshot_utils import capture_array
        ds = os.path.join(BASE_DIR, 'debug_mbr')
        os.makedirs(ds, exist_ok=True)
        n = sum(1 for f in os.listdir(ds) if f.startswith('sel_') and f.endswith('.png'))
        if n >= 40:
            return
        tab = None
        for k in ('balloon', 'dragon', 'e_drag', 'siege_machine'):
            if attacks.TABS.get(k):
                tab = attacks.TABS[k]
                break
        if tab is None:
            for v in attacks.TABS.values():
                if v:
                    tab = v
                    break
        if not tab:
            return
        attacks.run_adb(["shell", "input", "tap", str(tab[0]), str(tab[1])])
        time.sleep(0.5)
        img = capture_array()
        if img is None:
            return
        if img.ndim == 3 and img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        elif img.ndim == 3 and img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        out = os.path.join(ds, f'sel_{n + 1:03d}.png')
        cv2.imwrite(out, img)
        print(f'[MBR-CSV][debug] selected-troop frame -> {out}')
    except Exception as e:
        print(f'[MBR-CSV][debug] selected frame failed: {e}')


def _save_battle_frame():
    """M2-A: снять кадр УЖЕ ИДУЩЕГО боя (после первого деплоя) → debug_mbr/battle_NNN.png.
    В бою redline (граница высадки) чёткий — нужен для разработки DeployAreaDetector."""
    try:
        import cv2
        from screenshot_utils import capture_array
        ds = os.path.join(BASE_DIR, 'debug_mbr')
        os.makedirs(ds, exist_ok=True)
        n = sum(1 for f in os.listdir(ds) if f.startswith('battle_') and f.endswith('.png'))
        if n >= 40:
            return                                   # достаточно боевых кадров
        img = capture_array()
        if img is None:
            return
        if img.ndim == 3 and img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        elif img.ndim == 3 and img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        out = os.path.join(ds, f'battle_{n + 1:03d}.png')
        cv2.imwrite(out, img)
        print(f'[MBR-CSV][debug] battle frame -> {out}')
    except Exception as e:
        print(f'[MBR-CSV][debug] battle frame failed: {e}')


# ───────────────────── исполнитель ─────────────────────
def run_csv_attack(csv_path: str, cfg: dict | None = None):
    """Загрузить MBR-CSV и выполнить её на нашей механике."""
    from attacks import attacks  # подмодуль attacks.attacks (не namespace-пакет); лениво — от циклов

    strat = MBRStrategy(csv_path)
    mainside = random.choice(MAINSIDES)
    # Явные маркеры для живой валидации: runtime реально пошёл по CSV-пути (не fallback),
    # и однозначная привязка выбранной стратегии (UI ↔ runtime).
    print("\n=== MBR-CSV attack started ===")
    print(f"[MBR-CSV] attack = csv:{strat.name}")
    print(f"==== MBR-CSV «{strat.name}» | MAINSIDE={mainside} ====")
    for n in strat.notes:
        if n:
            print(f"   note: {n}")

    # 1) найти табы войск (подтверждает экран атаки) + человекоподобная пауза «осмотр базы» (#3/#6).
    #    К этому моменту вид атаки устаканился и redline ОТРИСОВАН (как в дракон-хуке) — только
    #    ПОСЛЕ этого калибруем, иначе ловим кадр загрузки/зума (redline ещё нет → B=0).
    attacks.TABS = attacks.update_tabs()
    pre = (cfg or {}).get('pre_attack_delay', (2.5, 6.0))
    attacks.human_delay(pre[0], pre[1])

    # 2) динамическая геометрия из redline (флаг use_calibration). Нет достоверного redline →
    #    CSV НЕ исполняется (no-fallback: иначе координаты стратегии лягут в чужую систему).
    field_grid = None
    if USE_CALIBRATION:
        field_grid = _calibrate_field_grid()
        if field_grid is None:
            print('=== MBR-CSV attack aborted (no reliable redline) ===')
            return

    # 3) построить именованные векторы (name → список точек) в калиброванной геометрии
    vectors = {}
    for mk in strat.makes:
        vectors[mk['name']] = make_points(mk['side'], mk['points'], mk['addtiles'],
                                          mainside, mk['rx'], mk['ry'], grid=field_grid)
    if DEBUG_OVERLAY:
        _save_debug_overlay(vectors, mainside, grid=field_grid)   # контур + точки (калиброванный grid)
        _save_selected_frame(attacks)               # M2-A: кадр с выбранным войском

    # 4) исполнить шаги
    _drop_count = 0
    _battle_snapped = False
    try:
        for kind, data in strat.steps:
            attacks._ensure_active()        # бой прерван/Stop? — прекращаем стратегию
            if kind == 'WAIT':
                lo, hi = data
                secs = random.uniform(lo, hi) / 1000.0
                print(f"   WAIT {secs:.2f}s")
                time.sleep(secs)
                continue
            _run_drop(attacks, data, vectors)
            # M2-A: после нескольких деплоев бой ТОЧНО идёт → redline чёткий (первый шаг часто SKIP).
            _drop_count += 1
            if DEBUG_OVERLAY and not _battle_snapped and _drop_count >= 4:
                _battle_snapped = True
                _save_battle_frame()
    except attacks._AttackAborted as e:
        # Пользователь прервал бой → НЕ тапаем дальше; наверх (one_cycle) — проверка
        # «бой закончен / мы на базе».
        print(f"[ABORT] MBR-CSV stopped — {e}; skipping remaining taps & speed-up")
        return
    except Exception as e:
        import traceback
        print(f"[WARN] MBR-CSV step error, continuing: {e}")
        traceback.print_exc()

    # 5) добить/ускорить как обычно
    attacks.speed_up()
    print("\n=== MBR-CSV attack finished ===")


def _run_drop(attacks, data, vectors):
    troop = data['troop']
    key = _troop_key(troop)
    if key is None:
        print(f"   [SKIP] «{troop}» — not supported (no tab/icon)")
        return
    if key == 'REMAIN':
        print("   REMAIN → deploy remaining troops")
        attacks.deploy_all_remaining()
        return
    tab = attacks.TABS.get(key)
    if not tab:
        print(f"   [SKIP] «{troop}»→{key}: tab not found on screen")
        return

    # собрать точки: по всем указанным векторам и индексам
    idx = _expand_indices(data['index']) or [1]
    pts = []
    for vname in _expand_vectors(data['vectors']):
        vpts = vectors.get(vname, [])
        for i in idx:
            if 1 <= i <= len(vpts):
                pts.append(vpts[i - 1])
    if not pts:
        print(f"   [SKIP] «{troop}»: no valid points (vec={data['vectors']} idx={data['index']})")
        return

    qty = max(1, data['qty'])
    lo, hi = data['delay']
    print(f"   DROP {troop}→{key} x{qty} on {len(pts)} pt(s).")
    attacks._ensure_active()                     # бой прерван? — не тапаем
    attacks.run_adb(["shell", "input", "tap", *map(str, tab)])
    time.sleep(0.3)
    # последовательность точек высадки; шлём БАТЧАМИ (быстро), между чанками —
    # проверка боя + пауза из CSV (если задана). Если задержка CSV нулевая — чистый батч.
    seq = [pts[n % len(pts)] for n in range(qty)]
    chunk = attacks.DEPLOY_CHUNK
    for i in range(0, len(seq), chunk):
        attacks._ensure_active()
        attacks.run_adb_taps(seq[i:i + chunk])
        if hi > 0:
            time.sleep(random.uniform(lo, hi) / 1000.0)
    if key in attacks._HERO_KEYS:                # герой высажен → можно мониторить/жать
        attacks._deployed_at[key] = time.time()
    slo, shi = data['sleep_after']
    if shi > 0:
        time.sleep(random.uniform(slo, shi) / 1000.0)
