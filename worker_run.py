"""Headless-раннер ОДНОГО эмулятора+инстанса (для супервайзера параллельного запуска).

Супервайзер (GUI) на каждую привязку деревня→эмулятор/инстанс поднимает отдельный процесс:
    run_from_source.py --worker --emulator <memu|ldplayer> --index <N> --village <V>
Каждый процесс = свои глобалы main, свой ADB-host, свой лок-порт → эмуляторы работают
параллельно, каждый управляет своим. Логи идут в stdout (супервайзер их подхватывает).

Одиночный режим: воркер ведёт ОДИН аккаунт на своём инстансе (без ротации — инстанс уже
держит нужный Supercell ID), настройки берутся из profiles/Village_<V>.json.
"""
import json
import os
import socket
import sys


def _lock_port(emu: str, index: int) -> int:
    """Лок-порт инстанса (как в GUI-выборе эмулятора), чтобы два бота не сели на один."""
    if emu == 'memu':
        return 6300 + int(index)
    if emu == 'ldplayer':
        return 6202 + int(index)
    return 6299


def _build_cfg(village: int) -> dict:
    """cfg воркера: дефолты + profiles/Village_<V>.json, одиночный режим (без мультиаккаунта)."""
    from paths import BASE_DIR
    cfg = {
        'gold_threshold': 650000, 'elixir_threshold': 650000, 'dark_elixir_threshold': 5000,
        'upgrade_wall': False, 'wall_level': 5, 'wall_level_from': 5, 'wall_level_to': 5,
        'wall_gold_threshold': 5000000, 'wall_elixir_threshold': 5000000,
        'enable_clan_games': False, 'enable_clan_capital': False, 'capital_hall_level': 9,
        'request_troops': True, 'attack': 'Dragon_Attack', 'train_mode': 'smart', 'quick_slot': 1,
        'enable_stats': False,
    }
    vpath = os.path.join(BASE_DIR, 'profiles', f'Village_{village}.json')
    try:
        with open(vpath, encoding='utf-8') as f:
            cfg.update(json.load(f))
    except Exception as e:
        print(f'[worker] Village_{village}.json load failed: {e} — using defaults')
    # Одиночный режим: воркер = один аккаунт на своём инстансе (без ротации).
    cfg['enable_multi_account'] = False
    cfg['selected_villages'] = [int(village)]
    cfg['current_village_idx'] = int(village)
    cfg.setdefault('multi_interval_mins', 30)
    return cfg


def _build_cfg_from_profile(path) -> dict:
    """cfg воркера из JSON-профиля GUI (полные настройки бота), одиночный режим."""
    cfg = _build_cfg(1)                 # дефолты + принудительный single-режим
    try:
        with open(path, encoding='utf-8') as f:
            cfg.update(json.load(f))
    except Exception as e:
        print(f'[worker] profile load failed: {e} — using defaults')
    # Multi-Village: если профиль GUI включил ротацию по деревням — оставляем её как есть
    # (воркер сам крутит selected_villages). Иначе принудительно одиночный режим.
    if not cfg.get('enable_multi_account'):
        cfg['enable_multi_account'] = False
        cfg.setdefault('selected_villages', [1])
    cfg.setdefault('current_village_idx', 1)
    return cfg


def _start_pause_watch(pausefile: str, main) -> None:
    """Демон-поток: следит за файлом-флагом паузы (создан GUI) и дёргает main.pause_bot/resume_bot.
    Флаг существует → бот на паузе (pause_event.clear); нет → работает (pause_event.set)."""
    import threading
    import time as _t

    def _loop():
        last = None
        while True:
            paused = os.path.exists(pausefile)
            if paused != last:
                (main.pause_bot if paused else main.resume_bot)()
                last = paused
            _t.sleep(0.5)

    threading.Thread(target=_loop, daemon=True).start()


def run_worker(emulator: str, index, village, profile=None) -> int:
    """Настроить main под эмулятор/инстанс, взять лок, запустить bot_loop. 0 — норм, 1 — занято.
    profile — путь к JSON с cfg бота (из GUI); если задан, используется вместо Village_<village>."""
    import main
    emulator = str(emulator).strip().lower()
    index = int(index)
    village = int(village)
    tag = f'[{emulator}#{index}]'

    # лок инстанса — не сесть на уже занятый другим ботом. Ретраим ~3с: при рестарте того же
    # инстанса предыдущий воркер мог ещё не отпустить порт (процесс умирает не мгновенно).
    import time as _t
    port = _lock_port(emulator, index)
    s = None
    for _attempt in range(6):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if sys.platform == 'win32':
            s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            s.bind(('127.0.0.1', port))
            break
        except OSError:
            s.close()
            s = None
            _t.sleep(0.5)
    if s is None:
        print(f'{tag} instance busy (another bot already on it) — exit')
        return 1

    # эмулятор/инстанс в глобалы main (без GUI-диалога)
    main.emulator_key = emulator
    if emulator == 'memu':
        main.memu_index = index          # пер-инстансный путь ensure_memu(index)
        main.ld_index = 0
        main.ld_name = None
    else:
        main.ld_index = index             # ensure_ldplayer(index)
        main.ld_name = f'{emulator}-{index}'
        main.memu_index = None
    main.host = None                      # host выставит менеджер после коннекта

    cfg = _build_cfg_from_profile(profile) if profile else _build_cfg(village)
    # пауза из GUI: файл-флаг рядом с профилем (profiles/_bot_N.json → profiles/_bot_N.pause)
    if profile and str(profile).endswith('.json'):
        _start_pause_watch(str(profile)[:-5] + '.pause', main)
    print(f'{tag} starting: attack={cfg.get("attack")}')
    try:
        main.bot_loop(cfg)
    except KeyboardInterrupt:
        print(f'{tag} stopped')
    return 0
