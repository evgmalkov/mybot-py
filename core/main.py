global wall_save
global _cycle_count
global _last_good_points
global _saved_wall_offset
global host
import subprocess
import threading
import time
import os
import math
import sys
import random
import cv2
import re
import numpy as np
import digit_ocr
from clan_games import run_events_open
from pathlib import Path
from memu_manager import ensure_memu
from ldplayer_manager import ensure_ldplayer
from bluestacks_manager import ensure_bluestacks
from Tap_Collectors import find_and_tap_collectors
from IsTarget import extract_resources
from request_troops import auto_request
from home_routine import handle_home_resources
from boot_recovery import boot_recovery
from ensure_home_base import ensure_home_base
from detect_home_base import detect_home_base
from screenshot_utils import take_screenshot, capture_array, load_template
from smart_train import smart_train
from quick_train import quick_train
from ready_villages import prepare_accounts, add_village, switch_to_village
import glob
from village_wiz import run_village_wizard
from wizard_bridge import bridge
from PyQt5.QtCore import QEventLoop
from zoom_out import multi_zoom_out
from unicode import imread_unicode
import json
from attacks.attacks import run_attack as attack_dispatch
ATTACK_FUNCS = {'Dragon_Attack': attack_dispatch, 'ElectroDragon_Attack': attack_dispatch}
CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
from paths import BASE_DIR, debug_path


# ── анти-бан: рандомизация (параметры в config/antiban.json, логика в коде) ──
def _load_antiban():
    import json
    try:
        with open(os.path.join(BASE_DIR, 'config', 'antiban.json'), encoding='utf-8') as _f:
            d = json.load(_f)
    except Exception:
        d = {}
    return {
        'tap_jitter_px': int(d.get('tap_jitter_px', 5)),
        'tap_delay_sec': tuple(d.get('tap_delay_sec', [0.08, 0.35])),
        'between_cycles_sec': tuple(d.get('between_cycles_sec', [8, 25])),
        'break_chance': float(d.get('break_chance', 0.05)),
        'break_sec': tuple(d.get('break_sec', [60, 240])),
        'transition_delay_sec': tuple(d.get('transition_delay_sec', [2, 6])),
    }


ANTIBAN = _load_antiban()
# ADB_BIN — динамический выбор adb по host (BlueStacks → HD-Adb.exe), см. adb_config.
from adb_config import ADB_BIN
import syscfg                       # системный конфиг (config/system.json)
os.chdir(BASE_DIR)
ADB_DIR = BASE_DIR
ATTACKS_DIR = os.path.join(ADB_DIR, 'attacks')
host = None
AHK_DIR = os.path.join(BASE_DIR, 'AutoHotkey', 'v2')
AHK_EXE = os.path.join(AHK_DIR, 'AutoHotkey64.exe')
TEMPLATE_DIR = os.path.join(BASE_DIR, 'Templates')
NEXT_BTN_TEMPLATE = os.path.join(TEMPLATE_DIR, 'next_button.png')
END_BATTLE_TEMPLATE = os.path.join(TEMPLATE_DIR, 'end_battle.png')
TEMPLATE_FILES = ['Another_device.png', 'Connection_lost.png', 'Client_error!.png', 'rate_coc.png']
THRESHOLD = 0.88
CLAN_CAPITAL_SCENERY_DIR = os.path.join(TEMPLATE_DIR, 'Clan Capital', 'Scenery')
CLAN_CAPITAL_ROI = (150, 200, 1292, 889)
CLAN_CAPITAL_THRESH = 0.65
CLAN_CAPITAL_CACHE = os.path.join(BASE_DIR, 'profiles', 'clan_capital_tpl.txt')
CLAN_CAPITAL_DIR = os.path.join(TEMPLATE_DIR, 'Clan Capital')
CC_THRESH_PCT = 75
CC_V1_ROI = (1, 106, 160, 246)
CC_V2_ROI = (1, 173, 198, 894)
CC_START_ROI = (1418, 661, 1593, 747)
CC_HOME_TAP = (105, 799)
CC_AVAIL_ATKS_ROI = (1441, 679, 1525, 724)
CC_ENEMY_SWIPE = (827, 274, 827, 110, 500)
CC_ENEMY_TAP = (1492, 808)
CC_CLOSE_PANEL = (246, 262)
CC_VILLAGE_STAR_ROI = (395, 736, 669, 810)
CC_VILLAGE_AVAIL_ROI = (819, 744, 1087, 869)
CC_TPL_AVAILABLE_ATKS = 'available_attacks.png'
CC_TPL_ENEMY_LAND = 'capital_enemy.png'
CC_TPL_VILLAGE_3STAR = 'capital_3star.png'
CC_TPL_VILLAGE_AVAIL = 'capital_available.png'
CC_TPL_TROOPS_READY = 'capital_troops_ready.png'
CC_TPL_FULL_GOLD_WINDOW = 'capital_full_gold_window.png'
CC_ARMY_WINDOW_TAP = (941, 804)
CC_TROOPS_ROI = (134, 185, 202, 249)
CC_SPELLS_ROI = (134, 423, 199, 481)
CC_ATTACK_READY_ROI = (5, 628, 230, 724)
CC_ATTACK_TAP = (1306, 513)
CC_REINITIATE_TAP = (972, 582)
CC_FULL_GOLD_ROI = (385, 195, 1248, 723)
CC_PANEL_ROI = (74, 722, 1500, 896)
CC_DIR_SPELLS = os.path.join(CLAN_CAPITAL_DIR, 'Spells')
CC_DIR_TROOPS = os.path.join(CLAN_CAPITAL_DIR, 'Troops')
CP_FRESH_TEMPLATE = os.path.join(CLAN_CAPITAL_DIR, 'capital_cp_fresh.png')
CP_FRESH_THRESHOLD = 0.95
CP_FIRST_DROPPOINTS = [(795, 444), (805, 432)]
CP_GLOW_POLY_REL = [(0.63125, 0.09555555555555556), (0.751875, 0.26555555555555554), (0.339375, 0.81), (0.19125, 0.6422222222222222)]
BRIGHT_EDGE_ROI_RAW = (1549, 722, 235, 210)
BRIGHT_EDGE_MARGIN = 10
DROP_SPACING = 160
_last_good_points = []
GLOW_TL = (1549, 722)
GLOW_BR = (235, 210)
EDGE_S_MAX_DEF = 50
EDGE_V_MIN_DEF = 210
EDGE_LOCAL_DELTA_DEF = 16
EDGE_GRAD_FLOOR = 60
EDGE_MIN_LINE_LEN_FR = 0.12
EDGE_MAX_GAP = 18
ANGLE_MIN = 15
ANGLE_MAX = 75
DROP_SPACING = 180
CC_VILLAGE_COORDS = {'Goblin Mines': (1063, 723), 'Skeleton Park': (712, 723), 'Golem Quarry': (391, 661), 'Balloon Lagoon': (583, 515), 'Builder\'s Workshop': (913, 550), 'Dragon Cliffs': (1135, 462), 'Wizard Valley': (766, 337), 'Barbarian Camp': (984, 252), 'Capital Peak': (759, 83)}
CC_VILLAGE_ORDER = ['Goblin Mines', 'Skeleton Park', 'Golem Quarry', 'Balloon Lagoon', 'Builder\'s Workshop', 'Dragon Cliffs', 'Wizard Valley', 'Barbarian Camp', 'Capital Peak']
CC_TROOP_TAP_COUNTS = {'s_miner.png': 11, 'mountain_golem.png': 2, 's_dragon.png': 4, 'pekka.png': 3, 'flying_fortress.png': 2}
CC_TROOP_DROPPOINTS = {'Balloon Lagoon': (754, 548), 'Barbarian Camp': (834, 520), 'Builder\'s Workshop': (868, 391), 'Dragon Cliffs': (847, 413), 'Goblin Mines': (701, 634), 'Golem Quarry': (796, 452), 'Skeleton Park': (901, 383), 'Wizard Valley': (1026, 283), 'Capital Peak': (759, 83)}
CC_SPELL_DROPPOINTS = {'Balloon Lagoon': [(318, 590), (302, 217), (482, 357)], 'Barbarian Camp': [(674, 285), (592, 223)], 'Builder\'s Workshop': [(571, 433), (869, 237)], 'Dragon Cliffs': [(835, 252), (605, 167)], 'Goblin Mines': [(648, 391), (316, 431)], 'Golem Quarry': [(436, 369), (636, 229)], 'Skeleton Park': [(839, 197), (673, 317)], 'Wizard Valley': [(912, 145), (661, 229), (278, 320)]}
DROP_THRESH = 0.7
SURRENDER_THRESH = 0.88
MAX_VILLAGES = 5
for tpl in (NEXT_BTN_TEMPLATE, END_BATTLE_TEMPLATE):
    if os.path.isfile(tpl):
        continue
    print(f'❌ Template not found: {tpl}')
    sys.exit(1)
NEXT_BTN_REGION = (1291, 563, 1592, 721)
NEXT_THRESH = 0.35
MAX_WAIT_BATTLE = 170
_cycle_count = 0
_saved_wall_offset = None
wall_save = False
MEMU = f"127.0.0.1:{syscfg.emu('memu', 'adb_base_port', 21503)}"
BLUESTACKS = f"127.0.0.1:{syscfg.emu('bluestacks', 'adb_port', 5556)}"
LDPLAYER = '127.0.0.1:5555'
def run_adb(cmd_args):
    """Run ADB with the given argument list silently."""
    subprocess.run([ADB_BIN, '-s', host, *cmd_args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
def return_home():
    """Equivalent to return_home.bat → tap 788 768."""
    run_adb(['shell', 'input', 'tap', '788', '768'])
    rsleep(3)
def search_attack():
    """Equivalent to search_attack.bat."""
    run_adb(['shell', 'input', 'tap', '113', '797'])
    rsleep(0.7)
    run_adb(['shell', 'input', 'tap', '272', '659'])
    rsleep(0.7)
    run_adb(['shell', 'input', 'tap', '1445', '804'])
def search_next():
    """Equivalent to search_next.bat → tap 1432 637."""
    run_adb(['shell', 'input', 'tap', '1432', '637'])
def _sorted_box(tl, br):
    x1, x2 = sorted([tl[0], br[0]])
    y1, y2 = sorted([tl[1], br[1]])
    return (x1, y1, x2, y2)
def _points_along(x1, y1, x2, y2, spacing=DROP_SPACING):
    L = math.hypot(x2 - x1, y2 - y1)
    if L < spacing:
        return [((x1 + x2) // 2, (y1 + y2) // 2)]
    n = int(L // spacing) + 1
    return [(int(round(x1 + (i + 0.5) / n * (x2 - x1))), int(round(y1 + (i + 0.5) / n * (y2 - y1)))) for i in range(n)]
def _abs_poly_from_rel(img_shape, poly_rel):
    H, W = img_shape[:2]
    return [(int(px * W), int(py * H)) for px, py in poly_rel]
def get_glow_drop_points_poly(img_bgr, poly_abs, spacing=DROP_SPACING):
    """\nLike get_glow_drop_points, but restricts detection inside a polygon (list of (x,y)).\n"""
    if not poly_abs:
        return get_glow_drop_points(img_bgr, spacing=spacing)
    else:
        xs = [p[0] for p in poly_abs]
        ys = [p[1] for p in poly_abs]
        x1, y1 = (max(0, min(xs)), max(0, min(ys)))
        x2, y2 = (min(img_bgr.shape[1] - 1, max(xs)), min(img_bgr.shape[0] - 1, max(ys)))
        if x2 <= x1 or y2 <= y1:
            cx = sum(xs) // 4
            cy = sum(ys) // 4
            return [(cx, cy)]
        roi = img_bgr[y1:y2, x1:x2]
        if roi.size == 0:
            cx = sum(xs) // 4
            cy = sum(ys) // 4
            return [(cx, cy)]
        poly_roi = np.array([[(px - x1, py - y1) for px, py in poly_abs]], dtype=np.int32)
        mask = np.zeros(roi.shape[:2], dtype=np.uint8)
        cv2.fillPoly(mask, poly_roi, 255)
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        _, Sc, Vc = cv2.split(hsv)
        white_mask = ((Sc < 80) & (Vc > 220)).astype(np.uint8) * 255
        white_mask = cv2.bitwise_and(white_mask, mask)
        white_mask = cv2.morphologyEx(white_mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=2)
        white_mask = cv2.dilate(white_mask, np.ones((3, 3), np.uint8), iterations=1)
        edges = cv2.Canny(white_mask, 50, 150)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=60, minLineLength=90, maxLineGap=12)
        if lines is None:
            cx = sum(xs) // 4
            cy = sum(ys) // 4
            return [(cx, cy)]
        segs = [tuple(map(int, l[0])) for l in lines]
        segs.sort(key=lambda L: math.hypot(L[2] - L[0], L[3] - L[1]), reverse=True)
        segs = segs[:6]
        pts = []
        for xa, ya, xb, yb in segs:
            xa, ya, xb, yb = (x1 + xa, y1 + ya, x1 + xb, y1 + yb)
            pts.extend(_points_along(xa, ya, xb, yb, spacing))
        out = []
        for px, py in pts:
            if all((abs(px - qx) > 18 or abs(py - qy) > 18 for qx, qy in out)):
                out.append((px, py))
        return out[:12]
def get_glow_drop_points(img_bgr, tl=GLOW_TL, br=GLOW_BR, spacing=DROP_SPACING):
    """\nReturns a list of absolute (x,y) tap points along the glowing white border\ninside your ROI. If nothing is found, returns the ROI center.\n"""
    H, W = img_bgr.shape[:2]
    x1, y1, x2, y2 = _sorted_box(tl, br)
    x1 = max(0, min(W - 1, x1))
    x2 = max(0, min(W, x2))
    y1 = max(0, min(H - 1, y1))
    y2 = max(0, min(H, y2))
    if x2 <= x1 or y2 <= y1:
        cx = (tl[0] + br[0]) // 2; cy = (tl[1] + br[1]) // 2
        return [(cx, cy)]
    roi = img_bgr[y1:y2, x1:x2]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    Hc, Sc, Vc = cv2.split(hsv)
    mask = ((Sc < 80) & (Vc > 220)).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=2)
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1)
    edges = cv2.Canny(mask, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=60, minLineLength=90, maxLineGap=12)
    if lines is None:
        return [((x1 + x2) // 2, (y1 + y2) // 2)]
    import math
    segs = [tuple(map(int, l[0])) for l in lines]
    segs.sort(key=lambda L: math.hypot(L[2] - L[0], L[3] - L[1]), reverse=True)
    segs = segs[:6]
    pts = []
    for xa, ya, xb, yb in segs:
        xa, ya, xb, yb = (x1 + xa, y1 + ya, x1 + xb, y1 + yb)
        pts.extend(_points_along(xa, ya, xb, yb, spacing))
    out = []
    for px, py in pts:
        if all((abs(px - qx) > 18 or abs(py - qy) > 18 for qx, qy in out)):
            out.append((px, py))
    return out[:12]
def save_glow_debug(img_bgr, path='glow_debug.png'):
    pts = get_glow_drop_points(img_bgr)
    vis = img_bgr.copy()
    for x, y in pts:
        cv2.circle(vis, (x, y), 10, (0, 0, 255), 3)
    cv2.imwrite(debug_path(path), vis)
def _norm_roi_any(img_shape, r, margin=0):
    H, W = img_shape[:2]
    a, b, c, d = map(int, r)
    if c <= W // 3 and d <= H // 3:
        br_x, br_y, w, h = (a, b, c, d)
        x1, y1 = (br_x - w, br_y - h)
        x2, y2 = (br_x, br_y)
    else:
        x1, y1, x2, y2 = (a, b, c, d)
    x1, x2 = (min(x1, x2), max(x1, x2))
    y1, y2 = (min(y1, y2), max(y1, y2))
    x1, y1 = (x1 - margin, y1 - margin)
    x2, y2 = (x2 + margin, y2 + margin)
    x1, y1 = (max(0, x1), max(0, y1))
    x2, y2 = (min(W, x2), min(H, y2))
    if x2 <= x1 or y2 <= y1:
        return None
    else:
        return (x1, y1, x2, y2)
def _white_tophat(gray, k=19):
    se = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    return cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, se)
def _auto_binary(img):
    _, t1 = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    t2 = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 31, -3)
    m = cv2.bitwise_or(t1, t2)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    return m
def _find_lines_hough(mask, xa, ya):
    med = np.median(mask)
    low = int(max(0, 0.66 * med))
    high = int(min(255, 1.33 * med))
    edges = cv2.Canny(mask, low, high)
    Ht, Wt = mask.shape[:2]
    min_len = max(80, int(0.12 * math.hypot(Wt, Ht)))
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 60, minLineLength=min_len, maxLineGap=16)
    out = []
    if lines is not None:
        for x1, y1, x2, y2 in lines[:, 0, :]:
            ang = abs(math.degrees(math.atan2(y2 - y1, x2 - x1)))
            if 12 <= ang <= 85 or 95 <= ang <= 168:
                out.append((xa + x1, ya + y1, xa + x2, ya + y2))
    return out
def _find_lines_lsd(gray, xa, ya):
    lsd = cv2.createLineSegmentDetector(0)
    lines, _, _, _ = lsd.detect(gray)
    out = []
    if lines is not None:
        for l in lines:
            x1, y1, x2, y2 = l[0]
            ang = abs(math.degrees(math.atan2(y2 - y1, x2 - x1)))
            if 12 <= ang <= 85 or 95 <= ang <= 168:
                out.append((xa + int(x1), ya + int(y1), xa + int(x2), ya + int(y2)))
    return out
def _points_along(x1, y1, x2, y2, spacing=DROP_SPACING):
    L = math.hypot(x2 - x1, y2 - y1)
    if L < spacing:
        return [((x1 + x2) // 2, (y1 + y2) // 2)]
    n = int(L // spacing) + 1
    return [(int(round(x1 + (i + 0.5) / n * (x2 - x1))), int(round(y1 + (i + 0.5) / n * (y2 - y1)))) for i in range(n)]
def _nudge_inside(pt, img_bgr, step=12):
    x, y = pt
    H, W = img_bgr.shape[:2]
    dirs = [(1, 0), (0, 1), ((-1), 0), (0, (-1)), (1, 1), ((-1), 1), (1, (-1)), ((-1), (-1))]
    best = (0, None)
    for dx, dy in dirs:
        xx = np.clip(x + dx * 8, 0, W - 1)
        yy = np.clip(y + dy * 8, 0, H - 1)
        b, g, r = img_bgr[int(yy), int(xx)]
        score = int(g) - (int(r) + int(b)) // 2
        if score > best[0]:
            best = (score, (dx, dy))
    if best[1] is None:
        return (x, y)
    else:
        dx, dy = best[1]
        xx = int(np.clip(x + dx * step, 0, W - 1))
        yy = int(np.clip(y + dy * step, 0, H - 1))
        return (xx, yy)
def detect_bright_field_drop_points(img_bgr, roi_spec=BRIGHT_EDGE_ROI_RAW, debug=None):
    """\nReturns (points:list[(x,y)], confidence:float). Uses ROI first.\n"""
    global _last_good_points
    box = _norm_roi_any(img_bgr.shape, roi_spec, margin=BRIGHT_EDGE_MARGIN)
    if not box:
        return (_last_good_points if _last_good_points else [], 0.0)
    else:
        x1, y1, x2, y2 = box
        roi = img_bgr[y1:y2, x1:x2]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        hat = _white_tophat(gray, k=21)
        mask = _auto_binary(hat)
        lines = _find_lines_hough(mask, x1, y1)
        if len(lines) < 2:
            lines = sorted(lines + _find_lines_lsd(hat, x1, y1), key=lambda L: math.hypot(L[2] - L[0], L[3] - L[1]), reverse=True)
        if debug:
            dbg = img_bgr.copy()
            cv2.rectangle(dbg, (x1, y1), (x2, y2), (0, 255, 0), 2)
            for L in lines[:8]:
                cv2.line(dbg, (L[0], L[1]), (L[2], L[3]), (0, 0, 255), 3)
            cv2.imwrite(debug_path(f'{os.path.basename(str(debug))}_dbg.png'), dbg)
            cv2.imwrite(debug_path(f'{os.path.basename(str(debug))}_hat.png'), hat)
            cv2.imwrite(debug_path(f'{os.path.basename(str(debug))}_mask.png'), mask)
        if not lines:
            if _last_good_points:
                return (_last_good_points, 0.15)
            else:
                return ([((x1 + x2) // 2, (y1 + y2) // 2)], 0.15)
        else:
            lines = lines[:6]
            pts = []
            for xa, ya, xb, yb in lines:
                pts += _points_along(xa, ya, xb, yb, spacing=DROP_SPACING)
            uniq = []
            for px, py in pts:
                if all((abs(px - ux) > 18 or abs(py - uy) > 18 for ux, uy in uniq)):
                    uniq.append(_nudge_inside((px, py), img_bgr, step=12))
            diag = math.hypot(x2 - x1, y2 - y1)
            total_len = sum((math.hypot(L[2] - L[0], L[3] - L[1]) for L in lines))
            conf = float(max(0.0, min(1.0, total_len / diag)))
            _last_good_points = uniq[:]
            return (uniq[:12], conf)
def _scan_icons_in_panel(img_bgr, folder_path: str, roi, threshold_pct: int=80) -> dict:
    """\nScan all *.png in folder_path against ROI of img_bgr (color TM).\nReturns {filename: (cx, cy, score)} for matches >= threshold.\n"""
    results = {}
    if not os.path.isdir(folder_path):
        print(f'[CC P4] ❌ folder missing: {folder_path}')
        return results
    else:
        thr = float(threshold_pct) / 100.0
        x1, y1, x2, y2 = roi
        H, W = img_bgr.shape[:2]
        x1, y1 = (max(0, x1), max(0, y1))
        x2, y2 = (min(W, x2), min(H, y2))
        if x2 <= x1 or y2 <= y1:
            print('[CC P4] ❌ invalid panel ROI after clamp')
            return results
        else:
            panel = img_bgr[y1:y2, x1:x2]
            for name in sorted(os.listdir(folder_path)):
                if not name.lower().endswith('.png'):
                    continue
                tpl_path = os.path.join(folder_path, name)
                tpl = imread_unicode(tpl_path, cv2.IMREAD_COLOR)
                if tpl is None or tpl.size == 0:
                    continue
                th, tw = tpl.shape[:2]
                if panel.shape[0] < th or panel.shape[1] < tw:
                    continue
                try:
                    res = cv2.matchTemplate(panel, tpl, cv2.TM_CCOEFF_NORMED)
                    _, score, _, loc = cv2.minMaxLoc(res)
                except cv2.error:
                    continue
                print(f'[CC P4] panel match {name}: {score:.2f}')
                if score >= thr:
                    cx = x1 + loc[0] + tw // 2
                    cy = y1 + loc[1] + th // 2
                    results[name] = (cx, cy, float(score))
            return results
def _canon(vname: str) -> str:
    v = vname.strip().lower()
    v = v.replace('gobline mines', 'goblin mines').replace('dragon cliff', 'dragon cliffs')
    return {'goblin mines': 'Goblin Mines', 'skeleton park': 'Skeleton Park', 'golem quarry': 'Golem Quarry', 'balloon lagoon': 'Balloon Lagoon', "builder's workshop": "Builder's Workshop", 'dragon cliffs': 'Dragon Cliffs', 'wizard valley': 'Wizard Valley', 'barbarian camp': 'Barbarian Camp', 'capital peak': 'Capital Peak'}.get(v, vname)
def popup_warning(message: str, title: str='Clan Capital'):
    """\nShow a blocking popup warning. Prefers native Windows MessageBox.\nFalls back to print if something goes wrong.\n"""
    try:
        import ctypes
        MB_ICONWARNING = 48
        MB_SYSTEMMODAL = 4096
        ctypes.windll.user32.MessageBoxW(0, message, title, MB_ICONWARNING | MB_SYSTEMMODAL)
    except Exception:
        print(f'[POPUP] {title}: {message}')
        return False
    return True
def _villages_for_ch_level(ch_level: int) -> list[str]:
    """\nReturn the list of villages that can appear at a given Capital Hall level,\nordered by CC_VILLAGE_ORDER (Capital Peak included at every level ≥1).\n"""
    sets = {1: {'Capital Peak'}, 2: {'Capital Peak', 'Barbarian Camp'}, 3: {'Wizard Valley', 'Capital Peak', 'Barbarian Camp'}, 4: {'Wizard Valley', 'Capital Peak', 'Barbarian Camp', 'Balloon Lagoon'}, 5: {'Wizard Valley', 'Barbarian Camp', 'Balloon Lagoon', "Builder's Workshop", 'Capital Peak'}, 6: {'Wizard Valley', 'Barbarian Camp', 'Balloon Lagoon', 'Dragon Cliffs', "Builder's Workshop", 'Capital Peak'}, 7: {'Wizard Valley', 'Barbarian Camp', 'Golem Quarry', 'Balloon Lagoon', 'Dragon Cliffs', "Builder's Workshop", 'Capital Peak'}, 8: {'Skeleton Park', 'Wizard Valley', 'Barbarian Camp', 'Golem Quarry', 'Balloon Lagoon', 'Dragon Cliffs', "Builder's Workshop", 'Capital Peak'}, 9: {'Skeleton Park', 'Goblin Mines', 'Wizard Valley', 'Barbarian Camp', 'Golem Quarry', 'Balloon Lagoon', 'Dragon Cliffs', "Builder's Workshop", 'Capital Peak'}, 10: {'Skeleton Park', 'Goblin Mines', 'Wizard Valley', 'Barbarian Camp', 'Golem Quarry', 'Balloon Lagoon', 'Dragon Cliffs', "Builder's Workshop", 'Capital Peak'}}
    avail = sets.get(max(1, min(10, ch_level))),
    avail = sets.get(max(1, min(10, ch_level)))
    return [v for v in CC_VILLAGE_ORDER if v in avail]
def _match_gray(img_gray, tpl_path: str, threshold, roi=None):
    """\nGrayscale template match (TM_CCOEFF_NORMED).\nthreshold: 0..1 or 0..100\nReturns (ok: bool, score: float, loc: (x,y) or None)\n"""
    thr = float(threshold)
    thr = thr / 100.0 if thr > 1.0 else thr
    thr = max(0.0, min(1.0, thr))
    if roi is not None:
        x1, y1, x2, y2 = roi
        h, w = img_gray.shape[:2]
        x1, y1 = (max(0, x1), max(0, y1))
        x2, y2 = (min(w, x2), min(h, y2))
        if x2 <= x1 or y2 <= y1:
            return (False, 0.0, None)
        else:
            src = img_gray[y1:y2, x1:x2]
    else:
        src = img_gray
    tpl = imread_unicode(tpl_path, cv2.IMREAD_GRAYSCALE)
    if tpl is None or tpl.size == 0:
        return (False, 0.0, None)
    else:
        if src.shape[0] < tpl.shape[0] or src.shape[1] < tpl.shape[1]:
            return (False, 0.0, None)
        else:
            res = cv2.matchTemplate(src, tpl, cv2.TM_CCOEFF_NORMED)
            _, score, _, loc = cv2.minMaxLoc(res)
            return (score >= thr, float(score), loc)
def _match_color(image_bgr, tpl_path, threshold_pct, roi=None):
    """\nColor (BGR) template match with optional ROI.\nReturns (ok, score, center_xy) where score ∈ [0..1].\n"""
    thr = float(threshold_pct)
    thr = thr / 100.0 if thr > 1.0 else thr
    thr = max(0.0, min(1.0, thr))
    tpl = imread_unicode(tpl_path, cv2.IMREAD_COLOR)
    if tpl is None or tpl.size == 0:
        print(f'[CC] ❌ missing template: {tpl_path}')
        return (False, 0.0, None)
    else:
        src = image_bgr
        if roi:
            x1, y1, x2, y2 = roi
            h, w = image_bgr.shape[:2]
            x1, y1 = (max(0, x1), max(0, y1))
            x2, y2 = (min(w, x2), min(h, y2))
            if x2 <= x1 or y2 <= y1:
                print('[CC] ❌ invalid ROI after clamp')
                return (False, 0.0, None)
            else:
                src = image_bgr[y1:y2, x1:x2]
        th, tw = tpl.shape[:2]
        if src.shape[0] < th or src.shape[1] < tw:
            return (False, 0.0, None)
        else:
            res = cv2.matchTemplate(src, tpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            cx = max_loc[0] + tw // 2
            cy = max_loc[1] + th // 2
            if roi:
                cx += x1
                cy += y1
            ok = max_val >= thr
            return (ok, float(max_val), (cx, cy))
def _load_last_cc_tpl() -> str | None:
    try:
        if os.path.isfile(CLAN_CAPITAL_CACHE):
            name = open(CLAN_CAPITAL_CACHE, 'r', encoding='utf-8').read().strip()
            if not name:
                return None
            path = os.path.join(CLAN_CAPITAL_SCENERY_DIR, name)
            return name if os.path.isfile(path) else None
    except Exception:
        pass
    return None
def _save_last_cc_tpl(name: str) -> None:
    try:
        os.makedirs(os.path.dirname(CLAN_CAPITAL_CACHE), exist_ok=True)
        with open(CLAN_CAPITAL_CACHE, 'w', encoding='utf-8') as f:
            f.write(name)
    except Exception as e:
        print(f'[CLAN CAPITAL] cache save failed: {e}')
def _scan_all_cc_templates(roi_gray, threshold: float):
    """\nScan 1.png..44.png, return best passing candidate.\nReturns tuple (ok, name, score, loc, (h,w)).\nok=False if none meet threshold.\n"""
    best_name, best_score, best_loc, best_shape = (None, (-1.0), None, None)
    for i in range(1, 45):
        name = f'{i}.png'
        tpl_path = os.path.join(CLAN_CAPITAL_SCENERY_DIR, name)
        if not os.path.isfile(tpl_path):
            continue
        tpl = imread_unicode(tpl_path, cv2.IMREAD_GRAYSCALE)
        if tpl is None or tpl.size == 0:
            continue
        th_h, th_w = tpl.shape[:2]
        if roi_gray.shape[0] < th_h or roi_gray.shape[1] < th_w:
            continue
        try:
            res = cv2.matchTemplate(roi_gray, tpl, cv2.TM_CCOEFF_NORMED)
            _, score, _, loc = cv2.minMaxLoc(res)
        except cv2.error as e:
            print(f'[CLAN CAPITAL] OpenCV error on {name}: {e} → skipping')
            continue
        if score > best_score:
            best_score, best_name, best_loc, best_shape = (score, name, loc, (th_h, th_w))
    if best_name and best_score >= threshold:
        return (True, best_name, best_score, best_loc, best_shape)
    else:
        return (False, best_name, best_score, best_loc, best_shape)
def clan_capital(cfg, threshold: float=CLAN_CAPITAL_THRESH, _restart_depth: int=0) -> bool:
    """\nLogic:\n  1) Try cached template; tap if >= threshold.\n  2) Else rescan all; tap best if >= threshold and cache it.\n  3) After a successful tap → Phase 2 → Phase 3 → Phase 4 (verify + attack).\n  Returns True only if we found an available village AND Phase 4 started the attack.\n"""
    if not os.path.isdir(CLAN_CAPITAL_SCENERY_DIR):
        print(f'[CLAN CAPITAL] ❌ scenery dir not found: {CLAN_CAPITAL_SCENERY_DIR}')
        return False
    else:
        run_adb(['shell', 'input', 'swipe', '725', '574', '709', '193', '1000'])
        pause_event.wait()
        shot_path = take_screenshot('clan_capital.png')
        rsleep(0.5)
        pause_event.wait()
        img = imread_unicode(shot_path, cv2.IMREAD_GRAYSCALE)
        if img is None or img.size == 0:
            print('[CLAN CAPITAL] ❌ screenshot failed')
            return False
        else:
            pause_event.wait()
            x1, y1, x2, y2 = CLAN_CAPITAL_ROI
            h, w = img.shape[:2]
            x1, y1 = (max(0, x1), max(0, y1))
            x2, y2 = (min(w, x2), min(h, y2))
            pause_event.wait()
            if x2 <= x1 or y2 <= y1:
                print('[CLAN CAPITAL] ❌ invalid ROI after clamp')
                return False
            else:
                pause_event.wait()
                roi_gray = img[y1:y2, x1:x2]
                thr = max(0.0, min(1.0, float(threshold)))
                level = int(cfg.get('capital_hall_level', 9))
                pause_event.wait()
                cached = _load_last_cc_tpl()
                if cached:
                    tpl_path = os.path.join(CLAN_CAPITAL_SCENERY_DIR, cached)
                    tpl = imread_unicode(tpl_path, cv2.IMREAD_GRAYSCALE)
                    pause_event.wait()
                    if tpl is not None and tpl.size > 0 and (roi_gray.shape[0] >= tpl.shape[0]) and (roi_gray.shape[1] >= tpl.shape[1]):
                        try:
                            pause_event.wait()
                            res = cv2.matchTemplate(roi_gray, tpl, cv2.TM_CCOEFF_NORMED)
                            _, score, _, loc = cv2.minMaxLoc(res)
                        except cv2.error as e:
                            print(f'[CLAN CAPITAL] OpenCV error on cached {cached}: {e} → will rescan')
                            score = (-1.0)
                        if score >= thr:
                            pause_event.wait()
                            th_h, th_w = tpl.shape[:2]
                            cx = x1 + loc[0] + th_w // 2
                            cy = y1 + loc[1] + th_h // 2
                            rsleep(0.5)
                            pause_event.wait()
                            tap(cx, cy)
                            print(f'[CLAN CAPITAL] ✅ tapped (cached) {cached} at ({cx}, {cy})')
                            rsleep(0.5)
                            pause_event.wait()
                            if not clan_capital_phase2():
                                return False
                            else:
                                p3 = clan_capital_phase3(prev_img=None, capital_hall_level=level)
                                pause_event.wait()
                                status = p3.get('status')
                                if status == 'available_found':
                                    pause_event.wait()
                                    selected = p3.get('selected')
                                    if not selected:
                                        return False
                                    else:
                                        p4 = clan_capital_phase4(selected_village=selected, is_peak_unlocked=p3.get('peak_unlocked', False))
                                        pause_event.wait()
                                        st = p4.get('status')
                                        if st == 'attack_started':
                                            return True
                                        else:
                                            if st == 'attack_ready_timeout' and _restart_depth < 1:
                                                print('[CC] Attack-ready timeout → boot-recover and restart Clan Capital flow (one-time).')
                                                boot_recovery()
                                                ensure_home_base()
                                                tap(140, 606)
                                                rsleep(0.6)
                                                return clan_capital(cfg, threshold=threshold, _restart_depth=_restart_depth + 1)
                                            else:
                                                return False
                                else:
                                    return False
                    else:
                        print(f'[CLAN CAPITAL] cached template missing/unusable: {cached} → will rescan')
                ok, name, score, loc, shape = _scan_all_cc_templates(roi_gray, thr)
                if ok:
                    th_h, th_w = shape
                    cx = x1 + loc[0] + th_w // 2
                    cy = y1 + loc[1] + th_h // 2
                    rsleep(0.5)
                    tap(cx, cy)
                    print(f'[CLAN CAPITAL] ✅ tapped {name} at ({cx}, {cy})')
                    _save_last_cc_tpl(name)
                    rsleep(0.5)
                    if not clan_capital_phase2():
                        return False
                    else:
                        p3 = clan_capital_phase3(prev_img=None, capital_hall_level=level)
                        status = p3.get('status')
                        if status == 'available_found':
                            selected = p3.get('selected')
                            if not selected:
                                return False
                            else:
                                p4 = clan_capital_phase4(selected_village=selected, is_peak_unlocked=p3.get('peak_unlocked', False))
                                pause_event.wait()
                                st = p4.get('status')
                                if st == 'attack_started':
                                    return True
                                else:
                                    if st == 'attack_ready_timeout' and _restart_depth < 1:
                                        print('[CC] Attack-ready timeout → boot-recover and restart Clan Capital flow (one-time).')
                                        boot_recovery()
                                        ensure_home_base()
                                        tap(140, 606)
                                        rsleep(0.6)
                                        return clan_capital(cfg, threshold=threshold, _restart_depth=_restart_depth + 1)
                                    else:
                                        return False
                        else:
                            return False
                else:
                    print('[CLAN CAPITAL] No template met the threshold; no tap.')
                    return False
def clan_capital_phase2(threshold_pct: int=CC_THRESH_PCT) -> bool:
    """\nPhase 2 flow (runs right after Phase 1 tap):\n  - Validate Clan Capital page via 2 checks (color match @ 75%):\n      1) capital_trophy.png in ROI (1,106)-(160,246)\n      2) else capital_return.png in ROI (1,173)-(198,894)\n    If both fail → not in Clan Capital → skip (return False).\n\n  - Handle popups: repeatedly match full-screen capital_popup.png; if found, tap,\n    wait 0.5s, take new screenshot, and repeat until not found.\n\n  - Try capital_go.png on the **previous** screenshot; tap if found (per spec).\n\n  - Check game start on the **previous** screenshot:\n      ROI (1418,661)-(1593,747) with capital_game_start.png.\n      If pass → started (return True).\n      Else → not started → tap home (105,799) and return False.\n"""
    shot_path = take_screenshot('clan_capital_phase2.png')
    img = imread_unicode(shot_path, cv2.IMREAD_COLOR)
    if img is None or img.size == 0:
        print('[CC] ❌ screenshot failed')
        return False
    else:
        trophy_tpl = os.path.join(CLAN_CAPITAL_DIR, 'capital_trophy.png')
        return_tpl = os.path.join(CLAN_CAPITAL_DIR, 'capital_return.png')
        popup_tpl = os.path.join(CLAN_CAPITAL_DIR, 'capital_popup.png')
        go_tpl = os.path.join(CLAN_CAPITAL_DIR, 'capital_go.png')
        start_tpl = os.path.join(CLAN_CAPITAL_DIR, 'capital_game_start.png')
        start_tpl_2 = os.path.join(CLAN_CAPITAL_DIR, 'capital_game_start_2.png')
        ok, score, _ = _match_color(img, trophy_tpl, threshold_pct, roi=CC_V1_ROI)
        print(f'[CC] v1 trophy score={score:.2f} thr={float(threshold_pct) / 100.0:.2f}')
        if not ok:
            ok, score, _ = _match_color(img, return_tpl, threshold_pct, roi=CC_V2_ROI)
            print(f'[CC] v2 return score={score:.2f} thr={float(threshold_pct) / 100.0:.2f}')
            if not ok:
                print('[CC] Not on Clan Capital page → skip.')
                return False
        while True:
            ok, score, pos = _match_color(img, popup_tpl, threshold_pct, roi=None)
            print(f'[CC] popup score={score:.2f} thr={float(threshold_pct) / 100.0:.2f}')
            if not ok:
                break
            else:
                tap(*pos)
                rsleep(0.5)
                shot_path = take_screenshot('cc_after_popup.png')
                img = imread_unicode(shot_path, cv2.IMREAD_COLOR)
                if img is None or img.size == 0:
                    break
        ok, score, pos = _match_color(img, go_tpl, threshold_pct, roi=None)
        print(f'[CC] go score={score:.2f} thr={float(threshold_pct) / 100.0:.2f}')
        if ok and pos:
                tap(*pos)
        ok1, score1, _ = _match_color(img, start_tpl, threshold_pct, roi=CC_START_ROI)
        ok2, score2, _ = _match_color(img, start_tpl_2, threshold_pct, roi=CC_START_ROI)
        thr_f = float(threshold_pct) / 100.0
        print(f'[CC] start#1 score={score1:.2f}  start#2 score={score2:.2f}  thr={thr_f:.2f}')
        if ok1 or ok2:
            chosen = 'capital_game_start_2.png' if score2 >= score1 and ok2 else 'capital_game_start.png'
            print(f'[CC] ✅ Clan Capital game started (matched: {chosen}).')
            return True
        else:
            tap(*CC_HOME_TAP)
            print('[CC] ❌ Not started → returning home.')
            return False
def clan_capital_phase3(prev_img=None, capital_hall_level: int=9) -> dict:
    """\nPhase 3 (early-stop version):\n  - If no attacks (available_attacks.png), go home and return.\n  - Enter enemy map; verify (capital_enemy.png).\n  - Iterate unlocked villages in order; for each:\n      * If 3-star -> mark complete, close panel, continue.\n      * Else if \'available\' -> RETURN IMMEDIATELY (panel stays open).\n      * Else -> mark busy, close panel, continue.\n  - Capital Peak is only considered if all earlier unlocked villages are complete.\nReturns:\n  {\n    \"status\": \"available_found\" | \"no_attacks\" | \"enemy_verify_failed\" | \"ok\",\n    \"selected\": \"<village name>\" (when available_found),\n    \"selected_coord\": (x, y)     (when available_found),\n    \"available\": [...],\n    \"complete\":  [...],\n    \"busy\":      [...],\n    \"peak_unlocked\": bool\n  }\n"""
    summary = {'status': 'ok', 'selected': None, 'selected_coord': None, 'available': [], 'complete': [], 'busy': [], 'peak_unlocked': False}
    pause_event.wait()
    if prev_img is None:
        shot = take_screenshot('cc_phase3_pre.png')
        pause_event.wait()
        prev_img = imread_unicode(shot, cv2.IMREAD_COLOR)
        if prev_img is None or prev_img.size == 0:
            print('[CC P3] ❌ screenshot failed')
            summary['status'] = 'screenshot_failed'
            return summary
    pause_event.wait()
    avail_tpl = os.path.join(CLAN_CAPITAL_DIR, CC_TPL_AVAILABLE_ATKS)
    ok, score, _ = _match_color(prev_img, avail_tpl, 85, roi=CC_AVAIL_ATKS_ROI)
    pause_event.wait()
    print(f'[CC P3] available_attacks score={score:.2f} thr=0.85')
    if ok:
        tap(*CC_HOME_TAP)
        pause_event.wait()
        print('[CC P3] No attacks available → returning home.')
        summary['status'] = 'no_attacks'
        return summary
    else:
        tap(*CC_ENEMY_TAP)
        rsleep(0.5)
        pause_event.wait()
        x1, y1, x2, y2, dur = CC_ENEMY_SWIPE
        run_adb(['shell', 'input', 'swipe', str(x1), str(y1), str(x2), str(y2), str(dur)])
        pause_event.wait()
        shot = take_screenshot('cc_phase3_enemy.png')
        img = imread_unicode(shot, cv2.IMREAD_COLOR)
        enemy_tpl = os.path.join(CLAN_CAPITAL_DIR, CC_TPL_ENEMY_LAND)
        pause_event.wait()
        ok, score, _ = _match_color(img, enemy_tpl, 75, roi=None)
        print(f'[CC P3] enemy_land score={score:.2f} thr=0.75')
        if not ok:
            pause_event.wait()
            print('[CC P3] ❌ Enemy page verify failed → rebooting CoC')
            boot_recovery()
            summary['status'] = 'enemy_verify_failed'
            return summary
        else:
            pause_event.wait()
            unlocked = _villages_for_ch_level(capital_hall_level)
            earlier_all_complete = True
            for v in CC_VILLAGE_ORDER:
                if v not in unlocked:
                    continue
                else:
                    pause_event.wait()
                    if v == 'Capital Peak' and (not earlier_all_complete):
                            print('[CC P3] Capital Peak locked (earlier not 100%). Skipping.')
                            summary['peak_unlocked'] = False
                            break
                    pause_event.wait()
                    vx, vy = CC_VILLAGE_COORDS[v]
                    tap(vx, vy)
                    rsleep(0.5)
                    shot = take_screenshot(f'cc_village_{v.replace(' ', '_')}.png')
                    vimg = imread_unicode(shot, cv2.IMREAD_COLOR)
                    pause_event.wait()
                    if vimg is None or vimg.size == 0:
                        print(f'[CC P3] ❌ screenshot failed on {v} → skipping')
                        pause_event.wait()
                        tap(*CC_CLOSE_PANEL)
                        rsleep(0.5)
                        earlier_all_complete = False
                    else:
                        pause_event.wait()
                        star_tpl = os.path.join(CLAN_CAPITAL_DIR, CC_TPL_VILLAGE_3STAR)
                        ok_star, star_score, _ = _match_color(vimg, star_tpl, 90, roi=CC_VILLAGE_STAR_ROI)
                        print(f'[CC P3] {v}: 3star score={star_score:.2f} thr=0.90')
                        pause_event.wait()
                        if ok_star:
                            summary['complete'].append(v)
                            tap(*CC_CLOSE_PANEL)
                            rsleep(0.5)
                            earlier_all_complete = earlier_all_complete and True
                        else:
                            avail_tpl2 = os.path.join(CLAN_CAPITAL_DIR, CC_TPL_VILLAGE_AVAIL)
                            ok_avail, avail_score, _ = _match_color(vimg, avail_tpl2, 92, roi=CC_VILLAGE_AVAIL_ROI)
                            print(f'[CC P3] {v}: available score={avail_score:.2f} thr=0.92')
                            if ok_avail:
                                pause_event.wait()
                                summary['available'].append(v)
                                summary['status'] = 'available_found'
                                summary['selected'] = v
                                summary['selected_coord'] = (vx, vy)
                                summary['peak_unlocked'] = earlier_all_complete
                                print(f'[CC P3] ✅ First available target: {v} → stop scanning.')
                                return summary
                            else:
                                pause_event.wait()
                                summary['busy'].append(v)
                                tap(*CC_CLOSE_PANEL)
                                rsleep(0.5)
                                earlier_all_complete = False
            pause_event.wait()
            if 'Capital Peak' in unlocked:
                pause_event.wait()
                summary['peak_unlocked'] = earlier_all_complete
            print(f'[CC P3] Summary: available={summary['available']}, complete={summary['complete']}, busy={summary['busy']}, peak_unlocked={summary['peak_unlocked']}')
            pause_event.wait()
            return summary
def clan_capital_phase4(selected_village: str, prev_img=None, threshold_pct: int=75, retry_until_ready: bool=True, retry_delay: float=1.0, max_retries: int | None=None, is_peak_unlocked: bool=False) -> dict:
    # irreducible cflow, using cdg fallback
    """\nPhase 4 complete:\n  A) Verify army & spells (popup loop until ready).\n  B) Initiate attack, handle full-gold window.\n  C) Discover Spells/Troops icons in bottom panel and perform drops.\n\nReturns a summary:\n  {\n    \"status\": \"attack_started\" | \"not_ready\" | \"screenshot_failed\",\n    \"troops_found\": [filenames...],\n    \"spells_found\": [filenames...],\n    \"drops_done\": {\"spells\": int, \"troops\": int},\n    \"attempts\": int\n  }\n"""
    is_first_attack = False
    vname_canon = _canon(selected_village)
    if vname_canon == 'Capital Peak' and is_peak_unlocked:
            shot_pre = take_screenshot('cc_phase4_precheck.png')
            img_pre = imread_unicode(shot_pre, cv2.IMREAD_COLOR)
            if img_pre is not None and img_pre.size:
                    is_first_attack = _is_capital_peak_fresh(img_pre)
    pause_event.wait()
    tap(*CC_ARMY_WINDOW_TAP)
    rsleep(0.5)
    pause_event.wait()
    tpl_ready = os.path.join(CLAN_CAPITAL_DIR, CC_TPL_TROOPS_READY)
    thr = float(threshold_pct) / 100.0 if threshold_pct > 1 else float(threshold_pct)
    thr = max(0.0, min(1.0, thr))
    pause_event.wait()
    attempts = 0
    while True:
        pause_event.wait()
        shot_path = take_screenshot('cc_phase4_army.png')
        img_ready = imread_unicode(shot_path, cv2.IMREAD_COLOR)
        pause_event.wait()
        if img_ready is None or img_ready.size == 0:
            print('[CC P4] ❌ screenshot failed')
            return {'status': 'screenshot_failed', 'troops_found': [], 'spells_found': [], 'drops_done': {'spells': 0, 'troops': 0}, 'attempts': attempts}
        else:
            pause_event.wait()
            ok_troops, score_t, _ = _match_color(img_ready, tpl_ready, thr, roi=CC_TROOPS_ROI)
            print(f'[CC P4] troops score={score_t:.2f} thr={thr:.2f}')
            ok_spells, score_s, _ = _match_color(img_ready, tpl_ready, thr, roi=CC_SPELLS_ROI)
            print(f'[CC P4] spells score={score_s:.2f} thr={thr:.2f}')
            pause_event.wait()
            if ok_troops and ok_spells:
                break
            pause_event.wait()
            popup_warning('Army not ready: please fix troops or spells before attacking.', title='Clan Capital – Army Check')
            attempts += 1
            if not retry_until_ready or (max_retries is not None and attempts >= max_retries):
                return {'status': 'not_ready', 'troops_found': [], 'spells_found': [], 'drops_done': {'spells': 0, 'troops': 0}, 'attempts': attempts}
            time.sleep(retry_delay)
    pause_event.wait()
    rsleep(0.5)
    tap(*CC_ATTACK_TAP)
    rsleep(0.5)
    pause_event.wait()
    shot_gold = take_screenshot('cc_phase4_goldcheck.png')
    img_gold = imread_unicode(shot_gold, cv2.IMREAD_COLOR)
    pause_event.wait()
    gold_tpl = os.path.join(CLAN_CAPITAL_DIR, CC_TPL_FULL_GOLD_WINDOW)
    ok_gold, gold_score, _ = _match_color(img_gold, gold_tpl, 0.75, roi=CC_FULL_GOLD_ROI)
    print(f'[CC P4] full-gold win score={gold_score:.2f} thr=0.75')
    if ok_gold:
        tap(*CC_REINITIATE_TAP)
    rsleep(1.0)
    pause_event.wait()
    ar_tpl1 = os.path.join(CLAN_CAPITAL_DIR, 'capital_attack_ready.png')
    ar_tpl2 = os.path.join(CLAN_CAPITAL_DIR, 'capital_attack_ready_2.png')
    thr_f = 0.9
    MAX_READY_POLLS = 14
    attack_ready = False
    for poll in range(1, MAX_READY_POLLS + 1):
        pause_event.wait()
        shot_ar = take_screenshot('cc_phase4_attack_ready.png')
        img_ar = imread_unicode(shot_ar, cv2.IMREAD_GRAYSCALE)
        if img_ar is None or img_ar.size == 0:
            pause_event.wait()
            print(f'[CC P4] ❌ screenshot failed (attack-ready) [try {poll}/{MAX_READY_POLLS}]')
            rsleep(0.5)
        else:
            pause_event.wait()
            ok1, s1, _ = _match_gray(img_ar, ar_tpl1, thr_f, roi=CC_ATTACK_READY_ROI)
            ok2, s2, _ = _match_gray(img_ar, ar_tpl2, thr_f, roi=CC_ATTACK_READY_ROI)
            pause_event.wait()
            print(f'[CC P4] attack-ready #1 score={s1:.2f}  #2 score={s2:.2f}  thr={thr_f:.2f}  [try {poll}/{MAX_READY_POLLS}]')
            if ok1 or ok2:
                pause_event.wait()
                chosen = 'capital_attack_ready_2.png' if ok2 and s2 >= s1 else 'capital_attack_ready.png'
                print(f'[CC P4] ✅ attack-ready detected using {chosen}')
                rsleep(0.5)
                attack_ready = True
                break
            else:
                rsleep(0.7)
    if not attack_ready:
        print(f'[CC P4] ❌ attack-ready timeout after {MAX_READY_POLLS} tries → rebooting and restarting CC')
        boot_recovery()
        ensure_home_base()
        tap(140, 606)
        rsleep(0.6)
        return {'status': 'attack_ready_timeout', 'troops_found': [], 'spells_found': [], 'drops_done': {'spells': 0, 'troops': 0}, 'attempts': attempts}
    else:
        pause_event.wait()
        shot_panel = take_screenshot('cc_phase4_panel.png')
        img_panel = imread_unicode(shot_panel, cv2.IMREAD_COLOR)
        if img_panel is None or img_panel.size == 0:
            pause_event.wait()
            print('[CC P4] ❌ screenshot failed (panel)')
            return {'status': 'screenshot_failed', 'troops_found': [], 'spells_found': [], 'drops_done': {'spells': 0, 'troops': 0}, 'attempts': attempts}
        else:
            spells = _scan_icons_in_panel(img_panel, CC_DIR_SPELLS, CC_PANEL_ROI, threshold_pct=80)
            troops = _scan_icons_in_panel(img_panel, CC_DIR_TROOPS, CC_PANEL_ROI, threshold_pct=80)
            pause_event.wait()
            print(f'[CC P4] spells found: {list(spells.keys())}')
            print(f'[CC P4] troops found: {list(troops.keys())}')
            vname = _canon(selected_village)
            troop_drop = CC_TROOP_DROPPOINTS.get(vname)
            spell_points = CC_SPELL_DROPPOINTS.get(vname, [])
            pause_event.wait()
            drops_troops = 0
            if troops:
                shot_field = take_screenshot('cc_phase4_field.png')
                img_field = imread_unicode(shot_field, cv2.IMREAD_COLOR)
                if img_field is None or img_field.size == 0:
                    x1, y1, x2, y2 = _sorted_box(GLOW_TL, GLOW_BR)
                    base_drop_points = [((x1 + x2) // 2, (y1 + y2) // 2)]
                    stride = 2
                    print('[CC P4] Using fallback center point (no field image).')
                else:
                    if vname == 'Capital Peak':
                        poly_abs = _abs_poly_from_rel(img_field.shape, CP_GLOW_POLY_REL)
                        base_drop_points = get_glow_drop_points_poly(img_field, poly_abs, spacing=DROP_SPACING)
                        if not base_drop_points:
                            base_drop_points = get_glow_drop_points(img_field)
                        print(f'[CC P4] Capital Peak (regular-first) points: {len(base_drop_points)} found')
                    else:
                        base_drop_points = get_glow_drop_points(img_field)
                    if not base_drop_points:
                        x1, y1, x2, y2 = _sorted_box(GLOW_TL, GLOW_BR)
                        base_drop_points = [((x1 + x2) // 2, (y1 + y2) // 2)]
                    stride = 2
                    print(f'[CC P4] Using {('diamond' if vname == 'Capital Peak' else 'glow')} droppoints (n={len(base_drop_points)}), stride={stride}')
                if troop_drop and isinstance(troop_drop, tuple) and (len(troop_drop) == 2):
                    sminer_point = troop_drop
                else:
                    sminer_point = base_drop_points[0] if base_drop_points else None
                    if sminer_point is None:
                        x1, y1, x2, y2 = _sorted_box(GLOW_TL, GLOW_BR)
                        sminer_point = ((x1 + x2) // 2, (y1 + y2) // 2)
                k = 0
                for fname, (ix, iy, _) in troops.items():
                    tap(ix, iy)
                    taps = CC_TROOP_TAP_COUNTS.get(fname, 2)
                    if fname.lower() == 's_miner.png':
                        if vname == 'Capital Peak' and is_first_attack:
                            for t in range(taps):
                                px, py = CP_FIRST_DROPPOINTS[t % len(CP_FIRST_DROPPOINTS)]
                                tap(px, py)
                            drops_troops += taps
                            rsleep(0.45)
                        else:
                            for _ in range(taps):
                                tap(*sminer_point)
                            drops_troops += taps
                            rsleep(0.45)
                    else:
                        for _ in range(taps):
                            px, py = base_drop_points[k % len(base_drop_points)]
                            tap(px, py)
                            k = (k + stride) % len(base_drop_points)
                            rsleep(0.45)
                        drops_troops += taps
                        rsleep(0.45)
            pause_event.wait()
            drops_spells = 0
            if spells:
                if spell_points:
                    points_seq = spell_points[:]
                else:
                    x1, y1, x2, y2 = _sorted_box(GLOW_TL, GLOW_BR)
                    points_seq = [((x1 + x2) // 2, (y1 + y2) // 2)]
                random.shuffle(points_seq)
                def _is_jump_or_lightning(name: str) -> bool:
                    n = name.lower()
                    return 'jump' in n or 'lightning' in n or 'zap' in n
                for i, (fname, (ix, iy, _)) in enumerate(spells.items()):
                    taps_needed = 3 if _is_jump_or_lightning(fname) else 1
                    if not points_seq:
                        x1, y1, x2, y2 = _sorted_box(GLOW_TL, GLOW_BR)
                        points_seq = [((x1 + x2) // 2, (y1 + y2) // 2)]
                    for j in range(taps_needed):
                        tap(ix, iy)
                        rsleep(0.25)
                        idx = (i + j * 2) % len(points_seq)
                        px, py = points_seq[idx]
                        tap(px, py)
                        rsleep(0.35)
                        drops_spells += 1
                    rsleep(0.4)
            MAX_VERIFY_ROUNDS = 4
            thr_verify = 85
            def _is_jump_or_lightning(name: str) -> bool:
                n = name.lower()
                return 'jump' in n or 'lightning' in n or 'zap' in n
            orig_spell_names = set(spells.keys())
            orig_troop_names = set(troops.keys())
            cp_mode = 'regular' if vname == 'Capital Peak' else 'regular'
            switched_to_fixed = False
            prev_pending = None
            def _safe_playfield_points(pts, img_shape=None):
                if not pts:
                    return []
                else:
                    if img_shape is None:
                        y_panel_top = CC_PANEL_ROI[1]
                        W = None
                    else:
                        H, W = img_shape[:2]
                        y_panel_top = CC_PANEL_ROI[1]
                    y_max = max(0, y_panel_top - 8)
                    safe = []
                    for x, y in pts:
                        if W is not None:
                            x = min(W - 20, max(20, x))
                        if y >= y_max:
                            y = y_max - 1
                        safe.append((x, y))
                    return safe or pts
            for vr in range(MAX_VERIFY_ROUNDS):
                pause_event.wait()
                shot_v = take_screenshot('cc_phase4_panel_verify.png')
                img_v = imread_unicode(shot_v, cv2.IMREAD_COLOR)
                if img_v is None or img_v.size == 0:
                    print('[CC P4] Verify: screenshot failed; stopping verification.')
                    break
                else:
                    spells_left = _scan_icons_in_panel(img_v, CC_DIR_SPELLS, CC_PANEL_ROI, threshold_pct=thr_verify)
                    troops_left = _scan_icons_in_panel(img_v, CC_DIR_TROOPS, CC_PANEL_ROI, threshold_pct=thr_verify)
                    spells_redrop = {k: v for k, v in spells_left.items() if k in orig_spell_names}
                    troops_redrop = {k: v for k, v in troops_left.items() if k in orig_troop_names}
                    if not spells_redrop and (not troops_redrop):
                        print(f'[CC P4] ✅ Panel clear after {vr} verification round(s).')
                        break
                    else:
                        if vname == 'Capital Peak' and cp_mode == 'regular' and (troops_redrop or spells_redrop) and (not switched_to_fixed):
                                        cp_mode = 'fixed'
                                        switched_to_fixed = True
                                        print('[CC P4] Capital Peak fallback → switching to FIXED CP points for redrops.')
                        pending_key = (tuple(sorted(spells_redrop.keys())), tuple(sorted(troops_redrop.keys())), cp_mode)
                        if prev_pending == pending_key:
                            print('[CC P4] No progress between verification rounds; stopping to avoid loop.')
                            break
                        else:
                            prev_pending = pending_key
                            print(f'[CC P4] Re-dropping (round {vr + 1}, mode={cp_mode}): spells={list(spells_redrop.keys())}, troops={list(troops_redrop.keys())}')
                            shot_field_v = take_screenshot('cc_phase4_field_verify_src.png')
                            img_field_v = imread_unicode(shot_field_v, cv2.IMREAD_COLOR)
                            def _regular_points_round():
                                if img_field_v is None or img_field_v.size == 0:
                                    bx1, by1, bx2, by2 = _sorted_box(GLOW_TL, GLOW_BR)
                                    pts = [((bx1 + bx2) // 2, (by1 + by2) // 2)]
                                else:
                                    if vname == 'Capital Peak':
                                        poly_abs = _abs_poly_from_rel(img_field_v.shape, CP_GLOW_POLY_REL)
                                        pts = get_glow_drop_points_poly(img_field_v, poly_abs, spacing=DROP_SPACING)
                                        if not pts:
                                            pts = get_glow_drop_points(img_field_v)
                                        print(f'[CC P4] Redrop REGULAR points (Capital Peak, diamond): {len(pts)}')
                                    else:
                                        pts = get_glow_drop_points(img_field_v)
                                        print(f'[CC P4] Redrop REGULAR points: {len(pts)}')
                                pts = pts or [((_sorted_box(GLOW_TL, GLOW_BR)[0] + _sorted_box(GLOW_TL, GLOW_BR)[2]) // 2, (_sorted_box(GLOW_TL, GLOW_BR)[1] + _sorted_box(GLOW_TL, GLOW_BR)[3]) // 2)]
                                return _safe_playfield_points(pts, img_shape=img_field_v.shape if img_field_v is not None else None)
                            base_regular_points = _regular_points_round()
                            base_regular_stride = 2
                            if troop_drop and isinstance(troop_drop, tuple) and (len(troop_drop) == 2):
                                sminer_point = troop_drop
                            else:
                                sminer_point = base_regular_points[0] if base_regular_points else None
                                if sminer_point is None:
                                    bx1, by1, bx2, by2 = _sorted_box(GLOW_TL, GLOW_BR)
                                    sminer_point = ((bx1 + bx2) // 2, (by1 + by2) // 2)
                            if spells_redrop:
                                if spell_points:
                                    points_seq = _safe_playfield_points(spell_points, img_shape=img_v.shape)
                                else:
                                    bx1, by1, bx2, by2 = _sorted_box(GLOW_TL, GLOW_BR)
                                    points_seq = _safe_playfield_points([((bx1 + bx2) // 2, (by1 + by2) // 2)], img_shape=img_v.shape)
                                random.shuffle(points_seq)
                                for i, (fname, (ix, iy, _)) in enumerate(spells_redrop.items()):
                                    taps_needed = 3 if _is_jump_or_lightning(fname) else 1
                                    for j in range(taps_needed):
                                        tap(ix, iy)
                                        rsleep(0.25)
                                        idx = (i + j * 2) % len(points_seq)
                                        px, py = points_seq[idx]
                                        tap(px, py)
                                        rsleep(0.35)
                                        drops_spells += 1
                                    rsleep(0.4)
                            k = 0
                            if troops_redrop:
                                for fname, (ix, iy, _) in troops_redrop.items():
                                    taps = CC_TROOP_TAP_COUNTS.get(fname, 2)
                                    tap(ix, iy)
                                    rsleep(0.15)
                                    fname_lower = fname.lower()
                                    if cp_mode == 'fixed' and vname == 'Capital Peak':
                                        for t in range(taps):
                                            px, py = CP_FIRST_DROPPOINTS[t % len(CP_FIRST_DROPPOINTS)]
                                            x1p, y1p, x2p, y2p = CC_PANEL_ROI
                                            py = min(py, y1p - 1)
                                            if fname_lower == 's_miner.png':
                                                tap(px, py)
                                                drops_troops += 1
                                            else:
                                                if t == 0:
                                                    tap(px, py)
                                                    tap(px, py)
                                                    drops_troops += 2
                                                else:
                                                    tap(px, py)
                                                    drops_troops += 1
                                                rsleep(0.4)
                                        rsleep(0.45)
                                    else:
                                        if fname_lower == 's_miner.png':
                                            target = base_regular_points[0] if base_regular_points else sminer_point
                                            for _ in range(taps):
                                                tap(*target)
                                                drops_troops += 1
                                            rsleep(0.45)
                                        else:
                                            for t in range(taps):
                                                if not base_regular_points:
                                                    bx1, by1, bx2, by2 = _sorted_box(GLOW_TL, GLOW_BR)
                                                    px, py = ((bx1 + bx2) // 2, (by1 + by2) // 2)
                                                    py = min(py, CC_PANEL_ROI[1] - 1)
                                                else:
                                                    px, py = base_regular_points[k % len(base_regular_points)]
                                                    k = (k + base_regular_stride) % max(1, len(base_regular_points))
                                                if t == 0:
                                                    tap(px, py)
                                                    tap(px, py)
                                                    drops_troops += 2
                                                else:
                                                    tap(px, py)
                                                    drops_troops += 1
                                                rsleep(0.4)
                                            rsleep(0.45)
            return {'status': 'attack_started', 'troops_found': list(troops.keys()), 'spells_found': list(spells.keys()), 'drops_done': {'spells': drops_spells, 'troops': drops_troops}, 'attempts': attempts}
def _is_capital_peak_fresh(img_bgr) -> bool:
    """Return True if the Capital Peak is fresh (nobody has attacked yet)."""
    ok, score, _ = _match_color(img_bgr, CP_FRESH_TEMPLATE, int(CP_FRESH_THRESHOLD * 100), roi=None)
    print(f'[CC P4] Capital Peak fresh score={score:.2f} thr={CP_FRESH_THRESHOLD:.2f}')
    return ok
def tap(x: int, y: int, device: str=None) -> bool:
    """\nSends an ADB tap event at (x, y) on the given emulator/device.\nReturns True on success.\n"""
    pause_event.wait()          # строгая пауза: заморозка на ближайшем тапе (если нажали Pause)
    device = device or host
    if device is None:
        raise RuntimeError('ADB target device is not set!  Make sure choose_emulator() has run.')
    # анти-бан: лёгкий случайный сдвиг точки + микропауза после (кнопки/иконки
    # крупные, ±несколько px не мешают попаданию). Параметры — config/antiban.json.
    j = ANTIBAN['tap_jitter_px']
    if j > 0:
        x = int(x) + random.randint(-j, j)
        y = int(y) + random.randint(-j, j)
    proc = subprocess.run([ADB_BIN, '-s', device, 'shell', 'input', 'tap', str(x), str(y)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
    _d0, _d1 = ANTIBAN['tap_delay_sec']
    time.sleep(random.uniform(_d0, _d1))
    return proc.returncode == 0


def transition_delay():
    """Случайная человекоподобная пауза между ПЕРЕХОДАМИ (сменами экрана/фазы цикла).
    Диапазон — config/antiban.json (transition_delay_sec, дефолт 2–6с). Прерывается stop/pause."""
    pause_event.wait()
    lo, hi = ANTIBAN['transition_delay_sec']
    stop_event.wait(timeout=random.uniform(lo, hi))


def rsleep(sec, jitter=0.3):
    """Человекоподобная задержка: базовое `sec` ± jitter (по умолчанию ±30%). Замена фиксированного
    time.sleep, чтобы паузы не были одинаковыми (анти-бан). Прерывается stop."""
    sec = float(sec)
    stop_event.wait(timeout=random.uniform(max(0.0, sec * (1.0 - jitter)), sec * (1.0 + jitter)))


def human_between_cycles():
    """Пауза между циклами + иногда длинный «перерыв» (анти-бан). Прерывается stop."""
    lo, hi = ANTIBAN['between_cycles_sec']
    total = random.uniform(lo, hi)
    if random.random() < ANTIBAN['break_chance']:
        blo, bhi = ANTIBAN['break_sec']
        total += random.uniform(blo, bhi)
        print(f'[ANTIBAN] long break ~{total:.0f}s')
    else:
        print(f'[ANTIBAN] pause between cycles {total:.0f}s')
    stop_event.wait(timeout=total)
def _match_template(img, tmpl_path, region, thresh):
    """\nReturn (score, cx, cy)   – score ∈ [0,1]; (None,None) if no match.\n"""
    x1, y1, x2, y2 = region
    h, w = img.shape[:2]
    x1, y1 = (max(0, x1), max(0, y1))
    x2, y2 = (min(w, x2), min(h, y2))
    if x2 <= x1 or y2 <= y1:
        return (0, None, None)
    else:
        roi = img[y1:y2, x1:x2]
        tmpl = load_template(tmpl_path, cv2.IMREAD_UNCHANGED)
        if tmpl is None:
            raise FileNotFoundError(f'template not found: {tmpl_path}')
        else:
            if tmpl.ndim == 3 and tmpl.shape[2] == 4:
                tmpl = cv2.cvtColor(tmpl, cv2.COLOR_BGRA2BGR)
            if roi.ndim == 3 and roi.shape[2] == 4:
                roi = cv2.cvtColor(roi, cv2.COLOR_BGRA2BGR)
            roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi
            tmpl_gray = cv2.cvtColor(tmpl, cv2.COLOR_BGR2GRAY) if tmpl.ndim == 3 else tmpl
            if roi_gray.shape[0] < tmpl_gray.shape[0] or roi_gray.shape[1] < tmpl_gray.shape[1]:
                return (0, None, None)
            else:
                res = cv2.matchTemplate(roi_gray, tmpl_gray, cv2.TM_CCOEFF_NORMED)
                _, score, _, loc = cv2.minMaxLoc(res)
                if score < thresh:
                    return (score, None, None)
                else:
                    cx = x1 + loc[0] + tmpl_gray.shape[1] // 2
                    cy = y1 + loc[1] + tmpl_gray.shape[0] // 2
                    return (score, cx, cy)
def treasure_event():
    hammer_tmpl = Path(TEMPLATE_DIR) / 'hammer.png'
    continue_tmpl = Path(TEMPLATE_DIR) / 'continue.png'
    print('Checking if treasure event is active. . .')
    img = capture_array()
    rsleep(0.2)
    hammer_score, _, _ = _match_template(img, hammer_tmpl, region=(622, 710, 964, 809), thresh=0.8)
    if hammer_score >= 0.8:
        print('Treasure event detected.')
        print('tapping. . . ')
        for _ in range(4):
            rsleep(0.2)
            tap(273, 643)
    else:
        return None
    rsleep(4)
    print('Treasure open successfully.')
    print('Going home. . .')
    tap(788, 751)
def is_next_button_present() -> bool:
    """\nGrabs a fresh screenshot as \'is_next_button.png\' then\nchecks for the Next button via template matching.\n"""
    img = capture_array()
    if img is None:
        print('❌ Could not capture screenshot for Next-button check')
        return False
    else:
        x1, y1, x2, y2 = NEXT_BTN_REGION
        roi = img[y1:y2, x1:x2]
        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        tpl = load_template(NEXT_BTN_TEMPLATE, cv2.IMREAD_GRAYSCALE)
        if tpl is None:
            print(f'❌ Cannot load template \'{NEXT_BTN_TEMPLATE}\'')
            return False
        else:
            res = cv2.matchTemplate(gray_roi, tpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            print(f'    [DEBUG] Next-btn match score: {max_val:.2f}')
            return max_val >= NEXT_THRESH
def connection_popup_visible() -> bool:
    img = capture_array()
    if img is None:
        return False
    else:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
        if img is None:
            return False
        else:
            for tmpl_name in TEMPLATE_FILES:
                tpl_path = os.path.join(TEMPLATE_DIR, tmpl_name)
                tpl = load_template(tpl_path, cv2.IMREAD_GRAYSCALE)
                if tpl is None:
                    print(f'❌ Missing template: {tpl_path}')
                else:
                    res = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, _ = cv2.minMaxLoc(res)
                    if max_val >= THRESHOLD:
                        print(f'[OK] Detected “{tmpl_name}” (score={max_val:.2f})')
                        return True
            return False
def wait_for_scout_screen(timeout=20, interval=2, threshold=0.7) -> bool:
    # irreducible cflow, using cdg fallback
    """\nWaits for the scouting UI by template-matching \'end_battle.png\'\nin the region x1=2, y1=612, x2=222, y2=724.\n"""
    print('[WAIT] Scouting UI loading…')
    start = time.time()
    tpl = load_template(END_BATTLE_TEMPLATE, cv2.IMREAD_GRAYSCALE)
    tpl_h, tpl_w = tpl.shape
    x1, y1, x2, y2 = (2, 612, 222, 724)
    while time.time() - start < timeout:
        rsleep(1.5)
        img = capture_array()
        if img is None:
            print('❌ Screenshot failed.')
            time.sleep(interval)
            continue
        roi = img[y1:y2, x1:x2]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        res = cv2.matchTemplate(gray, tpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)
        if max_val >= threshold:
            print('[OK] Scouting UI detected.')
            rsleep(0.6)
            return True
        time.sleep(interval)
    print('[WARN] Scouting UI never detected.')
    return False
RETURN_HOME_TEMPLATE = os.path.join(TEMPLATE_DIR, 'return_home.png')
CLAIM_REWARD_TEMPLATE = os.path.join(TEMPLATE_DIR, 'claim_reward.png')
RETURN_HOME_REGION = (650, 725, 940, 815)
# Ивент-карточки награды после боя: «Tap!» (скретч-карточка) → «Continue» (награда)
EVENT_TAP_CARD_TEMPLATE = os.path.join(TEMPLATE_DIR, 'event_tap_card.png')
EVENT_TAP_REGION = (650, 80, 950, 170)
EVENT_CARD_CENTER = (790, 445)
EVENT_CONTINUE_TEMPLATE = os.path.join(TEMPLATE_DIR, 'event_continue.png')
EVENT_CONTINUE_REGION = (600, 740, 950, 830)
EVENT_CONTINUE_CENTER = (768, 785)


def battle_ended() -> bool:
    # Конец боя = зелёная кнопка внизу: «Return Home» ИЛИ (во время ивента) «Claim
    # Reward» — обе в том же регионе, тап return_home() (788,768) попадает в любую.
    img = capture_array()
    if img is None:
        return False
    for tpl in (RETURN_HOME_TEMPLATE, CLAIM_REWARD_TEMPLATE):
        score, _, _ = _match_template(img, tpl, region=RETURN_HOME_REGION, thresh=0.8)
        if score >= 0.8:
            print('\n🏁 Battle ended')
            return True
    return False


def claim_event_cards(max_loops=20):
    """Ивент после боя: карточки-награды (не всегда). Карточку с «Tap!» надо СКРЕТЧИТЬ
    (несколько тапов по центру), затем показывается награда с кнопкой «Continue».
    Карточек может быть несколько. Обрабатываем по состоянию, пока есть Tap!/Continue,
    потом выходим (вернёмся на базу)."""
    empty = 0
    for _ in range(max_loops):
        img = capture_array()
        if img is None:
            return
        tap_score, _, _ = _match_template(img, EVENT_TAP_CARD_TEMPLATE,
                                          region=EVENT_TAP_REGION, thresh=0.7)
        if tap_score >= 0.7:
            empty = 0
            print('🎴 Event card — scratching')
            for _ in range(4):                   # скретч: несколько тапов по центру
                tap(*EVENT_CARD_CENTER)
                rsleep(0.4)
            rsleep(0.8)
            continue
        cont_score, _, _ = _match_template(img, EVENT_CONTINUE_TEMPLATE,
                                           region=EVENT_CONTINUE_REGION, thresh=0.8)
        if cont_score >= 0.8:
            empty = 0
            print('🎁 Event reward — Continue')
            tap(*EVENT_CONTINUE_CENTER)
            rsleep(1.5)
            continue
        # ни карточки, ни награды — возможно анимация вскрытия; подтолкнём тапом центра
        empty += 1
        if empty >= 4:
            return                               # похоже, награды кончились — выходим
        tap(*EVENT_CARD_CENTER)
        rsleep(1.0)
def wait_battle_end():
    """\nWaits up to MAX_WAIT_BATTLE seconds for the battle to finish,\nprinting a single-line countdown via \'\r\'.\n"""
    print('⏳ Waiting for battle to finish…')
    start_time = time.time()
    while True:
        if connection_popup_visible():
            print('\n[WARN] Connection lost detected—recovering…')
            boot_recovery()
            return
        if battle_ended():
            print()
            return
        elapsed = time.time() - start_time
        if elapsed >= MAX_WAIT_BATTLE:
            sys.stdout.write('\r⏰ Timeout—forcing Return Home.\n')
            sys.stdout.flush()
            return
        if connection_popup_visible():
            print('\n[WARN] Connection lost detected—recovering…')
            boot_recovery()
            return
        rsleep(1)
emulator_key = globals().get('emulator_key', None)
ld_index = globals().get('ld_index', 0)
ld_name = globals().get('ld_name', None)
host = globals().get('host', None)
def setup_emulator():
    key = globals().get('emulator_key', None)
    if not key:
        h = globals().get('host', None)
        if h == MEMU:
            key = 'memu'
        else:
            if h == BLUESTACKS:
                key = 'bluestacks'
    if not key:
        raise RuntimeError('No emulator selected for setup_emulator()')
    else:
        # BlueStacks: приватный порт adb-сервера бота, чтобы ЧУЖИЕ adb (системный/MEmu,
        # v41) не убивали наш сервер (HD-Adb v36) на общем 5037 → device offline/not found.
        if key == 'bluestacks':
            os.environ['ANDROID_ADB_SERVER_PORT'] = str(syscfg.emu('bluestacks', 'adb_server_port', 5137))
        if key == 'memu':
            # memu_index задан (через «MEmu Multi-Instance») → пер-инстансный путь;
            # None (обычная кнопка MEmu) → прежний дефолт (инстанс 0, host 21503).
            ensure_memu(index=globals().get('memu_index', None))
        else:
            if key == 'bluestacks':
                ensure_bluestacks()
            else:
                if key == 'ldplayer':
                    idx = globals().get('ld_index', 0)
                    ensure_ldplayer(index=idx)
                else:
                    raise RuntimeError(f'Unsupported emulator: {key}')
        print('▶ Checking if Clash of Clans is installed…')
        try:
            pkg_list = subprocess.check_output([ADB_BIN, '-s', host, 'shell', 'pm', 'list', 'packages', 'com.supercell.clashofclans'], stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW).decode().strip()
        except subprocess.CalledProcessError:
            pkg_list = ''
        if 'com.supercell.clashofclans' not in pkg_list:
            print('❌ Clash of Clans is not installed. Please install it and retry.')
            sys.exit(1)
        pkg = 'com.supercell.clashofclans'
        print('▶ Launching Clash of Clans…')
        try:
            pid = subprocess.check_output([ADB_BIN, '-s', host, 'shell', 'pidof', pkg], stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW).decode().strip()
        except subprocess.CalledProcessError:
            pid = ''
        if pid:
            print(f'🔄 Clash of Clans is running (pid={pid})—restarting...')
            subprocess.run([ADB_BIN, '-s', host, 'shell', 'am', 'force-stop', pkg], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
            rsleep(1)
        # Кросс-версийный запуск: Android 14/LDPlayer 14 без `monkey` → am start по активности.
        from app_launch import launch_app
        launch_app(host, pkg)
        print('✅ Clash of Clans should now be in the foreground.')
stop_event = threading.Event()
pause_event = threading.Event()
pause_event.set()
def pause_bot():
    """Call this to pause the bot."""
    pause_event.clear()
    print('---------PAUSE---------')
def resume_bot():
    """Call this to resume a paused bot."""
    pause_event.set()
    print('---------RESUME---------')
def _check_stop():
    """Return True if we should abort the current step."""
    return stop_event.is_set()
def get_stars_from_screen() -> int:
    rsleep(0.5)
    shot = take_screenshot('resources_gained.png')
    rsleep(0.5)
    img = imread_unicode(shot)
    if img is None:
        return 0
    else:
        def _match(tpl_name: str, roi_tuple) -> bool:
            x1, y1, x2, y2 = roi_tuple
            roi = img[y1:y2, x1:x2]
            tpl_path = os.path.join(TEMPLATE_DIR, tpl_name)
            tpl = imread_unicode(tpl_path)
            if tpl is None or roi.size == 0:
                print(f'[DEBUG] {tpl_name}: template/ROI missing')
                return False
            else:
                res = cv2.matchTemplate(roi, tpl, cv2.TM_CCOEFF_NORMED)
                _, score, _, _ = cv2.minMaxLoc(res)
                return score >= 0.4
        if not _match('one_star.png', (518, 90, 747, 316)):
            return 0
        else:
            if not _match('two_star.png', (670, 106, 926, 285)):
                return 1
            else:
                if _match('three_star.png', (840, 96, 1064, 317)):
                    return 3
                else:
                    return 2
def gain_resources(stars: int) -> tuple[int, int, int]:
    """\nRead the GOLD / ELIXIR / DARK-ELIXIR gained on the battle-end screen.\n\nReturns (gold, elixir, dark_elixir), each an *int*.\nIf OCR fails on any field, that field falls back to 0.\n"""
    rsleep(0.5)
    img = capture_array()
    if img is None:
        return (0, 0, 0)
    else:
        def _read(x1, y1, x2, y2) -> int:
            """Число внутри ROI (digit_ocr) или 0."""
            return digit_ocr.read_int(img[y1:y2, x1:x2]) or 0
        gold_left = _read(586, 372, 825, 420)
        elixir_left = _read(590, 431, 827, 482)
        de_left = _read(643, 489, 826, 539)
        if stars > 0:
            gold_right = _read(1012, 444, 1176, 490)
            elixir_right = _read(1016, 493, 1176, 537)
            de_right = _read(1036, 541, 1176, 584)
        else:
            gold_right = elixir_right = de_right = 0
        return (gold_left + gold_right, elixir_left + elixir_right, de_left + de_right)
def zero_all_stats_files() -> None:
    """\nOverwrite profiles/Village_<n>_stats.json (n = 1..MAX_VILLAGES)\nwith an all-zero dictionary.\n"""
    zeroed = {'gold': 0, 'elixir': 0, 'de': 0, 'attacks': 0, 'stars': {'0': 0, '1': 0, '2': 0, '3': 0}, 'last_update_ts': 0}
    profiles_dir = Path(BASE_DIR) / 'profiles'
    profiles_dir.mkdir(parents=True, exist_ok=True)
    for vidx in range(1, MAX_VILLAGES + 1):
        path = profiles_dir / f'Stats_{vidx}.json'
        try:
            with path.open('w') as fh:
                json.dump(zeroed, fh, indent=2)
        except Exception as e:
            print(f'[ERROR] could not reset {path}: {e}')
def _stats_file_path(village_idx: int) -> Path:
    """\nReturn the Path to “profiles/Village_{village_idx}_stats.json”.\nCreates the directory if it does not exist.\n"""
    base_path = Path(BASE_DIR)
    profiles_dir = base_path / 'profiles'
    profiles_dir.mkdir(exist_ok=True)
    return profiles_dir / f'Stats_{village_idx}.json'
def _load_stats_from_disk(village_idx: int) -> dict:
    """\nRead and return the JSON-loaded dict for that village.\nIf the file doesn’t exist or is invalid, return defaults.\n"""
    path = _stats_file_path(village_idx)
    if not path.exists():
        return {'gold': 0, 'elixir': 0, 'de': 0, 'attacks': 0, 'stars': {'0': 0, '1': 0, '2': 0, '3': 0}, 'last_update_ts': 0}
    else:
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            data.setdefault('gold', 0)
            data.setdefault('elixir', 0)
            data.setdefault('de', 0)
            data.setdefault('attacks', 0)
            data.setdefault('stars', {'0': 0, '1': 0, '2': 0, '3': 0})
            data.setdefault('last_update_ts', 0)
            return data
        except Exception:
            return {'gold': 0, 'elixir': 0, 'de': 0, 'attacks': 0, 'stars': {'0': 0, '1': 0, '2': 0, '3': 0}, 'last_update_ts': 0}
# Полные хранилища → сон (параметры в config/farming.json)
FARM_HUD_REGIONS = {'gold': (1247, 24, 1504, 68), 'elixir': (1247, 110, 1532, 176),
                    'dark': (1247, 192, 1540, 246)}


def _load_farming_cfg():
    import json
    try:
        with open(os.path.join(BASE_DIR, 'config', 'farming.json'), encoding='utf-8') as f:
            d = json.load(f)
    except Exception:
        d = {}
    return {'enabled': bool(d.get('enabled', True)),
            'gold': int(d.get('gold', 0)), 'elixir': int(d.get('elixir', 0)),
            'dark': int(d.get('dark', 0)), 'sleep_min': tuple(d.get('sleep_minutes', [30, 60]))}


def _village_profile_from_cfg(c):
    """Профиль деревни (Village_N.json) из текущего GUI-конфига — фолбэк, если юзер
    не сохранил деревню кнопкой Save. Берём только per-village ключи."""
    keys = ('gold_threshold', 'elixir_threshold', 'dark_elixir_threshold', 'upgrade_wall',
            'wall_level', 'wall_level_from', 'wall_level_to', 'wall_gold_threshold',
            'wall_elixir_threshold', 'request_troops', 'attack', 'train_mode', 'quick_slot',
            'enable_clan_games', 'enable_clan_capital', 'capital_hall_level', 'enable_stats')
    return {k: c[k] for k in keys if k in c}


# Ресурс-бары (1600×900) — по ШКАЛЕ ЗАПОЛНЕНИЯ, а не по числу: полный бар залит целиком,
# у неполного справа тёмный «пустой» хвост. Надёжно, без OCR и знания вместимости (у всех
# аккаунтов разная). Регионы = внутренняя область бара (без иконки/цифр по краям).
RESOURCE_BARS = {'gold': (1345, 34, 1512, 74), 'elixir': (1345, 118, 1512, 158),
                 'dark': (1345, 198, 1512, 238)}
BAR_EMPTY_FULL_THRESH = 0.06     # доля пустых столбцов меньше → бар считаем полным


def _bar_empty_frac(img, region):
    """Доля «пустых» (тёмных, незаполненных) столбцов бара. Полный бар → ~0."""
    x0, y0, x1, y1 = region
    reg = img[y0:y1, x0:x1].astype('int16')
    b, g, r = reg[:, :, 0], reg[:, :, 1], reg[:, :, 2]
    bright = (b + g + r) / 3
    empty = (bright < 95) & (b >= r - 10)          # тёмная незаполненная часть бара
    col_empty = empty.mean(axis=0) > 0.5           # столбец пустой
    return float(col_empty.mean())


# Тёмный бар — заливка ФИОЛЕТОВАЯ (сам DE тёмно-фиол.), растёт справа-налево. Меряем долю
# фиолетовых столбцов по тонким полосам БЕЗ цифр (цифры белые в центре бара). Калибровано:
# мало→0.00, ~77%→0.47, полный→0.98. Кэп знать не нужно (меряем визуальную заливку).
DARK_BAR_X = (1345, 1512)
DARK_BAR_STRIPS = ((201, 207), (232, 238))         # верх/низ бара, вне числа
DARK_FULL_THRESH = 0.90


def _dark_bar_fill(img):
    """Доля заполнения тёмного бара (0..1) по фиолетовой заливке. Полный ≈ 0.98."""
    x0, x1 = DARK_BAR_X
    best = 0.0
    for y0, y1 in DARK_BAR_STRIPS:
        reg = img[y0:y1, x0:x1].astype('int16')
        b, g, r = reg[:, :, 0], reg[:, :, 1], reg[:, :, 2]
        purple = (r > g + 10) & (b > g + 10) & ((b + g + r) / 3 < 175)
        best = max(best, float((purple.mean(axis=0) > 0.4).mean()))
    return best


# Золото/эликсир: их бары в CoC НЕ показывают уровень (залиты цветом целиком при любом
# количестве — проверено: 19.2M и 17.5M читаются как полные). Поэтому «полно» ловим по
# ПЕРЕСТАЛО РАСТИ: farming капнутое хранилище не увеличивает. Число читаем digit_ocr
# (надёжно). Состояние по (аккаунт, ресурс), т.к. значения у аккаунтов разные.
_res_max = {}                                       # (vidx, key) -> макс. виденное значение
_res_stall = {}                                     # (vidx, key) -> проверок подряд без роста
FULL_STALL_CYCLES = 3                               # столько проверок без роста → полно


def _resource_full_by_growth(vidx, key, value):
    """True, если ресурс перестал расти (капнут). Заметный рост (новый максимум) → не полно
    и сброс счётчика; иначе счётчик++, полно после FULL_STALL_CYCLES."""
    k = (vidx, key)
    prev = _res_max.get(k, -1)
    if value > prev + max(2000, int(prev * 0.005)):  # заметный рост → ещё фармим
        _res_max[k] = value
        _res_stall[k] = 0
        return False
    if value > prev:
        _res_max[k] = value
    _res_stall[k] = _res_stall.get(k, 0) + 1
    return _res_stall[k] >= FULL_STALL_CYCLES


def read_storages_full(vidx=1):
    """Полны ли ВСЕ отмеченные хранилища. gold/elixir — по «перестало расти» (их бары уровень
    не показывают), dark — по ЗАЛИВКЕ бара (фиолетовая). config/farming.json: gold/elixir/dark
    > 0 → учитывать ресурс, 0 → нет. Возвращает {full, fills, sleep_min} или None."""
    cfg = _load_farming_cfg()
    if not cfg['enabled']:
        return None
    img = capture_array()
    if img is None:
        return None
    fills, full, any_checked = {}, True, False
    for key in ('gold', 'elixir'):
        if cfg[key] <= 0:
            continue
        any_checked = True
        x1, y1, x2, y2 = FARM_HUD_REGIONS[key]
        val = digit_ocr.read_int(img[y1:y2, x1:x2]) or 0
        fills[key] = val
        if not _resource_full_by_growth(vidx, key, val):
            full = False
    if cfg['dark'] > 0:                              # тёмное — по заливке (растёт справа)
        any_checked = True
        dfill = _dark_bar_fill(img)
        fills['dark'] = round(dfill, 2)
        if dfill < DARK_FULL_THRESH:
            full = False
    if not any_checked:
        return None                                 # ни один ресурс не отмечен — не спим
    dbg = {k: (v if k == 'dark' else f"{v}/stall{_res_stall.get((vidx, k), 0)}/{FULL_STALL_CYCLES}")
           for k, v in fills.items()}
    print(f"[STORAGE] {dbg} full={full}")
    return {'full': full, 'fills': fills, 'sleep_min': cfg['sleep_min']}


def _sleep_storages_full(info):
    """Уснуть на случайное время (config/farming.json sleep_minutes). Прерывается
    по stop_event."""
    lo, hi = info['sleep_min']
    mins = random.uniform(lo, hi)
    print(f"[SLEEP] storages full (fills {info['fills']}) → sleeping {mins:.0f} min")
    stop_event.wait(timeout=mins * 60)


def one_cycle(cfg):
    """One attack cycle, abortable and recoverable at each micro-step."""
    global _cycle_count
    global _saved_wall_offset
    global wall_save
    pause_event.wait()
    if _check_stop():
        print('[INFO] Cycle aborted before home-prep')
        _saved_wall_offset = None
        wall_save = False
        return
    treasure_event()
    transition_delay()                    # человекоподобная пауза между переходами (2–6с)
    pause_event.wait()
    ensure_home_base()
    tap(140, 606)
    if connection_popup_visible():
        print('[WARN] Connection lost → recovering')
        boot_recovery()
        return
    if _check_stop():
        print('[INFO] Cycle aborted before prep')
        _saved_wall_offset = None
        wall_save = False
        return
    # полные хранилища (config/farming.json): при мультиаккаунте — принудительно
    # менять аккаунт СЕЙЧАС (не ждать интервал), иначе — уходить в сон.
    _st = read_storages_full(cfg.get('current_village_idx', 1))
    if _st and _st['full']:
        if cfg.get('enable_multi_account'):
            print(f"[INFO] storages full (fills {_st['fills']}) → forcing account switch")
            return 'STORAGES_FULL'
        _sleep_storages_full(_st)
        return
    transition_delay()                    # пауза перед зумом (переход)
    print('ZOOMING OUT . . .')
    pause_event.wait()
    multi_zoom_out(host)
    transition_delay()                    # пауза после зума перед следующей фазой
    if cfg.get('enable_clan_capital', False):
        while not _check_stop():
            pause_event.wait()
            started = clan_capital(cfg)
            if not started:
                print('[CC] No attacks available or CC not ready → exiting CC loop.')
                break
            rsleep(1.0)
            print('[CC] Rebooting Clash for next CC pass…')
            boot_recovery()
            if _check_stop():
                break
            pause_event.wait()
            print('[CC] Ensuring home base…')
            ensure_home_base()
            tap(140, 606)
            rsleep(0.5)
            print('[CC] Zooming out for next CC run…')
            pause_event.wait()
            try:
                multi_zoom_out(host)
            except Exception as e:
                print(f'[CC] Zoom-out failed: {e}')
                break
            if connection_popup_visible():
                print('[CC] Connection lost → recovering')
                boot_recovery()
                break
    if connection_popup_visible():
        print('[WARN] Connection lost → recovering')
        boot_recovery()
        return
    if _check_stop():
        print('[INFO] Cycle aborted before collecting')
        _saved_wall_offset = None
        wall_save = False
        return
    pause_event.wait()
    if cfg['train_mode'] == 'quick':
        pause_event.wait()
        print('[quick_train] using quick train to cook army.')
        if _cycle_count % 5 == 0:
            pause_event.wait()
            quick_train(cfg['quick_slot'])
    else:
        if _cycle_count % 3 == 0:
            pause_event.wait()
            smart_train(cfg)
    pause_event.wait()
    if connection_popup_visible():
        print('[WARN] Connection lost → recovering')
        boot_recovery()
        return
    if cfg['upgrade_wall'] and (not _check_stop()):
        wall_from = cfg.get('wall_level_from', cfg.get('wall_level', 8))
        wall_to = cfg.get('wall_level_to', wall_from)
        print(f"[INFO] Upgrading walls, levels {wall_from}→{wall_to} (multi-pass, price from config)…")
        multi_zoom_out(host)          # фикс. масштаб перед поиском: эталон сегмента стены масштабо-зависим
        handle_home_resources(wall_from, wall_to,
                              cfg.get('wall_gold_threshold'), cfg.get('wall_elixir_threshold'))
    pause_event.wait()
    if cfg.get('enable_clan_games', False):
        print('[INFO] Running Clan Games…')
        run_events_open(host)
        if _check_stop():
            _saved_wall_offset = None
            wall_save = False
            return
    pause_event.wait()
    rsleep(0.5)
    if cfg['request_troops'] and (not _check_stop()):
        if connection_popup_visible():
            print('[WARN] Connection lost → recovering')
            boot_recovery()
            return
        print('[INFO] Requesting troops')
        auto_request()
    pause_event.wait()
    if _check_stop():
        print('[INFO] Cycle aborted before search')
        _saved_wall_offset = None
        wall_save = False
        return
    if connection_popup_visible():
        print('[WARN] Connection lost → recovering')
        boot_recovery()
        return
    find_and_tap_collectors()
    print(f"[INFO] Search criteria -> Gold ≥ {cfg['gold_threshold']}, Elixir ≥ {cfg['elixir_threshold']}")
    print('[INFO] Searching for base to attack...')
    pause_event.wait()
    search_attack()
    pause_event.wait()
    while not _check_stop():
        pause_event.wait()
        if connection_popup_visible():
            print('[WARN] Connection lost during evaluation → recovering')
            boot_recovery()
            return
        if not wait_for_scout_screen():
            print('[WARN] Scouting UI not detected → recovering')
            boot_recovery()
            return
        for attempt in range(1, 4):
            pause_event.wait()
            if is_next_button_present():
                break
            print(f'⚠️ Next button missing—retrying ({attempt}/3)')
            rsleep(2)
        else:
            print('⚠️ Next button still missing after 3 attempts—triggering recovery')
            boot_recovery()
            print('✅ Recovered successfully')
            break
        pause_event.wait()
        e_gold, e_elixir, e_dark_elixir = map(int, extract_resources())
        print(f'[LOOT] GOLD: {e_gold}  ELIXIR: {e_elixir}  DARK_ELIXIR: {e_dark_elixir}')
        pause_event.wait()
        if e_gold >= cfg['gold_threshold'] and e_elixir >= cfg['elixir_threshold'] and (e_dark_elixir >= cfg['dark_elixir_threshold']):
            print('[INFO] Good base found → attacking')
            attack_fn = ATTACK_FUNCS.get(cfg['attack'])
            if not attack_fn:
                print(f"[ERROR] Unknown attack: {cfg['attack']!r}")
                return
            pause_event.wait()
            attack_fn(cfg)
            pause_event.wait()
            wait_battle_end()
            if cfg.get('enable_stats', False):
                village_idx = cfg['current_village_idx']
                try:
                    stars_got = get_stars_from_screen()
                except Exception:
                    stars_got = 0
                e_gold, e_elixir, e_dark_elixir = gain_resources(stars_got)
                stats = _load_stats_from_disk(village_idx)
                stats['gold'] = stats.get('gold', 0) + e_gold
                stats['elixir'] = stats.get('elixir', 0) + e_elixir
                stats['de'] = stats.get('de', 0) + e_dark_elixir
                stats['attacks'] = stats.get('attacks', 0) + 1
                print(f"[STATS] attack recorded (village {village_idx}): "
                      f"total={stats['attacks']} stars={stars_got}")
                key = str(stars_got)
                stars_block = stats.setdefault('stars', {'0': 0, '1': 0, '2': 0, '3': 0})
                stars_block[key] = stars_block.get(key, 0) + 1
                stats['stars'] = stars_block
                stats['last_update_ts'] = time.time()
                path = _stats_file_path(village_idx)
                with open(path, 'w') as f:
                    json.dump(stats, f, indent=2)
                cfg['stats'] = stats
            else:
                print(f"[{time.strftime('%H:%M:%S')}] [WORKER] ENABLE_STATS=False, skipping stats update")
            return_home()
            claim_event_cards()          # ивент: прожать карточки-награды после боя (если есть)
            break
        else:
            print('[INFO] Loot below threshold → next')
            search_next()
    pause_event.wait()
    if connection_popup_visible():
        print('Connection lost detected—recovering…')
        boot_recovery()
        return
    rsleep(2)
    _cycle_count += 1

def bot_loop(cfg):
    global _cycle_count
    global _saved_wall_offset
    global wall_save
    try:
        from sysdiag import log_virtualization
        log_virtualization()          # VT-x/Hyper-V авто-проверка в лог старта
    except Exception:
        pass
    setup_emulator()
    pause_event.wait()
    ensure_home_base()
    tap(140, 606)
    rsleep(2)
    pause_event.wait()
    if connection_popup_visible():
        print('Connection lost detected—recovering…')
        boot_recovery()
        ensure_home_base()
        tap(140, 606)
        rsleep(2)
    profiles_dir = os.path.join(BASE_DIR, 'profiles')
    json_paths = glob.glob(os.path.join(profiles_dir, 'Village_*.json'))
    existing_count = len(json_paths)
    desired_count = min(len(cfg['selected_villages']), 5)
    selected = cfg.get('selected_villages', [])
    if cfg['enable_multi_account']:
        pause_event.wait()
        # Деревни настраиваются прямо в главном GUI (вкладка Multi-Village, кнопки
        # Load/Save на каждую). Отдельный мастер-popup убран (дублировал и выбивался из
        # стиля). Если у выбранной деревни ещё нет профиля — создаём его из ТЕКУЩИХ
        # настроек, без диалога. Число аккаунтов пишем через prepare_accounts (device-free).
        os.makedirs(profiles_dir, exist_ok=True)
        for idx in selected:
            vpath = os.path.join(profiles_dir, f'Village_{idx}.json')
            if not os.path.exists(vpath):
                print(f'[INFO] Village_{idx}: no saved profile → creating from current settings')
                with open(vpath, 'w', encoding='utf-8') as f:
                    json.dump(_village_profile_from_cfg(cfg), f, indent=2)
        try:
            prepare_accounts(start=1, count=len(selected))
        except Exception as e:
            print(f'[WARN] prepare_accounts failed: {e} — continuing')
        existing_count = len(glob.glob(os.path.join(profiles_dir, 'Village_*.json')))
    else:
        print('[INFO] Multi-village disabled → single-village mode')
    pause_event.wait()
    accounts_file = os.path.join(profiles_dir, 'accounts.txt')
    if os.path.isfile(accounts_file):
        try:
            accounts_count = int(open(accounts_file).read().strip())
        except ValueError:
            print('Value Error')
    else:
        print('accounts.txt does not exist.')
    if cfg['enable_multi_account'] and accounts_count == 1:
        print('[WARN] We found 1 account only. Forcing Single Mode Village.')
        cfg['enable_multi_account'] = False
    pause_event.wait()
    if cfg['enable_multi_account']:
        user_list = cfg['selected_villages']
        if len(user_list) > accounts_count:
            print(f'[WARN] You requested {len(user_list)} villages but only {accounts_count} exist → using first {accounts_count}.')
            cfg['selected_villages'] = user_list[:accounts_count]
        desired_count = len(cfg['selected_villages'])
    pause_event.wait()
    if not cfg['enable_multi_account']:
        pause_event.wait()
        _cycle_count = 0
        cfg.setdefault('current_village_idx', 1)   # single-режим: беречь per-bot индекс (стат-бакет)
        while not stop_event.is_set():
            pause_event.wait()
            one_cycle(cfg)
            if not stop_event.is_set():
                human_between_cycles()          # анти-бан: пауза/перерыв между циклами
        print('[INFO] Bot stopped')
        _saved_wall_offset = None
        wall_save = False
        return
    village_list = cfg['selected_villages']
    interval_secs = cfg['multi_interval_mins'] * 60
    mins = interval_secs / 60.0
    if mins >= 60:
        hrs = mins / 60.0
        time_str = f'{hrs:.1f} hr'
    else:
        time_str = f'{mins:.1f} minutes'
    print(f'[INFO] Cycling through villages {village_list} every {time_str}')
    pause_event.wait()
    while not stop_event.is_set():
        for idx in village_list:
            pause_event.wait()
            if connection_popup_visible():
                print('Connection lost detected—recovering…')
                boot_recovery()
                break
            _cycle_count = 0
            if stop_event.is_set():
                break
            if existing_count == 0:
                print(f'[INFO] First setup: cleaning & ensuring home for Village_{idx}')
                boot_recovery()
                pause_event.wait()
                ensure_home_base()
                pause_event.wait()
                tap(140, 606)
                rsleep(3)
                existing_count = accounts_count
            pause_event.wait()
            ensure_home_base()
            tap(140, 606)
            print(f'[INFO] → Switching to Village_{idx}')
            bridge.setActiveVillage.emit(idx)
            try:
                import emu_driver
                if emu_driver.account_mode() == 'per_instance':
                    # Модель B: аккаунт = свой инстанс эмулятора (разные виртуалки).
                    binding = emu_driver.binding_for(idx)
                    if binding:
                        print(f"[INFO] per-instance → {binding['emulator']} #{binding['index']}")
                        emu_driver.ensure(binding['emulator'], binding['index'])
                    else:
                        print(f'[WARN] Village_{idx}: no binding in accounts.json -> staying on current instance')
                else:
                    # Модель A: переключение Supercell ID тапами по слотам (FLAG_SECURE).
                    switch_to_village(idx)
            except Exception as e:
                # Переключение аккаунтов ненадёжно (FLAG_SECURE / старт инстанса) —
                # не роняем бота, продолжаем на текущем аккаунте.
                print(f'[WARN] switch to Village_{idx} failed: {e} — staying on current account')
            rsleep(5)
            pause_event.wait()
            ensure_home_base()
            tap(140, 606)
            _saved_wall_offset = None
            wall_save = False
            cfg['current_village_idx'] = idx
            pause_event.wait()
            cfg_path = os.path.join(profiles_dir, f'Village_{idx}.json')
            try:
                with open(cfg_path, 'r') as f:
                    village_cfg = json.load(f)
            except FileNotFoundError:
                print(f'[WARN] Missing config for Village_{idx}, using defaults')
                village_cfg = {}
            for k in ('enable_trophy_drop', 'trophy_limit', 'target_trophy'):
                village_cfg.pop(k, None)
            village_cfg.setdefault('enable_clan_capital', False)
            village_cfg.setdefault('capital_hall_level', 9)
            merged_cfg = {**cfg, **village_cfg}
            pause_event.wait()
            slot_start = time.time()
            while time.time() - slot_start < interval_secs:
                pause_event.wait()
                if stop_event.is_set():
                    _saved_wall_offset = None
                    wall_save = False
                    break
                if one_cycle(merged_cfg) == 'STORAGES_FULL':
                    print(f'[INFO] Village_{idx} storages full → switching account early')
                    break                         # досрочно к следующему аккаунту
    print('[INFO] Bot stopped')
    _saved_wall_offset = None
    wall_save = False

def main():
    default_cfg = {'gold_threshold': 650000, 'elixir_threshold': 650000, 'dark_elixir_threshold': 0, 'upgrade_wall': True, 'wall_level': 12, 'wall_gold_threshold': 5000000, 'wall_elixir_threshold': 5000000, 'request_troops': True, 'attack': 'Dragon_Attack', 'train_mode': 'smart', 'quick_slot': 1, 'enable_multi_account': True, 'enable_clan_capital': False, 'capital_hall_level': 7}
    try:
        bot_loop(config)
    except KeyboardInterrupt:
        stop_event.set()
        print('\n[MAIN] Interrupted by user, exiting...')
if __name__ == '__main__':
    main_gui()