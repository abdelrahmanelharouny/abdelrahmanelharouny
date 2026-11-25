#!/usr/bin/env python3
"""Build a compact, self-hosted SVG dashboard from GitHub's public API."""

from __future__ import annotations

import argparse
import html
import json
import os
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

USERNAME = os.environ.get("GITHUB_USERNAME", "abdelrahmanelharouny")
API_ROOT = "https://api.github.com"
PROFILE_REPOSITORY = f"{USERNAME}/{USERNAME}"

PALETTE = {
    "Python": "#D7F36A",
    "TypeScript": "#79C9D2",
    "JavaScript": "#B9D9A0",
    "C++": "#E4BD75",
    "C": "#9CB8D0",
    "Jupyter Notebook": "#D6A77D",
    "HTML": "#D99A82",
    "CSS": "#C8A5D8",
    "Java": "#E4C58A",
    "Go": "#86C6CA",
    "Rust": "#D1A58F",
    "Shell": "#9FC69B",
    "Kotlin": "#B8A8D9",
    "Dart": "#83B9D0",
    "PHP": "#A9A9D5",
    "Ruby": "#D88F8F",
}
FALLBACK_COLORS = ["#A9C1AD", "#83B6AD", "#C9C58C", "#A2B5C9", "#C1A5B7"]


def api_json(url: str, token: str) -> object:
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "ael-profile-telemetry",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    for attempt in range(4):
        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")[:240]
            if error.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(
                f"GitHub API returned HTTP {error.code} for {url}: {details}"
            ) from error
        except (TimeoutError, URLError) as error:
            if attempt < 3:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"GitHub API request failed for {url}: {error}") from error
    raise RuntimeError(f"GitHub API request failed after retries: {url}")


def fetch_repositories(token: str) -> list[dict]:
    repositories: list[dict] = []
    page = 1
    while True:
        url = (
            f"{API_ROOT}/users/{USERNAME}/repos"
            f"?type=owner&sort=updated&per_page=100&page={page}"
        )
        batch = api_json(url, token)
        if not isinstance(batch, list):
            raise RuntimeError("Unexpected repository response from GitHub API.")
        repositories.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return repositories


def collect_language_bytes(repositories: list[dict], token: str) -> Counter:
    totals: Counter = Counter()
    eligible = [
        repo for repo in repositories
        if not repo.get("fork")
        and not repo.get("archived")
        and repo.get("full_name", "").lower() != PROFILE_REPOSITORY.lower()
        and repo.get("size", 0) > 0
    ]
    for repository in eligible:
        languages_url = repository.get("languages_url")
        if not languages_url:
            continue
        language_data = api_json(languages_url, token)
        if isinstance(language_data, dict):
            for language, byte_count in language_data.items():
                if isinstance(byte_count, int) and byte_count > 0:
                    totals[language] += byte_count
    return totals


def format_number(value: int) -> str:
    return f"{value:,}"


def build_svg(profile: dict, repositories: list[dict], languages: Counter) -> str:
    followers = int(profile.get("followers", 0))
    public_repositories = int(profile.get("public_repos", len(repositories)))
    stars = sum(int(repo.get("stargazers_count", 0)) for repo in repositories)
    forks = sum(int(repo.get("forks_count", 0)) for repo in repositories)

    metrics = [
        ("FOLLOWERS", followers, "People following this account"),
        ("PUBLIC REPOSITORIES", public_repositories, "Repositories visible on GitHub"),
        ("STARS EARNED", stars, "Stars across owned public repositories"),
        ("FORKS", forks, "Forks across owned public repositories"),
    ]

    total_bytes = sum(languages.values())
    top_languages = languages.most_common(6) if total_bytes else []
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    metric_cards = []
    card_x = [52, 389, 726, 1063]
    for index, (label, value, description) in enumerate(metrics):
        x = card_x[index]
        metric_cards.append(f"""
  <g transform="translate({x} 104)">
    <rect width="315" height="116" rx="10" fill="#121D21" stroke="#34464A"/>
    <text x="22" y="31" fill="#8D9E98" font-family="monospace" font-size="10" font-weight="700" letter-spacing="1.5">{html.escape(label)}</text>
    <text x="22" y="79" fill="#F1F3EC" font-family="Arial,Helvetica,sans-serif" font-size="39" font-weight="800">{format_number(value)}</text>
    <text x="22" y="101" fill="#71827D" font-family="Arial,Helvetica,sans-serif" font-size="10">{html.escape(description)}</text>
  </g>""")

    bar_x, bar_y, bar_width, bar_height = 54, 298, 1332, 16
    segments = []
    legend = []
    current_x = bar_x
    for index, (language, byte_count) in enumerate(top_languages):
        share = byte_count / total_bytes
        segment_width = bar_width * share
        color = PALETTE.get(language, FALLBACK_COLORS[index % len(FALLBACK_COLORS)])
        segments.append(
            f'<rect x="{current_x:.2f}" y="{bar_y}" width="{segment_width:.2f}" '
            f'height="{bar_height}" fill="{color}"/>'
        )
        current_x += segment_width
        legend_x = bar_x + (index % 3) * 450
        legend_y = 353 + (index // 3) * 38
        percentage = share * 100
        legend.append(f"""
  <g transform="translate({legend_x} {legend_y})">
    <circle cx="5" cy="-4" r="5" fill="{color}"/>
    <text x="20" y="0" fill="#DCE4DE" font-family="Arial,Helvetica,sans-serif" font-size="13" font-weight="700">{html.escape(language)}</text>
    <text x="405" y="0" text-anchor="end" fill="#8D9E98" font-family="monospace" font-size="12">{percentage:.1f}%</text>
  </g>""")

    if not top_languages:
        segments.append(
            f'<rect x="{bar_x}" y="{bar_y}" width="{bar_width}" height="{bar_height}" fill="#34464A"/>'
        )
        legend.append(
            '<text x="54" y="355" fill="#8D9E98" font-family="Arial,Helvetica,sans-serif" font-size="13">Language data is not available yet.</text>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="430" viewBox="0 0 1440 430" role="img" aria-labelledby="title desc">
<title id="title">Abdelrahman El-Harouny — GitHub profile metrics</title>
<desc id="desc">Automatically refreshed public GitHub metrics and programming language distribution.</desc>
<defs>
  <linearGradient id="background" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#0A0F12"/><stop offset="1" stop-color="#111B1F"/></linearGradient>
  <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0"><stop stop-color="#D7F36A"/><stop offset="1" stop-color="#9BD7B2"/></linearGradient>
</defs>
<rect width="1440" height="430" rx="18" fill="url(#background)"/>
<path d="M52 77H1388" stroke="#34464A"/>
<circle cx="60" cy="43" r="5" fill="#D7F36A"/>
<text x="76" y="47" fill="#D7F36A" font-family="monospace" font-size="11" font-weight="700" letter-spacing="2">GITHUB / PUBLIC PROFILE SIGNAL</text>
<text x="1387" y="47" text-anchor="end" fill="#81918D" font-family="monospace" font-size="10" letter-spacing="1">LAST REFRESHED {html.escape(timestamp)}</text>
{''.join(metric_cards)}
<text x="54" y="259" fill="#F1F3EC" font-family="Arial,Helvetica,sans-serif" font-size="16" font-weight="700" letter-spacing=".7">LANGUAGE FOOTPRINT</text>
<text x="1386" y="259" text-anchor="end" fill="#81918D" font-family="monospace" font-size="10" letter-spacing="1">ORIGINAL, NON-ARCHIVED REPOSITORIES</text>
<rect x="{bar_x}" y="{bar_y}" width="{bar_width}" height="{bar_height}" rx="8" fill="#26363B"/>
<clipPath id="barClip"><rect x="{bar_x}" y="{bar_y}" width="{bar_width}" height="{bar_height}" rx="8"/></clipPath>
<g clip-path="url(#barClip)">{''.join(segments)}</g>
{''.join(legend)}
<path d="M52 402H1388" stroke="#34464A"/>
<text x="54" y="419" fill="#71827D" font-family="monospace" font-size="9" letter-spacing="1">SOURCE: GITHUB REST API · PUBLIC ACCOUNT &amp; REPOSITORY DATA</text>
<text x="1386" y="419" text-anchor="end" fill="#71827D" font-family="monospace" font-size="9" letter-spacing="1">AUTO-UPDATED EVERY 6 HOURS</text>
</svg>"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="dist/profile-metrics.svg")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required to read GitHub public profile data.")

    profile = api_json(f"{API_ROOT}/users/{USERNAME}", token)
    if not isinstance(profile, dict):
        raise RuntimeError("Unexpected profile response from GitHub API.")

    repositories = fetch_repositories(token)
    languages = collect_language_bytes(repositories, token)
    svg = build_svg(profile, repositories, languages)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(svg, encoding="utf-8")
    print(
        f"Generated {output} from {len(repositories)} public repositories; "
        f"tracked {len(languages)} language categories."
    )


if __name__ == "__main__":
    main()
