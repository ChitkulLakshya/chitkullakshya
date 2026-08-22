#!/usr/bin/env python3
"""
Generate a GitHub-style contribution heatmap PNG using the GraphQL API.

Fetches the full contribution calendar via GitHub's GraphQL API
(user.contributionsCollection.contributionCalendar), which returns
real contribution counts per day for the past year.

Usage:
    python scripts/gen_contribution_heatmap.py [--user USER] [--output PATH] [--token TOKEN]

In a GitHub Action, GITHUB_TOKEN is auto-provided. Locally, pass --token
or set GITHUB_TOKEN / GH_TOKEN env var (e.g. from `gh auth token`).
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from urllib.request import Request, urlopen

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import FancyBboxPatch
import numpy as np

BG_COLOR = '#0d1117'
TEXT_COLOR = '#8b949e'
TEXT_BRIGHT = '#c9d1d9'
GRID_BG = '#161b22'

# GitHub green scale
GREEN_COLORS = ['#161b22', '#0e4429', '#006d32', '#26a641', '#39d353']


def graphql_query(query, token):
    """Execute a GraphQL query against GitHub's API."""
    url = 'https://api.github.com/graphql'
    body = json.dumps({'query': query}).encode('utf-8')
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    req = Request(url, data=body, headers=headers, method='POST')
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode('utf-8'))


def fetch_contributions(username, token):
    """Fetch contribution calendar via GraphQL API."""
    query = f"""
    query {{
      user(login: "{username}") {{
        contributionsCollection {{
          contributionCalendar {{
            totalContributions
            weeks {{
              contributionDays {{
                date
                contributionCount
                color
              }}
            }}
          }}
        }}
      }}
    }}
    """
    print(f'Fetching contribution calendar for @{username} via GraphQL...')
    result = graphql_query(query, token)

    if 'errors' in result:
        print(f'GraphQL errors: {result["errors"]}')
        return {}, 0

    cal = result['data']['user']['contributionsCollection']['contributionCalendar']
    total = cal['totalContributions']
    weeks = cal['weeks']

    contributions = {}
    for week in weeks:
        for day in week['contributionDays']:
            contributions[day['date']] = day['contributionCount']

    print(f'Total contributions: {total}')
    print(f'Days with data: {len(contributions)}')
    return contributions, total


def render_heatmap(contributions, total, output_path, username):
    """Render the contribution heatmap as a PNG with column gaps."""
    if not contributions:
        fig, ax = plt.subplots(figsize=(12, 3), facecolor=BG_COLOR)
        ax.text(0.5, 0.5, 'Contribution data unavailable (token required)',
                ha='center', va='center', color=TEXT_COLOR, fontsize=14)
        ax.axis('off')
        fig.savefig(output_path, facecolor=BG_COLOR, dpi=150, bbox_inches='tight')
        plt.close(fig)
        return

    # Build date range from the data
    dates = sorted(contributions.keys())
    start_date = datetime.strptime(dates[0], '%Y-%m-%d')
    end_date = datetime.strptime(dates[-1], '%Y-%m-%d')

    # Align start to Sunday (GitHub weeks start on Sunday)
    start_sunday = start_date - timedelta(days=(start_date.weekday() + 1) % 7)

    total_weeks = (end_date - start_sunday).days // 7 + 1
    grid = np.zeros((7, total_weeks), dtype=int)

    current = start_sunday
    while current <= end_date:
        date_str = current.strftime('%Y-%m-%d')
        day_idx = (current.weekday() + 1) % 7  # Sunday=0
        week_idx = (current - start_sunday).days // 7
        if 0 <= week_idx < total_weeks:
            grid[day_idx, week_idx] = contributions.get(date_str, 0)
        current += timedelta(days=1)

    # Create figure
    fig, ax = plt.subplots(figsize=(14, 3.2), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    cell_size = 1.0
    gap = 0.15  # visible gap between week columns

    for week in range(total_weeks):
        for day in range(7):
            x = week * (cell_size + gap)
            y = (6 - day) * (cell_size + gap)
            count = grid[day, week]
            # Color: 0=empty, then 4 green levels
            if count == 0:
                color = GREEN_COLORS[0]
            elif count <= 3:
                color = GREEN_COLORS[1]
            elif count <= 7:
                color = GREEN_COLORS[2]
            elif count <= 12:
                color = GREEN_COLORS[3]
            else:
                color = GREEN_COLORS[4]

            rect = FancyBboxPatch(
                (x, y), cell_size, cell_size,
                boxstyle="round,pad=0.02",
                facecolor=color, edgecolor='none',
            )
            ax.add_patch(rect)

    # Month labels along the top
    last_month = None
    for week in range(total_weeks):
        week_date = start_sunday + timedelta(weeks=week)
        month_name = week_date.strftime('%b')
        if month_name != last_month and week_date.day <= 7:
            x = week * (cell_size + gap) + cell_size / 2
            ax.text(x, 7 * (cell_size + gap) + 0.3, month_name,
                    ha='center', va='bottom', color=TEXT_COLOR, fontsize=8,
                    fontfamily='sans-serif')
            last_month = month_name

    # Day labels (Mon, Wed, Fri)
    day_names = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    for day in [1, 3, 5]:
        y = (6 - day) * (cell_size + gap) + cell_size / 2
        ax.text(-1.5, y, day_names[day],
                ha='right', va='center', color=TEXT_COLOR, fontsize=8,
                fontfamily='sans-serif')

    # Legend: Less [][][][] More
    legend_y = -1.8
    legend_x_start = total_weeks * (cell_size + gap) - 5.5 * (cell_size * 0.7 + 0.1)
    ax.text(legend_x_start - 0.5, legend_y + 0.35, 'Less',
            ha='right', va='center', color=TEXT_COLOR, fontsize=8)
    for i, color in enumerate(GREEN_COLORS):
        x = legend_x_start + i * (cell_size * 0.7 + 0.1)
        rect = FancyBboxPatch(
            (x, legend_y), cell_size * 0.7, cell_size * 0.7,
            boxstyle="round,pad=0.02",
            facecolor=color, edgecolor='none',
        )
        ax.add_patch(rect)
    ax.text(legend_x_start + 5 * (cell_size * 0.7 + 0.1) + 0.3, legend_y + 0.35, 'More',
            ha='left', va='center', color=TEXT_COLOR, fontsize=8)

    # Total contributions label (bottom right)
    ax.text(total_weeks * (cell_size + gap) - 0.5, legend_y + 0.35,
            f'{total} contributions in the last year',
            ha='right', va='center', color=TEXT_BRIGHT, fontsize=9,
            fontfamily='sans-serif', fontweight='bold')

    ax.set_xlim(-3, total_weeks * (cell_size + gap) + 1)
    ax.set_ylim(legend_y - 1, 7 * (cell_size + gap) + 2)
    ax.set_aspect('equal')
    ax.axis('off')

    plt.subplots_adjust(left=0.04, right=0.98, top=0.92, bottom=0.08)
    fig.savefig(output_path, facecolor=BG_COLOR, dpi=150, bbox_inches='tight', pad_inches=0.4)
    plt.close(fig)
    print(f'Contribution heatmap saved: {output_path}')


def main():
    parser = argparse.ArgumentParser(description='Generate contribution heatmap via GraphQL')
    parser.add_argument('--user', default='ChitkulLakshya')
    parser.add_argument('--output', default=None)
    parser.add_argument('--token', default=None)
    args = parser.parse_args()

    token = args.token or os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if not token:
        print('ERROR: No GitHub token provided. Set GITHUB_TOKEN or pass --token.')
        print('  Local: gh auth token  |  Action: auto-provided')
        sys.exit(1)

    if args.output:
        output_path = args.output
    else:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        output_path = os.path.join(project_root, 'assets', 'contribution-heatmap.png')

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    contributions, total = fetch_contributions(args.user, token)
    render_heatmap(contributions, total, output_path, args.user)
    print('Done!')


if __name__ == '__main__':
    main()
