"""Применение сохранённого рецепта с подтверждением возврата в состав армии."""
import cv2
import time
from paths import BASE_DIR
from screenshot_utils import capture_array, load_template
from game_ui import UI, open_army, close_army, tap_named, wait_visible, visible


def quick_train(use_army: int) -> bool:
    region = UI['recipe_slots'].get(str(use_army))
    if region is None or not open_army():
        return False
    if tap_named('recipes') is False:
        return False
    time.sleep(UI['poll_interval'])
    image = capture_array()
    if image is None:
        return False
    template = load_template(str(BASE_DIR / 'Templates' / 'Smart_Auto_train' / 'use_button.png'), cv2.IMREAD_COLOR)
    x1, y1, x2, y2 = region
    roi = image[y1:y2, x1:x2]
    if template is None or any(a < b for a, b in zip(roi.shape[:2], template.shape[:2])):
        return False
    _, score, _, loc = cv2.minMaxLoc(cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED))
    if score < UI['threshold']:
        print(f'[QUICK] Recipe {use_army} is unavailable')
        tap_named('my_army')
        wait_visible('army')
        close_army()
        return False
    from smart_train import tap
    import main
    main.pause_event.wait()
    if main._check_stop():
        return False
    tap((x1 + loc[0] + template.shape[1] // 2, y1 + loc[1] + template.shape[0] // 2))
    # При существующем подкреплении игра запрашивает подтверждение рецепта.
    deadline = time.monotonic() + UI['transition_timeout']
    while time.monotonic() < deadline:
        if main._check_stop():
            return False
        image = capture_array()
        if visible('recipe_confirm', image):
            if tap_named('recipe_confirm') is False:
                return False
        elif visible('army', image):
            print(f'[QUICK] Recipe {use_army} applied')
            return close_army()
        time.sleep(UI['poll_interval'])
    print(f'[QUICK] Recipe {use_army} was not confirmed')
    return False
