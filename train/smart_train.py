"""smart_train.py – complete, folder-aware smart trainer

Folder layout under Templates/Smart_Auto_train:
    Army Troops/        -- dragon.png, balloon.png, …
    s_troops/           -- electro_dragon.png, …
    Spells/             -- rage.png, freeze.png, …
    Siege Machines/     -- slammer.png, blimp.png, …
    to_train/           -- same icons used when tab is open (dragon, electro_dragon, balloon, rage, freeze, slammer, trash_icon)

Usage:
    smart_train({"attack":"Dragon_Attack"})
    smart_train({"attack":"ElectroDragon_Attack"})

Validates current army troops, spells, and siege; retrains missing or incorrect items
using the COC Army window and ADB taps. Closes the Army tab upon success.
"""
import os, sys, time, cv2, subprocess
from typing import Tuple
import numpy as np
import main
from paths import BASE_DIR, DEBUG
TEMPLATE_ROOT = os.path.join(BASE_DIR, 'Templates', 'Smart_Auto_train')
PNG_EXT = '.png'
from screenshot_utils import take_screenshot
from adb_config import ADB_BIN
import digit_ocr
from unicode import imread_unicode
CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
ARMY_TROOPS_DIR = os.path.join(TEMPLATE_ROOT, 'Army Troops')
S_TROOPS_DIR = os.path.join(TEMPLATE_ROOT, 's_troops')
SIEGE_DIR = os.path.join(TEMPLATE_ROOT, 'Siege Machines')
SPELL_DIR = os.path.join(TEMPLATE_ROOT, 'Spells')


def tap(pt: Tuple[int, int]):
    """Tap screen coordinate (x,y) via ADB."""
    host = main.host
    subprocess.run([ADB_BIN, '-s', host, 'shell', 'input', 'tap', str(pt[0]), str(pt[1])], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)


def _roi(img, x1: int, y1: int, x2: int, y2: int):
    """Crop region of interest from image."""
    return img[y1:y2, x1:x2]


def _find_template_path(name: str, subdir: str | None) -> str | None:
    """Search for name.png in TEMPLATE_ROOT or subdir."""
    filename = name if name.lower().endswith(PNG_EXT) else name + PNG_EXT
    target = filename.lower()
    if subdir:
        root_dir = os.path.join(TEMPLATE_ROOT, subdir)
        for root, _, files in os.walk(root_dir):
            for f in files:
                if f.lower() == target:
                    return os.path.join(root, f)
    for root, _, files in os.walk(TEMPLATE_ROOT):
        for f in files:
            if f.lower() == target:
                return os.path.join(root, f)
    return None


def _match(name: str, hay, thresh: float=0.92, subdir: str | None=None):
    """Template-match haystack with template name in optional subdir."""
    path = _find_template_path(name, subdir)
    if path is None or hay is None:
        return (False, 0.0, (0, 0))
    tpl = imread_unicode(path)
    if tpl is None or tpl.shape[0] > hay.shape[0] or tpl.shape[1] > hay.shape[1]:
        return (False, 0.0, (0, 0))
    res = cv2.matchTemplate(hay, tpl, cv2.TM_CCOEFF_NORMED)
    _, val, _, loc = cv2.minMaxLoc(res)
    h, w = tpl.shape[:2]
    return (val >= thresh, val, (loc[0] + w // 2, loc[1] + h // 2))


ARMY_ROI = (682, 228, 1573, 383)
SPELL_ROI = (689, 461, 1250, 600)
SIEGE_ROI = (1256, 457, 1554, 608)
SPACE_ROI = (718, 193, 835, 227)
SPELL_SPACE_ROI = (731, 398, 810, 464)
# Верхняя граница вместимости казарм (санити для OCR; TH18 ~340, запас на буст-баннер).
MAX_HOUSING = 400
TRASH_ARMY_ROI = (1519, 184, 1570, 231)
TRASH_SPELL_ROI = (1197, 408, 1250, 455)
TRASH_SIEGE_ROI = (1511, 406, 1577, 458)
TAP_CLEAR_ARMY = (1546, 209)
TAP_CLEAR_SPELL = (1225, 429)
TAP_CLEAR_SIEGE = (1545, 427)
CONFIRM_TAP_ARMY = (969, 579)
CONFIRM_TAP_SPELL = (978, 583)
CONFIRM_TAP_SIEGE = (966, 581)
OPEN_ARMY_TAB = (1063, 305)
CLOSE_ARMY_TAB = (47, 85)
OPEN_SPELL_TAB = (1008, 531)
CLOSE_SPELL_TAB = (59, 52)
OPEN_SIEGE_TAB = (1398, 533)
CLOSE_SIEGE_TAB = (27, 85)
CLOSE_ARMY_WINDOW = (1545, 81)
SPACE_COST = {'dragon': 20, 'electro_dragon': 30, 'balloon': 5}
SPELL_COST = {'rage': 2, 'freeze': 1}
ARMY_SETS = {'Dragon_Attack': {'main': 'dragon', 'troops': ['dragon', 'balloon'], 'spells': ['rage', 'freeze'], 'siege': 'slammer'}, 'ElectroDragon_Attack': {'main': 'electro_dragon', 'troops': ['electro_dragon', 'balloon'], 'spells': ['rage', 'freeze'], 'siege': 'slammer'}}


def _read_fraction(img) -> Tuple[int, int]:
    n, d = digit_ocr.read_fraction(img)
    return (n or 0, d or 0)


def _clear_if_trash(roi, tap_coord, confirm_coord):
    shot = imread_unicode(take_screenshot(), cv2.IMREAD_COLOR)
    ok, _, _ = _match('trash_icon', _roi(shot, *roi), 0.8, subdir='to_train')
    if ok:
        print('[TRASH] cleaning troops... ')
        tap(tap_coord)
        time.sleep(1)
        tap(confirm_coord)
        time.sleep(1)


def _validate_troops(cfg) -> bool:
    spec = ARMY_SETS[cfg['attack']]
    shot = imread_unicode(take_screenshot(), cv2.IMREAD_COLOR)
    roi = _roi(shot, *ARMY_ROI)
    main_ok, _, _ = _match(spec['main'], roi, 0.92, subdir='Army Troops')
    if not main_ok:
        main_ok, _, _ = _match(spec['main'], roi, 0.92, subdir='s_troops')
    bal_ok, _, _ = _match('balloon', roi, 0.92, subdir='Army Troops')
    if not main_ok or not bal_ok:
        return False
    n, d = _read_fraction(_roi(shot, *SPACE_ROI))
    return n == d and n != 0


def _validate_spells() -> bool:
    shot = imread_unicode(take_screenshot(), cv2.IMREAD_COLOR)
    roi = _roi(shot, *SPELL_ROI)
    rage_ok, _, _ = _match('rage', roi, 0.92, subdir='Spells')
    freeze_ok, _, _ = _match('freeze', roi, 0.92, subdir='Spells')
    if not rage_ok or not freeze_ok:
        return False
    n, d = _read_fraction(_roi(shot, *SPELL_SPACE_ROI))
    return n == d and n != 0


def _validate_siege() -> bool:
    shot = imread_unicode(take_screenshot(), cv2.IMREAD_COLOR)
    roi = _roi(shot, *SIEGE_ROI)
    ok, _, _ = _match('slammer', roi, 0.92, subdir='Siege Machines')
    return ok


def _tap_icon_in_tab(name: str, count: int):
    tab = imread_unicode(take_screenshot(), cv2.IMREAD_COLOR)
    ok, _, center = _match(name, tab, 0.7, subdir='to_train')
    if not ok:
        print(f'[TRAIN] {name}.png not found in tab')
    else:
        for _ in range(count):
            tap(center)


def _measure_army_space_secondary(shot, roi_xyxy=(751, 183, 858, 230), template_dir=TEMPLATE_ROOT, threshold=0.9):
    """
Secondary army space measurement via template matching.
- shot: full color screenshot (BGR)
- roi_xyxy: (x0, y0, x1, y1)
- template_dir: TEMPLATE_ROOT containing army_space_0..7 PNGs
- threshold: normalized TM_CCOEFF_NORMED score (0.90 = 90%)
Returns: int space if confident, else None
"""
    x0, y0, x1, y1 = roi_xyxy
    region = shot[y0:y1, x0:x1]
    if region is None or region.size == 0:
        return None
    region_gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    space_map = {0: 220, 1: 240, 2: 260, 3: 280, 4: 310, 5: 320, 6: 300, 7: 340}
    best_idx = None
    best_val = -1.0
    for idx in range(8):
        tpl_path = os.path.join(template_dir, f'army_space_{idx}{PNG_EXT}')
        tpl = cv2.imread(tpl_path, cv2.IMREAD_GRAYSCALE)
        if tpl is None or tpl.size == 0:
            continue
        res = cv2.matchTemplate(region_gray, tpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)
        if max_val > best_val:
            best_val = max_val
            best_idx = idx
    if best_idx is not None and best_val >= threshold:
        space = space_map[best_idx]
        print(f'[SPACE secondary] match=army_space_{best_idx}  score={best_val:.3f}  => space={space}')
        return space
    print(f'[SPACE secondary] no confident match (best={best_val:.3f}), skipping.')
    return None


def train_troops(cfg, shot=None):
    spec = ARMY_SETS[cfg['attack']]
    main = spec['main']
    if cfg['attack'] == 'Dragon attack':
        icons = ['dragon', 'balloon']
    elif cfg['attack'] == 'Electro Dragon attack':
        icons = ['balloon', 'electro_dragon']
    else:
        icons = [main, 'balloon']
    if shot is None:
        shot = imread_unicode(take_screenshot(), cv2.IMREAD_COLOR)
    roi = _roi(shot, *ARMY_ROI)
    # Состав проверяем по шаблонам иконок (без OCR количеств).
    composition_ok = True
    for icon in icons:
        tpl = imread_unicode(os.path.join(ARMY_TROOPS_DIR, icon + PNG_EXT), cv2.IMREAD_COLOR)
        res = cv2.matchTemplate(roi, tpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _max_loc = cv2.minMaxLoc(res)
        if max_val < 0.7:
            print(f"[VALIDATION] '{icon}' missing – retraining.")
            composition_ok = False
            break
    if composition_ok:
        print('[VALIDATION] composition ok')
    else:
        print('[VALIDATION] will train fresh load')
    # Место армии — из дроби «used/limit» матчингом цифр (digit_ocr), без easyocr.
    used_now, limit = digit_ocr.read_fraction(_roi(shot, *SPACE_ROI))
    if limit is None:
        limit = -1
    print(f'[SPACE CHECK] Housing = {used_now}/{limit}')
    # Защита от сбойного OCR: реальная вместимость казарм ~≤ MAX_HOUSING. Лишний символ
    # (пульсирующий «!»-варнинг рядом с числом) раздувал лимит в 10× (напр. 340→3401)
    # → тренировались сотни юнитов. Неправдоподобный лимит → вторичный замер, иначе пропуск.
    if not (120 <= limit <= MAX_HOUSING):
        print(f'[SPACE CHECK] implausible housing ({limit}) → trying secondary measurement')
        sec = _measure_army_space_secondary(shot)
        if isinstance(sec, int) and 120 <= sec <= MAX_HOUSING:
            limit = sec
            print(f'[SPACE CHECK] Using secondary measurement → {limit}')
        else:
            print('[SPACE CHECK] cannot read housing reliably → skip training this pass (avoid over-brew)')
            return None
    primary = spec['main']
    # Готова, если состав верный И казармы полны (used==limit) — тогда не перетренировываем.
    if composition_ok and used_now is not None and limit is not None and used_now == limit and used_now != 0:
        print(f'[TRAIN] army full & composition ok ({used_now}/{limit}) — skipping training.')
        return None
    _clear_if_trash(TRASH_ARMY_ROI, TAP_CLEAR_ARMY, CONFIRM_TAP_ARMY)
    tap(OPEN_ARMY_TAB)
    time.sleep(1)
    main_cost = SPACE_COST[main]
    main_space = limit * 80 // 100 // main_cost * main_cost
    main_cnt = main_space // main_cost
    bal_cnt = (limit - main_space) // SPACE_COST['balloon']
    print(f'[TRAIN] {main_cnt}×{main}, {bal_cnt}×balloon (limit={limit})')
    _tap_icon_in_tab(main, main_cnt)
    _tap_icon_in_tab('balloon', bal_cnt)
    tap(CLOSE_ARMY_TAB)
    time.sleep(1)


SPELL_STATE_PATH = os.path.join(BASE_DIR, 'profiles', 'spell_state.json')


def _load_spell_counts():
    """Желаемый состав заклов из config/army.json (по стратегии). Фолбэк 4 rage/3 freeze."""
    import json
    try:
        with open(os.path.join(BASE_DIR, 'config', 'army.json'), encoding='utf-8') as f:
            s = json.load(f).get('spells') or {}
        return {'rage': int(s.get('rage', 4)), 'freeze': int(s.get('freeze', 3))}
    except Exception:
        return {'rage': 4, 'freeze': 3}


def _spell_config_changed(desired) -> bool:
    """Изменился ли желаемый состав с прошлой тренировки (profiles/spell_state.json)."""
    import json
    try:
        with open(SPELL_STATE_PATH, encoding='utf-8') as f:
            return json.load(f) != desired
    except Exception:
        return True


def _save_spell_state(desired):
    import json
    os.makedirs(os.path.dirname(SPELL_STATE_PATH), exist_ok=True)
    with open(SPELL_STATE_PATH, 'w', encoding='utf-8') as f:
        json.dump(desired, f)


# Геометрия бара заклов в баре армии (1600×900) для счёта плиток по яркости.
SPELL_BAR_BAND = (478, 592)      # y-полоса плиток заклов
SPELL_BAR_X0 = 690               # левый край первой плитки
SPELL_TILE_PITCH = 133           # шаг между плитками
SPELL_BAR_XEND = 1220            # правый край зоны заклов (до осадной секции)


def _has_extra_spell_tiles(shot, n_expected) -> bool:
    """True, если ПРАВЕЕ ожидаемых n_expected плиток заклов есть ещё яркие плитки —
    признак подмешанных лишних/чужих заклов (ивентовые/донатные). Каждый тип закла =
    одна плитка (стек xN), поэтому правильный состав занимает ровно n_expected плиток."""
    y0, y1 = SPELL_BAR_BAND
    a = SPELL_BAR_X0 + n_expected * SPELL_TILE_PITCH + 15
    b = SPELL_BAR_XEND
    if a >= b:
        return False
    V = cv2.cvtColor(shot[y0:y1, a:b], cv2.COLOR_BGR2HSV)[:, :, 2]
    return float((V > 120).mean()) > 0.25


def train_spells(cfg, shot=None):
    """Держит состав заклов = config/army.json (точное кол-во rage/freeze по стратегии).

    Читать «xN» с иконок нельзя (шрифт бейджа не распознаётся digit_ocr), поэтому счёт
    из стратегии соблюдается так: тренируем РОВНО заданное кол-во; пересобираем, если
    (а) заклов нет/не полны (израсходованы в бою), ИЛИ (б) в конфиге изменили состав
    (детект по profiles/spell_state.json). Иначе — не трогаем (без лишнего расхода)."""
    if shot is None:
        shot = imread_unicode(take_screenshot(), cv2.IMREAD_COLOR)
    desired = _load_spell_counts()
    changed = _spell_config_changed(desired)
    desired_icons = [k for k, v in desired.items() if v > 0]      # напр. ['rage','freeze']
    roi = _roi(shot, *SPELL_ROI)
    # (1) желаемые заклы присутствуют?
    present_ok = True
    for icon in desired_icons:
        tpl = imread_unicode(os.path.join(SPELL_DIR, icon + PNG_EXT), cv2.IMREAD_COLOR)
        if tpl is None:
            continue
        _, mv, _, _ = cv2.minMaxLoc(cv2.matchTemplate(roi, tpl, cv2.TM_CCOEFF_NORMED))
        if mv < 0.7:
            present_ok = False
            break
    # (2) лишних/чужих заклов быть НЕ должно. Считать бейдж «xN» нельзя, а пер-закловые
    #     шаблоны из панели выбора не совпадают с баром (масштаб/рамка). Надёжный сигнал:
    #     каждый ТИП заклинания = одна плитка в баре (стек x4/x3), т.е. правильный состав =
    #     len(desired_icons) плиток. Если правее ожидаемых плиток есть ещё яркие плитки —
    #     значит подмешаны лишние (ивентовые/донатные) заклы → пересобрать.
    foreign = _has_extra_spell_tiles(shot, len(desired_icons))
    composition_ok = present_ok and not foreign
    used_now, cap = digit_ocr.read_fraction(_roi(shot, *SPELL_SPACE_ROI))
    full = bool(used_now and cap and used_now == cap)
    if composition_ok and full and not changed:
        print(f"[SPELL] ok ({desired['rage']}×rage / {desired['freeze']}×freeze) — skip")
        return None
    if changed:
        print('[SPELL] config counts changed → rebuilding to strategy composition')
    elif foreign:
        print('[SPELL] extra/foreign spells in bar → rebuilding to strategy composition')
    elif not present_ok:
        print('[SPELL] missing spell → rebuilding')
    else:
        print('[SPELL] not full (used in battle) → refilling')
    _clear_if_trash(TRASH_SPELL_ROI, TAP_CLEAR_SPELL, CONFIRM_TAP_SPELL)
    tap(OPEN_SPELL_TAB)
    time.sleep(1)
    print(f"[TRAIN] {desired['rage']}×rage, {desired['freeze']}×freeze (from config/army.json)")
    _tap_icon_in_tab('rage', desired['rage'])
    _tap_icon_in_tab('freeze', desired['freeze'])
    tap(CLOSE_SPELL_TAB)
    time.sleep(1)
    _save_spell_state(desired)


def train_slammer(cfg=None, shot=None):
    """
Validates and (if needed) rebuilds your siege ‘slammer’ loadout.
Mirrors train_troops/train_spells structure.
"""
    if shot is None:
        shot = imread_unicode(take_screenshot(), cv2.IMREAD_COLOR)
    if shot is None:
        print('[SIEGE] ERROR: failed to grab screenshot')
        return None
    roi = _roi(shot, *SIEGE_ROI)
    # Осадка «на месте», если в слоте совпал ЛЮБОЙ шаблон осадной машины из
    # Siege Machines/ (slammer/slammer1/blimp/…). Раньше проверяли только slammer.png
    # → при другой осадке (напр. Battle Blimp) или альт-виде slammer1 ложно ребилдили.
    best_name, best_val = None, 0.0
    for f in sorted(os.listdir(SIEGE_DIR)):
        if not f.lower().endswith(PNG_EXT):
            continue
        t = imread_unicode(os.path.join(SIEGE_DIR, f), cv2.IMREAD_COLOR)
        if t is None or t.shape[0] > roi.shape[0] or t.shape[1] > roi.shape[1]:
            continue
        mv = float(cv2.matchTemplate(roi, t, cv2.TM_CCOEFF_NORMED).max())
        if mv > best_val:
            best_val, best_name = mv, f
    if best_val >= 0.8:
        print(f'[SIEGE] present ({best_name} {best_val:.2f}) — skipping training.')
        return None
    print(f"[SIEGE] no siege detected (best {best_name} {best_val:.2f}) – will rebuild slammer")
    _clear_if_trash(TRASH_SIEGE_ROI, TAP_CLEAR_SIEGE, CONFIRM_TAP_SIEGE)
    tap(OPEN_SIEGE_TAB)
    time.sleep(1)
    print('[TRAIN] 3×slammer')
    _tap_icon_in_tab('slammer', 3)
    tap(CLOSE_SIEGE_TAB)
    time.sleep(1)


def _validate_army_window():
    """
Tap the Army button, wait, then confirm the Army window is open
by template‐matching 'army_window.png' in the given ROI.
Returns True if match ≥0.90, False otherwise.
"""
    OPEN_ARMY_WINDOW = (62, 658)
    tap(OPEN_ARMY_WINDOW)
    time.sleep(1)
    shot = imread_unicode(take_screenshot(), cv2.IMREAD_COLOR)
    if shot is None:
        print('[WINDOW CHECK] failed to capture screenshot')
        return False
    army_roi = _roi(shot, 76, 57, 565, 156)
    if DEBUG:
        roi_path = os.path.join(BASE_DIR, 'debug_army_roi.png')
        cv2.imwrite(roi_path, army_roi)
        print(f'[DEBUG] saved army ROI to {roi_path}, shape={army_roi.shape}')
    tpl_path = os.path.join(TEMPLATE_ROOT, 'army_window.png')
    tpl = imread_unicode(tpl_path, cv2.IMREAD_COLOR)
    if tpl is None:
        print(f'[WINDOW CHECK] missing template {tpl_path}')
        return False
    res = cv2.matchTemplate(army_roi, tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(res)
    print(f'[WINDOW CHECK] army window match score = {max_val:.3f}')
    return max_val >= 0.6


def smart_train(cfg):
    if not _validate_army_window():
        print('[SMART] Army window not detected – skipping Army training')
        return None
    print('Army window detected')
    # MBR-CSV/неизвестная стратегия: состав войск не задан в ARMY_SETS (ключ вида "csv:<имя>").
    # Не трогаем войска (ожидается заранее собранная под стратегию армия), тренируем только
    # заклы/осаду — они не зависят от состава. Иначе ARMY_SETS[cfg['attack']] бросил бы KeyError.
    known_army = cfg.get('attack') in ARMY_SETS
    if known_army:
        army_ok = _validate_troops(cfg)
        if not army_ok:
            train_troops(cfg)
    elif str(cfg.get('attack', '')).startswith('csv:'):
        # MBR-CSV v1: авто-сборка армии не реализована (milestone-2). Явно логируем, чтобы пустая
        # армия на 2-й атаке диагностировалась как «нет auto-train», а не «CSV сломан».
        print('[MBR-CSV] Army auto-training is not supported.')
        print('[MBR-CSV] Using currently prepared troops.')
    else:
        print('[SMART] Unknown strategy — army composition not defined; '
              'keeping barracks troops, training spells/siege only.')
    # Заклы ВСЕГДА через train_spells — он сам решает (skip/rebuild) по точному составу
    # из config/army.json. Старый гейт _validate_spells проверял лишь НАЛИЧИЕ rage+freeze
    # и полноту места, из-за чего чужие/лишние заклы (ивентовые jump/heal и т.п.) не
    # пересобирались до нужного 4×rage/3×freeze.
    train_spells(cfg)
    if not _validate_siege():
        train_slammer()
    print('[SMART] Training complete – closing Army tab')
    tap(CLOSE_ARMY_WINDOW)
    time.sleep(1)


if __name__ == '__main__':
    smart_train({'attack': 'Dragon_Attack'})
