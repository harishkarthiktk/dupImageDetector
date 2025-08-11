import os
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
import imagehash

try:
    import rawpy
except Exception:
    rawpy = None

try:
    import imageio
except Exception:
    imageio = None

from constants import SUPPORTED_EXTS

def safe_read_with_cv2(path):
    try:
        img = cv2.imread(str(path))
        return img
    except Exception:
        return None

def safe_read_with_pillow(path):
    try:
        with Image.open(str(path)) as pil:
            pil = pil.convert("RGB")
            arr = np.array(pil)
            bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            return bgr
    except Exception:
        return None

def safe_read_with_rawpy(path):
    if rawpy is None:
        return None
    try:
        with rawpy.imread(str(path)) as raw:
            rgb = raw.postprocess()
            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            return bgr
    except Exception:
        return None

def safe_read_with_imageio(path):
    if imageio is None:
        return None
    try:
        arr = imageio.imread(str(path))
        if arr.ndim == 2:
            arr = np.stack([arr]*3, axis=-1)
        if arr.shape[2] == 4:
            arr = arr[:, :, :3]
        bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        return bgr
    except Exception:
        return None

def compute_phash_from_bgr(bgr_image):
    try:
        rgb = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        h = imagehash.phash(pil)
        return str(h)
    except Exception:
        return None

def worker_process_file(full_path, workdir_str):
    full_path = str(full_path)
    try:
        size = os.path.getsize(full_path)
        mtime = os.path.getmtime(full_path)
    except Exception:
        return None

    read_method = None
    img = None

    img = safe_read_with_cv2(full_path)
    if img is not None:
        read_method = "opencv"
    else:
        img = safe_read_with_pillow(full_path)
        if img is not None:
            read_method = "pillow"
        else:
            ext = Path(full_path).suffix.lower()
            if ext == ".cr2" and rawpy is not None:
                img = safe_read_with_rawpy(full_path)
                if img is not None:
                    read_method = "rawpy"
            if img is None and imageio is not None:
                img = safe_read_with_imageio(full_path)
                if img is not None:
                    read_method = "imageio"

    if img is None:
        return (os.path.relpath(full_path, workdir_str), None, "fail", size, mtime)

    hash_hex = compute_phash_from_bgr(img)
    return (os.path.relpath(full_path, workdir_str), hash_hex, read_method, size, mtime)

def hamming_distance_hex(h1_hex, h2_hex):
    try:
        ih1 = imagehash.hex_to_hash(h1_hex)
        ih2 = imagehash.hex_to_hash(h2_hex)
        return ih1 - ih2
    except Exception:
        b1 = bin(int(h1_hex, 16))[2:].zfill(64)
        b2 = bin(int(h2_hex, 16))[2:].zfill(64)
        return sum(c1 != c2 for c1, c2 in zip(b1, b2))
