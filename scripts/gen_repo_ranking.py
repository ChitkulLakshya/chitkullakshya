#!/usr/bin/env python3
"""
Generate a ranked list image of repos by stars and commits.

Fetches all public repos, gets star counts from the repos list endpoint,
counts commits per repo via the commits API, and renders a clean ranked
list as a PNG image.

Usage:
    python scripts/gen_repo_ranking.py [--user USER] [--output PATH] [--token TOKEN]
"""
import argparse
import json
import os
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# GitHub Linguist colors (subset — same as treemap script)
LINGUIST_COLORS = {
    'JavaScript': '#f1e05a', 'TypeScript': '#3178c6', 'Python': '#3572A5',
    'Java': '#b07219', 'HTML': '#e34c26', 'CSS': '#563d7c', 'SCSS': '#c6538c',
    'PowerShell': '#012456', 'C': '#555555', 'C++': '#f34b7d', 'C#': '#178600',
    'Go': '#00ADD8', 'Rust': '#dea584', 'Ruby': '#701516', 'PHP': '#4F5D95',
    'Swift': '#F05138', 'Kotlin': '#A97BFF', 'Dart': '#00B4AB',
    'Shell': '#89e051', 'Dockerfile': '#384d54',
    'Jupyter Notebook': '#DA5B0B', 'Vue': '#41b883', 'Svelte': '#ff3e00',
    'SQL': '#e38c00', 'Lua': '#000080', 'R': '#198CE7',
    'Makefile': '#427819', 'CMake': '#DA3412',
    'YAML': '#cb171e', 'Markdown': '#083fa1',
}
DEFAULT_COLOR = '#8B949E'

BG_COLOR = '#0d1117'
TEXT_COLOR = '#c9d1d9'
TEXT_DIM = '#8b949e'
TEXT_BRIGHT = '#f0f6fc'
ACCENT_GOLD = '#d29922'
ACCENT_GREEN = '#39d353'
ROW_ALT_BG = '#161b22'


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


def fetch_all_repos(username, token=None):
    repos = []
    page = 1
    while True:
        url = f'https://api.github.com/users/{username}/repos?per_page=100&page={page}&type=public'
        print(f'Fetching repos page {page}...')
        data, link = api_get(url, token)
        if not data:
            break
        repos.extend(data)
        if 'rel="next"' in (link or ''):
            page += 1
        else:
            break
    return repos


def count_commits(username, repo_name, token=None):
    """Count total commits by paginating through commits."""
    count = 0
    page = 1
    while True:
        url = f'https://api.github.com/repos/{username}/{repo_name}/commits?per_page=100&page={page}'
        data, link = api_get(url, token)
        if not data:
            break
        count += len(data)
        if len(data) < 100:
            break
        page += 1
        if page > 20:  # Safety cap at 2000 commits
            break
        time.sleep(0.5)  # Rate limit friendly
    return count


def render_ranking(repos_data, output_path, username):
    """Render the ranked list as a PNG image."""
    if not repos_data:
        fig, ax = plt.subplots(figsize=(10, 4), facecolor=BG_COLOR)
        ax.text(0.5, 0.5, 'No repo data available',
                ha='center', va='center', color=TEXT_COLOR, fontsize=14)
        ax.axis('off')
        fig.savefig(output_path, facecolor=BG_COLOR, dpi=150, bbox_inches='tight')
        plt.close(fig)
        return

    # Sort by stars desc, then commits desc
    repos_data.sort(key=lambda x: (x['stars'], x['commits']), reverse=True)

    # Take top 5
    top = repos_data[:5]

    # Layout — wide and short for a clean full-width banner look
    n = len(top)
    fig_width = 16
    fig_height = 1.2 + n * 0.85
    fig, ax = plt.subplots(figsize=(fig_width, fig_height), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    y_start = 0.96
    y_step = 1.0 / (n + 2)

    for i, repo in enumerate(top):
        y = y_start - (i + 1) * y_step

        # Alternating row background
        if i % 2 == 0:
            ax.axhspan(y - y_step * 0.45, y + y_step * 0.45,
                       color=ROW_ALT_BG, zorder=0, alpha=0.5)

        # Rank number
        rank_color = ACCENT_GOLD if i < 3 else TEXT_DIM
        ax.text(0.02, y, f'{i+1}', ha='left', va='center',
                color=rank_color, fontsize=18, fontweight='bold', fontfamily='sans-serif')

        # Language color dot
        lang_color = LINGUIST_COLORS.get(repo.get('language'), DEFAULT_COLOR)
        ax.plot(0.08, y, 'o', color=lang_color, markersize=11, zorder=5)

        # Repo name
        ax.text(0.11, y, repo['name'], ha='left', va='center',
                color=TEXT_BRIGHT, fontsize=15, fontweight='bold', fontfamily='sans-serif',
                clip_on=True)

        # Stars (right side)
        stars_text = f'★ {repo["stars"]}'
        ax.text(0.80, y, stars_text, ha='right', va='center',
                color=ACCENT_GOLD, fontsize=14, fontfamily='sans-serif')

        # Commits (further right)
        commits_text = f'◆ {repo["commits"]} commits'
        ax.text(0.97, y, commits_text, ha='right', va='center',
                color=ACCENT_GREEN, fontsize=14, fontfamily='sans-serif')

    ax.set_xlim(0, 1)
    ax.set_ylim(-0.04, 1.0)
    ax.axis('off')

    plt.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)
    fig.savefig(output_path, facecolor=BG_COLOR, dpi=150, bbox_inches='tight', pad_inches=0.3)
    plt.close(fig)
    print(f'Repo ranking saved: {output_path}')


def main():
    parser = argparse.ArgumentParser(description='Generate repo ranking by stars and commits')
    parser.add_argument('--user', default='ChitkulLakshya')
    parser.add_argument('--output', default=None)
    parser.add_argument('--token', default=None)
    args = parser.parse_args()

    token = args.token or os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')

    if args.output:
        output_path = args.output
    else:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        output_path = os.path.join(project_root, 'assets', 'repo-ranking.png')

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    print(f'Fetching repos for @{args.user}...')
    repos = fetch_all_repos(args.user, token)
    print(f'Found {len(repos)} public repos')

    repos_data = []
    for i, repo in enumerate(repos):
        if repo.get('fork'):
            print(f'  [{i+1}/{len(repos)}] {repo["name"]} (fork, skipping)')
            continue
        name = repo['name']
        stars = repo.get('stargazers_count', 0)
        print(f'  [{i+1}/{len(repos)}] {name} — {stars} stars, counting commits...')
        commits = count_commits(args.user, name, token)
        repos_data.append({
            'name': name,
            'stars': stars,
            'commits': commits,
            'language': repo.get('language'),
        })
        print(f'    -> {commits} commits')

    print(f'\nTop repos by stars:')
    for r in sorted(repos_data, key=lambda x: x['stars'], reverse=True)[:10]:
        print(f'  {r["name"]:<30} {r["stars"]:>3} stars  {r["commits"]:>5} commits')

    render_ranking(repos_data, output_path, args.user)
    print('Done!')


if __name__ == '__main__':
    main()
