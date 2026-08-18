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


def run_worker(emulator: str, index, village) -> int:
    """Настроить main под эмулятор/инстанс, взять лок, запустить bot_loop. 0 — норм, 1 — занято."""
    import main
    emulator = str(emulator).strip().lower()
    index = int(index)
    village = int(village)
    tag = f'[{emulator}#{index} V{village}]'

    # лок инстанса — не сесть на уже занятый другим ботом
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if sys.platform == 'win32':
        s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        s.bind(('127.0.0.1', _lock_port(emulator, index)))
    except OSError:
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

    cfg = _build_cfg(village)
    print(f'{tag} starting: attack={cfg.get("attack")}')
    try:
        main.bot_loop(cfg)
    except KeyboardInterrupt:
        print(f'{tag} stopped')
    return 0
