# sharpness.py
# Contains functions for image sharpness analysis.

import cv2
import numpy as np

def downscale(image, downscale_width=800):
    """
    Downscales an image if its width is greater than a specified value.
    This helps speed up processing.
    """
    h, w = image.shape[:2]
    if w > downscale_width:
        new_h = int(h * (downscale_width / w))
        return cv2.resize(image, (downscale_width, new_h), interpolation=cv2.INTER_AREA)
    return image

def center_crop(image, crop_fraction=0.7):
    """
    Crops the center of an image to focus sharpness analysis on the main subject.
    """
    h, w = image.shape[:2]
    ch, cw = int(h * crop_fraction), int(w * crop_fraction)
    y1 = (h - ch) // 2
    x1 = (w - cw) // 2
    return image[y1:y1 + ch, x1:x1 + cw]

def sharpness_score(image):
    """
    Calculates the Laplacian variance and Tenengrad score for an image to
    determine its sharpness. Returns a tuple: (laplacian_variance, tenengrad_score).
    """
    image = center_crop(image)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    sobel_mag = cv2.magnitude(sobel_x, sobel_y)
    tenengrad = (sobel_mag ** 2).mean()
    return lap_var, tenengrad

def grid_sharpness_scores(image, grid_size=3):
    """
    Calculates sharpness scores for each tile in a grid.
    Returns a list of (laplacian_variance, tenengrad_score) tuples.
    """
    h, w = image.shape[:2]
    tile_h, tile_w = h // grid_size, w // grid_size
    scores = []
    for row in range(grid_size):
        for col in range(grid_size):
            tile = image[row*tile_h:(row+1)*tile_h, col*tile_w:(col+1)*tile_w]
            scores.append(sharpness_score(tile))
    return scores
