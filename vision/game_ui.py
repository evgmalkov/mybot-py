"""Проверяемые переходы интерфейса; геометрия — в config/game_ui.json."""
import json
import time
import cv2
from paths import BASE_DIR
from screenshot_utils import capture_array, load_template

with (BASE_DIR / 'config' / 'game_ui.json').open(encoding='utf-8') as _file:
    UI = json.load(_file)


def visible(name, image=None):
    """Проверить маркер только в его области и при ожидаемом разрешении."""
    if image is None:
        image = capture_array()
    if image is None or list(image.shape[1::-1]) != UI['resolution']:
        return False
    spec = UI['markers'][name]
    x1, y1, x2, y2 = spec['roi']
    roi = image[y1:y2, x1:x2]
    template = load_template(str(BASE_DIR / 'Templates' / spec['template']), cv2.IMREAD_COLOR)
    if template is None or any(a < b for a, b in zip(roi.shape[:2], template.shape[:2])):
        return False
    _, score, _, loc = cv2.minMaxLoc(cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED))
    patch = roi[loc[1]:loc[1] + template.shape[0], loc[0]:loc[0] + template.shape[1]]
    # NCC не замечает затемнение окна под модальным диалогом.
    difference = cv2.absdiff(patch, template).mean()
    return bool(score >= UI['threshold'] and difference <= UI['max_mean_difference'])


def tap_named(name):
    import main
    main.pause_event.wait()
    if main._check_stop():
        return False
    x, y = UI['taps'][name]
    main.run_adb(['shell', 'input', 'tap', str(x), str(y)])


def wait_visible(name):
    deadline = time.monotonic() + UI['transition_timeout']
    while time.monotonic() < deadline:
        import main
        if main._check_stop():
            return False
        if visible(name):
            return True
        time.sleep(UI['poll_interval'])
    print(f'[UI] Timed out waiting for {name}')
    return False


def dismiss_welcome():
    if visible('welcome'):
        tap_named('welcome_okay')
        return wait_visible('home')
    return False


def open_battle_menu():
    if visible('menu'):
        return True
    if not visible('home'):
        print('[UI] Home screen not confirmed; navigation cancelled')
        return False
    tap_named('battle')
    return wait_visible('menu')


def open_army():
    if visible('army'):
        return True
    if not open_battle_menu():
        return False
    tap_named('edit_army')
    return wait_visible('army')


def open_account_switcher():
    """Портрет по координатам → Settings → переключатель Supercell ID.

    Цвет и уровень ратуши не проверяются. Список ID может быть скрыт от ADB,
    поэтому здесь подтверждаются меню и кнопка перед открытием списка.
    """
    if not visible('account_settings'):
        if not visible('profile_menu'):
            if not visible('home'):
                print('[ACCOUNTS] Home screen not confirmed; navigation cancelled')
                return False
            if tap_named('player_profile') is False or not wait_visible('profile_menu'):
                return False
        if tap_named('profile_settings') is False or not wait_visible('account_settings'):
            return False
    if tap_named('account_switch') is False:
        return False
    print('[ACCOUNTS] Opened account switcher through profile settings')
    return True


def close_army():
    if not visible('army'):
        return False
    tap_named('close_army')
    if not wait_visible('menu'):
        return False
    tap_named('close_menu')
    return wait_visible('home')


def handle_battle_reward(image):
    """Дождаться ухода ивент-окна; известную валюту выбрать по маркеру."""
    if not visible('battle_reward', image):
        return True
    deadline = time.monotonic() + UI['reward_timeout']
    selected = False
    while time.monotonic() < deadline:
        import main
        if main._check_stop():
            return False
        if not visible('battle_reward', image):
            return True
        if not selected and visible('event_currency', image):
            tap_named('event_currency')
            selected = True
            print('[REWARD] Selected event currency')
        # Состав промежуточных карточек меняется; неизвестные исчезают по таймеру.
        # Пока открыт диалог, не отправляем игровые тапы и не читаем HP под ним.
        time.sleep(UI['poll_interval'])
        image = capture_array()
    print('[UI] Battle reward did not close; deployment stopped')
    return False
