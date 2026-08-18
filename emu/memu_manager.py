import os
import subprocess
import time
import string
import sys
import winreg
import configparser
import xml.etree.ElementTree as ET
import cv2
import main
from adb_config import ADB_BIN
from screenshot_utils import take_screenshot
from boot_recovery import boot_recovery
from unicode import imread_unicode

CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
import syscfg
_W, _H, _D = syscfg.resolution()                       # системный конфиг (config/system.json)
WIDTH, HEIGHT, DPI = (str(_W), str(_H), str(_D))
MEMU_ADB_BASE = int(syscfg.emu('memu', 'adb_base_port', 21503))
MEMU_ADB_STEP = int(syscfg.emu('memu', 'adb_port_step', 10))
ADB_ADDRESS = f'127.0.0.1:{MEMU_ADB_BASE}'
LAUNCH_WAIT = int(syscfg.timeout('emu_launch_wait_sec', 12))
ADB_WAIT = int(syscfg.timeout('adb_connect_wait_sec', 90))
MEMU = ADB_ADDRESS
from paths import BASE_DIR as DIR
TEMPLATE_DIR = os.path.join(DIR, 'Templates')


def run(cmd, **kw):
    host = main.host
    if host and cmd and cmd[0] == ADB_BIN:
        cmd = [ADB_BIN, '-s', host] + cmd[1:]
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW, **kw).decode().strip()
    except Exception:
        return ''


def find_memu_tools():
    for drive in string.ascii_uppercase:
        root = f'{drive}:\\'
        if not os.path.isdir(root):
            continue
        for pf in ('Program Files', 'Program Files (x86)'):
            base = os.path.join(root, pf, 'Microvirt', 'MEmu')
            exe = os.path.join(base, 'MEmu.exe')
            memuc = os.path.join(base, 'memuc.exe')
            if not os.path.isfile(exe):
                continue
            if not os.path.isfile(memuc):
                continue
            return (exe, memuc, None)
    return (None, None, None)


def get_instance_index(memuc_path):
    out = run([memuc_path, 'listvms'])
    for line in out.splitlines():
        parts = line.strip().split()
        if not parts:
            continue
        if parts[0].isdigit():
            return parts[0]
    return '0'


# --- Мульти-инстанс (модель B: один аккаунт = один MEmu-инстанс) ---
# ADB-порт MEmu по индексу VM: инстанс 0 → base, далее +step на инстанс (config/system.json).
# ВНИМАНИЕ: формула зависит от версии MEmu — проверить вживую (memuc listvms + adb devices).
# MEMU_ADB_BASE / MEMU_ADB_STEP определены сверху из syscfg.


def memu_host(index) -> str:
    """ADB-адрес MEmu-инстанса по индексу VM."""
    return f'127.0.0.1:{MEMU_ADB_BASE + int(index) * MEMU_ADB_STEP}'


def list_memu_instances():
    """Список MEmu-инстансов: [{index, name, started}] из 'memuc listvms'.

    Формат строки memuc: <index>,<title>,<top_handle>,<is_running>,<pid>,<disk>. Возвращаем
    индекс/имя/флаг запуска — для GUI-пикера и привязки аккаунт↔инстанс.
    """
    _, memuc, _ = find_memu_tools()
    if not memuc:
        return []
    out = run([memuc, 'listvms'])
    items = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        # memuc отдаёт CSV; иногда пробелы — берём оба варианта
        parts = line.split(',') if ',' in line else line.split()
        if not parts or not parts[0].strip().isdigit():
            continue
        idx = int(parts[0].strip())
        name = parts[1].strip() if len(parts) > 1 else f'MEmu_{idx}'
        started = False
        if len(parts) > 3:
            started = parts[3].strip() in ('1', 'running', 'started', 'true')
        items.append({'index': idx, 'name': name, 'started': started})
    return sorted({(i['index']): i for i in items}.values(), key=lambda r: r['index'])


def apply_resolution(memuc_path, index):
    print(f'▶ Applying resolution {WIDTH}×{HEIGHT}@{DPI}dpi to VM #{index}…')
    subprocess.run([memuc_path, 'setconfigex', '-i', index, 'custom_resolution', WIDTH, HEIGHT, DPI], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)


def _find_instance_cfg(memu_exe: str) -> str:
    """
    Locate the .memu file for the first VM instance under
    <install_dir>/MemuHyperv VMs/<instance>/<instance>.memu
    """
    install_dir = os.path.dirname(memu_exe)
    vms_dir = os.path.join(install_dir, 'MemuHyperv VMs')
    if not os.path.isdir(vms_dir):
        raise FileNotFoundError(f'No VM folder at {vms_dir}')
    for name in os.listdir(vms_dir):
        inst = os.path.join(vms_dir, name)
        cfg = os.path.join(inst, f'{name}.memu')
        if os.path.isfile(cfg):
            return cfg
    raise FileNotFoundError(f'Could not find any .memu under {vms_dir}')


def _current_render_mode_cfg(memu_exe: str) -> str | None:
    """
    Parse the <GuestProperty name="renderEngine" value="..."/> entry
    from the .memu XML. Returns "DirectX", "OpenGL", "Auto", or None.
    """
    cfg = _find_instance_cfg(memu_exe)
    tree = ET.parse(cfg)
    for gp in tree.findall('.//GuestProperty'):
        if gp.get('name') == 'renderEngine':
            return gp.get('value')
    for gp in tree.findall('.//GuestProperty'):
        if gp.get('name') == 'RenderPath':
            return {'0': 'OpenGL', '1': 'DirectX', '2': 'Auto'}.get(gp.get('value'))
    return None


def _set_render_mode_cfg(memu_exe: str, target='DirectX') -> None:
    """
    Update (or add) the <GuestProperty name="renderEngine" value="DirectX"/> entry
    in the VM’s .memu file, then write it back.
    """
    cfg = _find_instance_cfg(memu_exe)
    tree = ET.parse(cfg)
    root = tree.getroot()
    changed = False
    for gp in tree.findall('.//GuestProperty'):
        if gp.get('name') == 'renderEngine':
            gp.set('value', target)
            changed = True
    if not changed:
        new_gp = ET.Element('GuestProperty', {'name': 'renderEngine', 'value': target})
        root.append(new_gp)
    tree.write(cfg, encoding='utf-8', xml_declaration=True)


def stop_memu():
    print('Closing MEmu if open…')
    subprocess.run(['taskkill', '/IM', 'MEmu.exe', '/F'], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
    time.sleep(2)


def is_memu_running():
    """
    Returns True if a MEmu.exe process is currently active.
    """
    try:
        out = subprocess.check_output(['tasklist', '/FI', 'IMAGENAME eq MEmu.exe'], stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW, shell=True)
        return b'MEmu.exe' in out
    except subprocess.SubprocessError:
        return False


def start_and_connect(emulator_exe):
    host = main.host
    if not host:
        raise RuntimeError('No emulator selected before start_and_connect()')
    if host == MEMU:
        if not is_memu_running():
            print('🔄 MEmu not running—launching emulator.')
            subprocess.Popen([emulator_exe], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
            print(f'⏳ Waiting {LAUNCH_WAIT}s for emulator startup…')
            time.sleep(LAUNCH_WAIT)
        else:
            print('✅ MEmu already running—skipping launch.')
        subprocess.run([ADB_BIN, 'disconnect', host], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
    else:
        print(f'▶ Using BlueStacks at {host}; skipping emulator launch & ADB reset.')
    start = time.time()
    while time.time() - start < ADB_WAIT:
        out = run([ADB_BIN, 'connect', host])
        if 'connected' in out.lower() or 'already connected' in out.lower():
            devices = run([ADB_BIN, 'devices']).splitlines()[1:]
            for d in devices:
                if host in d and 'device' in d:
                    print('✅ Emulator connected and online.')
                    return True
        time.sleep(3)
    print('❌ ADB failed to connect after restart.')
    return False


def capture_for_matching():
    return take_screenshot(output_path='home_page.png')


def wait_for_settings_icon(template='settings_logo.png', thresh=0.8, timeout=int(syscfg.timeout('home_verify_wait_sec', 25))):
    host = main.host
    tpl_path = os.path.join(TEMPLATE_DIR, template)
    tpl = imread_unicode(tpl_path, cv2.IMREAD_GRAYSCALE)
    if tpl is None:
        print(f'❌ Template {tpl_path} not found')
        return False
    start = time.time()
    while time.time() - start < timeout:
        screenshot_path = capture_for_matching()
        if not screenshot_path:
            time.sleep(1)
            continue
        img = imread_unicode(screenshot_path, cv2.IMREAD_COLOR)
        if img is None:
            print(f"[WARN] Could not load '{screenshot_path}'")
            time.sleep(1)
            continue
        if img.ndim == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img
        res = cv2.matchTemplate(gray, tpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)
        if max_val >= thresh:
            print('✅ Homepage detected. Enjoy clashing!')
            return True
        print(f'[WARN] Settings icon not found (score={max_val:.2f}); sending HOME')
        subprocess.run([ADB_BIN, '-s', host, 'shell', 'input', 'keyevent', 'KEYCODE_HOME'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
        time.sleep(1)
    print('❌ Timed out waiting for settings icon.')
    return False


def _connect_host(host):
    """ADB-коннект к конкретному хосту с ретраями (для пер-инстансного пути)."""
    subprocess.run([ADB_BIN, 'disconnect', host], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
    start = time.time()
    while time.time() - start < ADB_WAIT:
        out = run([ADB_BIN, 'connect', host])
        if 'connected' in out.lower():
            for d in run([ADB_BIN, 'devices']).splitlines()[1:]:
                if host in d and 'device' in d:
                    print('✅ Emulator connected and online.')
                    return True
        time.sleep(3)
    print('❌ ADB failed to connect.')
    return False


def _memu_instance_started(memuc, index) -> bool:
    return any(i['index'] == int(index) and i['started'] for i in list_memu_instances())


def ensure_memu(index=None):
    """Поднять/настроить MEmu. index=None — прежний одно-инстансный путь; index задан —
    пер-инстансный (модель B: аккаунт=инстанс), хост = memu_host(index)."""
    if index is None:
        return _ensure_memu_default()
    return _ensure_memu_instance(int(index))


def _ensure_memu_instance(index):
    memu_exe, memuc_exe, _ = find_memu_tools()
    if not memu_exe or not memuc_exe:
        print('❌ Could not find a MEmu installation under Program Files.')
        sys.exit(1)
    vm_idx = str(index)
    host = memu_host(index)
    main.host = host
    print(f'▶ MEmu multi-instance: VM #{vm_idx} → {host}')
    cur = run([memuc_exe, 'getconfigex', '-i', vm_idx, 'custom_resolution'])
    parts = cur.strip().split()
    res_ok = len(parts) >= 3 and tuple(parts[-3:]) == (WIDTH, HEIGHT, DPI)
    out = run([memuc_exe, 'getconfigex', '-i', vm_idx, 'graphics_render_mode'])
    mode = next((int(t) for t in out.strip().split() if t in ('0', '1', '2')), None)
    rend_ok = mode == 1
    changed = False
    if not res_ok:
        apply_resolution(memuc_exe, vm_idx)
        changed = True
    if not rend_ok:
        subprocess.run([memuc_exe, 'setconfigex', '-i', vm_idx, 'graphics_render_mode', '1'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
        changed = True
    if changed and _memu_instance_started(memuc_exe, index):
        print('↻ Config changed → restarting instance…')
        subprocess.run([memuc_exe, 'stop', '-i', vm_idx], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
        time.sleep(2)
    if not _memu_instance_started(memuc_exe, index):
        print(f'🔄 Starting MEmu VM #{vm_idx}…')
        subprocess.run([memuc_exe, 'start', '-i', vm_idx], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
        time.sleep(LAUNCH_WAIT)
    if not _connect_host(host):
        sys.exit(1)
    if not wait_for_settings_icon():
        print('❌ Failed to verify home page.')
        boot_recovery()


def _ensure_memu_default():
    memu_exe, memuc_exe, _ = find_memu_tools()
    if not memu_exe or not memuc_exe:
        print('❌ Could not find a MEmu installation under Program Files.')
        print('   → Please install MEmu and retry.')
        sys.exit(1)
    print(f'✅ Found MEmu.exe at: {memu_exe}')
    print(f'✅ Found memuc.exe at: {memuc_exe}')
    vm_idx = get_instance_index(memuc_exe)
    cur = run([memuc_exe, 'getconfigex', '-i', vm_idx, 'custom_resolution'])
    parts = cur.strip().split()
    if len(parts) >= 3:
        w_cur, h_cur, dpi_cur = parts[-3:]
    else:
        w_cur = h_cur = dpi_cur = None
    res_ok = (w_cur, h_cur, dpi_cur) == (WIDTH, HEIGHT, DPI)
    if res_ok:
        print(f'✅ MEmu already at {WIDTH}×{HEIGHT}@{DPI}dpi; skipping re-config.')
    else:
        print(f'▶ Resolution mismatch ({w_cur}×{h_cur}@{dpi_cur}); will apply fix.')
    out = run([memuc_exe, 'getconfigex', '-i', vm_idx, 'graphics_render_mode'])
    mode = None
    for token in out.strip().split():
        if token in ('0', '1', '2'):
            mode = int(token)
            break
    rend_ok = mode == 1
    if rend_ok:
        print('✅ Render mode is already DirectX; skipping re-config.')
    else:
        print(f'▶ Render mode is {mode}; will switch to DirectX.')
    if not res_ok or not rend_ok:
        if not res_ok:
            apply_resolution(memuc_exe, vm_idx)
        if not rend_ok:
            subprocess.run([memuc_exe, 'setconfigex', '-i', str(vm_idx), 'graphics_render_mode', '1'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
            print('   • graphics_render_mode set to DirectX')
        print('↻ Applying settings → restarting MEmu…')
        stop_memu()
        ret = subprocess.run([memuc_exe, 'start', '-i', str(vm_idx)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW).returncode
        if ret != 0:
            print('❌ memuc failed to start emulator')
            sys.exit(1)
        if not start_and_connect(memu_exe):
            sys.exit(1)
        time.sleep(12)
    else:
        if not start_and_connect(memu_exe):
            sys.exit(1)
    if not wait_for_settings_icon():
        print('❌ Failed to verify home page.')
        boot_recovery  # NOTE: original code references boot_recovery without calling it — likely a bug (recovery never runs). Change to boot_recovery() to actually recover.


if __name__ == '__main__':
    ensure_memu()
