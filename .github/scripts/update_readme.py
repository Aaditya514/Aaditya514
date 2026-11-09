#!/usr/bin/env python3
"""Refresh the auto-generated activity blocks in the profile README.

Rewrites everything between these marker pairs:
  <!--START_SECTION:repos-->   ... <!--END_SECTION:repos-->
  <!--START_SECTION:commits--> ... <!--END_SECTION:commits-->

Uses only the standard library. GITHUB_TOKEN is optional (raises the rate limit).
"""
import json
import os
import re
import sys
import urllib.request

USER = os.environ.get("GH_USER", "Aaditya514")
TOKEN = os.environ.get("GITHUB_TOKEN")
README = sys.argv[1] if len(sys.argv) > 1 else "README.md"
MAX_REPOS = 5
MAX_COMMITS = 6


def api(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-readme-updater"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(f"https://api.github.com{path}", headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def clip(text, n):
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def cell(text):
    return text.replace("|", "\\|")


def pick_repos():
    repos = api(f"/users/{USER}/repos?sort=pushed&direction=desc&per_page=30&type=owner")
    return [
        r for r in repos
        if not r["fork"] and not r["archived"] and r["name"].lower() != USER.lower()
    ][:MAX_REPOS]


def repos_block(picked):
    if not picked:
        return "_No public repositories yet._"
    has_desc = any(r["description"] for r in picked)
    head = ["Repository"] + (["About"] if has_desc else []) + ["Language", "⭐", "Last push"]
    rows = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in picked:
        cols = [f"[**{r['name']}**]({r['html_url']})"]
        if has_desc:
            cols.append(cell(clip(r["description"], 80)) or "—")
        cols += [r["language"] or "—", str(r["stargazers_count"]), r["pushed_at"][:10]]
        rows.append("| " + " | ".join(cols) + " |")
    return "\n".join(rows)


def commits_block(picked):
    """Latest commits straight from each recently pushed repo (the public events
    feed no longer carries commit messages, so it can't be used for this)."""
    found = []
    for r in picked:
        try:
            commits = api(f"/repos/{USER}/{r['name']}/commits?per_page=3&author={USER}")
        except Exception:
            continue
        for c in commits:
            full = c["commit"]["message"]
            msg = clip(full.splitlines()[0], 72)
            if not msg or "[skip ci]" in full:
                continue
            found.append((c["commit"]["author"]["date"], r["name"], r["html_url"], msg))
    found.sort(reverse=True)
    lines = [f"- `{d[:10]}` [{n}]({u}) — {m}" for d, n, u, m in found[:MAX_COMMITS]]
    return "\n".join(lines) if lines else "_No recent public commits._"


def replace(text, name, content):
    pattern = re.compile(
        rf"(<!--START_SECTION:{name}-->)(.*?)(<!--END_SECTION:{name}-->)", re.DOTALL
    )
    if not pattern.search(text):
        sys.exit(f"Markers for '{name}' not found in {README}")
    return pattern.sub(lambda m: f"{m.group(1)}\n{content}\n{m.group(3)}", text, count=1)


def main():
    with open(README, encoding="utf-8") as f:
        text = f.read()
    picked = pick_repos()
    text = replace(text, "repos", repos_block(picked))
    text = replace(text, "commits", commits_block(picked))
    with open(README, "w", encoding="utf-8") as f:
        f.write(text)
    print("README activity sections refreshed")


if __name__ == "__main__":
    main()
