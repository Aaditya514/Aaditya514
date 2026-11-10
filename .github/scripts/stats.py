#!/usr/bin/env python3
"""Generate a self-hosted, animated GitHub stats card (assets/stats.svg).

Replaces third-party stat widgets (which hit GitHub rate limits and go blank).
Uses the GitHub GraphQL API with GITHUB_TOKEN. Standard library only.

  stats.py [--out assets/stats.svg]        real data
  stats.py --mock [--out path]             sample data for local testing
"""
import argparse
import datetime as dt
import html
import json
import os
import random
import urllib.request

USER = os.environ.get("GH_USER", "Aaditya514")
TOKEN = os.environ.get("GITHUB_TOKEN")

CYAN, VIO, PINK, GRN, AMB = "#61DAFB", "#A78BFA", "#F472B6", "#34D399", "#FBBF24"
TXT, MUT, PANEL = "#E6EDF3", "#8B949E", "#0f1623"
FONT = "'JetBrains Mono','Fira Code','SF Mono',Menlo,Consolas,'DejaVu Sans Mono',monospace"
W, H = 1000, 300


def esc(s):
    return html.escape(str(s), quote=True)


def fetch():
    q = """query($login:String!){user(login:$login){
      followers{totalCount}
      repositories(first:100, ownerAffiliations:OWNER, isFork:false, privacy:PUBLIC){
        totalCount
        nodes{stargazerCount languages(first:8, orderBy:{field:SIZE, direction:DESC}){edges{size node{name color}}}}}
      contributionsCollection{
        totalCommitContributions totalPullRequestContributions totalIssueContributions
        totalPullRequestReviewContributions
        contributionCalendar{totalContributions weeks{contributionDays{contributionCount date}}}}}}"""
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": q, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json", "User-Agent": "profile-stats"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data and not data.get("data"):
        raise SystemExit(f"GraphQL error: {data['errors']}")
    u = data["data"]["user"]
    cc = u["contributionsCollection"]
    days = [(d["date"], d["contributionCount"]) for w in cc["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    langs = {}
    for repo in u["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            n = e["node"]
            cur = langs.setdefault(n["name"], [0, n["color"] or "#8B949E"])
            cur[0] += e["size"]
    return {
        "days": days,
        "contributions": cc["contributionCalendar"]["totalContributions"],
        "commits": cc["totalCommitContributions"],
        "prs": cc["totalPullRequestContributions"],
        "issues": cc["totalIssueContributions"],
        "reviews": cc["totalPullRequestReviewContributions"],
        "stars": sum(r["stargazerCount"] for r in u["repositories"]["nodes"]),
        "repos": u["repositories"]["totalCount"],
        "followers": u["followers"]["totalCount"],
        "langs": langs,
    }


def mock():
    random.seed(3)
    today = dt.date.today()
    days = []
    for k in range(365, -1, -1):
        d = today - dt.timedelta(days=k)
        days.append((d.isoformat(), 0 if random.random() < 0.5 else random.randint(1, 9)))
    days[-1] = (days[-1][0], 3)
    days[-2] = (days[-2][0], 2)
    return {
        "days": days, "contributions": sum(c for _, c in days), "commits": 412, "prs": 38, "issues": 9, "reviews": 14,
        "stars": 27, "repos": 18, "followers": 12,
        "langs": {"Java": [520000, "#b07219"], "TypeScript": [410000, "#3178c6"], "JavaScript": [190000, "#f1e05a"],
                  "HTML": [90000, "#e34c26"], "CSS": [60000, "#563d7c"], "Python": [30000, "#3572A5"]},
    }


def streaks(days):
    days = sorted(days)
    longest = run = 0
    for _, c in days:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)
    # current streak: today may still be empty, so allow it to be skipped
    cur, i = 0, len(days) - 1
    if i >= 0 and days[i][1] == 0:
        i -= 1
    while i >= 0 and days[i][1] > 0:
        cur += 1
        i -= 1
    return cur, longest, sum(1 for _, c in days if c > 0)


def build(d):
    cur, longest, active = streaks(d["days"])
    out = []

    def panel(x, w, title, col):
        out.append(
            f'<rect x="{x}" y="14" width="{w}" height="{H - 28}" rx="16" fill="{PANEL}" fill-opacity=".85" stroke="{col}" stroke-opacity=".35" stroke-width="1.5"/>'
            f'<text x="{x + 22}" y="46" font-size="12" letter-spacing="2.5" fill="{col}">{esc(title)}</text>'
        )

    # ---- panel A: activity
    A_x, A_w = 14, 318
    panel(A_x, A_w, "ACTIVITY · LAST YEAR", CYAN)
    rows = [("Contributions", d["contributions"], CYAN), ("Commits", d["commits"], VIO), ("Pull requests", d["prs"], PINK),
            ("Issues", d["issues"], AMB), ("Stars earned", d["stars"], GRN), ("Public repos", d["repos"], CYAN)]
    for k, (lab, val, col) in enumerate(rows):
        y = 84 + k * 34
        out.append(
            f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" begin="{.15 + k * .1:.2f}s" dur=".4s" fill="freeze"/>'
            f'<animateTransform attributeName="transform" type="translate" from="-10 0" to="0 0" begin="{.15 + k * .1:.2f}s" dur=".4s" fill="freeze"/>'
            f'<circle cx="{A_x + 28}" cy="{y - 5}" r="4.5" fill="{col}"/>'
            f'<text x="{A_x + 44}" y="{y}" font-size="14" fill="{MUT}">{esc(lab)}</text>'
            f'<text x="{A_x + A_w - 24}" y="{y + 1}" font-size="20" font-weight="800" fill="{TXT}" text-anchor="end">{esc(f"{val:,}")}</text></g>'
        )

    # ---- panel B: streak ring
    B_x, B_w = 346, 308
    panel(B_x, B_w, "STREAK", PINK)
    cx, cy, r = B_x + B_w / 2, 138, 58
    circ = 2 * 3.14159265 * r
    frac = min(1.0, cur / longest) if longest else 0.0
    target = circ * (1 - frac)
    out.append(
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#1a2230" stroke-width="12"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="url(#ring)" stroke-width="12" stroke-linecap="round" '
        f'stroke-dasharray="{circ:.1f}" stroke-dashoffset="{circ:.1f}" transform="rotate(-90 {cx} {cy})" filter="url(#glow)">'
        f'<animate attributeName="stroke-dashoffset" from="{circ:.1f}" to="{target:.1f}" begin=".3s" dur="1.4s" fill="freeze" calcMode="spline" keySplines=".2 .8 .2 1" keyTimes="0;1"/></circle>'
        f'<text x="{cx}" y="{cy + 10}" font-size="34" font-weight="800" fill="{TXT}" text-anchor="middle">{cur}</text>'
        f'<text x="{cx}" y="{cy + 28}" font-size="11" letter-spacing="2" fill="{MUT}" text-anchor="middle">DAY STREAK</text>'
        f'<g text-anchor="middle"><text x="{B_x + 84}" y="244" font-size="22" font-weight="800" fill="{TXT}">{longest}</text>'
        f'<text x="{B_x + 84}" y="262" font-size="11" letter-spacing="1.5" fill="{MUT}">LONGEST</text>'
        f'<text x="{B_x + B_w - 84}" y="244" font-size="22" font-weight="800" fill="{TXT}">{active}</text>'
        f'<text x="{B_x + B_w - 84}" y="262" font-size="11" letter-spacing="1.5" fill="{MUT}">ACTIVE DAYS</text></g>'
    )

    # ---- panel C: languages
    C_x, C_w = 668, 318
    panel(C_x, C_w, "TOP LANGUAGES", VIO)
    langs = sorted(d["langs"].items(), key=lambda kv: -kv[1][0])
    total = sum(v[0] for _, v in langs) or 1
    top = langs[:5]
    barw = C_w - 48
    for k, (name, (size, color)) in enumerate(top):
        y = 80 + k * 42
        pct = size / total * 100
        w = max(4.0, barw * size / total)
        begin = .3 + k * .12
        out.append(
            f'<text x="{C_x + 24}" y="{y}" font-size="14" fill="{TXT}">{esc(name)}</text>'
            f'<text x="{C_x + C_w - 24}" y="{y}" font-size="13" fill="{MUT}" text-anchor="end">{pct:.1f}%</text>'
            f'<rect x="{C_x + 24}" y="{y + 9}" width="{barw}" height="9" rx="4.5" fill="#1a2230"/>'
            f'<rect x="{C_x + 24}" y="{y + 9}" width="0" height="9" rx="4.5" fill="{esc(color)}">'
            f'<animate attributeName="width" from="0" to="{w:.1f}" begin="{begin:.2f}s" dur=".9s" fill="freeze" calcMode="spline" keySplines=".2 .8 .2 1" keyTimes="0;1"/></rect>'
        )
    if not top:
        out.append(f'<text x="{C_x + 24}" y="90" font-size="14" fill="{MUT}">No language data yet</text>')

    defs = f"""<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0a0e17"/><stop offset="1" stop-color="#120d1f"/></linearGradient>
<pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1" fill="{CYAN}" fill-opacity=".1"/></pattern>
<linearGradient id="ring" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{PINK}"/><stop offset="1" stop-color="{VIO}"/></linearGradient>
<filter id="glow" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>"""
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{FONT}">\n'
        f'<defs>{defs}</defs>\n<rect width="{W}" height="{H}" rx="18" fill="url(#bg)"/><rect width="{W}" height="{H}" rx="18" fill="url(#dots)"/>\n'
        + "\n".join(out)
        + f'\n<text x="{W - 20}" y="{H - 5}" font-size="10" fill="{MUT}" fill-opacity=".6" text-anchor="end">updated {stamp} UTC</text>\n</svg>\n'
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="assets/stats.svg")
    ap.add_argument("--mock", action="store_true")
    a = ap.parse_args()
    data = mock() if a.mock else fetch()
    svg = build(data)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(svg)
    cur, longest, active = streaks(data["days"])
    print(f"wrote {a.out}: {len(svg) // 1024} KB | contributions {data['contributions']}, streak {cur}/{longest}, langs {len(data['langs'])}")


if __name__ == "__main__":
    main()
