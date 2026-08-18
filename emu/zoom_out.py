"""
zoom_out.py

Zoom-out базы жестом «щипок» через UIAutomator2.

ВАЖНО: используем ЯВНЫЙ симметричный двухпальцевый жест (`d().gesture`) вокруг центра экрана,
а НЕ `UiObject.pinch_in(percent, steps)`. На LDPlayer/Android 14 pinch_in привязан к bounds
объекта и инжектится несимметрично → база уезжает влево (панорама вместо чистого зума). Явные
координаты, симметричные относительно центра, дают zoom-out с базой по центру на MEmu и LDPlayer.

Если пользователь касается экрана одновременно (SecurityException про INJECT_EVENTS) —
короткая пауза и повтор вместо падения.
"""
import sys
import time
import uiautomator2 as u2
import main


def _pinch_points(w, h):
    """Симметричный pinch-in вокруг центра: (start1, start2, end1, end2). Горизонтальная ось."""
    cy = h // 2
    s1 = (int(w * 0.72), cy)   # правый палец у края
    s2 = (int(w * 0.28), cy)   # левый палец у края
    e1 = (int(w * 0.52), cy)   # к центру (симметрично)
    e2 = (int(w * 0.48), cy)
    return s1, s2, e1, e2


def _safe_pinch_in(d, w, h, steps=25, retries=5, backoff=0.35):
    """Один симметричный zoom-out жест с ретраями. True при успехе."""
    s1, s2, e1, e2 = _pinch_points(w, h)
    delay = backoff
    for _ in range(retries):
        try:
            d().gesture(s1, s2, e1, e2, steps=steps)
            return True
        except Exception as e:
            msg = str(e)
            if 'INJECT_EVENTS' in msg or 'SecurityException' in msg or 'performMultiPointerGesture' in msg:
                try:
                    d.shell('input tap 5 5')
                except Exception:
                    pass
            time.sleep(delay)
            delay = min(delay * 1.5, 2.0)
    return False


def multi_zoom_out(addr=None, percent=100, steps=25, count=3, interval=0.5, retries=5, backoff=0.35):
    """Сделать 'count' zoom-out'ов. Никогда не падает на коллизии с касанием пользователя.
    ``percent`` оставлен для совместимости сигнатуры (жест координатный, параметр не используется).
    Возвращает True, если хотя бы один жест прошёл."""
    if addr is None:
        addr = main.host
    if not addr:
        print('No emulator host set before calling multi_zoom_out()')
        return False
    try:
        d = u2.connect(addr)
        try:
            info = d.info
            w = int(info.get('displayWidth', 1600))
            h = int(info.get('displayHeight', 900))
        except Exception:
            w, h = 1600, 900
        any_success = False
        for i in range(count):
            ok = _safe_pinch_in(d, w, h, steps=steps, retries=retries, backoff=backoff)
            if ok:
                any_success = True
            else:
                print('⚠️ zoom-out attempt skipped after retries (likely due to user touch).')
            if i < count - 1:
                time.sleep(interval)
        return any_success
    except Exception as e:
        print(f'zoom-out aborted safely: {e}')
        return False


if __name__ == '__main__':
    try:
        args = sys.argv[1:]
        addr = args[0] if len(args) > 0 else main.host
        percent = int(args[1]) if len(args) > 1 else 100
        steps = int(args[2]) if len(args) > 2 else 25
        count = int(args[3]) if len(args) > 3 else 3
        interval = float(args[4]) if len(args) > 4 else 0.5
        multi_zoom_out(addr, percent, steps, count, interval)
        sys.exit(0)
    except Exception:
        sys.exit(0)
