"""
multi_pinch_out.py

Runs several pinch-in (zoom-out) gestures via UIAutomator2.
If the user touches the screen at the same time (causing a SecurityException
about INJECT_EVENTS), we wait briefly and retry instead of crashing.
"""
import sys
import time
import uiautomator2 as u2
from uiautomator2.exceptions import RPCUnknownError
import main


def _safe_pinch_in(uiobj, percent=100, steps=20, retries=5, backoff=0.35, device=None):
    """
    Perform pinch_in with retries. Returns True on success, False if all retries fail.
    Retries only for the transient "INJECT_EVENTS"/SecurityException case that occurs
    when a real touch is in progress on the emulator.
    """
    delay = backoff
    for attempt in range(1, retries + 1):
        try:
            uiobj.pinch_in(percent=percent, steps=steps)
            return True
        except RPCUnknownError as e:
            msg = str(e)
            if 'INJECT_EVENTS' in msg or 'SecurityException' in msg or 'performMultiPointerGesture' in msg:
                if device is not None:
                    try:
                        device.shell('input tap 5 5')
                    except Exception:
                        pass
                time.sleep(delay)
                delay = min(delay * 1.5, 2.0)
            else:
                time.sleep(delay)
                delay = min(delay * 1.5, 2.0)
        except Exception:
            time.sleep(delay)
            delay = min(delay * 1.5, 2.0)
    return False


def multi_zoom_out(addr=None, percent=100, steps=20, count=3, interval=0.5, retries=5, backoff=0.35):
    """
    Perform 'count' zoom-outs. Never raises on user-touch collisions.
    Returns True if at least one pinch succeeded, else False.
    """
    if addr is None:
        addr = main.host
    if not addr:
        print('No emulator host set before calling multi_zoom_out()')
        return False
    try:
        d = u2.connect(addr)
        root = d()
        any_success = False
        for i in range(count):
            ok = _safe_pinch_in(root, percent=percent, steps=steps, retries=retries, backoff=backoff, device=d)
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
        steps = int(args[2]) if len(args) > 2 else 20
        count = int(args[3]) if len(args) > 3 else 3
        interval = float(args[4]) if len(args) > 4 else 0.5
        multi_zoom_out(addr, percent, steps, count, interval)
        sys.exit(0)
    except Exception:
        sys.exit(0)
