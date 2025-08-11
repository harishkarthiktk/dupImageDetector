#!/usr/bin/env python3
"""
blurry_detector.py

Detects blurry images and moves them to a 'blurry' subfolder.

Usage:
    python blurry_detector.py -W /path/to/folder --lap-thresh 100 --ten-thresh 1000

Requirements:
    pip install pillow imagehash tqdm rawpy imageio opencv-python
"""

import os
import argparse
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from tqdm import tqdm
import sys
from pathlib import Path

from image_processing import safe_read_with_cv2, safe_read_with_pillow, safe_read_with_rawpy, safe_read_with_imageio
from sharpness import sharpness_score, grid_sharpness_scores, downscale
from utils import log_message, safe_move_and_update, gather_files_with_depth
from constants import LOG_FILE, SUPPORTED_EXTS

# Constants for this script
BLURRY_DIR_NAME = "blurry"

def process_file_for_blurry_detection(file_path, workdir_str, lap_thresh, ten_thresh, split_image):
    """
    Worker function to read an image and determine if it's blurry.
    """
    full_path = str(file_path)
    try:
        # Try multiple read methods for robustness
        img = safe_read_with_cv2(full_path)
        if img is None:
            img = safe_read_with_pillow(full_path)
        if img is None:
            img = safe_read_with_rawpy(full_path)
        if img is None:
            img = safe_read_with_imageio(full_path)

        if img is None:
            return (os.path.relpath(full_path, workdir_str), "fail", None)

        img = downscale(img)
        relpath = os.path.relpath(full_path, workdir_str)
        
        # Check sharpness based on user's flags
        if not split_image:
            lap, ten = sharpness_score(img)
            if lap < lap_thresh and ten < ten_thresh:
                return (relpath, "blurry", None)
        else:
            scores = grid_sharpness_scores(img)
            blurry_tiles = sum(1 for lap, ten in scores if lap < lap_thresh and ten < ten_thresh)

            if blurry_tiles >= 3:
                sub_dir = ""
                if blurry_tiles < 6:
                    sub_dir = "partially_blurry"
                elif blurry_tiles < 9:
                    sub_dir = "mostly_blurry"
                else:
                    sub_dir = "completely_blurry"
                
                return (relpath, "blurry_partial", sub_dir)

        return (relpath, "clear", None)
    except Exception as e:
        return (os.path.relpath(full_path, workdir_str), "error", str(e))

def main():
    parser = argparse.ArgumentParser(description="Move blurry images based on sharpness metrics.")
    parser.add_argument("-W", "--working-dir", required=True, help="Directory containing images to scan.")
    parser.add_argument("-j", "--jobs", type=int, default=os.cpu_count(), help="Number of worker processes.")
    parser.add_argument("-R", "--recursive", nargs="?", const=5, type=int, metavar="DEPTH",
                        help="Recursively scan subfolders up to DEPTH levels (default: 5).")
    parser.add_argument("--lap-thresh", type=float, default=100.0, help="Laplacian variance threshold.")
    parser.add_argument("--ten-thresh", type=float, default=1000.0, help="Tenengrad threshold.")
    parser.add_argument("-S", "--split-image", action="store_true", help="Split image into 3x3 grid to detect partial blurriness.")
    args = parser.parse_args()

    workdir = Path(args.working_dir).resolve()
    if not workdir.is_dir():
        print("Working directory not found:", workdir)
        sys.exit(1)

    max_depth = args.recursive if args.recursive is not None else 5
    log_message(workdir, f"Starting blurry image scan. jobs={args.jobs}, recursive_depth={max_depth}")

    all_files = gather_files_with_depth(workdir, max_depth)
    
    worker = partial(
        process_file_for_blurry_detection, 
        workdir_str=str(workdir), 
        lap_thresh=args.lap_thresh, 
        ten_thresh=args.ten_thresh,
        split_image=args.split_image
    )
    
    moved_count = 0
    with ProcessPoolExecutor(max_workers=args.jobs) as exe:
        for relpath, status, sub_dir in tqdm(
            exe.map(worker, all_files),
            total=len(all_files),
            desc="Detecting blur"
        ):
            if status == "blurry":
                dest_dir = workdir / BLURRY_DIR_NAME
                safe_move(workdir / relpath, dest_dir)
                log_message(workdir, f"MOVED blurry file: {relpath} -> {dest_dir}")
                moved_count += 1
            elif status == "blurry_partial":
                dest_dir = workdir / BLURRY_DIR_NAME / sub_dir
                safe_move(workdir / relpath, dest_dir)
                log_message(workdir, f"MOVED blurry file: {relpath} -> {dest_dir}")
                moved_count += 1
            elif status == "error":
                log_message(workdir, f"ERROR processing {relpath}: {sub_dir}")
            
    print(f"Done. Detected and moved {moved_count} blurry files. See {workdir / LOG_FILE} for details.")


if __name__ == "__main__":
    main()
