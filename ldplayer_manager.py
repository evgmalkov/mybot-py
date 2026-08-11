"""
LDPlayer manager: ensures LDPlayer meets required settings (resolution,
ADB port, ads off when possible) and can launch/connect reliably.

Designed to mirror the public API of `bluestacks_manager.py` so
`main.py` can swap managers with minimal changes.

Tested with LDPlayer 9. Adjust commands for older versions if needed.
"""
from __future__ import annotations
import os
import sys
import time
import json
import glob
import shutil
import string
import re
import subprocess
from typing import Tuple, Optional
import cv2
import main
from adb_config import ADB_BIN
from screenshot_utils import take_screenshot
from boot_recovery import boot_recovery
from unicode import imread_unicode

CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0

WIDTH, HEIGHT, DPI = ('1600', '900', '300')
LAUNCH_WAIT, ADB_WAIT = (5, 90)

if getattr(sys, 'frozen', False):
    DIR = os.path.dirname(sys.executable)
else:
    DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(DIR, 'Templates')

CACHE_PATH = os.path.join(DIR, '.ldplayer_cache.json')


def _popup_async(title: str, text: str):
    """Show a non-blocking popup via PowerShell; returns the Popen handle."""
    try:
        import subprocess
        import os
        try:
            CREATE_NO_WINDOW
        except NameError:
            CREATE_NO_WINDOW = 134217728
        ps_title = title.replace("'", "''")
        ps_text = text.replace("'", "''")
        cmd = ['powershell', '-NoProfile', '-WindowStyle', 'Hidden', '-Command', f"$ws=New-Object -ComObject Wscript.Shell;$null=$ws.Popup('{ps_text}', 86400, '{ps_title}', 64)"]
        return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
    except Exception:
        return None


def _popup_close(proc):
    """Close the popup started by _popup_async (if still running)."""
    try:
        if proc and proc.poll() is None:
            proc.terminate()
    except Exception:
        pass


def _from_env_pair():
    """Allow precise overrides via env."""
    cons = os.environ.get('LDPLAYER_CONSOLE')
    play = os.environ.get('LDPLAYER_PLAYER')
    if cons and play and os.path.isfile(cons) and os.path.isfile(play):
        return (cons, play)
    return (None, None)


def _from_path():
    """Find ldconsole/dnconsole via PATH, infer LDPlayer.exe in the same dir."""
    import shutil
    for exe in ('ldconsole.exe', 'dnconsole.exe'):
        p = shutil.which(exe)
        if not p:
            continue
        if not os.path.isfile(p):
            continue
        base = os.path.dirname(p)
        player = os.path.join(base, 'LDPlayer.exe')
        if not os.path.isfile(player):
            continue
        return (p, player)
    return (None, None)


def _from_app_paths():
    """HKLM/HKCU App Paths for LDPlayer.exe / ldconsole.exe / dnconsole.exe."""
    try:
        import winreg
    except Exception:
        return (None, None)

    def q(hive, subkey):
        try:
            with winreg.OpenKey(hive, subkey) as k:
                try:
                    target = winreg.QueryValue(k, None)
                except OSError:
                    target = ''
                if target and os.path.isfile(target):
                    return os.path.normpath(target)
                try:
                    path = winreg.QueryValueEx(k, 'Path')[0]
                except OSError:
                    path = ''
                if path:
                    name = os.path.basename(subkey)
                    exe = os.path.join(path, name)
                    if os.path.isfile(exe):
                        return os.path.normpath(exe)
            return ''
        except OSError:
            return ''
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for name in ('LDPlayer.exe', 'ldconsole.exe', 'dnconsole.exe'):
            exe = q(hive, f'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\{name}')
            if not exe:
                continue
            base = os.path.dirname(exe)
            console = exe if os.path.basename(exe).lower() in ('ldconsole.exe', 'dnconsole.exe') else ''
            player = os.path.join(base, 'LDPlayer.exe')
            if not console:
                for c in ('ldconsole.exe', 'dnconsole.exe'):
                    p = os.path.join(base, c)
                    if os.path.isfile(p):
                        console = p
                        break
            if console and os.path.isfile(player):
                return (console, player)
    return (None, None)


def _from_uninstall():
    """HKLM/HKCU Uninstall for LDPlayer/XuanZhi/Leidian entries."""
    try:
        import winreg
    except Exception:
        return (None, None)
    roots = [
        (winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall'),
        (winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall'),
        (winreg.HKEY_CURRENT_USER, 'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall'),
    ]

    def want(name: str) -> bool:
        n = (name or '').lower()
        return any(s in n for s in ('ldplayer', 'xuanzhi', 'leidian'))
    try:
        for hive, path in roots:
            with winreg.OpenKey(hive, path) as k:
                for i in range(winreg.QueryInfoKey(k)[0]):
                    try:
                        sub = winreg.EnumKey(k, i)
                        with winreg.OpenKey(k, sub) as sk:
                            try: disp = winreg.QueryValueEx(sk, 'DisplayName')[0]
                            except: disp = ''
                            if not want(disp):
                                continue
                            install = ''
                            for val in ('InstallLocation', 'InstallPath', 'DisplayIcon'):
                                try:
                                    v = winreg.QueryValueEx(sk, val)[0]
                                except OSError:
                                    v = ''
                                if not v:
                                    continue
                                if v.lower().endswith('.exe'):
                                    v = os.path.dirname(v)
                                install = v
                                break
                            if not install:
                                try: uninstall_str = winreg.QueryValueEx(sk, 'UninstallString')[0]
                                except OSError: uninstall_str = ''
                                if uninstall_str:
                                    install = os.path.dirname(uninstall_str)
                            if install:
                                console, player = _has_console_player(install)
                                if console and player:
                                    return (console, player)
                    except OSError:
                        continue
        return (None, None)
    except Exception:
        return (None, None)


def _find_by_filename_scan(max_depth: int = 7):
    """
Depth-limited walk across drives looking for the actual executables,
not just folder names. Stops at first good pair.
"""
    for drive in _drive_order():
        root = f'{drive}:\\'
        for dirpath, filenames in _iter_depth_limited(root, max_depth=max_depth):
            fl = {f.lower() for f in filenames}
            if 'ldplayer.exe' in fl:
                if 'ldconsole.exe' in fl or 'dnconsole.exe' in fl:
                    base = dirpath
                    console = os.path.join(base, 'ldconsole.exe')
                    if not os.path.isfile(console):
                        console = os.path.join(base, 'dnconsole.exe')
                    player = os.path.join(base, 'LDPlayer.exe')
                    if os.path.isfile(console) and os.path.isfile(player):
                        return (console, player)
    return (None, None)


def _load_cache():
    try:
        with open(CACHE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(data: dict):
    try:
        with open(CACHE_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def clear_ld_cache():
    try:
        os.remove(CACHE_PATH)
    except OSError:
        pass


def _drive_order():
    """Existing drive letters with C first, then D..Z, then A,B if present."""
    existing = [d for d in string.ascii_uppercase if os.path.isdir(f'{d}:\\')]
    ordered = []
    for d in ['C'] + list('DEFGHIJKLMNOPQRSTUVWXYZAB'):
        if d in existing and d not in ordered:
            ordered.append(d)
    return ordered


def _prime_ld_services(ldconsole: str):
    _ldconsole(ldconsole, ['list2'])
    _ldconsole(ldconsole, ['list'])
    _ldconsole(ldconsole, ['version'])
    time.sleep(0.5)


def _iter_depth_limited(root: str, max_depth: int = 6):
    """Yield (dirpath, filenames) under root, but stop recursing after max_depth."""
    root = os.path.normpath(root)
    root_depth = root.count(os.sep)
    for dirpath, dirnames, filenames in os.walk(root):
        depth = os.path.normpath(dirpath).count(os.sep) - root_depth
        if depth >= max_depth:
            dirnames[:] = []
        yield (dirpath, filenames)


def _has_console_player(base: str) -> tuple[Optional[str], Optional[str]]:
    """Return (console, player) if both exist in base; else (None, None)."""
    console = None
    for exe in ('ldconsole.exe', 'dnconsole.exe'):
        p = os.path.join(base, exe)
        if os.path.isfile(p):
            console = p
            break
    player = os.path.join(base, 'LDPlayer.exe')
    if not os.path.isfile(player):
        player = None
    return (console, player) if console and player else (None, None)


def _find_ldplayer_by_foldername(max_depth: int = 6) -> tuple[Optional[str], Optional[str]]:
    """
Scan all drives (C first) for folders named 'LDPlayer9'/'LDPlayer10' or
the multiplayer/config folder ('ldmultiplayer' or 'ldmutiplayer').

- If we see 'LDPlayer9' or 'LDPlayer10', that path is the base.
- If we see 'ldmultiplayer' or 'ldmutiplayer', treat its parent as root
  and prefer sibling 'LDPlayer10' or 'LDPlayer9' for binaries.
Validate that the base contains LDPlayer.exe + (ldconsole.exe | dnconsole.exe).
"""
    multi_dir_names = ('ldmultiplayer', 'ldmutiplayer')
    for drive in _drive_order():
        root = f'{drive}:\\'
        if not os.path.isdir(root):
            continue
        for candidate in (
            os.path.join(root, 'Program Files', 'LDPlayer', 'LDPlayer10'),
            os.path.join(root, 'Program Files', 'LDPlayer', 'LDPlayer9'),
            os.path.join(root, 'LDPlayer10'),
            os.path.join(root, 'LDPlayer9'),
        ):
            if not os.path.isdir(candidate):
                continue
            console, player = _has_console_player(candidate)
            if console and player:
                return (console, player)
        for dirpath, _ in _iter_depth_limited(root, max_depth=max_depth):
            base_name = os.path.basename(dirpath).lower()
            if base_name in ('ldplayer10', 'ldplayer9'):
                console, player = _has_console_player(dirpath)
                if console and player:
                    return (console, player)
            if base_name in multi_dir_names:
                parent = os.path.dirname(dirpath)
                for child in ('LDPlayer10', 'LDPlayer9'):
                    candidate = os.path.join(parent, child)
                    if not os.path.isdir(candidate):
                        continue
                    console, player = _has_console_player(candidate)
                    if console and player:
                        return (console, player)
                console, player = _has_console_player(parent)
                if console and player:
                    return (console, player)
    return (None, None)


def _run(cmd: list[str], **kw) -> str:
    host = getattr(main, 'host', None)
    try:
        is_adb = cmd and os.path.basename(cmd[0]).lower() in {'adb.exe', 'adb'}
        if is_adb and host:
            unsafe = {'disconnect', 'kill-server', 'devices', 'connect', 'start-server', 'version'}
            if len(cmd) > 1 and cmd[1] not in unsafe and '-s' not in cmd[1:]:
                cmd = [ADB_BIN, '-s', host] + cmd[1:]
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW, **kw).decode().strip()
    except subprocess.CalledProcessError:
        return ''


def _has_value(key, value_name: str) -> bool:
    try:
        import winreg
        winreg.QueryValueEx(key, value_name)
        return True
    except Exception:
        return False


COMMON_LD_DIRS = [
    os.path.join('C:\\', 'Program Files', 'LDPlayer', 'LDPlayer9'),
    os.path.join('C:\\', 'Program Files', 'LDPlayer'),
    os.path.join('C:\\', 'Program Files (x86)', 'LDPlayer'),
    os.path.join('C:\\', 'Program Files (x86)', 'LDPlayer', 'LDPlayer4'),
    os.path.join('C:\\', 'Program Files', 'XuanZhi', 'LDPlayer'),
    os.path.join('C:\\', 'LDPlayer'),
]


def _adb_start_server():
    try:
        subprocess.run([ADB_BIN, 'start-server'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
    except Exception:
        pass


def _adb_connect_spin(ldconsole: str, index: int, host: str,
                      total_timeout: int = 120, retry_every: float = 1.5) -> bool:
    """
Keep trying to connect to ADB on `host`. Every 4th attempt, reassert TCP props
and restart adbd inside the guest via ldconsole to kick it awake.
"""
    _adb_start_server()
    deadline = time.time() + total_timeout
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        _run([ADB_BIN, 'disconnect', host])
        out = _run([ADB_BIN, 'connect', host]).lower()
        if 'connected to' in out or 'already connected' in out:
            port = host.split(':')[-1]
            for line in _run([ADB_BIN, 'devices']).splitlines()[1:]:
                if port in line and '\tdevice' in line:
                    main.host = host
                    print(f'✅ ADB connected at {host} (attempt {attempt}).')
                    return True
        if attempt % 4 == 0:
            _ensure_adb_tcp(ldconsole, index)
        time.sleep(retry_every)
    return False


LD_ADB_BASE = 5555


def _find_ld_cfg_path(ldconsole: str, index: int) -> str | None:
    """
Prefer scanning under the discovered install root; fall back to common roots
across drives. Supports LDPlayer9/LDPlayer10 and both 'ldmultiplayer'/'ldmutiplayer'.
"""
    multi_dir_names = ('ldmultiplayer', 'ldmutiplayer')
    versions = ('LDPlayer10', 'LDPlayer9')
    console, player = (None, None)
    try:
        console, player = find_ldplayer_tools()
    except Exception:
        pass
    bases = []
    if player:
        base = os.path.dirname(player)
        parent = os.path.dirname(base)
        bases.append(os.path.join(base, 'vms', 'config'))
        for v in versions:
            bases.append(os.path.join(parent, v, 'vms', 'config'))
        for m in multi_dir_names:
            bases.append(os.path.join(parent, m, 'vms', 'config'))
    for drive in _drive_order():
        root = f'{drive}:\\'
        for v in versions:
            bases.append(os.path.join(root, 'LDPlayer', v, 'vms', 'config'))
            bases.append(os.path.join(root, v, 'vms', 'config'))
            bases.append(os.path.join(root, 'Program Files', 'LDPlayer', v, 'vms', 'config'))
            bases.append(os.path.join(root, 'Program Files (x86)', 'LDPlayer', v, 'vms', 'config'))
            bases.append(os.path.join(root, 'Program Files', 'XuanZhi', 'LDPlayer', v, 'vms', 'config'))
    seen = set()
    bases = [b for b in bases if not (b in seen or seen.add(b))]
    for b in bases:
        p = os.path.join(b, f'leidian{index}.config')
        if os.path.isfile(p):
            return p
    try:
        for drive in _drive_order():
            root = f'{drive}:\\'
            for dirpath, _ in _iter_depth_limited(root, max_depth=5):
                if dirpath.lower().endswith(os.path.join('vms', 'config')):
                    p = os.path.join(dirpath, f'leidian{index}.config')
                    if os.path.isfile(p):
                        return p
    except Exception:
        return None
    return None


def _patch_ld_cfg_basic_flags(cfg_path: str) -> bool:
    """
Force-enable:
    "basicSettings.adbDebug" : 1
    "basicSettings.rootMode" : true
Works whether the file is JSON or plain text.
Returns True if the file was modified.
"""
    try:
        with open(cfg_path, 'r', encoding='utf-8', errors='ignore') as f:
            raw = f.read()
    except OSError:
        return False
    try:
        cfg = json.loads(raw)
        changed = False
        if cfg.get('basicSettings.adbDebug') != 1:
            cfg['basicSettings.adbDebug'] = 1
            changed = True
        if str(cfg.get('basicSettings.rootMode')).lower() != 'true':
            cfg['basicSettings.rootMode'] = True
            changed = True
        if changed:
            with open(cfg_path, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            return True
        return False
    except Exception:
        new = raw
        new = re.sub('"basicSettings\\.adbDebug"\\s*:\\s*0', '"basicSettings.adbDebug": 1', new)
        new = re.sub('"basicSettings\\.rootMode"\\s*:\\s*(false|0)', '"basicSettings.rootMode": true', new, flags=re.I)
        if new != raw:
            with open(cfg_path, 'w', encoding='utf-8') as f:
                f.write(new)
            return True
        return False


def _patch_ld_cfg_file(cfg_path: str, port: int = 5555) -> bool:
    """
Force-enable root and ADB TCP in leidian<idx>.config.
Handles JSON-like and INI-like formats. Backs up once.
Returns True if something was changed/written.
"""
    try:
        with open(cfg_path, 'r', encoding='utf-8', errors='ignore') as f:
            raw = f.read()
    except OSError:
        return False
    bak = cfg_path + '.bak'
    try:
        if not os.path.exists(bak):
            shutil.copy2(cfg_path, bak)
    except OSError:
        pass
    changed = False
    try:
        cfg = json.loads(raw)
        before = json.dumps(cfg, sort_keys=True)
        for k in ('root', 'isRoot', 'rooted', 'enable_root'):
            if k in cfg:
                cfg[k] = 1 if isinstance(cfg[k], int) else '1' if isinstance(cfg[k], str) else True
        cfg.setdefault('root', '1')
        for k in ('adb_debug', 'debug_enable'):
            if k in cfg:
                cfg[k] = 1 if isinstance(cfg[k], int) else '1' if isinstance(cfg[k], str) else True
        cfg.setdefault('adb_debug', '1')
        for k in ('adb_port', 'service_adb_tcp_port', 'persist_adb_tcp_port'):
            cfg[k] = str(port)
        after = json.dumps(cfg, sort_keys=True)
        if before != after:
            with open(cfg_path, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=2)
            return True
        return False
    except Exception:
        new = raw

        def _repl(pattern, repl):
            nonlocal new
            out = re.sub(pattern, repl, new, flags=re.I | re.M)
            changed_local = out != new
            new = out
            return changed_local
        changed |= _repl('("?(?:root|isRoot|rooted|enable_root)"?\\s*[:=]\\s*)("?)(?:0|false)("?)', '\\1\\21\\3')
        changed |= _repl('("?(?:adb_debug|debug_enable)"?\\s*[:=]\\s*)("?)(?:0|false)("?)', '\\1\\21\\3')
        changed |= _repl('("?(?:adb_port|service_adb_tcp_port|persist_adb_tcp_port)"?\\s*[:=]\\s*)"?\\d+"?', f'\\1"{port}"')
        if changed:
            with open(cfg_path, 'w', encoding='utf-8') as f:
                f.write(new)
        return changed


def _chosen_ld_name(default: str | None = None) -> str | None:
    try:
        import main
        return getattr(main, 'ld_name', None) or default
    except Exception:
        return default


def _is_root_enabled(ldconsole: str, index: int) -> bool:
    """
Best-effort check using 'list2' JSON.
Some builds use keys like 'isRoot', others 'root' or 'rooted'.
"""
    out = _ldconsole(ldconsole, ['list2'])
    if not out:
        return False
    try:
        data = json.loads(out)
        items = data.get('instances') if isinstance(data, dict) else data
        if isinstance(items, list):
            for inst in items:
                try:
                    if str(inst.get('index')) == str(index):
                        for key in ('isRoot', 'root', 'rooted'):
                            v = inst.get(key)
                            if isinstance(v, bool):
                                return v
                            if isinstance(v, (int, str)):
                                return str(v) in ('1', 'true', 'True')
                except Exception:
                    continue
        return False
    except Exception:
        m = re.search(f'"index"\\s*:\\s*{index}.*?(?:"isRoot"|"root"|"rooted")\\s*:\\s*(true|false|1|0)', out, re.I | re.S)
        if m:
            return m.group(1).lower() in ('true', '1')
        return False


def _enable_root_offline(ldconsole: str, index: int) -> bool:
    """
Try all known flags to enable root for this index.
MUST be called while the instance is NOT running.
Returns True if any command responded (we assume it applied).
"""
    for args in (
        ['modify', '--index', str(index), '--root', 'enable'],
        ['modify', '--index', str(index), '--root', 'on'],
        ['modify', '--index', str(index), '--enable_root', '1'],
    ):
        out = _ldconsole(ldconsole, args)
        if out is not None and out != '':
            return True
    return False


def _force_adb_tcp(ldconsole: str, index: int, port: int = 5555):
    """
Ensure ADB-over-TCP is configured for this instance.
- If the VM is OFF: patch the config file only (non-blocking).
- If the VM is ON: set props via ldconsole and restart adbd.
"""
    if not is_instance_started(ldconsole, index) and not is_running():
        cfg = _find_ld_cfg_path(ldconsole, index)
        if cfg:
            _patch_ld_cfg_file(cfg, port=port)
        return
    _ldconsole(ldconsole, ['setprop', '--index', str(index), '--key', 'persist.service.adb.enable', '--value', '1'])
    for k in ('service.adb.tcp.port', 'persist.adb.tcp.port'):
        _ldconsole(ldconsole, ['setprop', '--index', str(index), '--key', k, '--value', str(port)])
    _ldconsole(ldconsole, ['adb', '--index', str(index), '--command', 'stop adbd'])
    _ldconsole(ldconsole, ['adb', '--index', str(index), '--command', 'start adbd'])


def find_ldplayer_tools(allow_deep_scan: bool = True) -> Tuple[Optional[str], Optional[str]]:
    """
Discovery order:
  0) cache
  0.5) FAST scan (C:\\LDPlayer, C:\\Program Files\\LDPlayer, C:\\Program Files (x86)\\LDPlayer)
  1) explicit env pair LDPLAYER_CONSOLE/LDPLAYER_PLAYER
  2) base env (LDPLAYER_HOME / LDPLAYER / LD_HOME)
  3) PATH (where/which)
  4) App Paths registry (HKLM/HKCU)
  5) Quick exact paths (all drives)
  6) Uninstall registry (HKLM + HKCU)
  7) Deep filename scan (ldconsole/dnconsole + LDPlayer.exe)
  8) Folder-name scan (fallback)
"""
    cache = _load_cache()
    if cache.get('console') and cache.get('player'):
        if os.path.isfile(cache['console']) and os.path.isfile(cache['player']):
            return (cache['console'], cache['player'])
        clear_ld_cache()
    pf = os.environ.get('ProgramFiles', 'C:\\Program Files')
    pfx86 = os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)')
    fast_bases = ['C:\\LDPlayer', os.path.join(pf, 'LDPlayer'), os.path.join(pfx86, 'LDPlayer')]
    for base in fast_bases:
        if not os.path.isdir(base):
            continue
        console, player = _has_console_player(base)
        if console and player:
            _save_cache({'console': console, 'player': player})
            return (console, player)
        for child in ('LDPlayer9', 'LDPlayer10'):
            sub = os.path.join(base, child)
            if not os.path.isdir(sub):
                continue
            console, player = _has_console_player(sub)
            if console and player:
                _save_cache({'console': console, 'player': player})
                return (console, player)
    console, player = _from_env_pair()
    if console and player:
        _save_cache({'console': console, 'player': player})
        return (console, player)
    for env_key in ('LDPLAYER_HOME', 'LDPLAYER', 'LD_HOME'):
        base = os.environ.get(env_key)
        if not base:
            continue
        console, player = _has_console_player(base)
        if console and player:
            _save_cache({'console': console, 'player': player})
            return (console, player)
    console, player = _from_path()
    if console and player:
        _save_cache({'console': console, 'player': player})
        return (console, player)
    console, player = _from_app_paths()
    if console and player:
        _save_cache({'console': console, 'player': player})
        return (console, player)
    for drive in _drive_order():
        for sub in (
            os.path.join('Program Files', 'LDPlayer', 'LDPlayer9'),
            os.path.join('LDPlayer9'),
            os.path.join('Program Files', 'XuanZhi', 'LDPlayer', 'LDPlayer9'),
            os.path.join('LDPlayer'),
        ):
            base = os.path.join(f'{drive}:\\', sub)
            if not os.path.isdir(base):
                continue
            console, player = _has_console_player(base)
            if console and player:
                _save_cache({'console': console, 'player': player})
                return (console, player)
            for child in ('LDPlayer9', 'LDPlayer10'):
                subdir = os.path.join(base, child)
                if not os.path.isdir(subdir):
                    continue
                console, player = _has_console_player(subdir)
                if console and player:
                    _save_cache({'console': console, 'player': player})
                    return (console, player)
    console, player = _from_uninstall()
    if console and player:
        _save_cache({'console': console, 'player': player})
        return (console, player)
    if allow_deep_scan:
        pop = _popup_async('Scanning LDPlayer', "Please wait while scanning LDPlayer.\nDon't press anything.")
        try:
            console, player = _find_by_filename_scan(max_depth=7)
            if console and player:
                _save_cache({'console': console, 'player': player})
                return (console, player)
            console, player = _find_ldplayer_by_foldername(max_depth=6)
            if console and player:
                _save_cache({'console': console, 'player': player})
                return (console, player)
        finally:
            _popup_close(pop)
    return (None, None)


def is_running() -> bool:
    try:
        out = subprocess.check_output(['tasklist', '/FI', 'IMAGENAME eq LDPlayer.exe'], stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW, shell=True)
        return b'LDPlayer.exe' in out
    except subprocess.SubprocessError:
        return False


def stop_player(ldconsole: str):
    subprocess.run([ldconsole, 'quitall'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
    time.sleep(2)
    subprocess.run(['taskkill', '/IM', 'LDPlayer.exe', '/F'], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
    time.sleep(2)


LD_CONSOLE_TIMEOUT = 4.0


def _ldconsole(ldconsole: str, args: list[str]) -> str:
    try:
        return subprocess.check_output([ldconsole] + args, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW, timeout=LD_CONSOLE_TIMEOUT).decode('utf-8', errors='ignore').strip()
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return ''


def _enable_root(ldconsole: str, index: int) -> bool:
    """
Try all known switches to enable root. Returns True if we *likely* changed it,
meaning a restart is recommended.
"""
    tried = False
    if _ldconsole(ldconsole, ['modify', '--index', str(index), '--root', 'enable']):
        tried = True
        return tried
    if _ldconsole(ldconsole, ['modify', '--index', str(index), '--root', 'on']):
        tried = True
        return tried
    if _ldconsole(ldconsole, ['modify', '--index', str(index), '--enable_root', '1']):
        tried = True
    return tried


def _ensure_adb_tcp(ldconsole: str, index: int, port: int = 5555) -> tuple[str, bool]:
    host = f'127.0.0.1:{port}'
    _ldconsole(ldconsole, ['setprop', '--index', str(index), '--key', 'service.adb.tcp.port', '--value', str(port)])
    _ldconsole(ldconsole, ['setprop', '--index', str(index), '--key', 'persist.adb.tcp.port', '--value', str(port)])
    _ldconsole(ldconsole, ['setprop', '--index', str(index), '--key', 'persist.service.adb.enable', '--value', '1'])
    changed = False
    if is_instance_started(ldconsole, index) or is_running():
        _ldconsole(ldconsole, ['adb', '--index', str(index), '--command', 'stop adbd'])
        _ldconsole(ldconsole, ['adb', '--index', str(index), '--command', 'start adbd'])
        changed = True
    return (host, changed)


def _get_adb_port(_ldconsole: str, index: int) -> int:
    return LD_ADB_BASE + 2 * max(0, int(index))


def _connect_only(ldconsole: str, index: int) -> bool:
    port = _get_adb_port(ldconsole, index)
    host = f'127.0.0.1:{port}'
    _adb_start_server()
    subprocess.run([ADB_BIN, 'disconnect', host], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
    CONNECT_TIMEOUT = 60
    t0 = time.time()
    while time.time() - t0 < CONNECT_TIMEOUT:
        out = _run([ADB_BIN, 'connect', host]).lower()
        if 'connected to' in out or 'already connected' in out:
            for d in _run([ADB_BIN, 'devices']).splitlines()[1:]:
                if str(port) in d and '\tdevice' in d:
                    print(f'✅ Emulator index {index} connected at {host}.')
                    main.host = host
                    return True
        time.sleep(1.2)
    return False


def _adb_wm(host: str):
    """Return (width, height, dpi) via `wm size` and `wm density`. Values may be None."""
    size_out = _run([ADB_BIN, '-s', host, 'shell', 'wm', 'size']) or ''
    dens_out = _run([ADB_BIN, '-s', host, 'shell', 'wm', 'density']) or ''
    w = h = d = None
    m = re.search('(Physical|Override) size:\\s*(\\d+)x(\\d+)', size_out)
    if m:
        w, h = int(m.group(2)), int(m.group(3))
    m = re.search('(Physical|Override) density:\\s*(\\d+)', dens_out)
    if m:
        d = int(m.group(2))
    return (w, h, d)


def _set_core(ldconsole: str, index: int) -> tuple[bool, str]:
    want_res = f'{WIDTH},{HEIGHT},{DPI}'
    print('DEBUG set_core: modify resolution')
    _ldconsole(ldconsole, ['modify', '--index', str(index), '--resolution', want_res])
    print('DEBUG set_core: enable root')
    needs_restart = _enable_root(ldconsole, index)
    print('DEBUG set_core: ensure ADB TCP')
    host, _ = _ensure_adb_tcp(ldconsole, index, port=_get_adb_port(ldconsole, index))
    return (needs_restart, host)


def _shot():
    return take_screenshot(output_path='home_page.png')


def wait_for_home_icon(template: str = 'store_home_page_LD.png', thresh: float = 0.8, timeout: int = 25) -> bool:
    host = getattr(main, 'host', None)
    tpl = imread_unicode(os.path.join(TEMPLATE_DIR, template), cv2.IMREAD_GRAYSCALE)
    if tpl is None:
        return False
    start = time.time()
    while time.time() - start < timeout:
        spath = _shot()
        if not spath:
            time.sleep(1)
            continue
        img = imread_unicode(spath)
        if img is None:
            time.sleep(1)
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
        if cv2.minMaxLoc(cv2.matchTemplate(gray, tpl, cv2.TM_CCOEFF_NORMED))[1] >= thresh:
            print('✅ Homepage detected. Enjoy clashing!')
            return True
        subprocess.run([ADB_BIN, '-s', host, 'shell', 'input', 'keyevent', 'KEYCODE_HOME'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
        time.sleep(1)
    return False


def _adb_start_server():
    try:
        subprocess.run([ADB_BIN, 'start-server'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
    except Exception:
        pass


def _wait_for_boot_adb(host: str, timeout: int = 120) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        out = _run([ADB_BIN, '-s', host, 'shell', 'getprop', 'sys.boot_completed']).strip()
        if out == '1':
            return True
        time.sleep(1.5)
    return False


def ensure_ldplayer(index: int = 0):
    """Verify / fix LDPlayer config; only restart when a core mismatch is detected."""
    ldconsole, player = find_ldplayer_tools(allow_deep_scan=False)
    if not ldconsole or not player:
        clear_ld_cache()
        ldconsole, player = find_ldplayer_tools(allow_deep_scan=True)
    if not ldconsole or not player:
        print('❌ LDPlayer installation not found.')
        sys.exit(1)
    running_before = is_instance_started(ldconsole, index)
    print(f'✅ Found LDPlayer.exe at: {player}')
    print(f'✅ Found ldconsole.exe at: {ldconsole}')
    print(f'▶ Using LDPlayer index: {index}')
    _prime_ld_services(ldconsole)
    cfg_path = _find_ld_cfg_path(ldconsole, index)
    port = _get_adb_port(ldconsole, index)
    host = f'127.0.0.1:{port}'
    _force_adb_tcp(ldconsole, index, port=port)
    need_fix = False
    if running_before:
        print('▶ LDPlayer is running — connecting without restart…')
        if _connect_only(ldconsole, index):
            w, h, d = _adb_wm(host)
            bad_res = w is None or h is None or str(w) != WIDTH or str(h) != HEIGHT
            bad_dpi = d is None or str(d) != DPI
            if cfg_path:
                flags_changed = _patch_ld_cfg_basic_flags(cfg_path)
            else:
                flags_changed = False
            need_fix = bad_res or bad_dpi or flags_changed
            if flags_changed:
                print('▶ Applied Root/ADB flags in config; restart required to take effect.')
            need_fix = bad_res or bad_dpi or root_changed
            if bad_res or bad_dpi:
                print(f'▶ Core mismatches detected (have: {w}x{h}@{d}, want: {WIDTH}x{HEIGHT}@{DPI})')
        else:
            print('⚠️  ADB connect failed while LDPlayer is running — will apply fixes and restart.')
            need_fix = True
    else:
        cfg_path = _find_ld_cfg_path(ldconsole, index)
        if cfg_path and _patch_ld_cfg_basic_flags(cfg_path):
            print('▶ Applied Root/ADB flags in config.')
        _set_core(ldconsole, index)
    if need_fix:
        print('↻ Applying core fixes → restarting LDPlayer…')
        _set_core(ldconsole, index)
        stop_player(ldconsole)
        cfg_path = _find_ld_cfg_path(ldconsole, index)
        if cfg_path and _patch_ld_cfg_file(cfg_path, port=port):
            print(f'▶ Patched LD config: {cfg_path}')
        stop_player(ldconsole)
    if not is_running():
        print('🔄 Launching LDPlayer…')
        _ldconsole(ldconsole, ['launch', '--index', str(index)])
    if not _connect_only(ldconsole, index):
        print('❌ ADB failed to connect.')
        sys.exit(1)
    if not _wait_for_boot_adb(host, timeout=120):
        print("⚠️ Android didn't report boot_completed in time; continuing anyway...")
    if not wait_for_home_icon():
        print('❌ Home screen not detected – attempting boot recovery…')
        boot_recovery()


def list_ld_instances(debug: bool = False):
    """
Returns: [{"index": 0, "name": "LDPlayer", "pid": 7456, "started": True}, ...]
Supports:
  - ldconsole list2 (7 cols or 10 cols variants)
  - ldconsole list  (key:value / key=value lines)
"""
    console, _ = find_ldplayer_tools()
    if not console:
        return []

    def call(args):
        try:
            out = subprocess.check_output([console] + args, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
            return out.decode('utf-8', errors='ignore').strip()
        except subprocess.CalledProcessError:
            return ''
    raw = call(['list2'])
    if not raw:
        raw = call(['list'])
    if debug:
        print('----- ldconsole raw -----')
        print(raw)
        print('-------------------------')
    lines = [ln.strip() for ln in raw.replace('\r', '').split('\n') if ln.strip()]
    result = []

    def is_started(flag: str, pid: int) -> bool:
        s = (flag or '').strip().lower()
        if s in {'started', '1', 'running', 'on', 'true'}:
            return True
        if s.isdigit():
            try:
                n = int(s)
                if n >= 2 and isinstance(pid, int) and pid > 0:
                    return True
            except Exception:
                pass
        if isinstance(pid, int) and pid > 0:
            return True
        return False
    parsed_csv = False
    for ln in lines:
        if ',' not in ln or any(h in ln.lower() for h in ('index', 'title', 'name,pid')):
            continue
        parts = [p.strip() for p in ln.split(',')]
        if len(parts) in (7, 10):
            if not parts[0].isdigit():
                continue
            parsed_csv = True
            idx = int(parts[0])
            name = parts[1] or f'LDPlayer-{idx}'
            status_col = 4
            pid_col = 5
            try:
                pid = int(parts[pid_col])
            except Exception:
                pid = 0
            started = is_started(parts[status_col], pid)
            result.append({'index': idx, 'name': name, 'pid': pid, 'started': started})
    if parsed_csv:
        return sorted(result, key=lambda r: r['index'])
    for ln in lines:
        tokens = re.split('[,\\s]+', ln)
        kv = {}
        for t in tokens:
            if ':' in t:
                k, v = t.split(':', 1)
            elif '=' in t:
                k, v = t.split('=', 1)
            else:
                continue
            kv[k.strip().lower()] = v.strip()
        if not kv:
            continue
        idx = kv.get('index') or kv.get('id') or kv.get('idx')
        if idx is None:
            continue
        try:
            idx_i = int(idx)
        except Exception:
            continue
        name = kv.get('name') or kv.get('title') or f'LDPlayer-{idx_i}'
        try:
            pid_i = int(kv.get('pid') or '0')
        except Exception:
            pid_i = 0
        status = kv.get('status') or kv.get('state') or kv.get('started') or ''
        result.append({'index': idx_i, 'name': name, 'pid': pid_i, 'started': is_started(status, pid_i)})
    return sorted({(r['index'], r['name']): r for r in result}.values(), key=lambda r: r['index'])


def is_instance_started(ldconsole: str, index: int) -> bool:
    try:
        from Ldplayer_Manager import list_ld_instances
    except Exception:
        try:
            items = list_ld_instances()
        except Exception:
            return False
    else:
        try:
            items = list_ld_instances()
        except Exception:
            return False
    for r in items:
        if r.get('index') == index:
            return bool(r.get('started'))
    return False


def _wait_started(ldconsole: str, index: int, timeout: int = 45) -> bool:
    """
Wait until the LDPlayer.exe process is up.
Ignore ldconsole's 'started' flag completely.
"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        if is_running():
            return True
        time.sleep(1)
    return False


if __name__ == '__main__':
    ensure_ldplayer(index=0)
