#!/usr/bin/env python3
"""
Generate a 7x24 activity heatmap (days x hours) from public GitHub events.

Fetches recent public events via /users/{user}/events/public (last 90 days),
extracts timestamps, bins by day-of-week x hour-of-day, and renders a heatmap
showing when the user is most active.

Usage:
    python scripts/gen_activity_heatmap.py [--user USER] [--output PATH] [--token TOKEN]
"""
import argparse
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np

BG_COLOR = '#0d1117'
TEXT_COLOR = '#8b949e'
TEXT_BRIGHT = '#c9d1d9'
CELL_BG = '#161b22'


def api_get(url, token=None, retries=3):
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'application/vnd.github+json',
    }
    if token:
        headers['Authorization'] = f'Bearer {token}'

    for attempt in range(retries):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                link_header = resp.headers.get('Link', '')
                return data, link_header
        except (HTTPError, URLError, TimeoutError) as e:
            if attempt < retries - 1:
                wait = 2 ** (attempt + 1)
                print(f'  Retry {attempt+1}/{retries} after {wait}s: {e}')
                time.sleep(wait)
            else:
                raise
    return None, None


def fetch_events(username, token=None):
    """Fetch public events (up to 10 pages = ~300 events)."""
    events = []
    for page in range(1, 11):
        url = f'https://api.github.com/users/{username}/events/public?per_page=100&page={page}'
        print(f'  Fetching events page {page}...')
        data, link = api_get(url, token)
        if not data:
            break
        events.extend(data)
        if len(data) < 100:
            break
        time.sleep(0.5)
    return events


def render_heatmap(events, output_path, username):
    """Render 7x24 activity heatmap."""
    # Bin events by day-of-week (0=Mon) x hour (0-23)
    grid = np.zeros((7, 24), dtype=int)

    for event in events:
        created_at = event.get('created_at')
        if not created_at:
            continue
        try:
            dt = datetime.strptime(created_at, '%Y-%m-%dT%H:%M:%SZ')
        except ValueError:
            continue
        day = dt.weekday()  # 0=Monday
        hour = dt.hour
        grid[day, hour] += 1

    total_events = len(events)
    max_count = grid.max() if grid.max() > 0 else 1

    print(f'  Total events: {total_events}')
    print(f'  Max activity in a single slot: {max_count}')

    # Color scale: green steps
    green_colors = ['#161b22', '#0e4429', '#006d32', '#26a641', '#39d353']
    cmap = mcolors.ListedColormap(green_colors)

    # Normalize: 0 -> 0, then quartiles of nonzero values
    nonzero = grid[grid > 0]
    if len(nonzero) > 0:
        q33 = np.percentile(nonzero, 33)
        q66 = np.percentile(nonzero, 66)
        bounds = [-0.5, 0.5, q33, q66, max_count + 0.5]
    else:
        bounds = [-0.5, 0.5, 1.5, 2.5, 3.5]
    norm = mcolors.BoundaryNorm(bounds, cmap.N)

    # Create figure
    fig, ax = plt.subplots(figsize=(13, 4.5), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    # Draw cells with rounded corners and gaps
    cell_w = 1.0
    cell_h = 1.0
    gap_x = 0.08
    gap_y = 0.08

    for day in range(7):
        for hour in range(24):
            x = hour * (cell_w + gap_x)
            y = (6 - day) * (cell_h + gap_y)
            count = grid[day, hour]

            if count == 0:
                color = CELL_BG
            else:
                idx = min(4, int(np.searchsorted([0.5, bounds[2], bounds[3]], count)))
                color = green_colors[idx]

            from matplotlib.patches import FancyBboxPatch
            rect = FancyBboxPatch(
                (x, y), cell_w, cell_h,
                boxstyle="round,pad=0.03",
                facecolor=color, edgecolor='none',
            )
            ax.add_patch(rect)

    # Hour labels (every 2 hours)
    for hour in range(0, 24, 2):
        x = hour * (cell_w + gap_x) + cell_w / 2
        ax.text(x, -0.8, f'{hour:02d}',
                ha='center', va='top', color=TEXT_COLOR, fontsize=8, fontfamily='sans-serif')

    # Day labels
    day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    for day in range(7):
        y = (6 - day) * (cell_h + gap_y) + cell_h / 2
        ax.text(-1.5, y, day_names[day],
                ha='right', va='center', color=TEXT_COLOR, fontsize=9, fontfamily='sans-serif')

    # Legend
    legend_y = -2.0
    legend_x = 24 * (cell_w + gap_x) - 5 * (cell_w * 0.8 + 0.1)
    ax.text(legend_x - 0.5, legend_y + 0.4, 'Less',
            ha='right', va='center', color=TEXT_COLOR, fontsize=8)
    for i, color in enumerate(green_colors):
        x = legend_x + i * (cell_w * 0.8 + 0.1)
        rect = FancyBboxPatch(
            (x, legend_y), cell_w * 0.8, cell_h * 0.8,
            boxstyle="round,pad=0.03",
            facecolor=color, edgecolor='none',
        )
        ax.add_patch(rect)
    ax.text(legend_x + 5 * (cell_w * 0.8 + 0.1) + 0.3, legend_y + 0.4, 'More',
            ha='left', va='center', color=TEXT_COLOR, fontsize=8)

    ax.set_xlim(-3, 24 * (cell_w + gap_x) + 1)
    ax.set_ylim(legend_y - 1, 7 * (cell_h + gap_y) + 1)
    ax.set_aspect('equal')
    ax.axis('off')

    plt.subplots_adjust(left=0.05, right=0.98, top=0.95, bottom=0.12)
    fig.savefig(output_path, facecolor=BG_COLOR, dpi=150, bbox_inches='tight', pad_inches=0.4)
    plt.close(fig)
    print(f'Activity heatmap saved: {output_path}')


def main():
    parser = argparse.ArgumentParser(description='Generate 7x24 activity heatmap')
    parser.add_argument('--user', default='ChitkulLakshya')
    parser.add_argument('--output', default=None)
    parser.add_argument('--token', default=None)
    args = parser.parse_args()

    token = args.token or os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')

    if args.output:
        output_path = args.output
    else:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        output_path = os.path.join(project_root, 'assets', 'activity-heatmap.png')

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    print(f'Fetching public events for @{args.user}...')
    events = fetch_events(args.user, token)
    print(f'Found {len(events)} events')

    render_heatmap(events, output_path, args.user)
    print('Done!')


if __name__ == '__main__':
    main()
