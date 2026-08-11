
from __future__ import annotations
import os, sys, subprocess, time, random
import cv2, numpy as np

# ───────────────────── project paths ─────────────────────
project_root = os.path.abspath(os.path.join(__file__, os.pardir, os.pardir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import main
from adb_config       import ADB_BIN
from screenshot_utils import take_screenshot, capture_array, load_template
from unicode          import imread_unicode

CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

# base dir for templates
BASE_DIR      = project_root
TEMPLATE_DIR  = os.path.join(BASE_DIR, "Templates")
SCREENSHOT_PATH = os.path.join(BASE_DIR, "toAttack.png")

# ───────────────────── templates / tab names ─────────────────────
TM_NAMES = [
    "dragon", "E_Drag", "balloon", "siege_with_troops", "empty_siege",
    "queen", "bk", "warden", "prince", "duke", "rc", "rage", "freeze","event_goblin", "azure_dragon", "ice_minion", "ice_golem"
]

MATCH_THRESHOLD = 0.5
TABS: dict[str, tuple[int,int]] = {}

# ───────────────────── coordinate presets ─────────────────────
# LEFT‑side originals (existing values)
DRAGON_L = [
    (170,384), (214,348), (246,327), (270,306), (305,285), (345,255),
    (368,238), (396,216), (417,201), (442,182), (487,152), (535,121),
    (640,35), (442,182)
]
BALLOON_L = [
    (170,384), (214,348), (246,327), (270,306), (305,285), (345,255),
    (368,238), (396,216), (417,201), (444,183), (486,1154), (534,122),
    (345,255), (444,183), (368,238), (246,327), (417,201)
]
RAGE_L   = [(549,353), (674,247), (797,317), (690,439), (777, 403)]
FREEZE_L = [(614,371), (769,276), (770,363), (704, 494), (798, 405), (874, 405)]

# Hero tab‑tap coordinates (left)
HERO_L = [
    {"name":"siege_machine",    "coord":(364,236)},
    {"name":"Queen",            "coord":(364,236)},
    {"name":"BK",               "coord":(513,135)},
    {"name":"Warden",           "coord":(445,191)},
    {"name":"Prince",           "coord":(445,191)},
    {"name":"Duke",           "coord":(445,191)},
    {"name":"RC",               "coord":(426,204)}
]
# take the 5 median heroes for deployment (drop first & last)
HERO_L_MEDIAN = HERO_L

# RIGHT‑side explicit dragon coordinates provided by user
DRAGON_R = [
    (1344,346), (1272,295), (1234,261), (1191,229), (1150,200), (1116,173),
    (1074,138), (1042,114), (1000,91),  (946,47),  (904,18),  (1033,108),
    (1091,152), (1109,172)
]
# balloon pattern mirrors dragon pattern 1‑to‑1
BALLOON_R = DRAGON_R.copy()
BALLOON_R.extend([
    (1207, 209),
    (1296, 273),
    (1311, 256)
])

# hero median coords mirrored horizontally vs 1440‑px wide screen
SCREEN_W = 1600  # MEmu display width (1600×900)
HERO_R_MEDIAN = [
    {
        "name": h["name"],
        "coord": (SCREEN_W - 1 - h["coord"][0], h["coord"][1])
    } for h in HERO_L_MEDIAN
]

# derive electro dragon coords: take 10 middle pts of DRAGON_L / DRAGON_R
E_DRAGON_L = DRAGON_L[2:12]   # 10 middle
E_DRAGON_R = DRAGON_R[2:12]

# ice minion: 10 middle dragon points *events troop*
ICE_MINION_L = DRAGON_L[2:12]   
ICE_MINION_R = DRAGON_R[2:12] 

# ice golem: 5 middle dragon points *events troop*
ICE_GOLEM_L = DRAGON_L[4:9]  
ICE_GOLEM_R = DRAGON_R[4:9]   

# rage & freeze right coords are horizontal flips of left set
RAGE_R   = [(SCREEN_W-1-x, y) for x,y in RAGE_L]
FREEZE_R = [(SCREEN_W-1-x, y) for x,y in FREEZE_L]
AZURE_DRAGON_L = [ HERO_L_MEDIAN[2]["coord"] ]
AZURE_DRAGON_R = [ HERO_R_MEDIAN[2]["coord"] ]

PATTERNS = {
    "left": {
        "dragon":  DRAGON_L,
        "e_drag":E_DRAGON_L,
        "balloon": BALLOON_L,
        "heroes":  HERO_L_MEDIAN,
        "rage":    RAGE_L,
        "freeze":  FREEZE_L,
        "azure_dragon":  AZURE_DRAGON_L,
        "ice_minion": ICE_MINION_L,
        "ice_golem":    ICE_GOLEM_L,
    },
    "right": {
        "dragon":  DRAGON_R,
        "e_drag":E_DRAGON_R,
        "balloon": BALLOON_R,
        "heroes":  HERO_R_MEDIAN,
        "rage":    RAGE_R,
        "freeze":  FREEZE_R,
        "azure_dragon":  AZURE_DRAGON_R,
        "ice_minion":   ICE_MINION_R,
        "ice_golem":    ICE_GOLEM_R,
    },
}

# DEPLOY_COORDS will be bound to the chosen side at runtime
DEPLOY_COORDS: dict[str, list] = {}

# Which side is currently being used ("left" or "right")
SIDE: str = "left"


def _load_deploy_cfg():
    """Параметры рандомизации высадки из config/antiban.json (логика в коде,
    значения снаружи). Пустой/битый конфиг → дефолты."""
    import json
    try:
        with open(os.path.join(BASE_DIR, "config", "antiban.json"), encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        d = {}
    return {
        "drop_delay":   tuple(d.get("deploy_drop_delay_sec", [0.02, 0.10])),
        "jitter_left":  tuple(d.get("deploy_jitter_left",  [0, 39, -27, 0])),
        "jitter_right": tuple(d.get("deploy_jitter_right", [-44, 0, -33, 0])),
        "event_target": tuple(d.get("event_potion_target", [800, 430])),
        "chunk":        int(d.get("deploy_chunk", 6)),
    }


# Ивент-банки, которые кидаем в центр базы (event-only: только если есть в баре):
# тотем (агрит пушки) + DE-лут (на хранилище чёрного эликсира) — оба здания центральные.
EVENT_DEPLOY_POTIONS = ("event_aggro_totem_potion.png", "event_de_loot_potion.png")


def _find_potion_slot_x(shot_bgr, name, thresh=0.70):
    """x-центр слота банки `name` в деплой-баре, или None (её нет в баре / нет ивента)."""
    tpl = load_template(os.path.join(TEMPLATE_DIR, name), cv2.IMREAD_COLOR)
    if tpl is None:
        return None
    strip = shot_bgr[745:835, :]
    if strip.shape[0] < tpl.shape[0] or strip.shape[1] < tpl.shape[1]:
        return None
    _, mx, _, loc = cv2.minMaxLoc(cv2.matchTemplate(strip, tpl, cv2.TM_CCOEFF_NORMED))
    return (loc[0] + tpl.shape[1] // 2) if mx >= thresh else None


def deploy_event_potions():
    """EVENT-ONLY: если событийные банки (тотем/DE-лут) есть в баре — прожать их в
    ЦЕНТР вражеской базы (там и оборона, и DE-хранилище). Нет банки = нет ивента → скип.
    Точка центра — config/antiban.json (event_potion_target)."""
    shot = capture_array()
    if shot is None:
        return
    tx, ty = DEPLOY_CFG["event_target"]
    for name in EVENT_DEPLOY_POTIONS:
        sx = _find_potion_slot_x(shot, name)
        if sx is None:
            continue
        print(f"→ Event potion {name} → base center ({tx},{ty})")
        _ensure_active()                                           # бой прерван? — не тапаем
        run_adb(["shell", "input", "tap", str(sx), str(SLOT_Y)])   # выбрать слот банки
        human_delay(0.4, 0.9)
        jx, jy = jitterCoord(tx, ty)
        run_adb(["shell", "input", "tap", str(jx), str(jy)])       # кинуть в центр
        human_delay(0.6, 1.2)
        new_shot = capture_array()                # бар изменился — обновим кадр
        if new_shot is not None:
            shot = new_shot


DEPLOY_CFG = _load_deploy_cfg()
# Сколько тапов слать одним adb-вызовом при высадке (баланс скорость/отзывчивость
# на прерывание боя): чем больше — быстрее, но реже проверяется stop/бой.
DEPLOY_CHUNK = int(DEPLOY_CFG.get("chunk", 6))


def jitterCoord(x: int, y: int) -> tuple[int, int]:
    """Случайно сместить точку высадки (человекоподобно). Диапазоны на сторону —
    из config/antiban.json (deploy_jitter_left/right = [dx_min, dx_max, dy_min, dy_max])."""
    if SIDE == "left":
        ax, bx, ay, by = DEPLOY_CFG["jitter_left"]
    elif SIDE == "right":
        ax, bx, ay, by = DEPLOY_CFG["jitter_right"]
    else:
        ax, bx, ay, by = (-10, 10, -10, 10)
    return x + random.randint(ax, bx), y + random.randint(ay, by)

# ───────────────────── human-like timing ─────────────────────

def human_delay(a: float, b: float) -> None:
    """Случайная человекоподобная пауза в диапазоне [a, b] секунд.

    Используется, чтобы не действовать мгновенно/однотипно (снижает риск
    детекта автоматизации). См. также jitterCoord (случайная точка тапа).
    """
    time.sleep(random.uniform(a, b))

# ───────────────────── adb helpers ─────────────────────

def run_adb(cmd):
    # строгая пауза: заморозка на ближайшем adb-действии, если нажали Pause
    getattr(main, "pause_event", None) and main.pause_event.wait()
    try:
        subprocess.run(
            [ADB_BIN, "-s", main.host] + cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=CREATE_NO_WINDOW
        )
        return True
    except subprocess.CalledProcessError as e:
        print("[ADB]", e.stderr.decode().strip())
        return False


def run_adb_taps(points):
    """Несколько тапов ОДНИМ adb-вызовом (`input tap` через ';' на устройстве).
    Убирает главный тормоз высадки — запуск adb.exe на КАЖДЫЙ тап (оверхед ~50-100мс
    на Windows). Пауза/стоп проверяются вызывающим по чанкам (см. _ensure_active)."""
    if not points:
        return True
    getattr(main, "pause_event", None) and main.pause_event.wait()
    cmd = " ; ".join(f"input tap {int(x)} {int(y)}" for x, y in points)
    try:
        subprocess.run(
            [ADB_BIN, "-s", main.host, "shell", cmd],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=CREATE_NO_WINDOW,
        )
        return True
    except subprocess.CalledProcessError as e:
        print("[ADB]", e.stderr.decode().strip())
        return False

# ───────────────────── abort guard (бой прерван) ─────────────────────
# Если пользователь прервал бой (сдался/бой закончился/вышли на базу) или нажал Stop,
# стратегия НЕ должна продолжать слепо тапать по экрану. Проверяем «бой ещё идёт»
# перед каждым шагом высадки и периодически внутри длинных циклов тапов.

class _AttackAborted(Exception):
    """Бой прерван/закончился или нажат Stop — прекращаем высадку по стратегии."""


_last_battle_chk = [0.0, True]      # (время, активен ли бой) — троттлинг проверки


def _battle_active(force: bool = False) -> bool:
    """True, пока идёт бой. False, если появился экран результатов (Return Home /
    Claim Reward) — бой прерван пользователем/закончился. Троттлинг ~0.4с, чтобы не
    снимать экран на каждый тап."""
    now = time.time()
    if not force and now - _last_battle_chk[0] < 0.4:
        return _last_battle_chk[1]
    active = True
    try:
        if main.battle_ended():         # виден экран результатов → бой не идёт
            active = False
    except Exception:
        pass
    _last_battle_chk[0] = now
    _last_battle_chk[1] = active
    return active


_guard_t = [0.0]        # троттлинг тяжёлой части guard'а (скриншот)


def _ensure_active() -> None:
    """Guard высадки, вызывается по шагам/чанкам:
    (1) при Stop или прерванном/законченном бое бросает _AttackAborted;
    (2) следит за HP героев В ТЕЧЕНИЕ ВСЕЙ высадки (а не только в speed_up) и жмёт
        способность при низком HP — иначе герой умирал до старта фазы speed_up.
    Тяжёлая часть (скриншот + детекты) троттлится ~0.5с; проверка Stop — всегда."""
    ev = getattr(main, "stop_event", None)
    if ev is not None and ev.is_set():
        raise _AttackAborted("stop pressed")
    now = time.time()
    if now - _guard_t[0] < 0.3:                  # чаще опрашиваем — HP падает быстро
        return
    _guard_t[0] = now
    shot = capture_array()
    if shot is not None:
        try:
            monitor_hero_hp(shot)           # герой при низком HP → прожать способность
        except Exception:
            pass
    if not _battle_active(force=True):       # бой прерван/закончился?
        raise _AttackAborted("battle interrupted / ended")


def _sleep_monitor(secs: float) -> None:
    """Пауза `secs`, но НЕ слепая: каждые ~0.25с дёргаем guard (проверка боя +
    мониторинг HP героев). Иначе во время долгих sleep в кастах заклов герой успевал
    умереть, не попав в окно активации между замерами."""
    end = time.time() + secs
    while time.time() < end:
        _ensure_active()
        time.sleep(min(0.25, max(0.0, end - time.time())))


# ───────────────────── imaging helpers ─────────────────────

def capture_screenshot():
    img = capture_array()                      # кадр в память, без диск-раунд-трипа
    if img is None:
        print("[ERROR] take_screenshot failed")
        return None
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img


def find_tab(template_name: str, screenshot):
    path = os.path.join(TEMPLATE_DIR, f"{template_name}.png")
    tpl = load_template(path, cv2.IMREAD_GRAYSCALE)

    if tpl is None:
        print("[TPL] missing", path); return None
    if screenshot is None:
        return None
    res = cv2.matchTemplate(screenshot, tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    if max_val < MATCH_THRESHOLD:
        print(f"[TPL] {template_name} not found ({max_val:.2f})")
        return None
    h,w = tpl.shape
    return (max_loc[0] + w//2,  max_loc[1] + h//2)


def update_tabs():
    print("\n=== Detecting troop tabs ===")
    shot = capture_screenshot()
    if shot is None:
        return {}

    # 1) detect everything (raw), including both siege templates
    raw: dict[str, tuple[int,int] | None] = {
        name.lower(): find_tab(name, shot)
        for name in TM_NAMES
    }

    # 2) re-match siege templates to get their scores
    def match_score(name: str) -> tuple[tuple[int,int] | None, float]:
        tpl_path = os.path.join(TEMPLATE_DIR, f"{name}.png")
        tpl = load_template(tpl_path, cv2.IMREAD_GRAYSCALE)

        res = cv2.matchTemplate(shot, tpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        print(f"[DEBUG] {name}: max match = {max_val:.3f}")
        if max_val >= MATCH_THRESHOLD:
            h, w = tpl.shape
            coord = (max_loc[0] + w//2, max_loc[1] + h//2)
        else:
            coord = None
        return coord, max_val

    swt_coord, swt_score = match_score("siege_with_troops")
    es_coord,  es_score  = match_score("empty_siege")

    # 3) pick the stronger one
    if swt_coord and swt_score >= es_score:
        siege_coord = swt_coord
    else:
        siege_coord = es_coord

    # 4) build the final tabs dict
    tabs = {
        "dragon":        raw.get("dragon"),
        "e_drag":        raw.get("e_drag"),
        "balloon":       raw.get("balloon"),
        "siege_machine": siege_coord,
        "queen":         raw.get("queen"),
        "bk":            raw.get("bk"),
        "warden":        raw.get("warden"),
        "prince":        raw.get("prince"),
        "duke":          raw.get("duke"),
        "rc":            raw.get("rc"),
        "rage":          raw.get("rage"),
        "freeze":        raw.get("freeze"),
        "azure_dragon":  raw.get("azure_dragon"),
        "ice_minion":    raw.get("ice_minion"),
        "ice_golem":     raw.get("ice_golem"),
    }
    return tabs

# ───────────────────── deploy helpers ─────────────────────

def deploy_troops(troop_key):
    tab = TABS.get(troop_key)
    if not tab:
        print("[SKIP] tab not found for", troop_key); return
    coords = DEPLOY_COORDS.get(troop_key, [])
    if not coords:
        print("[SKIP] no coords for", troop_key); return
    print(f"\n→ Deploying {troop_key} ({len(coords)} taps)")
    _ensure_active()                                # бой прерван? — не тапаем
    global _last_selected
    run_adb(["shell","input","tap",*map(str,tab)])
    _last_selected = tuple(tab)                     # запомнить выбор (вернём после активации героя)
    human_delay(0.25, 0.5)                          # человек не переключает таб мгновенно

    # Высадка БАТЧАМИ: чанк тапов одним adb-вызовом (быстро), между чанками —
    # проверка боя + короткая пауза (нерегулярный ритм). Точка высадки — с jitter.
    pts = [jitterCoord(x, y) for x, y in coords]
    for i in range(0, len(pts), DEPLOY_CHUNK):
        _ensure_active()                           # бой ещё идёт?
        run_adb_taps(pts[i:i + DEPLOY_CHUNK])
        human_delay(*DEPLOY_CFG["drop_delay"])     # пауза между чанками

def deploy_heroes():
    print("\n→ Deploying Heroes")
    global _last_selected
    _last_selected = None                                   # во время высадки героев нечего восстанавливать
    for hero in DEPLOY_COORDS["heroes"]:
        tab = TABS.get(hero["name"].lower())
        if not tab:
            print("[SKIP] tab for", hero["name"]); continue
        _ensure_active()                                   # бой прерван? — не тапаем
        run_adb(["shell","input","tap", *map(str, tab)])   # выбрать таб героя
        human_delay(0.35, 0.9)                             # человек не переключается мгновенно
        jx, jy = jitterCoord(*hero["coord"])
        run_adb(["shell","input","tap", str(jx), str(jy)]) # высадить героя
        _deployed_at[hero["name"].lower()] = time.time()   # теперь его можно мониторить
        human_delay(0.5, 1.2)                              # пауза перед следующим героем

def deploy_spells(spell_key):
    tab = TABS.get(spell_key)
    if not tab:
        print("[SKIP] tab not found for", spell_key); return
    coords = DEPLOY_COORDS.get(spell_key, [])
    print(f"\n→ Casting {spell_key} ({len(coords)} taps)")
    _ensure_active()                                # бой прерван? — не тапаем
    global _last_selected
    run_adb(["shell","input","tap",*map(str,tab)])
    _last_selected = tuple(tab)                     # запомнить выбор (вернём после активации героя)
    delay = 1 if spell_key == "rage" else 2
    for x, y in coords:
        _sleep_monitor(delay)                      # ждать, но мониторить HP героев (не слепо)
        jx, jy = jitterCoord(x, y)
        run_adb(["shell","input","tap", str(jx), str(jy)])

def retap_heroes():
    print("\n→ Retapping hero abilities")
    for tag in ("warden","queen","bk","prince","rc","duke"):
        if tab := TABS.get(tag):
            _ensure_active()                       # бой прерван? — не тапаем
            run_adb(["shell","input","tap",*map(str,tab)])
            human_delay(0.25, 0.6)                 # способности не жмут мгновенно подряд

# ───────────────────── battle speed-up ─────────────────────
# Green "1x" button on the right side during battle. Tapping it cycles the
# battle speed 1x → 2x → 3x → 4x. Fixed UI position (independent of attack side).
SPEED_BUTTON = (1512, 507)
# 'TRY AGAIN' centre within Templates/Connection_lost.png (977x296).
TRY_AGAIN_OFFSET = (118, 247)
CONN_THRESHOLD = 0.6
_conn_tpl = None

_speed_tpl = None

def _speed_button_present(shot_bgr):
    """True, если зелёная кнопка «1x» ускорения реально на экране — МАТЧИНГ эталона
    speed_button_1x.png (надёжнее эвристики зелёного покрытия, которая ложно
    срабатывала в начале боя, из-за чего бот «ускорял» пустоту)."""
    global _speed_tpl
    if _speed_tpl is None:
        _speed_tpl = imread_unicode(os.path.join(TEMPLATE_DIR, "speed_button_1x.png"),
                                    cv2.IMREAD_COLOR)
    if _speed_tpl is None:
        return False
    x, y = SPEED_BUTTON
    reg = shot_bgr[max(0, y - 60):y + 60, max(0, x - 90):x + 90]
    if reg.shape[0] < _speed_tpl.shape[0] or reg.shape[1] < _speed_tpl.shape[1]:
        return False
    return float(cv2.matchTemplate(reg, _speed_tpl, cv2.TM_CCOEFF_NORMED).max()) >= 0.80

def _handle_connection_lost(shot_gray):
    """If the 'Connection lost' popup is up (network dropped mid-attack), tap its
    TRY AGAIN button to reconnect. Returns True when it acted."""
    global _conn_tpl
    if _conn_tpl is None:
        _conn_tpl = imread_unicode(os.path.join(TEMPLATE_DIR, "Connection_lost.png"),
                                   cv2.IMREAD_GRAYSCALE)
    if _conn_tpl is None:
        return False
    res = cv2.matchTemplate(shot_gray, _conn_tpl, cv2.TM_CCOEFF_NORMED)
    _, maxv, _, maxloc = cv2.minMaxLoc(res)
    if maxv < CONN_THRESHOLD:
        return False
    tx = maxloc[0] + TRY_AGAIN_OFFSET[0]
    ty = maxloc[1] + TRY_AGAIN_OFFSET[1]
    print(f"[CONN] Connection lost (score={maxv:.2f}) — tapping TRY AGAIN at ({tx},{ty})")
    run_adb(["shell", "input", "tap", str(tx), str(ty)])
    time.sleep(3)
    return True

# ───────────────────── hero auto-ability (#4) ─────────────────────
# Мониторинг HP-полоски (зелёная сверху карточки) каждого задеплоенного героя.
# При HP < порога (полоска мигает) прожимаем героя — восполняет часть HP и активирует
# способность, вне зависимости от цикла стратегии.
_HERO_KEYS = ("bk", "queen", "warden", "prince", "duke", "rc")
_hero_cfg_cache = None
_hero_last_activate: dict[str, float] = {}
_hero_dbg_t = [0.0]                        # троттлинг debug-лога чтения HP
_last_selected: tuple | None = None        # последний выбранный слот/таб высадки (закл/войско/банка)
_deploy_phase = False                       # идёт фаза высадки (в speed_up восстановление не нужно)
_deployed_at: dict[str, float] = {}        # герой → время высадки (deploy_heroes/MBR).
_hero_dead_count: dict[str, int] = {}      # подряд «0.0» замеров (подтверждение смерти)
_hero_monitor_done = False                 # все герои мертвы/активированы — мониторинг стоп
# Только высаженных можно мониторить/жать: тап по карточке НЕвысаженного = его ВЫСАДКА,
# а не активация способности. Время нужно для ПРОАКТИВНЫХ героев (Warden).


def _load_hero_cfg():
    global _hero_cfg_cache
    if _hero_cfg_cache is not None:
        return _hero_cfg_cache
    import json
    try:
        with open(os.path.join(BASE_DIR, "config", "heroes.json"), encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        d = {}
    _hero_cfg_cache = {
        "enabled": bool(d.get("enabled", True)),
        "hp_threshold": float(d.get("hp_threshold", 0.30)),
        "cooldown": float(d.get("reactivate_cooldown_sec", 8)),
        "bar_y": tuple(d.get("bar_y", [717, 725])),
        "half_w": int(d.get("bar_half_w", 46)),
        "min_alive": float(d.get("min_alive_frac", 0.03)),
        "proactive": {s.lower() for s in d.get("proactive_heroes", ["warden"])},
        "proactive_delay": float(d.get("proactive_delay_sec", 4)),
        "debug": bool(d.get("debug", False)),
    }
    return _hero_cfg_cache


def _hero_hp_fraction(shot_bgr, cx, cfg):
    """Доля заполнения HP-полоски героя (0..1) по зелёным столбцам в полосе бара.
    Полоска зелёная на заполненной части и тёмная/красная на пустой; ширина зелёного
    ≈ HP%. Возвращает долю столбцов бара, содержащих зелёные пиксели."""
    y0, y1 = cfg["bar_y"]
    x0, x1 = cx - cfg["half_w"], cx + cfg["half_w"]
    strip = shot_bgr[y0:y1, x0:x1]
    if strip.size == 0:
        return 0.0
    b = strip[:, :, 0].astype("int16")
    g = strip[:, :, 1].astype("int16")
    r = strip[:, :, 2].astype("int16")
    green = (g > 110) & (g - r > 25) & (g - b > 25)      # зелёный HP
    col_has_green = green.any(axis=0)                     # столбец с зелёным
    return float(col_has_green.mean())


def _restore_selection():
    """После активации способности героя тап пришёлся на карточку героя и СБРОСИЛ выбор
    закла/войска/банки → оставшиеся касты/высадки уходили в никуда. Возвращаем курсор на
    последний выбранный слот. Только в фазе высадки (в speed_up восстанавливать нечего)."""
    if _deploy_phase and _last_selected:
        run_adb(["shell", "input", "tap", str(_last_selected[0]), str(_last_selected[1])])
        human_delay(0.1, 0.25)


def monitor_hero_hp(shot_bgr):
    """Прожать способность у героев с HP ниже порога (config/heroes.json). Тапает
    карточку героя (TABS) — это активирует способность и чуть лечит. Уважает кулдаун
    на героя, чтобы не спамить. min_alive отсекает мёртвых/невысаженных (нет бара)."""
    global _hero_monitor_done
    cfg = _load_hero_cfg()
    if not cfg["enabled"] or _hero_monitor_done:
        return
    now = time.time()
    # только УЖЕ высаженные герои: до высадки тап по карточке = высадка, не способность
    keys = [k for k in _HERO_KEYS if k in _deployed_at and TABS.get(k)]
    if not keys:
        return
    dbg = cfg["debug"] and (now - _hero_dbg_t[0] > 2.5)
    if dbg:
        _hero_dbg_t[0] = now
        reads = {k: round(_hero_hp_fraction(shot_bgr, TABS[k][0], cfg), 2) for k in keys}
        print(f"[HERO][dbg] HP fractions: {reads}")
    done = 0                                              # герои «завершённые»: активирован ИЛИ мёртв
    for key in keys:
        tab = TABS[key]
        if key in _hero_last_activate:
            done += 1
            continue                                     # способность уже прожата — больше не трогаем
        # ПРОАКТИВНЫЕ герои (Warden): HP-полоска ненадёжна (в воздухе читается полной до
        # смерти), поэтому жмём способность один раз через proactive_delay после высадки.
        if key in cfg["proactive"]:
            if now - _deployed_at[key] >= cfg["proactive_delay"]:
                print(f"[HERO] {key} proactive ability (+{cfg['proactive_delay']:.0f}s after deploy)")
                run_adb(["shell", "input", "tap", *map(str, tab)])
                _hero_last_activate[key] = now
                human_delay(0.2, 0.5)
                _restore_selection()
                done += 1
            continue
        frac = _hero_hp_fraction(shot_bgr, tab[0], cfg)
        if frac < cfg["min_alive"]:
            # мёртв/нет бара — но одиночный 0.0 бывает шальным кадром: подтверждаем 2 замера
            _hero_dead_count[key] = _hero_dead_count.get(key, 0) + 1
            if _hero_dead_count[key] >= 2:
                done += 1                                # подтверждённо мёртв/ушёл
            continue
        _hero_dead_count[key] = 0
        if frac >= cfg["hp_threshold"]:
            continue                                     # HP в норме
        print(f"[HERO] {key} HP low ({frac*100:.0f}%) → activating ability")
        run_adb(["shell", "input", "tap", *map(str, tab)])
        _hero_last_activate[key] = now
        human_delay(0.2, 0.5)
        _restore_selection()                             # вернуть курсор на закл/войско
        done += 1
    if done >= len(keys):
        # все высаженные герои мертвы или уже активированы — дальше мониторить незачем
        _hero_monitor_done = True
        print("[HERO] all heroes dead or abilities used → stop monitoring")


def speed_up(timeout=200):
    """Wait for the '1x' speed button (only appears in the last minute), then tap
    once -> x4. Meanwhile recovers from the 'Connection lost' popup, and stops
    if the battle ends first (e.g. a fast 3-star)."""
    print("\n→ Waiting for x4 speed button…")
    t0 = time.time()
    while time.time() - t0 < timeout:
        shot = capture_array()
        if shot is None:
            time.sleep(2); continue
        gray = cv2.cvtColor(shot, cv2.COLOR_BGR2GRAY)
        if _handle_connection_lost(gray):
            continue                              # popup handled; keep waiting
        monitor_hero_hp(shot)                     # #4: прожать способность героя при низком HP
        if _speed_button_present(shot):
            print("→ Speeding up battle (x4)")
            run_adb(["shell", "input", "tap", str(SPEED_BUTTON[0]), str(SPEED_BUTTON[1])])
            return
        try:
            if main.battle_ended():
                print("[speed] battle already ended — nothing to speed up")
                return
        except Exception:
            pass
        time.sleep(0.6)                           # чаще опрашиваем — HP героев падает быстро
    print("[speed] speed button did not appear within timeout")
# ───────────────────── public API ─────────────────────

def run_attack(cfg: dict|None = None):
    """Entry called from GUI. Chooses side + executes chosen strategy."""
    attack = (cfg or {}).get("attack", "Dragon_Attack")

    # #7 совместимость со стратегиями MyBot-MBR: attack вида "csv:<имя>" исполняется
    # интерпретатором MBR-CSV (папка strategies/), а не встроенной последовательностью.
    if isinstance(attack, str) and attack.startswith("csv:"):
        import mbr_csv
        mbr_csv.run_csv_attack(mbr_csv.strategy_path(attack[4:]), cfg)
        return

    side   = random.choice(["left", "right"])
    print(f"\n==== {attack} on {side.upper()} side ====")

    # bind global coordinate set
    global DEPLOY_COORDS, TABS, SIDE
    DEPLOY_COORDS = PATTERNS[side]
    SIDE = side

    # #3 человекоподобная пауза перед высадкой: не бьём в ту же секунду, как
    # появилась база (моделируем «осмотр» деревни игроком). ВАЖНО: пауза ДО детекта
    # табов — экран боя успевает устаканиться, распознавание войск стабильнее.
    pre_delay = (cfg or {}).get("pre_attack_delay", (2.5, 6.0))
    print(f"…pause before deploy ({pre_delay[0]:.1f}-{pre_delay[1]:.1f}s)")
    human_delay(pre_delay[0], pre_delay[1])

    TABS = update_tabs()
    _hero_last_activate.clear()                  # #4: кулдауны способностей — с чистого листа
    _deployed_at.clear()                         # никого ещё не высадили — не мониторим
    _hero_dead_count.clear()
    global _deploy_phase, _last_selected, _hero_monitor_done
    _hero_monitor_done = False
    _deploy_phase = True                         # фаза высадки: после активации героя вернём выбор
    _last_selected = None

    try:
        deploy_event_potions()          # event-only: тотем/DE-лут в центр базы (если есть в баре)
        if attack == "Dragon_Attack":
            _dragon_sequence()
        elif attack == "ElectroDragon_Attack":
            _edragon_sequence()
        else:
            print("[ERROR] Unknown attack:", attack)
            return
        # Если авто-способность по HP включена — НЕ прожимаем способности сразу
        # (иначе к моменту низкого HP они уже потрачены/на кулдауне). Бережём их:
        # активирует monitor_hero_hp в speed_up при HP < порога. Иначе — старое
        # поведение: прожать все способности сразу после высадки.
        if not _load_hero_cfg()["enabled"]:
            retap_heroes()
    except _AttackAborted as e:
        # Пользователь прервал бой / нажал Stop → НЕ тапаем дальше по стратегии.
        # Управление уходит наверх (one_cycle): проверка «бой закончен / мы на базе».
        print(f"[ABORT] strategy stopped — {e}; skipping remaining taps & speed-up")
        return
    except Exception as e:
        import traceback
        print("[WARN] attack sequence error, continuing to speed-up:", e)
        traceback.print_exc()
    _deploy_phase = False                         # высадка окончена — в speed_up выбор не восстанавливаем
    # always try to speed up, even if a step above failed
    speed_up()
    print("\n=== Attack script finished ===")

# ───────────────────── sequences ─────────────────────

# ── deploy-bar geometry (1600x900) ──
# The bar sits along the bottom; icon centres are found dynamically (slot spacing
# shifts with army composition, so a fixed grid is unreliable).
SLOT_Y = 790
BAR_TOP, BAR_BOT = 745, 835

# Slots to protect from the "dump remaining" sweep: heroes (a tap would trigger
# their ability early), spells (a tap would waste them) and the siege/battle-blimp
# with reinforcements — #5: после высадки шар с подкрепом трогать нельзя, пока его
# не собьют пушки или не выйдет его время; иначе повторный тап собьёт логику.
# Позиции слотов берутся из update_tabs(), где все табы уже найдены в начале атаки.
PROTECTED_KEYS = ("queen", "bk", "warden", "prince", "duke", "rc", "rage", "freeze",
                  "siege_machine")

# Банки-предметы (событийные / из подкрепа КК): НЕ выкидывать в добивающем сбросе —
# иначе тратятся впустую. Ищем их в баре матчингом эталонов (позиция слота плавает).
PROTECTED_POTION_TEMPLATES = ("event_wall_jump_potion.png", "event_aggro_totem_potion.png",
                              "event_revive_potion.png", "event_de_loot_potion.png")
POTION_MATCH_THRESH = 0.70


def _protected_potion_centers(shot_bgr):
    """x-центры слотов-банок в деплой-баре (jump/aggro/…), которые нельзя трогать
    в добивающем сбросе. Пусто, если банок в баре нет."""
    strip = shot_bgr[BAR_TOP:BAR_BOT, :]
    centers = []
    for name in PROTECTED_POTION_TEMPLATES:
        tpl = load_template(os.path.join(TEMPLATE_DIR, name), cv2.IMREAD_COLOR)
        if tpl is None or strip.shape[0] < tpl.shape[0] or strip.shape[1] < tpl.shape[1]:
            continue
        res = cv2.matchTemplate(strip, tpl, cv2.TM_CCOEFF_NORMED)
        _, mx, _, loc = cv2.minMaxLoc(res)
        if mx >= POTION_MATCH_THRESH:
            centers.append(loc[0] + tpl.shape[1] // 2)
    return centers

def _colored_slot_centers(shot_bgr):
    """x-centres of the colored (available) icons in the deploy bar. Greyed-out
    'x0' slots and the dark gaps between icons have low saturation and are
    ignored, so this returns one centre per still-usable troop/hero/spell."""
    strip = cv2.cvtColor(shot_bgr[BAR_TOP:BAR_BOT, :], cv2.COLOR_BGR2HSV)
    # Доля насыщенных пикселей в колонке (НЕ среднее): бледные событийные войска
    # (фрост-валькирия x50 и т.п.) имеют мало ярких пикселей, поэтому среднее их
    # теряло. Серый спущенный слот (x0) полностью монохромен → доля ~0 и он верно
    # отбрасывается, а любой доступный слот (даже бледный) даёт >порога.
    sat = strip[:, :, 1].astype(np.float32)
    col_frac = (sat > 70).mean(axis=0)         # fraction of saturated px per column
    mask = col_frac > 0.10
    centers, x = [], 90                          # deploy bar spans ~x=90..1160;
    W = min(shot_bgr.shape[1], 1160)             # ignore edges / right-side UI
    while x < W:
        if mask[x]:
            x0 = x
            while x < W and mask[x]:
                x += 1
            width = x - x0
            if width >= 55:                      # an icon is ~100px wide
                n = max(1, round(width / 113))   # split merged (adjacent) icons
                for i in range(n):
                    centers.append(int(x0 + width * (i + 0.5) / n))
        else:
            x += 1
    return centers

def deploy_all_remaining(max_rounds=6):
    """After the main cycle, dump every remaining TROOP (event units, leftovers)
    on the drop line so the round finishes without waiting. Hero and spell slots
    are skipped so abilities aren't triggered early and spells aren't wasted.

    Повторяем проход с ПЕРЕ-снимком, пока в баре остаются доступные (не защищённые)
    войска: один слот может нести больше юнитов, чем точек сброса за проход, а после
    высадки бар меняется — иначе часть событийного войска остаётся невыпущенной.
    """
    global _last_selected
    skip = [TABS[k][0] for k in PROTECTED_KEYS if TABS.get(k)]
    drop = DEPLOY_COORDS.get("dragon", [])[:12]
    print("\n→ Dumping all remaining troops (heroes & spells skipped)")
    for rnd in range(max_rounds):
        try:
            _ensure_active()                     # бой прерван? — прекращаем сброс
            shot = capture_array()
            if shot is None:
                print("[SKIP] deploy_all_remaining: no screenshot"); return
            # банки (jump/aggro/…) исключаем — не тратим их в добивающем сбросе
            all_skip = skip + _protected_potion_centers(shot)
            centers = [cx for cx in _colored_slot_centers(shot)
                       if not any(abs(cx - c) < 55 for c in all_skip)]
            if not centers:
                break                            # бар пуст — всё высажено
            print(f"   round {rnd + 1}: {len(centers)} slot(s) left")
            for cx in centers:
                _ensure_active()
                run_adb(["shell", "input", "tap", str(cx), str(SLOT_Y)])
                _last_selected = (cx, SLOT_Y)
                human_delay(0.15, 0.35)             # выбор слота — не мгновенно
                pts = [jitterCoord(x, y) for x, y in drop]
                for i in range(0, len(pts), DEPLOY_CHUNK):
                    run_adb_taps(pts[i:i + DEPLOY_CHUNK])   # батч тапов — быстро
                    human_delay(*DEPLOY_CFG["drop_delay"])  # нерегулярный ритм
        except _AttackAborted:
            raise                                # пробрасываем — прерываем всю стратегию
        except Exception as e:
            print("[WARN] deploy_all_remaining error (skipping):", e)
            return


def _dragon_sequence():
    deploy_troops("dragon")
    deploy_troops("balloon")
    deploy_troops("siege_machine")
    deploy_heroes()
    deploy_spells("rage")
    print("Waiting before Freeze…")
    deploy_spells("freeze")
    deploy_all_remaining()


def _edragon_sequence():
    deploy_troops("e_drag")
    deploy_troops("balloon")
    deploy_troops("siege_machine")
    deploy_heroes()
    deploy_spells("rage")
    print("Waiting before Freeze…")
    deploy_spells("freeze")
    deploy_all_remaining()

# ───────────────────── CLI test ─────────────────────
if __name__ == "__main__":
    run_attack({"attack":"Dragon_Attack"})
