#!/usr/bin/env python3
"""Fetch live GitHub stats for Kuzensky and render the neofetch-style whoami card."""

import os
import re
import sys
from pathlib import Path
from string import Template

import requests

USERNAME = "Kuzensky"
API = "https://api.github.com"
GRAPHQL_API = "https://api.github.com/graphql"
VIEWS_BADGE_URL = f"https://komarev.com/ghpvc/?username={USERNAME}"

ROLE = "Full-Stack Dev (mostly caffeine)"

ACCENT = "#3fb950"  # github green, matches the prompt color used elsewhere in the profile

TEMPLATE_PATH = Path(__file__).parent / "whoami_card_template.svg"


def gh_headers(token: str, accept: str = "application/vnd.github+json") -> dict:
    return {"Authorization": f"Bearer {token}", "Accept": accept}


def fetch_profile(token: str) -> dict:
    resp = requests.get(f"{API}/users/{USERNAME}", headers=gh_headers(token), timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_repos(token: str) -> list:
    repos = []
    page = 1
    while True:
        resp = requests.get(
            f"{API}/users/{USERNAME}/repos",
            headers=gh_headers(token),
            params={"per_page": 100, "page": page, "type": "owner"},
            timeout=30,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        repos.extend(batch)
        page += 1
    return repos


def fetch_stars_and_top_lang(token: str, repos: list) -> tuple:
    total_stars = 0
    lang_bytes: dict = {}
    for repo in repos:
        total_stars += repo.get("stargazers_count", 0)
        if repo.get("fork"):
            continue
        resp = requests.get(
            f"{API}/repos/{USERNAME}/{repo['name']}/languages",
            headers=gh_headers(token),
            timeout=30,
        )
        resp.raise_for_status()
        for lang, count in resp.json().items():
            lang_bytes[lang] = lang_bytes.get(lang, 0) + count
    top_lang = max(lang_bytes, key=lang_bytes.get) if lang_bytes else "n/a"
    return total_stars, top_lang


def fetch_contributions(token: str) -> int:
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
          }
        }
      }
    }
    """
    resp = requests.post(
        GRAPHQL_API,
        headers=gh_headers(token, accept="application/json"),
        json={"query": query, "variables": {"login": USERNAME}},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]


def fetch_views() -> str:
    resp = requests.get(VIEWS_BADGE_URL, timeout=30)
    resp.raise_for_status()
    counts = re.findall(r">([\d,]+)<", resp.text)
    return counts[-1] if counts else "n/a"


def render(template: Template, accent: str, stats: dict) -> str:
    return template.substitute(
        ACCENT=accent,
        NAME=stats["name"],
        ROLE=stats["role"],
        STARS=stats["stars"],
        REPOS=stats["repos"],
        FOLLOWERS=stats["followers"],
        TOP_LANG=stats["top_lang"],
        ACTIVITY=stats["activity"],
        VIEWS=stats["views"],
    )


def main() -> None:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN is required", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("dist")
    out_dir.mkdir(parents=True, exist_ok=True)

    profile = fetch_profile(token)
    repos = fetch_repos(token)
    stars, top_lang = fetch_stars_and_top_lang(token, repos)
    activity = fetch_contributions(token)
    views = fetch_views()

    stats = {
        "name": "Christian Nayre",
        "role": ROLE,
        "stars": stars,
        "repos": profile.get("public_repos", len(repos)),
        "followers": profile.get("followers", 0),
        "top_lang": top_lang,
        "activity": f"{activity} contributions",
        "views": views,
    }

    template = Template(TEMPLATE_PATH.read_text())

    (out_dir / "whoami.svg").write_text(render(template, ACCENT, stats))

    print(f"Wrote whoami.svg to {out_dir}")


if __name__ == "__main__":
    main()
