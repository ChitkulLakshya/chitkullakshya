"""Combine PNG frames into an optimized GIF using Pillow."""
import os
import glob
from PIL import Image

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FRAMES_DIR = os.path.join(PROJECT_ROOT, '.preview', 'frames')
OUTPUT_GIF = os.path.join(PROJECT_ROOT, 'assets', 'skills-animation.gif')

FRAME_DURATION = 80  # ms per frame (~12.5fps)
MAX_COLORS = 256     # GIF palette limit

def main():
    frame_paths = sorted(glob.glob(os.path.join(FRAMES_DIR, 'frame_*.png')))
    if not frame_paths:
        raise SystemExit(f'No frames found in {FRAMES_DIR}')

    print(f'Found {len(frame_paths)} frames')

    frames = []
    for fp in frame_paths:
        img = Image.open(fp).convert('RGBA')
        # Composite onto a transparent background — preserve alpha for GIF
        # Flatten alpha into palette: transparent pixels become palette index 255
        alpha = img.split()[3]
        # Create a P-mode image with a transparent index
        p = img.convert('RGB').convert('P', palette=Image.ADAPTIVE, colors=MAX_COLORS - 1)
        # Reserve index 255 for transparency
        p.paste(255, mask=Image.eval(alpha, lambda a: 255 if a < 128 else 0))
        p.info['transparency'] = 255
        frames.append(p)

    print(f'Composing GIF with {len(frames)} frames at {FRAME_DURATION}ms/frame...')

    # Save with optimization
    frames[0].save(
        OUTPUT_GIF,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_DURATION,
        loop=0,  # infinite loop
        disposal=2,
        optimize=True,
    )

    size_kb = os.path.getsize(OUTPUT_GIF) / 1024
    print(f'Saved: {OUTPUT_GIF} ({size_kb:.0f} KB)')

if __name__ == '__main__':
    main()
