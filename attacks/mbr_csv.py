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
import os
import re
import time
import random

from paths import BASE_DIR

STRATEGIES_DIR = os.path.join(BASE_DIR, 'strategies')

# ───────────────────── геометрия «алмаза» (1600×900, подстраиваемо) ─────────────────────
# 4 апекса ромба базы на экране (примерные значения; подстроить под свою базу).
APEX_TOP = (770, 25)
APEX_BOTTOM = (770, 710)
APEX_LEFT = (160, 368)
APEX_RIGHT = (1360, 368)
CENTER = ((APEX_LEFT[0] + APEX_RIGHT[0]) // 2, (APEX_TOP[1] + APEX_BOTTOM[1]) // 2)
TILE_PX = 24            # ~пикселей на «тайл» (для ADDTILES-сдвига линии высадки)
ADDTILES_OUTWARD = -1   # знак ADDTILES: отрицательный сдвиг = наружу от центра базы


def _mid(a, b):
    return ((a[0] + b[0]) // 2, (a[1] + b[1]) // 2)


# 8 физических полурёбер: имя → (начало, конец) отрезка вдоль периметра.
# Половина «-UP» ближе к верхнему апексу ребра, «-DOWN» — к нижнему/боковому.
_HALF_EDGES = {
    'TOP-LEFT-DOWN':     (APEX_LEFT,   _mid(APEX_LEFT, APEX_TOP)),
    'TOP-LEFT-UP':       (_mid(APEX_LEFT, APEX_TOP),   APEX_TOP),
    'TOP-RIGHT-UP':      (APEX_TOP,    _mid(APEX_TOP, APEX_RIGHT)),
    'TOP-RIGHT-DOWN':    (_mid(APEX_TOP, APEX_RIGHT),  APEX_RIGHT),
    'BOTTOM-LEFT-UP':    (APEX_LEFT,   _mid(APEX_LEFT, APEX_BOTTOM)),
    'BOTTOM-LEFT-DOWN':  (_mid(APEX_LEFT, APEX_BOTTOM), APEX_BOTTOM),
    'BOTTOM-RIGHT-DOWN': (APEX_BOTTOM, _mid(APEX_BOTTOM, APEX_RIGHT)),
    'BOTTOM-RIGHT-UP':   (_mid(APEX_BOTTOM, APEX_RIGHT), APEX_RIGHT),
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
                rx: int = 0, ry: int = 0):
    """Список экранных точек вдоль стороны (как MBR MakeDropPoints, упрощённо)."""
    phys = _resolve_side(csv_side, mainside)
    if phys is None or phys not in _HALF_EDGES:
        return []
    (x0, y0), (x1, y1) = _HALF_EDGES[phys]
    qty = max(1, int(qty))
    # перпендикулярный сдвиг линии высадки на addtiles тайлов (наружу/внутрь базы)
    ox = oy = 0
    if addtiles:
        midx, midy = (x0 + x1) / 2, (y0 + y1) / 2
        vx, vy = midx - CENTER[0], midy - CENTER[1]
        norm = (vx * vx + vy * vy) ** 0.5 or 1.0
        shift = ADDTILES_OUTWARD * int(addtiles) * TILE_PX
        ox, oy = vx / norm * shift, vy / norm * shift
    pts = []
    for i in range(qty):
        t = 0.5 if qty == 1 else i / (qty - 1)
        jx = random.randint(-abs(rx), abs(rx)) if rx else 0
        jy = random.randint(-abs(ry), abs(ry)) if ry else 0
        px = x0 + (x1 - x0) * t + ox + jx
        py = y0 + (y1 - y0) * t + oy + jy
        pts.append((int(px), int(py)))
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


# ───────────────────── исполнитель ─────────────────────
def run_csv_attack(csv_path: str, cfg: dict | None = None):
    """Загрузить MBR-CSV и выполнить её на нашей механике."""
    import attacks  # лениво, чтобы избежать циклического импорта

    strat = MBRStrategy(csv_path)
    mainside = random.choice(MAINSIDES)
    print(f"\n==== MBR-CSV «{strat.name}» | MAINSIDE={mainside} ====")
    for n in strat.notes:
        if n:
            print(f"   note: {n}")

    # 1) построить именованные векторы (name → список точек)
    vectors = {}
    for mk in strat.makes:
        vectors[mk['name']] = make_points(mk['side'], mk['points'], mk['addtiles'],
                                          mainside, mk['rx'], mk['ry'])

    # 2) найти табы войск на экране (переиспользуем логику атаки)
    attacks.TABS = attacks.update_tabs()

    # 3) человекоподобная пауза перед высадкой (#3/#6)
    pre = (cfg or {}).get('pre_attack_delay', (2.5, 6.0))
    attacks.human_delay(pre[0], pre[1])

    # 4) исполнить шаги
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
