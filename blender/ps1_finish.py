"""PS1 finish for rendered frames: composite over white, 15-bit colour with a 4x4 Bayer dither,
nearest-neighbour upscale, centre-crop to the delivery size. No scanlines or other screen effects.

    python3 blender/ps1_finish.py <frames_dir> <out_dir> <upscale> <width> <height>

From the goosnav-3D-assets character ads (work/2026-10-08-character-ads/post_ps1.py).
Render the PS1 characters natively at delivery/upscale (1080x1350 / 3 = 360x450), 1 sample, no filtering.
"""
import glob
import os
import sys

import numpy as np
from PIL import Image

BAYER4 = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) + 0.5) / 16.0


def finish(src, dst, k, width, height):
    os.makedirs(dst, exist_ok=True)
    for p in sorted(glob.glob(os.path.join(src, '*.png'))):
        a = np.asarray(Image.open(p).convert('RGBA'), np.float32) / 255
        h, w = a.shape[:2]
        rgb = a[..., :3] * a[..., 3:] + (1 - a[..., 3:])
        threshold = np.tile(BAYER4, (h // 4 + 1, w // 4 + 1))[:h, :w][..., None]
        rgb = np.clip(np.floor(rgb * 31 + threshold) / 31, 0, 1)
        img = Image.fromarray((rgb * 255 + 0.5).astype(np.uint8)).resize((w * k, h * k), Image.NEAREST)
        x0, y0 = (img.width - width) // 2, (img.height - height) // 2
        img.crop((x0, y0, x0 + width, y0 + height)).save(os.path.join(dst, os.path.basename(p)))


if __name__ == '__main__':
    finish(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]))
