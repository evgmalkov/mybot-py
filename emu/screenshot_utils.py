import subprocess
import sys
import time
import struct
import cv2
import numpy as np
from adb_config import ADB_BIN
from boot_recovery import boot_recovery
from unicode import imread_unicode
from paths import debug_path
import main

CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
PNG_MAGIC = b'\x89PNG\r\n\x1a\n'
ADB_TIMEOUT = 15  # сек: жёсткий лимит на adb screencap, чтобы зависший adb не морозил бота


# --- централизованный слой захвата экрана (кэш кадра + кэш шаблонов) ---
# Цель: несколько проверок в одном шаге берут ОДИН кадр (grab), а шаблоны
# грузятся с диска один раз. Поэтому добавление новых фич не увеличивает
# число screencap/чтений с диска кратно.
_frame = None
_frame_ts = 0.0
_last_png = None
_templates = {}


def _remember(img, png=None):
    global _frame, _frame_ts, _last_png
    _frame = img
    _frame_ts = time.monotonic()
    _last_png = png


def invalidate_frame():
    """Сбросить кэш кадра — следующий grab() снимет свежий."""
    global _frame
    _frame = None


def load_template(path, flags=cv2.IMREAD_UNCHANGED):
    """Шаблон с диска, загружается один раз и живёт в памяти (immutable)."""
    key = (path, flags)
    tmpl = _templates.get(key)
    if tmpl is None:
        tmpl = imread_unicode(path, flags)
        _templates[key] = tmpl
    return tmpl


def _screencap_raw(host):
    """Быстрый захват: `adb exec-out screencap` (RAW RGBA, без PNG-кодека) → BGR ndarray.

    ~2x быстрее PNG-пути (нет encode на устройстве и decode на хосте). Возвращает
    None при неожиданном формате/ошибке — тогда capture_array падает на PNG-путь.
    Заголовок screencap: 16 байт (width, height, format, colorspace), format=1 = RGBA_8888.
    """
    proc = subprocess.Popen([ADB_BIN, '-s', host, 'exec-out', 'screencap'],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            creationflags=CREATE_NO_WINDOW)
    try:
        raw, _ = proc.communicate(timeout=ADB_TIMEOUT)
    except subprocess.TimeoutExpired:
        # adb/эмулятор завис — убиваем процесс, чтобы не морозить бота навсегда
        proc.kill()
        proc.communicate()
        print('⚠️ raw screencap timeout — kill + PNG fallback')
        return None
    if proc.returncode != 0 or len(raw) < 16:
        return None
    w, h, fmt, _cs = struct.unpack('<IIII', raw[:16])
    need = w * h * 4
    body = raw[16:]
    if fmt != 1 or w <= 0 or h <= 0 or len(body) < need:
        return None
    arr = np.frombuffer(body[:need], dtype=np.uint8).reshape(h, w, 4)
    return cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)


def capture_array(max_retries=4, retry_delay=5.0):
    """Свежий кадр эмулятора как BGR ndarray, БЕЗ записи на диск.

    Быстрый путь — RAW screencap; при любой проблеме уходит на надёжный PNG-путь
    (ретраи + blank-check + boot_recovery). Кэширует последний кадр (для grab).
    """
    host = main.host
    if not host:
        raise RuntimeError('No emulator selected (main.host is None)')
    img = _screencap_raw(host)
    if img is not None:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, stddev = cv2.meanStdDev(gray)
        if stddev[0][0] >= 1.0:            # кадр не пустой
            _remember(img, None)
            return img
    return _capture_png_array(max_retries, retry_delay)


def _capture_png_array(max_retries=4, retry_delay=5.0):
    """Надёжный PNG-путь (screencap -p) с ретраями/blank-check/boot_recovery."""
    host = main.host
    if not host:
        raise RuntimeError('No emulator selected (main.host is None)')
    for attempt in range(1, max_retries + 1):
        proc = subprocess.Popen([ADB_BIN, '-s', host, 'exec-out', 'screencap', '-p'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW)
        try:
            raw, err = proc.communicate(timeout=ADB_TIMEOUT)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            print(f'❌ adb screencap timeout (attempt {attempt}) — kill')
            if attempt < max_retries:
                time.sleep(retry_delay)
                continue
            else:
                boot_recovery()
                return _frame
        if proc.returncode != 0:
            msg = err.decode(errors="ignore").strip()
            print(f'❌ adb stream error (attempt {attempt}): {msg}')
            if attempt < max_retries:
                # BlueStacks часто роняет СЕТЕВОЕ adb-подключение (device offline/not found)
                # после рестарта CoC — надёжный reconnect (disconnect+connect+ждать device)
                # вместо тяжёлого рекавери эмулятора.
                if 'offline' in msg or 'not found' in msg:
                    try:
                        from boot_recovery import ensure_connected
                        if ensure_connected(host, tries=3, delay=2.0):
                            print('↻ adb reconnected')
                            continue                  # сразу пробуем снова, без лишней паузы
                        print('↻ adb reconnect failed')
                    except Exception:
                        pass
                time.sleep(retry_delay)
                continue
            else:
                boot_recovery()
        idx = raw.find(PNG_MAGIC)
        if idx < 0:
            print(f'❌ PNG signature not found (attempt {attempt})')
            if attempt < max_retries:
                time.sleep(retry_delay)
                continue
            else:
                boot_recovery()
                return _frame                     # НЕ проваливаться дальше после recovery
        png_data = raw[idx:]
        arr = np.frombuffer(png_data, dtype=np.uint8)
        # imdecode бросает cv2.error на пустом/битом буфере — ловим, считаем неудачей
        try:
            img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED) if arr.size else None
        except cv2.error:
            img = None
        if img is None:
            print(f'❌ Failed to decode image (attempt {attempt})')
            if attempt < max_retries:
                time.sleep(retry_delay)
                continue
            else:
                boot_recovery()
                return _frame
        if img.ndim == 3 and img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
        _, stddev = cv2.meanStdDev(gray)
        if stddev[0][0] < 1.0:
            print(f'⚠️ Blank screen detected (std={stddev[0][0]:.2f}) on attempt {attempt}')
            if attempt < max_retries:
                time.sleep(retry_delay)
                continue
            else:
                print('❌ Max retries reached with blank screens')
                boot_recovery()
                return _frame
        _remember(img, png_data)
        return img
    remote_path = '/sdcard/__frame.png'
    local_tmp = debug_path('screen.png')
    subprocess.run([ADB_BIN, '-s', host, 'shell', 'screencap', '-p', remote_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
    subprocess.run([ADB_BIN, '-s', host, 'pull', remote_path, local_tmp], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
    img = imread_unicode(local_tmp)
    _remember(img, None)
    return img


def grab(max_age=0.0):
    """Текущий кадр эмулятора; переиспользует кэш, если он свежее max_age секунд.

    max_age=0 (по умолчанию) — всегда свежий кадр. Указывайте небольшой TTL
    (напр. 0.3), когда несколько проверок в одном шаге могут работать по
    одному кадру — так число screencap не растёт с числом проверок.
    """
    if _frame is not None and max_age > 0 and time.monotonic() - _frame_ts <= max_age:
        return _frame
    return capture_array()


def take_screenshot(output_path='screen.png', max_retries=4, retry_delay=5.0):
    """Совместимость: снимает кадр, сохраняет PNG в output_path, возвращает путь.

    Внутри — capture_array (кадр кэшируется для grab). Если нужен только массив
    изображения, используйте capture_array()/grab() без диск-раунд-трипа.

    Голое имя файла складывается в DEBUG_DIR (не в корень проекта).
    """
    output_path = debug_path(output_path)
    img = capture_array(max_retries, retry_delay)
    if _last_png is not None:
        with open(output_path, 'wb') as f:
            f.write(_last_png)
    elif img is not None:
        ok, buf = cv2.imencode('.png', img)
        if ok:
            with open(output_path, 'wb') as f:
                f.write(buf.tobytes())
    return output_path


if __name__ == '__main__':
    take_screenshot()
