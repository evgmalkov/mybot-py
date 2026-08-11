import os
import sys
import cv2
import subprocess
import time
import random
import numpy as np
import math
import main
from screenshot_utils import take_screenshot, capture_array, load_template
import digit_ocr
from adb_config import ADB_BIN
from unicode import imread_unicode
from pathlib import Path
CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
from paths import BASE_DIR, DEBUG
os.chdir(BASE_DIR)
ROOT = BASE_DIR
ADB_DIR = BASE_DIR
TEMPLATE_DIR = os.path.join(BASE_DIR, 'Templates')
CLOSE_TEMPLATES = [os.path.join(TEMPLATE_DIR, fn) for fn in ['close_button_layout.png', 'close_button_profile.png', 'close_button_setting.png', 'close_button_shield.png', 'close_button_shop.png']]
CLOSE_BTN_THRESH = 0.75
GOLD_REGION = (1247, 24, 1504, 68)
ELIXIR_REGION = (1247, 110, 1532, 176)
GOLD_THRESHOLD = 5000000
ELIXIR_THRESHOLD = 5000000
BORDER_TOP, BORDER_BOTTOM = (20, 20)
BORDER_LEFT, BORDER_RIGHT = (30, 30)
UPSCALE = 2
VALIDATE_REGION = (626, 572, 981, 622)
POPUP_REGION = (513, 35, 1135, 89)
DISMISS_COORD = (1143, 209)
GOLD_UPGRADE = (0, 707)
ELIXIR_UPGRADE = (0, 702)
CONFIRM_UPGRADE = (1115, 782)
ANGLE_LO = 35
ANGLE_HI = 55
HOUGH_CFG = dict(rho=1, theta=np.pi / 180, threshold=100, minLineLength=60, maxLineGap=6)
CANNY_THRESH = (50, 150)


def get_home_resources():
    time.sleep(1)
    img = capture_array()
    x1, y1, x2, y2 = GOLD_REGION
    gold = digit_ocr.read_int(img[y1:y2, x1:x2]) or 0
    x1, y1, x2, y2 = ELIXIR_REGION
    elixir = digit_ocr.read_int(img[y1:y2, x1:x2]) or 0
    print(f'[RESOURCES] Gold={gold}, Elixir={elixir}')
    return (gold, elixir)


ROI_X0, ROI_Y0, ROI_X1, ROI_Y1 = (270, 100, 1339, 785)
TAP_HOME_X, TAP_HOME_Y = (738, 36)
SWIPE_START_X, SWIPE_START_Y = (809, 648)
SWIPE_END_X, SWIPE_END_Y = (809, 115)
SWIPE_DURATION_MS = 600
THRESHOLD = 0.9


def prepare_wall_search():
    """
1) Tap the home-base menu button
2) Swipe down twice to reveal all walls
"""
    host = main.host
    time.sleep(0.5)
    subprocess.run([ADB_BIN, '-s', host, 'shell', 'input', 'tap', str(TAP_HOME_X), str(TAP_HOME_Y)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
    time.sleep(1)
    for _ in range(6):
        subprocess.run([ADB_BIN, '-s', host, 'shell', 'input', 'swipe', str(SWIPE_START_X), str(SWIPE_START_Y), str(SWIPE_END_X), str(SWIPE_END_Y), str(SWIPE_DURATION_MS)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
    time.sleep(0.5)


def _match_coords_single(gray_roi, tpl_path, threshold):
    """Run matchTemplate for one template and return screen coords."""
    coords = []
    raw = imread_unicode(tpl_path, cv2.IMREAD_UNCHANGED)
    if raw is None:
        return coords
    if raw.ndim == 3 and raw.shape[2] == 4:
        bgr, alpha = (raw[..., :3], raw[..., 3])
        tpl_gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        mask = (alpha > 0).astype(np.uint8)
    else:
        tpl_gray = cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY)
        mask = None
    th, tw = tpl_gray.shape
    res = cv2.matchTemplate(gray_roi, tpl_gray, cv2.TM_CCOEFF_NORMED, mask=mask)
    dilated = cv2.dilate(res, np.ones((3, 3), np.uint8))
    ys, xs = np.where((res == dilated) & (res >= threshold))
    for y, x in zip(ys, xs):
        cx = ROI_X0 + x + tw // 2
        cy = ROI_Y0 + y + th // 2
        coords.append((cx, cy))
    return coords


def _dedupe_coords(coords, tol=10):
    """Remove near-duplicates within ±tol px (both axes). Keeps first occurrence."""
    out = []
    for cx, cy in coords:
        if any((abs(cx - ox) <= tol and abs(cy - oy) <= tol for ox, oy in out)):
            continue
        out.append((cx, cy))
    return out


def _load_wall_detect():
    """Параметры цветового детекта стен + тайминги из config/wall_detect.json (фолбэк)."""
    import json
    try:
        with open(os.path.join(BASE_DIR, 'config', 'wall_detect.json'), encoding='utf-8') as f:
            d = json.load(f)
    except Exception:
        d = {}
    return {
        'hsv_lo': tuple(d.get('hsv_lo', [88, 90, 150])),
        'hsv_hi': tuple(d.get('hsv_hi', [110, 255, 255])),
        'min_area': int(d.get('min_area_px', 30)),
        'tol': int(d.get('dedupe_tol_px', 18)),
        'cluster_dist': int(d.get('cluster_dist_px', 55)),
        'min_cluster': int(d.get('min_cluster_size', 5)),
        'tap_delay': tuple(d.get('tap_delay_sec', [0.4, 0.9])),
        'step_delay': tuple(d.get('step_delay_sec', [0.6, 1.4])),
    }


def _keep_wall_clusters(pts, dist, min_size):
    """Оставить точки только из КРУПНЫХ кластеров: стены — плотный грид (много ячеек
    рядом), а мелкие голубые выбросы (КОРАБЛИК на воде, синий декор) — отдельные
    мини-кластеры. Отсекаем их, иначе тап по кораблику уносит в другую деревню."""
    seen, out = set(), []
    for i in range(len(pts)):
        if i in seen:
            continue
        stack, comp = [i], []
        while stack:
            j = stack.pop()
            if j in seen:
                continue
            seen.add(j)
            comp.append(pts[j])
            jx, jy = pts[j]
            for k in range(len(pts)):
                if k not in seen and abs(pts[k][0] - jx) <= dist and abs(pts[k][1] - jy) <= dist:
                    stack.append(k)
        if len(comp) >= min_size:
            out.extend(comp)
    return out


_WALL_TIMINGS = None


def _wall_timings():
    """Кэш таймингов wall-флоу (грузим один раз; при правке конфига — перезапуск)."""
    global _WALL_TIMINGS
    if _WALL_TIMINGS is None:
        _WALL_TIMINGS = _load_wall_detect()
    return _WALL_TIMINGS


def find_all_wall_coords(threshold: float=None):
    """Поиск стен на карте ПО ЦВЕТУ (циан/голубой глоу стен) — ОДИН кадр, без свайпов.

    Цветовой детект инвариантен к зуму И повороту базы (в отличие от матчинга
    шаблона сегмента, который ломался при смене масштаба/угла). Маска HSV → компоненты
    → центры = точки тапа по стенам. Параметры цвета — config/wall_detect.json.
    Защита от зданий — на стороне upgrade (нужны обе иконки gold+elixir)."""
    cfg = _load_wall_detect()
    img = capture_array()
    if img is None or img.size == 0:
        print('[WALL] wall screenshot failed → skip')
        return []
    roi = img[ROI_Y0:ROI_Y1, ROI_X0:ROI_X1]
    if roi.size == 0:
        print('[WALL] wall ROI empty — check ROI bounds → skip')
        return []
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, cfg['hsv_lo'], cfg['hsv_hi'])
    n, _lab, stats, cent = cv2.connectedComponentsWithStats(mask, 8)
    coords = []
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= cfg['min_area']:
            coords.append((ROI_X0 + int(cent[i][0]), ROI_Y0 + int(cent[i][1])))
    # отсечь одиночные голубые выбросы (кораблик/декор) — тап по ним = переход в др. деревню
    coords = _keep_wall_clusters(coords, cfg['cluster_dist'], cfg['min_cluster'])
    coords = _dedupe_coords(coords, tol=cfg['tol'])
    coords.sort(key=lambda p: (p[1], p[0]))
    if not coords:
        print('[WALL] no walls detected by color (adjust config/wall_detect.json hsv)')
    else:
        print(f'[WALL] wall cells detected (color): {len(coords)}')
    return coords


def _hsleep(a, b):
    """Случайная человекоподобная пауза [a, b] сек (анти-бан)."""
    time.sleep(random.uniform(a, b))


def _tap(host, x, y, jitter=6, delay=None):
    """Тап с лёгким случайным смещением точки и СЛУЧАЙНОЙ паузой после (анти-мисклик
    + анти-бан). Диапазон паузы — из config/wall_detect.json (tap_delay_sec), если не
    задан явно. Джиттер мал (±6px), кнопки/стены широкие — попадание не страдает."""
    getattr(main, "pause_event", None) and main.pause_event.wait()  # строгая пауза
    jx = int(x) + random.randint(-jitter, jitter)
    jy = int(y) + random.randint(-jitter, jitter)
    subprocess.run([ADB_BIN, '-s', host, 'shell', 'input', 'tap', str(jx), str(jy)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   creationflags=CREATE_NO_WINDOW)
    _hsleep(*(delay or _wall_timings()['tap_delay']))


# Кнопки апгрейда стены в нижней панели действий (современный UI): отдельные
# Upgrade-золото и Upgrade-эликсир. Ищем их по ИКОНКЕ ресурса (монета/кристалл) —
# level-independent и иммунно к ивент-скидке (матчим иконку, а не зачёркнутую цену).
# Старый свотч verify_wall_level больше не нужен для позиционирования.
WALL_GOLD_ICON = os.path.join(TEMPLATE_DIR, 'wall_upgrade_gold.png')
WALL_ELIXIR_ICON = os.path.join(TEMPLATE_DIR, 'wall_upgrade_elixir.png')
PRICE_ROW = (600, 625, 1300, 675)   # ряд иконок цены в панели стены
WALL_BTN_Y = 690                    # y-центр кнопок Upgrade
ICON_TO_BTN_DX = -58                # смещение от иконки ресурса к центру её кнопки
WALL_ICON_THRESH = 0.80

# Проверка УРОВНЯ стены по подписи «Wall (Level N)» над нижней панелью. Цветовой детект
# на карте уровень не различает, а игровой шрифт подписи не берётся digit_ocr, поэтому
# держим пер-уровневые шаблоны ЧИСЛА (кремовый текст → бинарная маска) и матчим их.
WALLS_DIR = os.path.join(BASE_DIR, 'Templates', 'walls')
WALL_LEVEL_TEXT_DIR = os.path.join(WALLS_DIR, 'level_text')   # <N>.png — бинарная маска числа
WALL_LEVEL_TEXT_ROI = (560, 578, 1040, 622)  # строка «Wall (Level N)» (центрирована)
WALL_LEVEL_THRESH = 0.62


def _wall_cream_mask(bgr):
    """Кремовый текст подписи → бинарная маска (яркие R&G, умеренный B)."""
    b = bgr[:, :, 0].astype(int); g = bgr[:, :, 1].astype(int); r = bgr[:, :, 2].astype(int)
    return (((r > 170) & (g > 160) & (b < 190) & (r - b > 20)).astype('uint8')) * 255


def read_wall_level():
    """Уровень стены по подписи «Wall (Level N)» (матчинг пер-уровневых шаблонов числа).
    None — уверенно не определить (тогда безопаснее пропустить стену)."""
    import glob
    img = capture_array()
    if img is None:
        return None
    x0, y0, x1, y1 = WALL_LEVEL_TEXT_ROI
    roi = _wall_cream_mask(img[y0:y1, x0:x1])
    best_lvl, best_score = None, 0.0
    for p in glob.glob(os.path.join(WALL_LEVEL_TEXT_DIR, '*.png')):
        try:
            n = int(os.path.splitext(os.path.basename(p))[0])
        except ValueError:
            continue
        tpl = load_template(p, cv2.IMREAD_GRAYSCALE)
        if tpl is None or roi.shape[0] < tpl.shape[0] or roi.shape[1] < tpl.shape[1]:
            continue
        s = float(cv2.matchTemplate(roi, tpl, cv2.TM_CCOEFF_NORMED).max())
        if s > best_score:
            best_score, best_lvl = s, n
    if best_lvl is not None:
        print(f'[WALL] detected level L{best_lvl} (score {best_score:.2f})')
    return best_lvl if best_score >= WALL_LEVEL_THRESH else None


def _match_icon_x(img, name):
    """x-центр иконки ресурса в ряду цен, или None (порог WALL_ICON_THRESH)."""
    tpl = load_template(os.path.join(TEMPLATE_DIR, name), cv2.IMREAD_COLOR)
    if tpl is None:
        return None
    x0, y0, x1, y1 = PRICE_ROW
    row = img[y0:y1, x0:x1]
    if row.shape[0] < tpl.shape[0] or row.shape[1] < tpl.shape[1]:
        return None
    _, mx, _, loc = cv2.minMaxLoc(cv2.matchTemplate(row, tpl, cv2.TM_CCOEFF_NORMED))
    return (x0 + loc[0] + tpl.shape[1] // 2) if mx >= WALL_ICON_THRESH else None


def find_upgrade_button(resource):
    """(x, y) кнопки Upgrade нужного ресурса — ТОЛЬКО если это панель СТЕНЫ.

    Панель стены содержит И золото, И эликсир Upgrade (стена улучшается любым
    ресурсом). У зданий одна кнопка Confirm — пары нет. Так мы НЕ трогаем здания
    (защита от случайного апгрейда, напр. Hidden Tesla). None = не панель стены."""
    img = capture_array()
    if img is None:
        return None
    gx = _match_icon_x(img, 'wall_upgrade_gold.png')
    ex = _match_icon_x(img, 'wall_upgrade_elixir.png')
    if gx is None or ex is None:
        return None                               # не панель стены → не трогаем
    icon_x = gx if resource == 'gold' else ex
    return (icon_x + ICON_TO_BTN_DX, WALL_BTN_Y)


UPGRADE_WORD_TEMPLATE = os.path.join(TEMPLATE_DIR, 'upgrade_word.png')


def validate_upgrade_window():
    # Попап апгрейда — матчингом слова «Upgrade» (вместо OCR): score ~1.0 на попапе
    # против <0.18 на других экранах.
    img = capture_array()
    if img is None:
        return False
    x1, y1, x2, y2 = POPUP_REGION
    tpl = load_template(UPGRADE_WORD_TEMPLATE, cv2.IMREAD_GRAYSCALE)
    if tpl is None:
        return False
    roi = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
    if roi.shape[0] < tpl.shape[0] or roi.shape[1] < tpl.shape[1]:
        return False
    return float(cv2.matchTemplate(roi, tpl, cv2.TM_CCOEFF_NORMED).max()) >= 0.7


def _try_upgrade_wall_at(host, cx, cy, resource, wall_from=None, wall_to=None):
    """Тапнуть стену (cx, cy) → кнопка Upgrade ресурса → диалог → Confirm.
    True — апгрейд сделан; False — панель/кнопка не появились (не та стена / макс /
    не хватает ресурса: игра гасит кнопку) ИЛИ уровень стены вне диапазона [from..to).
    Все тапы человекоподобны (_tap/_hsleep)."""
    _tap(host, cx, cy)                         # тап по стене → нижняя панель
    _hsleep(0.7, 1.5)                          # ждём появления панели
    btn = find_upgrade_button(resource)
    if not btn:
        _tap(host, *DISMISS_COORD)             # панель не появилась / нет ресурса
        return False
    # Проверка УРОВНЯ по карточке: улучшаем только стены в диапазоне [from..to).
    # Цветовой детект на карте уровень не различает → без этого апгрейдились и стены
    # выше указанного. Уровень не прочитался → безопаснее пропустить, чем бить вслепую.
    if wall_from is not None and wall_to is not None:
        lvl = read_wall_level()
        if lvl is None:
            print('[WALL] level unreadable → skip this wall (safety)')
            _tap(host, *DISMISS_COORD)
            return False
        if not (wall_from <= lvl < wall_to):
            print(f'[WALL] wall L{lvl} out of range [{wall_from}..{wall_to}) → skip')
            _tap(host, *DISMISS_COORD)
            return False
    _hsleep(0.4, 1.1)                          # «прицеливание» перед кнопкой
    _tap(host, *btn)                           # Upgrade (золото/эликсир) → диалог
    _hsleep(0.7, 1.5)                          # ждём диалог подтверждения
    if not validate_upgrade_window():
        print('[WARN] Confirm dialog not detected → dismiss.')
        _tap(host, *DISMISS_COORD)
        return False
    _hsleep(0.3, 0.9)
    _tap(host, *CONFIRM_UPGRADE)               # Confirm
    _hsleep(0.4, 1.0)
    _tap(host, 1229, 25)                       # закрыть
    print(f'[OK] Wall upgraded using {resource}.')
    _hsleep(0.8, 1.6)
    return True


def upgrade_wall(resource, wall_level=None):
    """Одиночный апгрейд: пиксельный скан карты → первая подходящая стена."""
    host = main.host
    coords = find_all_wall_coords()
    if not coords:
        print(f'[WARN] No walls found on map → skip {resource}.')
        _tap(host, 422, 68)
        return False
    for cx, cy in reversed(coords):
        if _try_upgrade_wall_at(host, cx, cy, resource):
            return True
    print(f'[WARN] No upgradeable wall for {resource}.')
    return False


# Цены апгрейда стен по уровням — в конфиге (логика в коде, ПАРАМЕТРЫ снаружи).
WALL_PRICES_PATH = os.path.join(BASE_DIR, 'config', 'wall_prices.json')
MAX_WALL_UPGRADES_PER_CYCLE = 20   # предохранитель от бесконечного цикла
MAX_CONSEC_WALL_FAILS = 4          # подряд неудач (ложный детект/вне диапазона) → стоп


def load_wall_prices():
    """{'gold': {уровень: цена}, 'elixir': {...}} из config/wall_prices.json."""
    import json
    try:
        with open(WALL_PRICES_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {'gold': data.get('gold', {}), 'elixir': data.get('elixir', {})}
    except Exception as e:
        print(f'[WALL] price config not read ({e}) → price threshold unavailable')
        return {'gold': {}, 'elixir': {}}


def handle_home_resources(wall_from, wall_to=None, wall_gold_threshold=None,
                          wall_elixir_threshold=None):
    """Апгрейд стен в диапазоне уровней [wall_from..wall_to] с НЕСКОЛЬКИМИ проходами
    за цикл (пока хватает ресурса — «дешёвый забор = несколько уровней за прогон»).

    Порог лота = цена уровня wall_from из config/wall_prices.json (или ручной, если
    задан). Уровень каждой стены не читаем — игра сама гасит недоступные кнопки
    (иммунно к ивент-скидке). Ошибки не роняют бота — только скип шага."""
    try:
        prices = load_wall_prices()
        gold, elixir = get_home_resources()
        host = main.host
        coords = find_all_wall_coords()            # ОДИН скан карты на цикл
        if not coords:
            print('[WALL] No walls found on the map → skip.')
            _tap(host, 422, 68)
            return
        for resource, loot, manual in (('gold', gold, wall_gold_threshold),
                                       ('elixir', elixir, wall_elixir_threshold)):
            # ПРИОРИТЕТ у конфига цен (параметры снаружи); ручной порог — фолбэк,
            # если уровня нет в config/wall_prices.json.
            cfg_price = prices.get(resource, {}).get(str(wall_from))
            threshold = cfg_price if cfg_price else (manual or 10 ** 12)
            done = i = fails = 0
            while loot >= threshold and done < MAX_WALL_UPGRADES_PER_CYCLE and i < len(coords):
                cx, cy = coords[-1 - i]            # с конца (визуальный порядок)
                i += 1
                if _try_upgrade_wall_at(host, cx, cy, resource, wall_from, wall_to):
                    done += 1
                    fails = 0
                    g, e = get_home_resources()
                    loot = g if resource == 'gold' else e
                else:
                    # Ложный детект (не забор / вне диапазона / макс). Много подряд →
                    # улучшаемых стен нет, дальше тапать бессмысленно — выходим.
                    fails += 1
                    if fails >= MAX_CONSEC_WALL_FAILS:
                        print(f'[WALL] {resource}: {fails} misses in a row → no upgradeable walls, stop')
                        break
                _hsleep(*_wall_timings()['step_delay'])   # анти-мисклик между стенами
            print(f'[WALL] {resource}: upgraded this cycle {done} '
                  f'(range L{wall_from}-{wall_to}, threshold {threshold}, loot {loot})')
    except Exception as e:
        import traceback
        print(f'[WARN] wall upgrade skipped due to error: {e}')
        traceback.print_exc()


if __name__ == '__main__':
    handle_home_resources(wall_from=12, wall_to=14)
