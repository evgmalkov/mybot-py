import os
import sys
from pathlib import Path
from paths import BASE_DIR
import syscfg                       # системный конфиг (config/system.json)

_BS_PORT = int(syscfg.emu('bluestacks', 'adb_port', 5556))   # порт BlueStacks (общий системный)

adb_subdir = BASE_DIR / 'adb'
local_adb = adb_subdir / 'adb.exe'
if not local_adb.is_file():
    print(f"❌ Cannot find bundled adb.exe at:\n    {local_adb}\n   Please make sure the entire 'adb' folder (including AdbWinApi.dll\n   and AdbWinUsbApi.dll) sits next to the executable.")
    sys.exit(1)

# BlueStacks поставляет СВОЙ adb (HD-Adb.exe, сервер новой версии). Если ходить к нему
# нашим bundled adb другой версии — клиент и сервер убивают друг друга
# («server version (NN) doesn't match this client; killing...») → устройство сваливается
# в `device offline`. Для BlueStacks (:5556) используем его же HD-Adb.exe.
_BLUESTACKS_ADB_CANDIDATES = (
    r'C:\Program Files\BlueStacks_nxt\HD-Adb.exe',
    r'C:\Program Files\BlueStacks\HD-Adb.exe',
)


class _AdbBin(os.PathLike):
    """Динамический выбор adb-бинаря по текущему host (main.host): для BlueStacks —
    его HD-Adb.exe, иначе — bundled adb.exe. Так ВСЕ вызовы subprocess([ADB_BIN, …])
    берут совместимый adb без правок в местах вызова (устраняет конфликт версий adb)."""

    def __init__(self, bundled):
        self._bundled = str(bundled)

    def _resolve(self) -> str:
        host = key = None
        try:
            import main
            host = getattr(main, 'host', None)
            key = getattr(main, 'emulator_key', None)
        except Exception:
            host = key = None
        # BlueStacks: по host :5556 ИЛИ по выбранному эмулятору (host может быть ещё не
        # выставлен на раннем вызове → иначе уйдём в bundled v41 и убьём сервер HD-Adb).
        is_bluestacks = (host and str(host).endswith(f':{_BS_PORT}')) or key == 'bluestacks'
        if is_bluestacks:
            for p in _BLUESTACKS_ADB_CANDIDATES:
                if os.path.isfile(p):
                    return p
        return self._bundled

    def __fspath__(self) -> str:
        return self._resolve()

    def __str__(self) -> str:
        return self._resolve()

    def __repr__(self) -> str:
        return f'_AdbBin({self._resolve()!r})'


ADB_BIN = _AdbBin(local_adb)
