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


def _screencap_alive(host, timeout=8):
    """Эмулятор реально отвечает на screencap, а не завис на кадре. get-state может говорить
    'device' (adb жив), но сам эмулятор повис → screencap таймаутит. Это и есть «зависание»,
    при котором рестарт CoC бесполезен, а нужен рестарт VM."""
    try:
        p = subprocess.run([ADB_BIN, '-s', host, 'exec-out', 'screencap'], capture_output=True,
                           timeout=timeout, creationflags=CREATE_NO_WINDOW)
        return p.returncode == 0 and len(p.stdout or b'') > 10000
    except Exception:
        return False


def _is_memu(host):
    """Текущий эмулятор — MEmu? (для жёсткого рестарта конкретной VM)."""
    if getattr(main, 'emulator_key', None) == 'memu':
        return True
    try:
        import memu_manager
        port = int(str(host).rsplit(':', 1)[-1])
        return port >= memu_manager.MEMU_ADB_BASE
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
    """Эмулятор нездоров (adb offline ИЛИ screencap завис) — поднять/рестартнуть VM.
    1) Только сетевой adb отвалился, VM жива → лёгкий реконнект.
    2) VM повисла (MEmu) → жёсткий рестарт именно этой инстанции (memuc stop→start).
    3) Иначе — полный setup активного эмулятора."""
    print('⚠️ Emulator unhealthy — recovering emulator...')
    if ensure_connected(host) and _screencap_alive(host):
        print('✅ ADB reconnected.')
        return
    if _is_memu(host):                 # MEmu: зависшую VM обычный setup НЕ рестартит (она 'started')
        try:
            import memu_manager
            if memu_manager.force_restart_current() and _screencap_alive(host):
                print('✅ Emulator back online (VM restarted).')
                return
        except Exception as e:
            print(f'[RECOVERY] MEmu force-restart failed: {e}')
    try:
        main.setup_emulator()          # рестарт+конфиг активного эмулятора (MEmu/BS/LD)
    except Exception as e:
        print(f'[RECOVERY] setup_emulator failed: {e}')
    # ждём готовности устройства (до ~60с)
    for _ in range(12):
        if _device_online(host):
            print('✅ Emulator back online.')
            return
        main.rsleep(5)
    print('[RECOVERY] emulator still offline after restart attempt.')


def boot_recovery():
    """Restarts the emulator (if it died) and Clash of Clans, then dismisses pop-ups."""
    host = main.host
    if not host:
        print('[RECOVERY] no emulator host set — skip')
        return
    # #D самовыживание: эмулятор нездоров (adb offline ИЛИ screencap ЗАВИС) — сперва поднять/
    # рестартнуть VM. Раньше проверяли только get-state ('device'), поэтому зависшую-но-'online'
    # VM гнали в рестарт CoC (am force-stop висел минутами) — теперь ловим и это.
    if not (_device_online(host) and _screencap_alive(host)):
        _recover_emulator(host)
        if not _device_online(host):
            return                     # эмулятор не поднялся — рестарт игры бессмыслен
    print('🔁 Restarting Clash of Clans...')
    # Таймауты: на зависшем эмуляторе adb shell мог висеть минутами.
    try:
        subprocess.run([ADB_BIN, '-s', host, 'shell', 'am', 'force-stop', 'com.supercell.clashofclans'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, creationflags=CREATE_NO_WINDOW)
    except Exception as e:
        print(f'[RECOVERY] force-stop timed out: {e}')
    # Android 14/LDPlayer 14 без `monkey` → кросс-версийный запуск через am start.
    from app_launch import launch_app
    launch_app(host, 'com.supercell.clashofclans', check=False)
    print('⏳ Waiting 10 seconds for game to load...')
    main.rsleep(10)
    print('👆 Dismissing pop-ups…')
    try:
        subprocess.run([ADB_BIN, '-s', host, 'shell', 'input', 'tap', '146', '487'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15, creationflags=CREATE_NO_WINDOW)
    except Exception:
        pass
