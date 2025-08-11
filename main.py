#!/usr/bin/env python3
"""
dup_sqlite.py

Duplicate detection with SQLite caching + robust image read failover.

Usage:
    python main.py -W /path/to/folder -T 6

Requirements:
    pip install pillow imagehash tqdm rawpy imageio opencv-python
"""

import os
import sys
import argparse
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from tqdm import tqdm
import cv2
from PIL import Image

from .db_helpers import init_db, get_metadata_map, upsert_entries, update_filepath
from .image_processing import worker_process_file, hamming_distance_hex
from .utils import log_message, group_duplicates, safe_move_and_update, gather_files_with_depth
from .constants import DB_NAME, LOG_FILE, DUP_DIR_NAME

def main():
    parser = argparse.ArgumentParser(description="Duplicate detection with SQLite cache and robust read failovers.")
    parser.add_argument("-W", "--working-dir", required=True, help="Folder to scan (will store DB and logs here).")
    parser.add_argument("-T", "--threshold", type=int, default=6,
                        help=("Hamming distance threshold (phash, 64-bit). "
                              "Max possible = 64. realistic ranges: 0-3 strict, 4-6 balanced, 7-12 loose"))
    parser.add_argument("-j", "--jobs", type=int, default=os.cpu_count(), help="Number of worker processes.")
    parser.add_argument("-R", "--recursive", nargs="?", const=5, type=int, metavar="DEPTH",
                        help="Recursively scan subfolders up to DEPTH levels (default: 5). Example: -R 10 for 10 levels deep.")
    parser.add_argument("--force-rescan", action="store_true", help="Ignore cache and rehash all files.")
    args = parser.parse_args()

    workdir = Path(args.working_dir).resolve()
    if not workdir.is_dir():
        print("Working directory not found:", workdir)
        sys.exit(1)

    if args.threshold < 0 or args.threshold > 64:
        print("Invalid threshold. Must be between 0 and 64.")
        sys.exit(2)

    max_depth = args.recursive if args.recursive is not None else 5

    db_path = workdir / DB_NAME
    conn = init_db(db_path)

    log_message(workdir, f"Starting scan. threshold={args.threshold}, jobs={args.jobs}, force_rescan={args.force_rescan}, recursive_depth={max_depth}")

    all_files = gather_files_with_depth(workdir, max_depth)

    db_meta = get_metadata_map(conn)
    to_process = []
    entries_from_db = {}
    for p in all_files:
        rel = os.path.relpath(str(p), str(workdir))
        try:
            size = p.stat().st_size
            mtime = p.stat().st_mtime
        except Exception:
            size = None
            mtime = None

        if args.force_rescan or rel not in db_meta:
            to_process.append(str(p))
        else:
            db_size, db_mtime, db_hash = db_meta[rel]
            if (db_size != size) or (abs(db_mtime - mtime) > 1e-6):
                to_process.append(str(p))
            else:
                entries_from_db[rel] = (rel, db_hash, db_size, db_mtime)

    if to_process:
        log_message(workdir, f"Hashing {len(to_process)} files (workers={args.jobs})")
        worker = partial(worker_process_file, workdir_str=str(workdir))
        results = []
        with ProcessPoolExecutor(max_workers=args.jobs) as exe:
            for res in tqdm(exe.map(worker, to_process), total=len(to_process), desc="Hashing"):
                if res is None:
                    continue
                relpath, hash_hex, read_method, size, mtime = res
                results.append((relpath, hash_hex, read_method, size, mtime))
                if read_method == "fail":
                    log_message(workdir, f"UNREADABLE: {relpath}")
                else:
                    log_message(workdir, f"READ: {relpath} via {read_method}")
        upsert_entries(conn, results)
        for r in results:
            entries_from_db[r[0]] = (r[0], r[1], r[3], r[4])
    else:
        log_message(workdir, "No files needed hashing (cache up-to-date).")

    entries = []
    for rel, v in entries_from_db.items():
        entries.append((rel, v[1], v[2], v[3]))

    if not entries:
        print("No image entries found after scanning.")
        conn.close()
        return

    log_message(workdir, f"Grouping duplicates with threshold {args.threshold}")
    groups = group_duplicates(entries, args.threshold)

    moved_count = 0
    if groups:
        for group in groups:
            best = None
            best_score = -1
            scores = {}
            for rel in group:
                full = workdir / rel
                try:
                    with Image.open(str(full)) as im:
                        gray = im.convert("L")
                        arr = np.array(gray)
                        score = float(cv2.Laplacian(arr, cv2.CV_64F).var())
                except Exception:
                    score = 0.0
                scores[rel] = score
                if score > best_score:
                    best_score = score
                    best = rel

            for rel in group:
                if rel == best:
                    continue

                if max_depth > 0:
                    original_dir = (workdir / rel).parent
                    dup_dir_full = original_dir / DUP_DIR_NAME
                else:
                    dup_dir_full = workdir / DUP_DIR_NAME

                if not dup_dir_full.exists():
                    dup_dir_full.mkdir(parents=True, exist_ok=True)

                try:
                    rel_dst_dir = os.path.relpath(str(dup_dir_full), str(workdir))
                    new_rel = safe_move_and_update(conn, workdir, rel, rel_dst_dir)
                    moved_count += 1
                    log_message(workdir, f"MOVED: {rel} -> {new_rel} (kept: {best})")
                except Exception as e:
                    log_message(workdir, f"ERROR moving {rel}: {e}")

    log_message(workdir, f"Scan complete. groups={len(groups)}, moved={moved_count}")
    print(f"Done. Found {len(groups)} duplicate group(s). Moved {moved_count} file(s). See {workdir / LOG_FILE} for details.")

    conn.close()

if __name__ == "__main__":
    main()