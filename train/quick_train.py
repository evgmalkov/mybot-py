from __future__ import annotations
from typing import Tuple
from unicode import imread_unicode
import os, sys, time, cv2, subprocess
import numpy as np
import re
from paths import BASE_DIR
TEMPLATE_ROOT = os.path.join(BASE_DIR, 'Templates', 'Smart_Auto_train')
PNG_EXT = '.png'
from screenshot_utils import take_screenshot
from adb_config import ADB_BIN
from smart_train import _validate_army_window, tap, _roi
CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
CLOSE_ARMY_WINDOW = (1545, 81)
ARMY_RECIPE_PANE = (777, 90)


def quick_train(use_army: int) -> bool:
    """
Quickly load an army recipe (1 or 2) from the Army Recipes window.
Returns True if the function ran (even if no template matched), False on fatal error.
"""
    if not _validate_army_window():
        print('[quick_train] Army window not detected – aborting')
        return False
    tap(ARMY_RECIPE_PANE)
    time.sleep(0.5)
    shot = imread_unicode(take_screenshot(), cv2.IMREAD_COLOR)
    if shot is None:
        print('[quick_train] failed to capture screenshot after opening recipes')
        tap(CLOSE_ARMY_WINDOW)
        return False
    if use_army == 1:
        roi_coords = (1364, 189, 1574, 425)
    else:
        roi_coords = (1368, 486, 1572, 735)
    slot_roi = _roi(shot, *roi_coords)
    slot_roi = _roi(shot, *roi_coords)
    tpl = imread_unicode(os.path.join(TEMPLATE_ROOT, 'use_button.png'), cv2.IMREAD_COLOR)
    match_result = cv2.matchTemplate(slot_roi, tpl, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(match_result)
    print(f'[quick_train] use_button match score = {max_val:.3f}')
    if max_val >= 0.9:
        x0, y0, _, _ = roi_coords
        tpl_h, tpl_w = tpl.shape[:2]
        mx, my = max_loc
        center_x = x0 + mx + tpl_w // 2
        center_y = y0 + my + tpl_h // 2
        tap((center_x, center_y))
        time.sleep(0.6)
        shot2 = imread_unicode(take_screenshot(), cv2.IMREAD_COLOR)
        tpl2 = imread_unicode(os.path.join(TEMPLATE_ROOT, 'use_army_recipe_window.png'), cv2.IMREAD_COLOR)
        match2 = cv2.matchTemplate(shot2, tpl2, cv2.TM_CCOEFF_NORMED)
        _, max2, _, _ = cv2.minMaxLoc(match2)
        print(f'[quick_train] recipe window match score = {max2:.3f}')
        if max2 >= 0.9:
            tap((972, 584))
    time.sleep(0.5)
    tap(CLOSE_ARMY_WINDOW)
    time.sleep(0.5)
    return True


if __name__ == '__main__':
    quick_train(1)
