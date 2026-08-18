"""Диагностика виртуализации хоста (VT-x/AMD-V + гипервизор) — лог при старте бота.

Android-эмулятор быстр только с аппаратной виртуализацией (VT-x/AMD-V) и БЕЗ конфликтующего
гипервизора: Hyper-V/WSL2/VBS перехватывают VT-x → эмулятор падает в медленный софт-режим.
Проверяем через WMI (PowerShell) и подсказываем, что включить/выключить. Лог — по-английски.
"""
import subprocess
import sys

CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0

_PS = (
    "$c=Get-CimInstance Win32_ComputerSystem;"
    "$p=Get-CimInstance Win32_Processor;"
    "Write-Output ('HV='+$c.HypervisorPresent+';VT='+$p.VirtualizationFirmwareEnabled+"
    "';SLAT='+$p.SecondLevelAddressTranslationExtensions)"
)

_checked = False   # один раз на процесс


def log_virtualization():
    """Однократно за процесс залогировать статус виртуализации + рекомендации. Никогда не бросает."""
    global _checked
    if _checked or sys.platform != 'win32':
        return
    _checked = True
    try:
        out = subprocess.check_output(
            ['powershell', '-NoProfile', '-NonInteractive', '-Command', _PS],
            stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW, timeout=15,
        ).decode('utf-8', errors='ignore').strip()
    except Exception:
        print('[SYSCHECK] virtualization check skipped (WMI/PowerShell unavailable)')
        return
    kv = {}
    for part in out.split(';'):
        if '=' in part:
            k, v = part.split('=', 1)
            kv[k.strip()] = v.strip().lower()
    vt = kv.get('VT') == 'true'
    hv = kv.get('HV') == 'true'
    slat = kv.get('SLAT') == 'true'
    if hv:
        # Гипервизор (Hyper-V/WSL2/VBS) владеет VT-x → WMI-флаги VT/SLAT маскируются и НЕ надёжны,
        # поэтому НЕ ругаемся на BIOS. Проблема — сам факт активного гипервизора.
        print('[SYSCHECK] Virtualization: a hypervisor is running (Hyper-V / WSL2 / VBS); '
              'it owns VT-x (WMI VT/SLAT flags are masked here and unreliable).')
        print('[SYSCHECK][WARN] Emulator may run slow -> use its Hyper-V-compatible mode '
              '(LDPlayer/MEmu support it), OR disable the hypervisor for max speed: '
              'bcdedit /set hypervisorlaunchtype off + reboot; turn off WSL2 and '
              'Core Isolation / Memory Integrity.')
    else:
        print(f'[SYSCHECK] Virtualization: VT-x/AMD-V={"on" if vt else "OFF"}, '
              f'SLAT={"on" if slat else "OFF"}, no hypervisor.')
        if not vt:
            print('[SYSCHECK][WARN] Hardware virtualization is OFF -> enable VT-x (Intel) / SVM (AMD) '
                  'in BIOS, otherwise the emulator runs in slow software mode.')
        else:
            print('[SYSCHECK] Virtualization OK -> emulator can use hardware acceleration.')
