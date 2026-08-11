import subprocess
import time
import sys
import main
from adb_config import ADB_BIN

CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0


def _device_online(host, timeout=8):
    """ADB-устройство доступно? (эмулятор жив)."""
    try:
        r = subprocess.run([ADB_BIN, '-s', host, 'get-state'], capture_output=True,
                           timeout=timeout, creationflags=CREATE_NO_WINDOW)
        return r.returncode == 0 and b'device' in (r.stdout or b'')
    except Exception:
        return False


def ensure_connected(host, tries=6, delay=2.0):
    """Надёжно поднять СЕТЕВОЕ adb-подключение к устройству: сначала disconnect (сбросить
    stale/offline запись), затем connect, и дождаться состояния 'device'. BlueStacks часто
    роняет подключение (после рестарта CoC / под нагрузкой), а плейн 'connect' без
    'disconnect' его не поднимает. True — устройство снова онлайн."""
    for _ in range(tries):
        if _device_online(host):
            return True
        for verb in ('disconnect', 'connect'):
            try:
                subprocess.run([ADB_BIN, verb, host], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW,
                               timeout=10)
            except Exception:
                pass
        time.sleep(delay)
        if _device_online(host):
            return True
    return False


def _recover_emulator(host):
    """Эмулятор закрыт/adb offline — сперва надёжный реконнект, при неудаче рестарт целиком."""
    print('⚠️ Emulator/ADB offline — recovering emulator...')
    if ensure_connected(host):
        print('✅ ADB reconnected.')
        return
    try:
        main.setup_emulator()          # рестарт+конфиг активного эмулятора (MEmu/BS/LD)
    except Exception as e:
        print(f'[RECOVERY] setup_emulator failed: {e}')
    # ждём готовности устройства (до ~60с)
    for _ in range(12):
        if _device_online(host):
            print('✅ Emulator back online.')
            return
        time.sleep(5)
    print('[RECOVERY] emulator still offline after restart attempt.')


def boot_recovery():
    """Restarts the emulator (if it died) and Clash of Clans, then dismisses pop-ups."""
    host = main.host
    if not host:
        print('[RECOVERY] no emulator host set — skip')
        return
    # #D самовыживание: если эмулятор закрыт (adb offline) — сперва поднять эмулятор
    if not _device_online(host):
        _recover_emulator(host)
        if not _device_online(host):
            return                     # эмулятор не поднялся — рестарт игры бессмыслен
    print('🔁 Restarting Clash of Clans...')
    subprocess.run([ADB_BIN, '-s', host, 'shell', 'am', 'force-stop', 'com.supercell.clashofclans'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
    subprocess.run([ADB_BIN, '-s', host, 'shell', 'monkey', '-p', 'com.supercell.clashofclans', '-c', 'android.intent.category.LAUNCHER', '1'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
    print('⏳ Waiting 10 seconds for game to load...')
    time.sleep(10)
    print('👆 Dismissing pop-ups…')
    subprocess.run([ADB_BIN, '-s', host, 'shell', 'input', 'tap', '146', '487'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
