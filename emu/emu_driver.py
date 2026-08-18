"""Единый фасад над менеджерами эмуляторов (MEmu / LDPlayer / BlueStacks).

Мультиаккаунт модель B (аккаунт = инстанс): ротация в main.py обращается СЮДА и не знает
деталей конкретного менеджера. Плоские импорты (emu/ и корень в sys.path).

Функции:
- ensure(key, index)     — поднять/настроить нужный инстанс, подключить ADB, вернуть host;
- list_instances(key)    — список инстансов [{index,name,started}] (LD/MEmu);
- stop(key)              — остановить эмулятор;
- account_mode()         — 'id_switch' (модель A) | 'per_instance' (модель B);
- binding_for(idx)       — привязка деревни(аккаунта) → {'emulator','index'} из config/accounts.json.
"""
import json
import os

from paths import BASE_DIR

_ACCOUNTS_CFG = os.path.join(BASE_DIR, 'config', 'accounts.json')

SUPPORTED = ('memu', 'ldplayer', 'bluestacks')


def _load_accounts():
    try:
        with open(_ACCOUNTS_CFG, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def account_mode() -> str:
    """Как разводить аккаунты: 'id_switch' (модель A) или 'per_instance' (модель B)."""
    mode = str(_load_accounts().get('mode', 'id_switch')).strip().lower()
    return 'per_instance' if mode == 'per_instance' else 'id_switch'


def binding_for(account_idx):
    """Привязка аккаунта(деревни) idx → {'emulator', 'index'} для модели B, или None."""
    b = _load_accounts().get('bindings', {}) or {}
    rec = b.get(str(account_idx))
    if not isinstance(rec, dict):
        return None
    emu = str(rec.get('emulator', '')).strip().lower()
    if emu not in SUPPORTED:
        return None
    try:
        idx = int(rec.get('index', 0))
    except (TypeError, ValueError):
        idx = 0
    return {'emulator': emu, 'index': idx}


def ensure(key, index=0):
    """Поднять/настроить эмулятор `key` (инстанс `index`), подключить ADB. Возвращает main.host."""
    import main
    key = str(key).strip().lower()
    if key == 'memu':
        from memu_manager import ensure_memu
        ensure_memu(index if index else None)
    elif key == 'ldplayer':
        from ldplayer_manager import ensure_ldplayer
        ensure_ldplayer(index=index)
    elif key == 'bluestacks':
        from bluestacks_manager import ensure_bluestacks
        ensure_bluestacks()
    else:
        raise RuntimeError(f'Unsupported emulator: {key}')
    return getattr(main, 'host', None)


def list_instances(key):
    """Список инстансов эмулятора [{index,name,started}] (для GUI-пикера/привязки)."""
    key = str(key).strip().lower()
    try:
        if key == 'ldplayer':
            from ldplayer_manager import list_ld_instances
            return list_ld_instances()
        if key == 'memu':
            from memu_manager import list_memu_instances
            return list_memu_instances()
    except Exception as e:
        print(f'[emu_driver] list_instances({key}) failed: {e}')
    return []


def stop(key):
    """Остановить эмулятор `key`."""
    key = str(key).strip().lower()
    try:
        if key == 'memu':
            from memu_manager import stop_memu
            stop_memu()
        elif key == 'ldplayer':
            from ldplayer_manager import find_ldplayer_tools, stop_player
            ldconsole, _ = find_ldplayer_tools(allow_deep_scan=False)
            if ldconsole:
                stop_player(ldconsole)
        elif key == 'bluestacks':
            from bluestacks_manager import stop_player as bs_stop
            bs_stop()
    except Exception as e:
        print(f'[emu_driver] stop({key}) failed: {e}')
