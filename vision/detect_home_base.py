import cv2
import subprocess
import os
import sys
import numpy as np
from screenshot_utils import take_screenshot, capture_array, load_template
from unicode import imread_unicode

from paths import BASE_DIR
TEMPLATES_DIR = os.path.join(BASE_DIR, 'Templates')
SHOP_TEMPLATE = os.path.join(TEMPLATES_DIR, 'shop.png')
GAME_SETTING = os.path.join(TEMPLATES_DIR, 'game_setting.png')
CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
x1, y1, x2, y2 = (1408, 826, 1582, 886)


def detect_home_base():
    """Detects if we're on the home base screen by using three validations."""
    img = capture_array()
    if img is None:
        print('❌ Failed to read screenshot.')
        return False
    else:
        x1_roi, y1_roi, x2_roi, y2_roi = (1445, 499, 1599, 708)
        roi = img[y1_roi:y2_roi, x1_roi:x2_roi]
        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        tpl_settings = load_template(GAME_SETTING, cv2.IMREAD_GRAYSCALE)
        if tpl_settings is not None:
            res_settings = cv2.matchTemplate(gray_roi, tpl_settings, cv2.TM_CCOEFF_NORMED)
            if res_settings.max() >= 0.7:
                return True
        gray_full = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        tpl = load_template(SHOP_TEMPLATE, cv2.IMREAD_GRAYSCALE)
        if tpl is not None:
            res = cv2.matchTemplate(gray_full, tpl, cv2.TM_CCOEFF_NORMED)
            if res.max() >= 0.7:
                return True
        return False
