import os
import shutil
import time
from pathlib import Path
from .constants import DUP_DIR_NAME, LOG_FILE, SUPPORTED_EXTS
from .image_processing import hamming_distance_hex

def log_message(workdir: Path, msg: str):
    log_path = workdir / LOG_FILE
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {msg}\n")

def gather_files_with_depth(base_path: Path, max_depth: int):
    result = []
    base_depth = len(base_path.parts)

    for root, dirs, files in os.walk(base_path):
        current_depth = len(Path(root).parts) - base_depth
        if current_depth > max_depth:
            dirs.clear()
            continue

        if DUP_DIR_NAME in Path(root).parts:
            dirs.clear()
            continue

        for f in files:
            if Path(f).suffix.lower() in SUPPORTED_EXTS:
                result.append(Path(root) / f)
    return result

def group_duplicates(entries, threshold):
    indexed = [(i, e[0], e[1]) for i, e in enumerate(entries) if e[1] is not None]
    n = len(indexed)
    used = [False]*n
    groups = []

    for i in range(n):
        if used[i]:
            continue
        _, path_i, hash_i = indexed[i]
        group = [path_i]
        used[i] = True
        for j in range(i+1, n):
            if used[j]:
                continue
            _, path_j, hash_j = indexed[j]
            dist = hamming_distance_hex(hash_i, hash_j)
            if dist <= threshold:
                group.append(path_j)
                used[j] = True
        if len(group) > 1:
            groups.append(group)
    return groups

def safe_move_and_update(conn, workdir: Path, rel_src, rel_dst_dir):
    from .db_helpers import update_filepath
    src_full = workdir / rel_src
    dst_dir_full = workdir / rel_dst_dir
    dst_dir_full.mkdir(parents=True, exist_ok=True)
    dst_full = dst_dir_full / Path(rel_src).name

    counter = 1
    while dst_full.exists():
        dst_full = dst_dir_full / f"{Path(rel_src).stem}_{counter}{Path(rel_src).suffix}"
        counter += 1

    shutil.move(str(src_full), str(dst_full))

    new_rel = os.path.relpath(str(dst_full), str(workdir))
    new_size = dst_full.stat().st_size
    new_mtime = dst_full.stat().st_mtime
    update_filepath(conn, rel_src, new_rel, new_size, new_mtime)
    return new_rel