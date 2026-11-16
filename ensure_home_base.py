import time
from detect_home_base import detect_home_base
from boot_recovery import boot_recovery

def ensure_home_base(max_wait=50):
    """Закрыть возобновившиеся награды до проверки дома; ограничить рестарты."""
    import main
    from game_ui import UI, dismiss_welcome, dismiss_pending_rewards
    cfg = UI['home_recovery']
    print('[HOME] Checking home screen and pending rewards')
    for attempt in range(cfg['max_restarts'] + 1):
        deadline = time.monotonic() + max_wait
        while time.monotonic() < deadline:
            if main._check_stop():
                return False
            dismiss_welcome()
            # Ивент может появиться с задержкой после загрузки игры.
            if not dismiss_pending_rewards():
                print('[HOME] Pending reward was not completed; stopping home preparation')
                return False
            if detect_home_base():
                print('[HOME] Home base confirmed')
                return True
            if main.stop_event.wait(cfg['poll_interval']):
                return False
        if attempt < cfg['max_restarts']:
            print('[HOME] Home screen timed out; restarting game')
            if boot_recovery() is False:
                return False
    print('[HOME] Recovery limit reached; home preparation cancelled')
    return False

if __name__ == '__main__':
    ensure_home_base()
