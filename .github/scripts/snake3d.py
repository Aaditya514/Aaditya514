#!/usr/bin/env python3
"""Generate an isometric 3D "snake eats contributions" SVG.

Usage:
  snake3d.py [--out assets/snake-3d.svg]          # real data (needs GITHUB_TOKEN)
  snake3d.py --mock [--out path]                  # random data, for local testing

Standard library only. Animation is pure SVG/SMIL, so it plays when the file is
embedded with <img> on a GitHub profile.
"""
import argparse
import json
import math
import os
import random
import urllib.request

USER = os.environ.get("GH_USER", "Aaditya514")
TOKEN = os.environ.get("GITHUB_TOKEN")

# ---- projection: weeks run left->right and slightly "up" (away), days run down
IX, IY = 16.8, -3.4   # one week step (i)
JX, JY = 6.0, 9.0     # one weekday step (j)
HALF = 0.40           # footprint half-size as a fraction of a cell
HEIGHTS = [0, 8, 15, 23, 32]
PALETTE = ["#1a2230", "#0f5a78", "#1b97c0", "#61DAFB", "#C4A5FF"]
SNAKE = ["#F472B6", "#EC6FC4", "#D66FDB", "#BE6FF0", "#A78BFA", "#9380F5", "#7E8BF0"]
FONT = "'JetBrains Mono','Fira Code','SF Mono',Menlo,Consolas,'DejaVu Sans Mono',monospace"
W, H = 1000, 380
STEP = 0.048          # seconds per cell the head travels
LAG = 0.34            # seconds between snake segments
HOLD = 2.6            # pause at the end of the loop

LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}


def fetch():
    q = """query($login:String!){user(login:$login){contributionsCollection{contributionCalendar{
      totalContributions weeks{contributionDays{contributionCount contributionLevel weekday date}}}}}}"""
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": q, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json", "User-Agent": "snake3d"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    cells = {}
    for wi, w in enumerate(cal["weeks"]):
        for d in w["contributionDays"]:
            cells[(wi, d["weekday"])] = (d["contributionCount"], LEVELS[d["contributionLevel"]])
    return len(cal["weeks"]), cells, cal["totalContributions"]


def mock():
    random.seed(7)
    n = 53
    cells, total = {}, 0
    for i in range(n):
        for j in range(7):
            if i == n - 1 and j > 3:
                continue
            c = 0 if random.random() < 0.55 else random.choice([1, 2, 3, 5, 8, 14])
            lvl = 0 if c == 0 else 1 if c < 2 else 2 if c < 4 else 3 if c < 8 else 4
            cells[(i, j)] = (c, lvl)
            total += c
    return n, cells, total


def shade(hexcol, f):
    r, g, b = (int(hexcol[k:k + 2], 16) for k in (1, 3, 5))
    return "#%02x%02x%02x" % (min(255, int(r * f)), min(255, int(g * f)), min(255, int(b * f)))


def f2(v):
    s = f"{v:.1f}"
    return s[:-2] if s.endswith(".0") else s


def pts(*p):
    return " ".join(f"{f2(x)},{f2(y)}" for x, y in p)


def cube(cx, cy, h, color, half=HALF, extra=""):
    """Isometric box whose footprint centre is (cx, cy), extruded up by h."""
    ex, ey = IX * half, IY * half
    fx, fy = JX * half, JY * half
    A = (cx - ex - fx, cy - ey - fy)
    B = (cx + ex - fx, cy + ey - fy)
    C = (cx + ex + fx, cy + ey + fy)
    D = (cx - ex + fx, cy - ey + fy)
    up = lambda p: (p[0], p[1] - h)
    out = []
    if h > 0:
        out.append(f'<polygon points="{pts(up(A), up(D), D, A)}" fill="{shade(color, .62)}"{extra}/>')
        out.append(f'<polygon points="{pts(up(D), up(C), C, D)}" fill="{shade(color, .8)}"{extra}/>')
    out.append(f'<polygon points="{pts(up(A), up(B), up(C), up(D))}" fill="{color}"{extra}/>')
    return "".join(out)


def build(n_weeks, cells, total):
    ox = (W - (IX * (n_weeks - 1) + JX * 6)) / 2
    oy = 78 - IY * (n_weeks - 1)

    def centre(i, j):
        return ox + IX * i + JX * j, oy + IY * i + JY * j

    # snake path: down one week column, up the next
    order = []
    for i in range(n_weeks):
        js = [j for j in range(7) if (i, j) in cells]
        order += [(i, j) for j in (js if i % 2 == 0 else reversed(js))]

    top = lambda i, j: centre(i, j)[1] - HEIGHTS[cells[(i, j)][1]]
    path_pts = [(centre(i, j)[0], top(i, j)) for i, j in order]
    seglen = [0.0]
    for a, b in zip(path_pts, path_pts[1:]):
        seglen.append(seglen[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    Ltot = seglen[-1]

    K = len(SNAKE)
    M = len(order) * STEP
    E = M + (K - 1) * LAG
    T = E + HOLD
    d_path = "M" + " L".join(f"{f2(x)} {f2(y)}" for x, y in path_pts)
    eat_t = {c: seglen[k] / Ltot * M for k, c in enumerate(order)}

    # cells, back to front
    draw = []
    for (i, j), (cnt, lvl) in sorted(cells.items(), key=lambda kv: (centre(*kv[0])[1], centre(*kv[0])[0])):
        cx, cy = centre(i, j)
        g = [cube(cx, cy, 1.5, PALETTE[0], 0.44)]
        if lvl > 0:
            t = eat_t[(i, j)]
            kt = f"0;{t / T:.4f};{(t + .22) / T:.4f};{(T - .7) / T:.4f};1"
            g.append(
                f'<g><animate attributeName="opacity" dur="{T:.2f}s" repeatCount="indefinite" keyTimes="{kt}" values="1;1;0;0;1"/>'
                f'<animateTransform attributeName="transform" type="translate" dur="{T:.2f}s" repeatCount="indefinite" '
                f'keyTimes="0;{t / T:.4f};{(t + .22) / T:.4f};1" values="0 0;0 0;0 -9;0 -9"/>'
                f'{cube(cx, cy, HEIGHTS[lvl], PALETTE[lvl])}</g>'
            )
        draw.append("".join(g))

    # snake segments (head first so the head is drawn last = on top)
    segs = []
    for k in range(K - 1, -1, -1):
        a, b = k * LAG / T, (M + k * LAG) / T
        half = 0.50 if k == 0 else 0.44
        hh = 9 if k == 0 else 7
        segs.append(
            f'<g><animateMotion dur="{T:.2f}s" repeatCount="indefinite" calcMode="linear" '
            f'keyPoints="0;0;1;1" keyTimes="0;{a:.4f};{b:.4f};1" path="{d_path}"/>'
            f'{cube(0, 0, hh, SNAKE[k], half)}'
            + (f'<circle cx="{f2(IX * .42)}" cy="{f2(-hh - 1.5)}" r="1.6" fill="#0a0e17"/><circle cx="{f2(IX * .42 - 4.2)}" cy="{f2(-hh - 0.3)}" r="1.6" fill="#0a0e17"/>' if k == 0 else "")
            + "</g>"
        )
    fade = f"0;{.4 / T:.4f};{E / T:.4f};{(E + .6) / T:.4f};1"
    snake = (
        f'<g filter="url(#glow)"><animate attributeName="opacity" dur="{T:.2f}s" repeatCount="indefinite" '
        f'keyTimes="{fade}" values="0;1;1;0;0"/>{"".join(segs)}</g>'
    )

    legend_x = W - 250
    legend = "".join(
        f'<rect x="{legend_x + 48 + 20 * k}" y="{H - 38}" width="14" height="14" rx="3" fill="{PALETTE[k]}"/>' for k in range(5)
    )
    body = f"""
<rect width="{W}" height="{H}" rx="18" fill="url(#bg)"/>
<rect width="{W}" height="{H}" rx="18" fill="url(#dots)"/>
<ellipse cx="{W / 2}" cy="{H * .64}" rx="450" ry="105" fill="#61DAFB" opacity=".05"/>
<text x="30" y="40" font-size="14" fill="#8B949E">// snake.exe --3d</text>
<circle cx="206" cy="36" r="4" fill="#34D399"><animate attributeName="opacity" values="1;.25;1" dur="1.3s" repeatCount="indefinite"/></circle>
{"".join(draw)}
{snake}
<text x="30" y="{H - 26}" font-size="14" fill="#E6EDF3">{total}<tspan fill="#8B949E"> contributions in the last year</tspan></text>
<text x="{legend_x}" y="{H - 26}" font-size="12" fill="#8B949E">Less</text>{legend}
<text x="{legend_x + 154}" y="{H - 26}" font-size="12" fill="#8B949E">More</text>
"""
    defs = """<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0a0e17"/><stop offset="1" stop-color="#120d1f"/></linearGradient>
<pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1" fill="#61DAFB" fill-opacity=".12"/></pattern>
<filter id="glow" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="2.2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>"""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{FONT}">\n'
        f"<defs>{defs}</defs>{body}</svg>\n"
    ), T


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="assets/snake-3d.svg")
    ap.add_argument("--mock", action="store_true")
    a = ap.parse_args()
    n, cells, total = mock() if a.mock else fetch()
    svg, T = build(n, cells, total)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"wrote {a.out}: {len(svg) // 1024} KB, {total} contributions, loop {T:.1f}s")


if __name__ == "__main__":
    main()
