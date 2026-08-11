import os
import sys
import subprocess
from screenshot_utils import capture_array
import digit_ocr

CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
from paths import BASE_DIR as SCRIPT_DIR
coords = {'Gold': (55, 117, 251, 161), 'Elixir': (60, 167, 261, 208), 'Dark Elixir': (73, 214, 183, 248)}


def extract_resources():
    # Лут врага читаем матчингом цифр (digit_ocr) — фиксированный шрифт CoC,
    # точнее и в разы легче easyocr. Кадр берём в память (capture_array).
    img = capture_array()
    results = {}
    for label, (x1, y1, x2, y2) in coords.items():
        val = digit_ocr.read_int(img[y1:y2, x1:x2])
        results[label] = str(val) if val is not None else '0'
    return (results['Gold'], results['Elixir'], results['Dark Elixir'])


if __name__ == '__main__':
    gold, elixir, dark_elixir = extract_resources()
    print(f'Gold:        {gold}')
    print(f'Elixir:      {elixir}')
    print(f'Dark Elixir: {dark_elixir}')
