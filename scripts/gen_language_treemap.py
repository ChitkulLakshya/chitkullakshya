#!/usr/bin/env python3
"""
Generate a language treemap PNG for a GitHub user.

Fetches all public repositories, queries each repo's /languages endpoint,
aggregates total bytes per language across all repos, and renders a treemap
using squarify + matplotlib with GitHub Linguist's official language colors.

Usage:
    python scripts/gen_language_treemap.py [--user USER] [--output PATH] [--token TOKEN]

In a GitHub Action, GITHUB_TOKEN is auto-provided via env var.
"""
import argparse
import json
import os
import sys
import time
from collections import defaultdict
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import squarify

# ─── GitHub Linguist official language colors ───────────────────────────────
# Source: https://github.com/github-linguist/linguist/blob/master/lib/linguist/languages.yml
LINGUIST_COLORS = {
    'JavaScript': '#f1e05a', 'TypeScript': '#3178c6', 'Python': '#3572A5',
    'Java': '#b07219', 'HTML': '#e34c26', 'CSS': '#563d7c', 'SCSS': '#c6538c',
    'PowerShell': '#012456', 'C': '#555555', 'C++': '#f34b7d', 'C#': '#178600',
    'Go': '#00ADD8', 'Rust': '#dea584', 'Ruby': '#701516', 'PHP': '#4F5D95',
    'Swift': '#F05138', 'Kotlin': '#A97BFF', 'Dart': '#00B4AB', 'Flutter': '#00B4AB',
    'Shell': '#89e051', 'Batchfile': '#C1F12E', 'Dockerfile': '#384d54',
    'Jupyter Notebook': '#DA5B0B', 'Vue': '#41b883', 'Svelte': '#ff3e00',
    'React': '#61dafb', 'Next': '#000000', 'Astro': '#ff5a03',
    'SQL': '#e38c00', 'TSQL': '#e38c00', 'PLpgSQL': '#336790',
    'Lua': '#000080', 'R': '#198CE7', 'Scala': '#c22d40', 'Elixir': '#6e4a7e',
    'Haskell': '#5e5086', 'Clojure': '#db5855', 'Erlang': '#B83998',
    'Objective-C': '#438eff', 'Perl': '#0298c3', 'Groovy': '#4298b8',
    'Assembly': '#6E4C13', 'F#': '#b845fc', 'OCaml': '#3be133',
    'Julia': '#a270ba', 'Nim': '#ffc200', 'Zig': '#ec915c',
    'Vim Script': '#199f4b', 'Makefile': '#427819', 'CMake': '#DA3412',
    'Nix': '#7e7eff', 'HCL': '#844FBA', 'Terraform': '#844FBA',
    'YAML': '#cb171e', 'TOML': '#9c4221', 'JSON': '#292929', 'Markdown': '#083fa1',
    'TeX': '#3D6117', 'Roff': '#ecdebe', 'Text': '#cccccc',
    'FreeMarker': '#0050b2', 'Mustache': '#724b3b', 'Handlebars': '#f7931e',
    'Less': '#1d365d', 'Stylus': '#ff6347', 'Sass': '#a53b70',
    'CoffeeScript': '#244776', 'LiveScript': '#499886', 'Pug': '#a86454',
    'GLSL': '#5686a5', 'WGSL': '#3a3a3a', 'ShaderLab': '#222c37',
    'Smalltalk': '#3f9100', 'Emacs Lisp': '#c065db', 'Common Lisp': '#3fb68b',
    'Scheme': '#1e4aec', 'Racket': '#3c5caa', 'Prolog': '#74283c',
    'Fortran': '#4d41b1', 'Ada': '#02f88c', 'COBOL': '#005CA5',
    'Vala': '#ebe5ff', 'Crystal': '#000100', 'Elm': '#60B5CC',
    'PureScript': '#1D222D', 'Reason': '#c62433', 'ReScript': '#e6484f',
    'Solidity': '#AA6741', 'Vyper': '#2980b9', 'Move': '#8e5300',
    'Apex': '#1797c0', 'Visual Basic': '#945db7', 'VBA': '#867db1',
    'ABAP': '#E8274B', 'SAS': '#B34936', 'Stata': '#1a5f7a',
    'MATLAB': '#e16737', 'LabVIEW': '#fede06', 'Arduino': '#bd79d1',
    'Processing': '#0096D8', 'GAP': '#00c200', 'Idris': '#b30000',
    'Agda': '#315665', 'Coq': '#d0b68c', 'Lean': '#d4b00f',
    'Verilog': '#b2b7f8', 'VHDL': '#adb2cb', 'SystemVerilog': '#DAE1C2',
    'OpenSCAD': '#e5cd45', 'GDScript': '#355570', 'Godot': '#355570',
    'Game Maker Language': '#71b417', 'Pony': '#9aa3ff',
    'Inno Setup': '#264b99', 'NSIS': '#f7c84800', 'AutoHotkey': '#6594b9',
    'ColdFusion': '#ed2cd6', 'ActionScript': '#882B0F', 'M4': '#0f0f0f',
    'Awk': '#c30e9e', ' sed': '#64b970', 'VCL': '#148AA8',
    'WebAssembly': '#04133b', 'Wasm': '#04133b',
    'Jinja': '#a52a22', 'Django': '#0c4a33',
    'PostScript': '#da2912', 'Component Pascal': '#b9ce9f',
    'LLVM': '#185619', 'Hy': '#7790B2',
    'Hack': '#878787', 'Standard ML': '#ab5b1e',
    'Oz': '#fab738', 'Koka': '#cfa2b2', 'Nemerle': '#0d3b6e',
    'Oxygene': '#5f2537', 'Xojo': '#81b80b', 'Nit': '#0c9c6f',
    'ooc': '#b0b77d', 'Cirru': '#ccccff', 'Blade': '#f74b86',
    'Boo': '#d4bec1', 'ABAP CDS': '#555e25', 'Apex': '#1797c0',
    'API Blueprint': '#2ACCA8', 'AsciiDoc': '#73a0c5',
    'Brainfuck': '#2F2530', 'Clean': '#3a81c3', 'Cucumber': '#5B206D',
    'D': '#ba595e', 'DM': '#447265', 'Diff': '#88dddd',
    'ECL': '#8a1267', 'Eiffel': '#946d57', 'Ezhil': '#b8cc04',
    'Fantom': '#dbded5', 'Forth': '#341708', 'Factor': '#636747',
    'GAMS': '#f49a22', 'GAP': '#00c200', 'Gnuplot': '#f0a8f0',
    'Golo': '#88562A', 'Grammatical Framework': '#79aa7a',
    'Harbour': '#0e60e3', 'Haxe': '#df7900', 'HyPhy': '#276333',
    'Io': '#a9188d', 'Ioke': '#078193', 'Isabelle': '#FEF004',
    'J': '#9EEDFF', 'JSONiq': '#2cbee0', 'Lasso': '#999999',
    'Latte': '#A8FF97', 'Lex': '#DBCA00', 'LilyPond': '#9ccc7c',
    'Logos': '#7a838d', 'Logtalk': '#2956a0', 'Mako': '#7e4f9c',
    'Max': '#c4a79c', 'Mercury': '#ff2b2b', 'Modula-3': '#223388',
    'MoonScript': '#ff4585', 'MQL4': '#62A8D6', 'MQL5': '#4A76A8',
    'MTML': '#b7e1f4', 'NCL': '#28431f', 'Nemerle': '#0d3b6e',
    'NetLinx': '#447265', 'NetLinx+ERB': '#f8c247',
    'NewLisp': '#87AED7', 'Nim': '#ffc200', 'Nu': '#c9df00',
    'OCaml': '#3be133', 'Oxygene': '#5f2537', 'Pan': '#cc0000',
    'Papyrus': '#6600cc', 'Pawn': '#dbb284', 'Pep8': '#C76F5B',
    'Pkl': '#7e88c7', 'PklDoc': '#7e88c7', 'Pony': '#9aa3ff',
    'PostScript': '#da2912', 'PowerBuilder': '#8f0f1d',
    'Processing': '#0096D8', 'Propeller Spin': '#7fa2a7',
    'Puppet': '#302B6D', 'QML': '#44a51c', 'Quik': '#888e85',
    'RAML': '#77d9b4', 'Rascal': '#fffaa0', 'Rebol': '#358a5b',
    'Red': '#ee0000', 'Ring': '#2d54cb', 'Rouge': '#cc0088',
    'Runoff': '#665a2e', 'Sage': '#7d6c4b', 'Salt': '#646464',
    'Sather': '#355570', 'Self': '#0579aa', 'Shen': '#120F14',
    'Slash': '#007eff', 'SmPL': '#969696', 'Snowball': '#4a4a4a',
    'SourcePawn': '#5c2a3e', 'SQF': '#3F3F3F', 'Squirrel': '#800000',
    'Stan': '#b2011d', 'Turing': '#cf142b', 'TypeScript': '#3178c6',
    'UnityPivot': '#a47115', 'UnrealScript': '#a54c16',
    'V': '#4f87c4', 'Vala': '#ebe5ff', 'Verilog': '#b2b7f8',
    'VHDL': '#adb2cb', 'Vim Script': '#199f4b', 'Vim Snippet': '#199f4b',
    'Volt': '#1F1F1F', 'WebIDL': '#ac4d3c', 'Wget': '#0f0f0f',
    'Wolfram': '#dd1100', 'XBase': '#403a40', 'XC': '#99DA07',
    'Xojo': '#81b80b', 'Xonsh': '#285EEF', 'YARA': '#220000',
    'YASnippet': '#32AB90', 'ZAP': '#7a4c20', 'ZIL': '#a3b7c8',
    'Zig': '#ec915c', 'eC': '#913960', 'fish': '#4aae47',
    'jq': '#c7254e', 'nanorc': '#2d004d', 'reStructuredText': '#141414',
    'wdl': '#42f1f4', 'wisp': '#7582D1', 'xBase': '#403a40',
}

DEFAULT_COLOR = '#8B949E'  # GitHub gray for unknown languages

# GitHub dark theme colors
BG_COLOR = '#0d1117'
TEXT_COLOR = '#c9d1d9'
TEXT_DARK = '#010409'
BORDER_COLOR = '#0d1117'
TITLE_COLOR = '#f0f6fc'
SUBTITLE_COLOR = '#8B949E'


def api_get(url, token=None, retries=3):
    """Fetch JSON from GitHub API with retries."""
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
                # Check for pagination
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
    """Fetch all public repos for a user, handling pagination."""
    repos = []
    page = 1
    while True:
        url = f'https://api.github.com/users/{username}/repos?per_page=100&page={page}&type=public'
        print(f'Fetching repos page {page}...')
        data, link = api_get(url, token)
        if not data:
            break
        repos.extend(data)
        # Check if there are more pages
        if 'rel="next"' in (link or ''):
            page += 1
        else:
            break
    return repos


def fetch_repo_languages(username, repo_name, token=None):
    """Fetch language breakdown for a single repo."""
    url = f'https://api.github.com/repos/{username}/{repo_name}/languages'
    data, _ = api_get(url, token)
    return data or {}


def aggregate_languages(username, token=None):
    """Aggregate total bytes per language across all repos."""
    repos = fetch_all_repos(username, token)
    print(f'Found {len(repos)} public repos')

    lang_totals = defaultdict(int)
    for i, repo in enumerate(repos):
        name = repo['name']
        # Skip forks to focus on original work
        if repo.get('fork'):
            print(f'  [{i+1}/{len(repos)}] {name} (fork, skipping)')
            continue
        print(f'  [{i+1}/{len(repos)}] {name}...')
        langs = fetch_repo_languages(username, name, token)
        for lang, bytes_count in langs.items():
            lang_totals[lang] += bytes_count

    # Remove zero/empty entries
    lang_totals = {k: v for k, v in lang_totals.items() if v > 0}
    return lang_totals


def render_treemap(lang_totals, output_path, username):
    """Render a donut chart PNG from language byte totals."""
    if not lang_totals:
        print('No language data to render!')
        # Create a placeholder image
        fig, ax = plt.subplots(figsize=(10, 6), facecolor='none')
        ax.text(0.5, 0.5, 'No language data available',
                ha='center', va='center', color=TEXT_COLOR, fontsize=16)
        ax.axis('off')
        fig.savefig(output_path, facecolor='none', transparent=True, dpi=150, bbox_inches='tight')
        plt.close(fig)
        return

    # Sort by bytes descending
    sorted_langs = sorted(lang_totals.items(), key=lambda x: x[1], reverse=True)

    # Show top 12 languages, group rest as "Other"
    TOP_N = 12
    if len(sorted_langs) > TOP_N:
        top = sorted_langs[:TOP_N]
        other_bytes = sum(v for _, v in sorted_langs[TOP_N:])
        top.append(('Other', other_bytes))
        sorted_langs = top

    labels = [name for name, _ in sorted_langs]
    sizes = [max(v, 1) for _, v in sorted_langs]
    total = sum(sizes)
    colors = [LINGUIST_COLORS.get(name, DEFAULT_COLOR) for name in labels]

    # Only annotate slices large enough to read
    def autopct(pct):
        return f'{pct:.1f}%' if pct >= 4 else ''

    # Create figure
    fig, ax = plt.subplots(figsize=(14, 9), facecolor='none')
    ax.set_facecolor('none')

    # Plot donut chart
    wedges, _texts, autotexts = ax.pie(
        sizes,
        colors=colors,
        startangle=90,
        counterclock=False,
        autopct=autopct,
        pctdistance=0.78,
        wedgeprops={'width': 0.42, 'edgecolor': BG_COLOR, 'linewidth': 2},
        textprops={'color': TEXT_COLOR, 'fontsize': 14, 'fontweight': 'bold',
                   'fontfamily': 'sans-serif'},
    )

    # Center label: total languages
    ax.text(0, 0.08, str(len(lang_totals)), ha='center', va='center',
            color=TITLE_COLOR, fontsize=44, fontweight='bold', fontfamily='sans-serif')
    ax.text(0, -0.16, 'languages', ha='center', va='center',
            color=SUBTITLE_COLOR, fontsize=16, fontfamily='sans-serif')

    ax.set_aspect('equal')

    # Build legend
    legend_patches = []
    for name, size in zip(labels, sizes):
        pct = size / total * 100
        color = LINGUIST_COLORS.get(name, DEFAULT_COLOR)
        legend_patches.append(mpatches.Patch(color=color, label=f'{name}  {pct:.1f}%'))

    ax.legend(
        handles=legend_patches,
        loc='center left',
        bbox_to_anchor=(1.01, 0.5),
        frameon=False,
        labelcolor=TEXT_COLOR,
        fontsize=12,
    )

    plt.subplots_adjust(left=0.02, right=0.68, top=0.96, bottom=0.04)
    fig.savefig(output_path, facecolor='none', transparent=True, dpi=150, bbox_inches='tight', pad_inches=0.3)
    plt.close(fig)
    print(f'Donut chart saved: {output_path}')


def main():
    parser = argparse.ArgumentParser(description='Generate language treemap for a GitHub user')
    parser.add_argument('--user', default='ChitkulLakshya', help='GitHub username')
    parser.add_argument('--output', default=None, help='Output PNG path')
    parser.add_argument('--token', default=None, help='GitHub token (for higher rate limits)')
    args = parser.parse_args()

    token = args.token or os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')

    if args.output:
        output_path = args.output
    else:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        output_path = os.path.join(project_root, 'assets', 'language-treemap.png')

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    print(f'Generating language treemap for @{args.user}...')
    lang_totals = aggregate_languages(args.user, token)

    if lang_totals:
        print(f'\nLanguage totals (bytes):')
        for lang, bytes_count in sorted(lang_totals.items(), key=lambda x: x[1], reverse=True):
            print(f'  {lang:<25} {bytes_count:>12,}')

    render_treemap(lang_totals, output_path, args.user)
    print('Done!')


if __name__ == '__main__':
    main()
