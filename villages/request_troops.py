import os
import cv2
import sys
import subprocess
import time
import numpy as np
import main
from ensure_home_base import ensure_home_base
from boot_recovery import boot_recovery
from adb_config import ADB_BIN
from screenshot_utils import take_screenshot, load_template
from unicode import imread_unicode
CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
from paths import BASE_DIR, DEBUG
TEMPLATE_DIR = os.path.join(BASE_DIR, 'Templates')
MY_ARMY_HDR = os.path.join(TEMPLATE_DIR, 'my_army_hdr.png')
REQUEST_BTN_TEMPLATE = os.path.join(TEMPLATE_DIR, 'request_button.png')
CLAN_CAKE_TEMPLATE = os.path.join(TEMPLATE_DIR, 'clan_castle_cake.png')
CLAN_TROOPS_SAVED = os.path.join(TEMPLATE_DIR, 'cc_no_troops.png')
CLAN_CAKE_THRESH = 0.7
REQUEST_THRESH = 0.95
ARMY_BUTTON = (63, 653)
REQUEST_BUTTON_TAP = (1491, 712)
SEND_BUTTON = (970, 627)
CLOSE_BUTTON = (1545, 84)
ARMY_WINDOW_REGION = (199, 64, 929, 121)
REQUEST_BUTTON_REGION = (1245, 655, 1583, 850)
WINDOW_KEYWORDS = ['ARMY', 'RECIPES', 'MY', 'SAVED']


def adb_screenshot(path):
    # take_screenshot складывает голое имя в debug/ и возвращает реальный путь —
    # его и отдаём наверх, иначе чтение по исходному имени не найдёт файл.
    try:
        return take_screenshot(output_path=path)
    except subprocess.CalledProcessError as e:
        print(f'❌ ADB error: {e}')
        return None


def tap(x, y):
    host = main.host
    subprocess.run([ADB_BIN, '-s', host, 'shell', 'input', 'tap', str(x), str(y)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)


def get_header_text(img):
    # Окно армии определяем матчингом заголовка «MY ARMY» (вместо OCR) — надёжнее.
    x1, y1, x2, y2 = ARMY_WINDOW_REGION
    tpl = load_template(MY_ARMY_HDR, cv2.IMREAD_GRAYSCALE)
    if tpl is None:
        return ''
    roi = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
    if roi.shape[0] < tpl.shape[0] or roi.shape[1] < tpl.shape[1]:
        return ''
    score = float(cv2.matchTemplate(roi, tpl, cv2.TM_CCOEFF_NORMED).max())
    return 'MY ARMY' if score >= 0.7 else ''


def is_request_button_present(img):
    x1, y1, x2, y2 = REQUEST_BUTTON_REGION
    roi = img[y1:y2, x1:x2]
    tpl = imread_unicode(REQUEST_BTN_TEMPLATE, cv2.IMREAD_COLOR)
    if tpl is None:
        print(f'❌ Cannot load template: {REQUEST_BTN_TEMPLATE}')
        return False
    res = cv2.matchTemplate(roi, tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    print(f'[DEBUG] template match score: {max_val:.2f} @ {max_loc}')
    return max_val >= REQUEST_THRESH


def is_castle_cake_avail(img) -> bool:
    """
Check if Clan Castle 'cake' option is available using the same screenshot (img).
Cake ROI: (1245, 669) - (1418, 766). On hit (≥ CLAN_CAKE_THRESH) we:
  1) tap cake,
  2) take a fresh screenshot and OCR the 'saved troops' banner ROI,
  3) if any keyword is present → tap (589,628) and return False,
  4) else continue with the request flow and return True.
"""
    x1, y1, x2, y2 = (1245, 669, 1418, 766)
    time.sleep(0.5)
    roi = img[y1:y2, x1:x2]
    tpl = imread_unicode(CLAN_CAKE_TEMPLATE, cv2.IMREAD_COLOR)
    if tpl is None:
        print(f'❌ Cannot load template: {CLAN_CAKE_TEMPLATE}')
        return False
    res = cv2.matchTemplate(roi, tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(res)
    print(f'[DEBUG] cake match score: {max_val:.2f}')
    if max_val < CLAN_CAKE_THRESH:
        return False
    tap(1337, 720)
    time.sleep(0.7)
    try:
        shot_path = take_screenshot(output_path='cc_check.png')
        scr = imread_unicode(shot_path, cv2.IMREAD_COLOR)
    except Exception as e:
        print(f'[WARN] fresh screenshot failed for saved-troops check: {e}')
        scr = None
    if scr is not None:
        sx1, sy1, sx2, sy2 = (460, 207, 1144, 286)
        cc_roi = scr[sy1:sy2, sx1:sx2]
        # Баннер «нет сохранённых войск» — матчингом шаблона cc_no_troops (вместо OCR-слов).
        tpl = load_template(CLAN_TROOPS_SAVED, cv2.IMREAD_COLOR)
        found = (tpl is not None and cc_roi.size > 0
                 and tpl.shape[0] <= cc_roi.shape[0] and tpl.shape[1] <= cc_roi.shape[1]
                 and float(cv2.matchTemplate(cc_roi, tpl, cv2.TM_CCOEFF_NORMED).max()) >= 0.7)
        if found:
            tap(589, 628)
            print('ℹ️ No saved troops. Please save you clan castle troops! Using regular request.')
            return False
    tap(993, 610)
    time.sleep(0.7)
    tap(*CLOSE_BUTTON)
    print('✅ Request sent.')
    return True


def auto_request():
    if not ensure_home_base():
        print('❌ Home base not detected.')
        return False
    print('✅ Home base confirmed.')
    tap(*ARMY_BUTTON)
    time.sleep(0.6)
    shot_path = adb_screenshot('request_troops.png')
    if not shot_path:
        print('❌ Screenshot failed.')
        return False
    img = imread_unicode(shot_path)
    if img is None:
        print('❌ Invalid screenshot.')
        return False
    header = get_header_text(img)
    if not any((k in header for k in WINDOW_KEYWORDS)):
        print(f"❌ Army window not detected. OCR: '{header}'")
        tap(*CLOSE_BUTTON)
        return False
    print('✅ Army window detected!')
    print('▶ Checking Request button availability...')
    if not is_request_button_present(img):
        print('⚠️ Request not available')
        tap(*CLOSE_BUTTON)
        return False
    print('✅ Request available.')
    if is_castle_cake_avail(img):
        return True
    tap(*REQUEST_BUTTON_TAP)
    time.sleep(0.7)
    tap(*SEND_BUTTON)
    time.sleep(0.7)
    tap(*CLOSE_BUTTON)
    print('✅ Request sent.')
    return True


if __name__ == '__main__':
    auto_request()
