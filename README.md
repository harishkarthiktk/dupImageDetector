# Duplicate Image Detector - dup\_ImageDectector

**dup\_ImageDectector** is a command-line tool for finding and organizing duplicate images within a specified directory. It uses perceptual hashing (phash) for fast, robust detection of similar images, even if they have slightly different sizes or file formats. The tool also features a robust image-reading failover system and an SQLite cache to avoid re-processing files on subsequent scans.

## Key Features

* **Perceptual Hashing (pHash):** Detects visually similar images, not just identical files.
* **SQLite Caching:** Scans are fast because only new or modified files are processed.
* **Multi-threaded Processing:** Leverages multiple CPU cores to speed up hashing.
* **Robust Image Reading:** Tries several libraries (OpenCV, Pillow, rawpy, imageio) to handle a wide range of image formats, including RAW files.
* **Automatic Duplicate Handling:** Groups duplicates and automatically moves all but the sharpest version into a dedicated duplicates folder.

## Requirements

To run this script, you'll need Python 3 and the following libraries:

```bash
pip install pillow imagehash tqdm rawpy imageio opencv-python
```

* **Pillow:** A powerful image processing library.
* **imagehash:** For calculating perceptual hashes.
* **tqdm:** For a nice progress bar in the terminal.
* **rawpy:** To handle RAW image formats like `.cr2`.
* **imageio:** An alternative image reading library.
* **opencv-python:** For image loading and sharpness analysis.

## Usage

Navigate to the `dup_ImageDectector` directory and run the script with the following command-line arguments:

```bash
python3 main.py [OPTIONS]
```

### Options:

* `-W, --working-dir <path>` (Required)
  The root folder to scan for images. The SQLite cache (`image_hashes.sqlite`) and log file (`scan_log.txt`) will be created here.

* `-T, --threshold <int>` (Default: 6)
  The maximum Hamming distance between two hashes for them to be considered a duplicate. A lower number is stricter.

  * 0-3: Strict match (almost identical images).
  * 4-6: Balanced (good for most use cases).
  * 7-12: Loose (finds more similar but not exact duplicates).

* `-j, --jobs <int>` (Default: number of CPU cores)
  The number of worker processes to use for hashing images. Using more cores will speed up the process.

* `-R, --recursive [depth]` (Optional)
  Recursively scan subfolders. If a number is provided (e.g., `-R 5`), it will scan up to that depth. If no number is provided (`-R`), the default depth is 5.

* `--force-rescan`
  Ignores the SQLite cache and re-hashes all files from scratch.

## Example

To scan a folder named `my_photos` recursively up to 10 levels deep with a moderate threshold, run:

```bash
python3 main.py -W /path/to/my_photos -T 8 -R 10
```

## How it Works

The script follows these steps:

1. **File Gathering:**
   Walks the specified working directory and finds all image files with supported extensions, respecting the recursion depth.

2. **Caching:**
   Checks the `image_hashes.sqlite` database. For each file, if a hash exists and the file's size and modification time haven't changed, it uses the cached hash. Otherwise, the file is added to a processing queue.

3. **Parallel Hashing:**
   Uses a process pool to hash the files in the queue. It attempts to read each file with multiple libraries until one succeeds, logs the method used, and then calculates the phash.

4. **Grouping:**
   Compares all image hashes to find groups of duplicates using the specified Hamming distance threshold.

5. **Duplicate Handling:**
   For each group of duplicates, determines the "best" image by calculating the Laplacian variance, a metric for sharpness. All other images in the group are moved to a duplicates subfolder.

## Logging and Output

A log file named `scan_log.txt` is created in your working directory. It records:

* Which images were hashed
* Which read method was used
* Which files were moved
