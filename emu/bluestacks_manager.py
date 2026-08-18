"""BlueStacks manager: ensures BlueStacks meets required settings (resolution,
render mode, ads off, ADB on) and can launch without config-file errors.

Changes in this revision (v2):
• **_get()** now returns the raw value (quotes included) so quoted numbers are
  treated as *incorrect*.
• **_set()** always writes unquoted scalars (ints / booleans).
• Logic unchanged otherwise.
"""
import os
import subprocess
import string
import sys
import re
import time
import contextlib
import cv2
import main
import glob
import datetime
import shutil
from adb_config import ADB_BIN
from screenshot_utils import take_screenshot
from boot_recovery import boot_recovery
from unicode import imread_unicode
CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
WIDTH, HEIGHT, DPI = ('1600', '900', '300')
LAUNCH_WAIT, ADB_WAIT = (15, 90)
from paths import BASE_DIR as DIR
TEMPLATE_DIR = os.path.join(DIR, 'Templates')


def run(cmd: list[str], **kw) -> str:
    host = main.host
    if host and cmd and cmd[0] == ADB_BIN:
        cmd = [ADB_BIN, '-s', host] + cmd[1:]
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW, **kw).decode().strip()
    except subprocess.CalledProcessError:
        return ''


def find_bluestacks_tools():
    for drive in string.ascii_uppercase:
        root = f'{drive}:\\'
        if not os.path.isdir(root):
            continue
        for folder in ('BlueStacks_nxt', 'BlueStacks'):
            base = os.path.join(root, 'Program Files', folder)
            player = os.path.join(base, 'HD-Player.exe')
            if not os.path.isfile(player):
                continue
            conf = os.path.join(os.getenv('PROGRAMDATA', 'C:\\ProgramData'), folder, 'bluestacks.conf')
            if not os.path.isfile(conf):
                continue
            return (player, conf)
    return (None, None)


def _read_conf(conf):
    with open(conf, 'r', encoding='utf-8', errors='ignore') as fh:
        return fh.readlines()


def _write_conf(conf_path: str, new_lines: list[str]):
    """
• Keeps **exactly one** backup of bluestacks.conf
• If ≥ 2 backups exist, deletes all but the newest
• Then copies the current conf to that backup (over-writing it)
• Finally writes the updated conf
"""
    dir_ = os.path.dirname(conf_path)
    stem = os.path.basename(conf_path)
    pattern = os.path.join(dir_, f'{stem}.bak.*')
    backups = sorted(glob.glob(pattern), key=os.path.getmtime)
    if backups:
        newest = backups[-1]
        for old in backups[:-1]:
            try: os.remove(old)
            except OSError: pass
        backup_path = newest
    else:
        ts = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        backup_path = f'{conf_path}.bak.{ts}'
    shutil.copy2(conf_path, backup_path)
    print(f'🗄️  Backup saved → {backup_path}')
    with open(conf_path, 'w', encoding='utf-8', errors='ignore') as fh:
        fh.writelines(new_lines)


def _detect_instance_prefix(lines):
    """Return 'bst.instance.<NAME>.' (trailing dot) of the first instance."""
    m = re.search('^bst\\.instance\\.([^.]+)\\.dpi=', '\n'.join(lines), re.M)
    return f'bst.instance.{m.group(1)}.' if m else 'bst.instance.0.'


def _get(lines: list[str], key: str) -> str | None:
    """
Return the value of key without surrounding quotes or whitespace.
If key is absent, return None.
"""
    for ln in lines:
        if not ln.startswith(key + '='):
            continue
        val = ln.split('=', 1)[1].strip()
        if val.startswith('"') and val.endswith('"'):
            val = val[1:-1]
        return val
    return None


def _set(lines: list[str], key: str, value: str):
    pat = key + '='
    lines[:] = [ln for ln in lines if not ln.lstrip().startswith(pat)]
    lines.append(f'{key}="{value}"\n')


def is_running():
    try:
        out = subprocess.check_output(['tasklist', '/FI', 'IMAGENAME eq HD-Player.exe'], stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW, shell=True)
        return b'HD-Player.exe' in out
    except subprocess.SubprocessError:
        return False


def stop_player():
    subprocess.run(['taskkill', '/IM', 'HD-Player.exe', '/F'], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
    time.sleep(3)


def start_and_connect(player):
    host = main.host
    if not is_running():
        print('🔄 BlueStacks not running—launching emulator…')
        subprocess.Popen([player], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
        time.sleep(LAUNCH_WAIT)
    subprocess.run([ADB_BIN, 'disconnect', host], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
    start = time.time()
    while time.time() - start < ADB_WAIT:
        res = run([ADB_BIN, 'connect', host]).lower()
        if 'connected' in res or 'already connected' in res:
            for d in run([ADB_BIN, 'devices']).splitlines()[1:]:
                if host in d and 'device' in d:
                    print('✅ Emulator connected and online.')
                    return True
        time.sleep(3)
    print('❌ ADB failed to connect.')
    return False


def _shot():
    return take_screenshot(output_path='home_page.png')


def wait_for_settings_icon(template='store_home_page.png', thresh=0.8, timeout=25):
    host = main.host
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


def _first_diff(lines, desired):
    """Return list of (key, current, expected) that don't match."""
    diffs = []
    for k, v in desired.items():
        cur = _get(lines, k)
        if cur != v:
            diffs.append((k, cur, v))
    return diffs


def ensure_bluestacks():
    """Verify / fix BlueStacks config, restart ONLY for core mismatches."""
    player, conf = find_bluestacks_tools()
    if not player or not conf:
        print('❌ BlueStacks installation not found.')
        sys.exit(1)
    running_before = is_running()
    print(f'✅ Found HD-Player.exe at: {player}')
    print(f'✅ Found bluestacks.conf at: {conf}')
    lines = _read_conf(conf)
    pref = _detect_instance_prefix(lines)
    print(f'▶ Using instance prefix: {pref}')
    import syscfg
    _bw, _bh, _bd = syscfg.resolution()                # общая resolution (config/system.json)
    _bp = str(syscfg.emu('bluestacks', 'adb_port', 5556))
    core_desired = {pref + 'fb_width': str(_bw), pref + 'fb_height': str(_bh), pref + 'dpi': str(_bd), pref + 'graphics_renderer': 'dx', pref + 'graphics_engine': 'aga', pref + 'adb_port': _bp, pref + 'status.adb_port': _bp, 'bst.qt_renderer': 'Direct3D11', 'bst.enable_adb_access': '1', 'bst.enable_adb_remote_access': '1'}
    bonus_desired = {'bst.feature.programmatic_ads': '0', 'bst.enable_programmatic_ads': '0'}
    bonus_changed = False
    for key, val in bonus_desired.items():
        want = f'{key}="{val}"'
        if not any((ln.strip().startswith(want) for ln in lines)):
            print(f'▶ Setting bonus flag {key}={val}')
            _set(lines, key, val)
            bonus_changed = True
    core_diffs = []
    for key, val in core_desired.items():
        want = f'{key}="{val}"'
        if not any((ln.strip().startswith(want) for ln in lines)):
            core_diffs.append((key, val))
    if core_diffs:
        print('▶ Core mismatches detected:')
        for key, val in core_diffs:
            print(f'   • {key} should be "{val}"')
            _set(lines, key, val)
    if core_diffs or bonus_changed:
        _write_conf(conf, lines)
        if core_diffs:
            print('↻ Applied core fixes → restarting BlueStacks…')
            stop_player()
        else:
            print('↻ Applied bonus flags → no restart needed.')
    else:
        print('▶ All core settings perfect – no changes.')
    if not running_before or core_diffs:
        if not start_and_connect(player):
            sys.exit(1)
    if not wait_for_settings_icon():
        print('❌ Home screen not detected – attempting boot recovery…')
        boot_recovery()


if __name__ == '__main__':
    ensure_bluestacks()
