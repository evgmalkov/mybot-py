import cv2
import time
import os
import numpy as np
from pathlib import Path


def imread_unicode(path, flags=cv2.IMREAD_COLOR, retries=3, delay=0.15):
    """
    Read an image from a Unicode path on all OSes, robust against half-written files.
    - retries: how many extra attempts if file is missing/empty/undecodable
    - delay: seconds to sleep between retries
    """
    p = Path(path)
    for attempt in range(retries + 1):
        try:
            if not p.exists():
                raise FileNotFoundError(str(p))
            size = p.stat().st_size
            if size <= 0:
                raise OSError(f'empty file ({size} B)')
            data = p.read_bytes()
            if not data:
                raise OSError('read_bytes() returned empty buffer')
            arr = np.frombuffer(data, dtype=np.uint8)
            img = cv2.imdecode(arr, flags)
            if img is not None:
                return img
            raise IOError('cv2.imdecode returned None')
        except Exception as e:
            if attempt >= retries:
                raise IOError(f"imread_unicode: failed to read/decode '{p}' (attempt {attempt + 1}/{retries + 1}): {e}") from e
            else:
                time.sleep(delay)
    raise IOError(f"imread_unicode: exhausted retries for '{p}'")
