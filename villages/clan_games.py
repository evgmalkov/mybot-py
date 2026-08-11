import os, sys, time, subprocess
import cv2
import numpy as np
from pathlib import Path
from screenshot_utils import take_screenshot
from unicode import imread_unicode
from paths import BASE_DIR
from adb_config import ADB_BIN          # динамический (BlueStacks → HD-Adb.exe)
CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
TEMPLATE_DIR = os.path.join(BASE_DIR, 'Templates')
CLAN_GAMES_DIR = Path(TEMPLATE_DIR) / 'Clan Games'
EVENTS_TPL = Path(TEMPLATE_DIR) / 'events.png'
CLAN_GAMES_TPL = Path(TEMPLATE_DIR) / 'clan_games.png'
OPEN_BTN_TPL = Path(TEMPLATE_DIR) / 'open_button.png'
OPEN_BTN_TPL_2 = Path(TEMPLATE_DIR) / 'open_button_2.png'


def tap(x: int, y: int, host: str) -> None:
    """ADB tap wrapper."""
    subprocess.run([ADB_BIN, '-s', host, 'shell', 'input', 'tap', str(x), str(y)], creationflags=CREATE_NO_WINDOW, check=False)


def match_template(img: np.ndarray,
    tpl_path: Path,
    roi: tuple[int, int, int, int],
    thr: float=0.95,
    grayscale: bool=True) -> tuple[int, int] | None:
    """ROI-restricted TM_CCOEFF_NORMED match → (cx, cy) or None."""
    x1, y1, x2, y2 = roi
    search = img[y1:y2, x1:x2]
    tpl = imread_unicode(tpl_path, cv2.IMREAD_GRAYSCALE)
    search_gray = cv2.cvtColor(search, cv2.COLOR_BGR2GRAY)
    res = cv2.matchTemplate(search_gray, tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    if max_val < thr:
        return None
    h, w = tpl.shape
    return (x1 + max_loc[0] + w // 2, y1 + max_loc[1] + h // 2)


def choose_game(host: str) -> None:
    time.sleep(3.5)
    templates = sorted(CLAN_GAMES_DIR.glob('*.png'), key=lambda p: int(p.stem) if p.stem.isdigit() else float('inf'))
    chosen = None
    for attempt in range(2):
        shot_games = take_screenshot('games.png')
        time.sleep(0.5)
        img = imread_unicode(Path(shot_games), cv2.IMREAD_COLOR)
        if img is None:
            print('❌ Failed to load games screenshot')
            return
        for tpl in templates:
            center = match_template(img,
                tpl,
                (0, 0, img.shape[1], img.shape[0]), thr=0.9)
            if center:
                tap(*center, host)
                chosen = tpl.name
                break
        if chosen:
            break
        if attempt == 0:
            subprocess.run([ADB_BIN, '-s', host, 'shell', 'input', 'swipe', '974', '667', '980', '134', '2000'], creationflags=CREATE_NO_WINDOW, check=False)
            time.sleep(2)
    if not chosen:
        print('ℹ️  No Clan-Games task matched ≥90%')
        tap(1422, 55, host)
        return
    time.sleep(0.5)
    start_shot = take_screenshot('start_CG.png')
    img_start = imread_unicode(Path(start_shot), cv2.IMREAD_COLOR)
    if img_start is None:
        print('❌ Failed to load start screenshot')
        tap(1422, 55, host)
        return
    time.sleep(0.5)
    thr = 0.95
    candidates = []
    for name in ['start_button.png', 'start_button_2.png']:
        tpl_path = Path(TEMPLATE_DIR) / name
        tpl_img = imread_unicode(tpl_path, cv2.IMREAD_COLOR)
        res = cv2.matchTemplate(img_start, tpl_img, cv2.TM_CCOEFF_NORMED)
        _, score, _, loc = cv2.minMaxLoc(res)
        candidates.append((score, loc, tpl_img, name))
    best = max(candidates, key=lambda x: x[0])
    score, (x, y), tpl_img, name = best
    if score >= thr:
        h, w = tpl_img.shape[:2]
        cx, cy = (x + w // 2, y + h // 2)
        time.sleep(0.5)
        tap(cx, cy, host)
    else:
        print(f'⚠️  START button not found (best={score:.2f})')
    time.sleep(0.5)
    tap(1422, 55, host)
    print(f'✅ Selected task {chosen}')


def run_events_open(host: str) -> None:
    tap(354, 830, host)
    time.sleep(1)
    shot_path = Path('events_window.png')
    take_screenshot(str(shot_path))
    img = imread_unicode(shot_path, cv2.IMREAD_COLOR)
    if img is None:
        print('❌ screenshot load failed')
        return
    if not match_template(img, EVENTS_TPL, (605, 8, 1038, 125), thr=0.95):
        print('⚠️  Events window missing')
        return
    cg_center = None
    for attempt in range(2):
        cg_center = match_template(img, CLAN_GAMES_TPL, (222, 24, 1391, 887), thr=0.95)
        if cg_center is not None:
            break
        if attempt == 0:
            subprocess.run([ADB_BIN, '-s', host, 'shell', 'input', 'swipe', '680', '815', '680', '167', '1000'], creationflags=CREATE_NO_WINDOW, check=False)
            time.sleep(1.2)
            take_screenshot(str(shot_path))
            img = imread_unicode(shot_path, cv2.IMREAD_COLOR)
            if img is None:
                print('❌ screenshot load failed after scroll')
                return
    if cg_center is None:
        print('ℹ️  Clan Games inactive')
        return
    region = (cg_center[0] - 180, cg_center[1] - 169, cg_center[0] + 1000, cg_center[1] + 131)
    open_center = None
    for tpl in (OPEN_BTN_TPL, OPEN_BTN_TPL_2):
        open_center = match_template(img, tpl, region, thr=0.95)
        if open_center is not None:
            break
    if open_center is None:
        print('⚠️  OPEN not found – closing')
        tap(1321, 65, host)
        return
    tap(*open_center, host)
    print('✅ Clan Games opened.')
    time.sleep(1)
    avail_shot = take_screenshot('is_cg_available.png')
    is_cg_img = imread_unicode(avail_shot, cv2.IMREAD_COLOR)
    if is_cg_img is None:
        print('❌ failed to load availability screenshot')
        tap(1417, 58, host)
        return
    if match_template(is_cg_img, Path(TEMPLATE_DIR) / 'clan_games_finished.png', (126, 735, 486, 872), thr=0.95):
        print('ℹ️  User already finished Clan Games.')
        tap(1417, 58, host)
        return
    busy_roi = (557, 144, 800, 420)
    x1, y1, x2, y2 = busy_roi
    sub_busy = is_cg_img[y1:y2, x1:x2]
    for name in ['clan_games_busy_1.png', 'clan_games_busy_2.png', 'clan_games_busy_3.png', 'clan_games_busy_4.png', 'clan_games_busy_5.png']:
        tpl_path = Path(TEMPLATE_DIR) / name
        tpl_img = imread_unicode(tpl_path, cv2.IMREAD_COLOR)
        res = cv2.matchTemplate(sub_busy, tpl_img, cv2.TM_CCOEFF_NORMED)
        _, score, _, _ = cv2.minMaxLoc(res)
        if score >= 0.6:
            print('ℹ️  Clan Games busy.')
            tap(1417, 58, host)
            return
    choose_game(host)


if __name__ == '__main__':
    run_events_open()
