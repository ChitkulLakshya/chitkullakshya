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
        # Composite onto dark background (matches GitHub dark theme)
        bg = Image.new('RGBA', img.size, (13, 17, 23, 255))  # #0d1117
        bg.paste(img, mask=img.split()[3] if img.mode == 'RGBA' else None)
        frames.append(bg.convert('P', palette=Image.ADAPTIVE, colors=MAX_COLORS))

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
