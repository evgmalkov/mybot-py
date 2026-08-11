import time
from detect_home_base import detect_home_base
from boot_recovery import boot_recovery

def ensure_home_base(max_wait=50):
    """Retries home base detection up to 20 seconds. Restarts game if needed."""
    print("🧠 Checking if we're on the home base screen...")
    start_time = time.time()

    while time.time() - start_time < max_wait:
        if detect_home_base():
            print('✅ Home base confirmed.')
            return True
        print('⏳ Still not on home base. Retrying in 5s...')
        time.sleep(5)

    print('❌ Failed to detect home base. Initiating reboot sequence...')
    boot_recovery()
    return ensure_home_base(max_wait=20)

if __name__ == '__main__':
    ensure_home_base()
