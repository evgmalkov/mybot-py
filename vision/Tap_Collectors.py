import cv2
import os
import sys
import subprocess
import time
import main
import numpy as np
from adb_config import ADB_BIN
from screenshot_utils import take_screenshot
from unicode import imread_unicode

CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
from paths import BASE_DIR
TEMPLATE_DIR = os.path.join(BASE_DIR, 'Templates')
DEVICE_SCREENSHOT = '/sdcard/Collectors.png'
LOCAL_SCREENSHOT = os.path.join(BASE_DIR, 'Collectors.png')
TEMPLATE_FILES = ['elixir_collector.png', 'DE_collector.png', 'gold_collector.png']
TEMPLATES = [os.path.join(TEMPLATE_DIR, fn) for fn in TEMPLATE_FILES]
AVAILABLE_THRESHOLD = 0.65
TAP_DELAY = 0.5


def run_adb(cmd_list):
    """
    Execute an ADB command (list form) and return True on success.
    Prints detailed stderr on failure.
    """
    host = main.host
    if host:
        cmd = [ADB_BIN, '-s', host] + cmd_list
    else:
        cmd = [ADB_BIN] + cmd_list
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW)
    if proc.returncode != 0:
        err = proc.stderr.decode(errors='ignore').strip()
        print(f'[ERROR] ADB failed: {" ".join(cmd_list)}\n  {err}')
        return False
    return True


def find_and_tap_collectors():
    """
    Match each collector template in the screenshot and tap its center via ADB
    only if the confidence is above AVAILABLE_THRESHOLD.
    """
    screenshot_path = take_screenshot(output_path='Collectors_resources.png')
    image = imread_unicode(screenshot_path, cv2.IMREAD_COLOR)
    if image is None:
        print('[ERROR] Could not load screenshot. Aborting.')
        return
    gray_img = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    for tmpl in TEMPLATES:
        template_path = os.path.join(TEMPLATE_DIR, tmpl)
        template = imread_unicode(template_path, cv2.IMREAD_GRAYSCALE)
        if template is None:
            print(f'[ERROR] Missing template: {template_path}')
            continue
        result = cv2.matchTemplate(gray_img, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        th, tw = template.shape[:2]
        cx = max_loc[0] + tw // 2
        cy = max_loc[1] + th // 2
        if max_val <= AVAILABLE_THRESHOLD:
            continue
        print('tapping…')
        run_adb(['shell', 'input', 'tap', str(cx), str(cy)])
        time.sleep(TAP_DELAY)
    print('All done.')


if __name__ == '__main__':
    find_and_tap_collectors()
