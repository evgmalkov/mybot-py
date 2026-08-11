"""
────────────────────────────────────────────────────────────────────────────
"""
import os
import sys
import time
import cv2
import subprocess
import glob
import threading
from typing import Tuple, Optional
import numpy as np
import json
import main
from PyQt5.QtCore import QObject, pyqtSignal, QEventLoop
from screenshot_utils import take_screenshot
from adb_config import ADB_BIN
from ahk_utils import run_ahk
from pathlib import Path
from unicode import imread_unicode
DEBUG = True


def dbg(msg: str):
    if DEBUG:
        ts = time.strftime('%H:%M:%S')
        print(f'[D] {ts}  {msg}')


from paths import BASE_DIR
TEMPLATE_DIR = BASE_DIR / 'Templates'
PROFILES_DIR = BASE_DIR / 'profiles'
PROFILES_DIR.mkdir(exist_ok=True, parents=True)
CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
LOADED_ROI = (1010, 36, 1422, 142)
LOADED_TPL = os.path.join(TEMPLATE_DIR, 'is_account_loaded.png')
FOURTH_ROI = (1006, 783, 1313, 858)
SWITCH_BUTTON_ROI = (562, 110, 1333, 282)
MEMU = '127.0.0.1:21503'
BLUESTACKS = '127.0.0.1:5555'
CROP_RECTS = [(876, 162, 1114, 271), (876, 325, 1114, 431), (876, 486, 1114, 592), (876, 647, 1114, 756), (876, 815, 1114, 894)]
VILLAGE_COORDS = {1: (1088, 212), 2: (1088, 379), 3: (1088, 532), 4: (1088, 702), 5: (1088, 858)}
ACCOUNT_DETECT_ROIS = [((753, 394, 1566, 526), 1), ((753, 557, 1566, 685), 2), ((753, 718, 1566, 842), 3)]


def tap(coord: Tuple[int, int]) -> None:
    host = main.host
    x, y = coord
    subprocess.run([ADB_BIN, '-s', host, 'shell', 'input', 'tap', str(x), str(y)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)


def match_one(template_name: str,
    screenshot: np.ndarray,
    roi: Tuple[int, int, int, int],
    thresh: float=0.9) -> Optional[Tuple[int, int]]:
    """
Debugging version: logs ROI, template/crop sizes, match scores,
and writes out an annotated 'debug_match_<template>.png' in BASE_DIR.
"""
    path = os.path.join(TEMPLATE_DIR, template_name)
    tmpl = imread_unicode(path, cv2.IMREAD_COLOR)
    if tmpl is None:
        dbg(f'! Failed to load template: {path}')
        return None
    x1, y1, x2, y2 = roi
    crop = screenshot[y1:y2, x1:x2]
    res = cv2.matchTemplate(crop, tmpl, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    vis = screenshot.copy()
    h, w = tmpl.shape[:2]
    top_left = (x1 + max_loc[0], y1 + max_loc[1])
    bottom_right = (top_left[0] + w, top_left[1] + h)
    cv2.rectangle(vis, top_left, bottom_right, (0, 0, 255), 3)
    if max_val >= thresh:
        cx = x1 + max_loc[0] + w // 2
        cy = y1 + max_loc[1] + h // 2
        return (cx, cy)


def clear_memu_screenshots():
    """
Deletes all 'Screenshot_*.png' files under
%USERPROFILE%\\Pictures\\MEmu Photo\\Screenshots to clean up old shots.
"""
    pics_dir = Path.home() / 'Pictures' / 'MEmu Photo' / 'Screenshots'
    if not pics_dir.is_dir():
        print(f'[WARN] No MEmu screenshot folder found at {pics_dir!r}, nothing to delete.')
        return
    pattern = str(pics_dir / 'Screenshot_*.png')
    files = glob.glob(pattern)
    if not files:
        print(f'[INFO] No screenshots to delete in {pics_dir!r}.')
        return
    deleted = 0
    for fp in files:
        try:
            os.remove(fp)
            deleted += 1
        except OSError as e:
            print(f'[ERROR] Could not delete {fp}: {e}')


def get_latest_memu_screenshot(retries: int=3, delay: float=1.0) -> Path:
    """
Return the Path to the newest Screenshot_*.png under:
  %USERPROFILE%/Pictures/MEmu Photo/Screenshots
Will retry up to `retries` times—each time triggering your AHK script
if no file is found, then waiting `delay` seconds.
"""
    dirs = [Path.home() / 'Pictures' / 'MEmu Photo' / 'Screenshots', Path.home() / 'Pictures' / 'MEmu' / 'Screenshots']
    for attempt in range(1, retries + 1):
        for pics_dir in dirs:
            if not pics_dir.is_dir():
                continue
            files = list(pics_dir.glob('Screenshot_*.png'))
            if not files:
                continue
            return max(files, key=lambda f: f.stat().st_mtime)
        run_ahk('bypass_screen.ahk')
        time.sleep(delay)
    tried = '\n'.join((str(d) for d in dirs))
    # НЕ бросаем — обход FLAG_SECURE через MEmu-скриншот/AHK ненадёжен; возвращаем None,
    # чтобы вызывающий деградировал, а не ронял бота. (Переключение аккаунтов — редизайн.)
    print(f'[WARN] get_latest_memu_screenshot: no MEmu screenshots in:\n{tried}')
    return None


def save_village_config(idx: int, cfg: dict):
    """
Writes Village_{idx}.json with the provided cfg dict,
then snaps & saves account_{idx}.png via take_screenshot().
"""
    PROFILES_DIR.mkdir(exist_ok=True)
    json_path = PROFILES_DIR / f'Village_{idx}.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2)
    print(f'[D] Saved config → {json_path}')
    img_path = PROFILES_DIR / f'account_{idx}.png'
    take_screenshot(output_path=str(img_path))
    print(f'[D] Captured image   → {img_path}')


def add_village(count: int):
    """
Capture and save the next `count` account slots from the
Supercell ID switcher UI, naming them account_{n}.png.
"""
    dbg('Opening Settings for add_village')
    tap((1534, 649))
    time.sleep(1)
    tmp = take_screenshot()
    scr0 = imread_unicode(tmp)
    sw_btn = match_one('switch_button.png', scr0, (562, 110, 1333, 282))
    if not sw_btn:
        print('[WARN] Could not find Switch-Account button.')
        tap((1288, 96))
        return
    dbg('Tapping Switch-Account')
    tap(sw_btn)
    time.sleep(2)
    if main.host == MEMU:
        run_ahk('bypass_screen.ahk')
        time.sleep(1)
        shot_path = get_latest_memu_screenshot()
    else:
        shot_path = take_screenshot()
    scr = imread_unicode(shot_path)
    if scr is None:
        print('[ERROR] Failed to load screenshot for add_village.')
        return
    total_avail = None
    for (x1, y1, x2, y2), num in ACCOUNT_DETECT_ROIS:
        if match_one('account_counter.png', scr, (x1, y1, x2, y2)):
            total_avail = num
            break
    if total_avail is None:
        total_avail = 4 if match_one('account_counter_2.png', scr, FOURTH_ROI) else 5
    print(f'[INFO] Device has {total_avail} Supercell IDs available')
    existing = len(glob.glob(str(PROFILES_DIR / 'account_*.png')))
    max_new = min(count, total_avail - existing, 5 - existing)
    if max_new <= 0:
        print(f'[INFO] No new villages to add (existing={existing}, avail={total_avail})')
        return
    for idx in range(existing + 1, existing + max_new + 1):
        x1, y1, x2, y2 = CROP_RECTS[idx - 1]
        crop = scr[y1:y2, x1:x2]
        out = PROFILES_DIR / f'account_{idx}.png'
        cv2.imwrite(str(out), crop)
        dbg(f'Saved new account_{idx}.png')
    if main.host == MEMU:
        clear_memu_screenshots()


def _load_accounts_cfg():
    """Координаты слотов и паузы переключения аккаунтов из config/accounts.json (фолбэк)."""
    import json
    try:
        with open(BASE_DIR / 'config' / 'accounts.json', encoding='utf-8') as f:
            d = json.load(f)
    except Exception:
        d = {}
    slots = d.get('slots') or {'1': [1088, 212], '2': [1088, 379], '3': [1088, 532],
                               '4': [1088, 702], '5': [1088, 858]}
    return {'slots': slots,
            'account_count': int(d.get('account_count', 0) or 0),
            'wait_list': float(d.get('wait_list_sec', 4)),
            'wait_switch': float(d.get('wait_switch_sec', 6))}


def switch_to_village(idx: int):
    """Открыть Settings → Switch-Account → тап по слоту аккаунта idx ПРЯМОЙ координатой.

    Список аккаунтов — FLAG_SECURE (adb-скриншот чёрный), поэтому НЕ скриншотим и НЕ
    матчим «загрузился» (старый AHK-обход не работал). Слоты — на фикс-позициях
    (config/accounts.json), кол-во задаёт юзер. Просто ждём и тапаем слот."""
    dbg(f'switch_to_village({idx})')
    acfg = _load_accounts_cfg()
    coord = acfg['slots'].get(str(idx))
    if not coord:
        print(f'[ERROR] Invalid account slot index: {idx}')
        return
    time.sleep(2)
    tap((1534, 649))                          # открыть Settings
    time.sleep(1)
    scr = imread_unicode(take_screenshot())
    sw = match_one('switch_button.png', scr, SWITCH_BUTTON_ROI) if scr is not None else None
    if not sw:
        print('[WARN] Switch-Account button not found; aborting switch_to_village')
        tap((1288, 96))
        return
    tap(sw)                                   # открыть список аккаунтов (FLAG_SECURE)
    # Список — FLAG_SECURE (adb-скриншот чёрный), проверить «загрузился» нельзя и не нужно
    # (старый AHK-обход не работал). Ждём загрузки и тапаем слот по ФИКС-координате.
    print(f'[ACCOUNTS] switching to slot {idx} at {tuple(coord)} (list wait {acfg["wait_list"]}s)')
    time.sleep(acfg['wait_list'])
    tap(tuple(coord))                         # прямой тап по слоту аккаунта
    time.sleep(acfg['wait_switch'])           # ждём загрузки выбранного аккаунта
    dbg(f'Switched to Village_{idx}')


def prepare_accounts(start: int=1, count: int=None) -> int:
    """Определить число аккаунтов для мастера настройки БЕЗ работы с устройством.

    Экран Switch ID помечен FLAG_SECURE → adb-скриншот чёрный, а старый обход через
    `run_ahk('bypass_screen.ahk')` перехватывал ввод Windows (открывал системный диалог
    и сворачивал эмулятор) и не давал реального кадра, из-за чего `imread_unicode(None)`
    ронял настройку. Поэтому список аккаунтов НЕ скриншотим и НЕ открываем здесь UI
    (переключение делает `switch_to_village` прямым тапом по фикс-координатам слота).

    Число аккаунтов берём из `config/accounts.json` → `account_count`; если там 0 —
    из запрошенного мастером `count` (число выбранных деревень), иначе из числа слотов.
    Пишем `profiles/accounts.txt` и возвращаем это число. Миниатюр аккаунтов больше нет —
    мастер (`ConfigPage`) их рисует опционально и без файла просто не показывает картинку.
    """
    acfg = _load_accounts_cfg()
    total_slots = len(acfg['slots'])
    detected_total = acfg['account_count'] or count or total_slots
    detected_total = max(1, min(int(detected_total), total_slots))
    PROFILES_DIR.mkdir(exist_ok=True)
    (PROFILES_DIR / 'accounts.txt').write_text(str(detected_total), encoding='utf-8')
    print(f'[INFO] prepare_accounts: {detected_total} account(s) '
          f'(from config account_count / selection; FLAG_SECURE list not captured)')
    return detected_total


if __name__ == '__main__':
    prepare_accounts()
