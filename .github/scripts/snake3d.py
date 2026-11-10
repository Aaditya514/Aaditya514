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
TAIL_COL, HEAD_COL = (126, 139, 240), (244, 114, 182)   # violet tail -> pink head
FONT = "'JetBrains Mono','Fira Code','SF Mono',Menlo,Consolas,'DejaVu Sans Mono',monospace"
W, H = 1000, 380
SPEED = 210.0         # head speed, px per second
BODY_LEN = 250.0      # snake length in px
MAX_W = 13.5          # body width just behind the head
MIN_W = 3.6           # width at the tail tip
WAVE_LEN = 52.0       # slither wavelength, px
WAVE_AMP = 4.6        # slither amplitude, px
HOLD = 2.4            # pause at the end of the loop

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


def resample(points, step):
    out = [points[0]]
    carry = 0.0
    for a, b in zip(points, points[1:]):
        seg = math.hypot(b[0] - a[0], b[1] - a[1])
        if seg == 0:
            continue
        d = step - carry
        while d <= seg:
            t = d / seg
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
            d += step
        carry = seg - (d - step)
    out.append(points[-1])
    return out


def smooth(p, radius, passes=2):
    n = len(p)
    for _ in range(passes):
        q = []
        for k in range(n):
            lo, hi = max(0, k - radius), min(n - 1, k + radius)
            m = hi - lo + 1
            q.append((sum(x for x, _ in p[lo:hi + 1]) / m, sum(y for _, y in p[lo:hi + 1]) / m))
        q[0], q[-1] = p[0], p[-1]
        p = q
    return p


def slither(base, step):
    """Smooth the cell-to-cell track, then add a travelling S-wave across it."""
    dense = smooth(resample(base, step), 4, 3)
    out, s = [], 0.0
    for k, (x, y) in enumerate(dense):
        a, b = dense[max(0, k - 3)], dense[min(len(dense) - 1, k + 3)]
        tx, ty = b[0] - a[0], b[1] - a[1]
        n = math.hypot(tx, ty) or 1.0
        off = WAVE_AMP * math.sin(2 * math.pi * s / WAVE_LEN)
        out.append((x - ty / n * off, y + tx / n * off))
        if k:
            s += step
    return out


def mix(t):
    return "#%02x%02x%02x" % tuple(int(TAIL_COL[c] + (HEAD_COL[c] - TAIL_COL[c]) * t) for c in range(3))


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
    SIT = 5.5   # the body rides this many px above the bar tops
    base = [(x, y - SIT) for x, y in path_pts]
    track = slither(base, 3.0)
    cum = [0.0]
    for u, v in zip(track, track[1:]):
        cum.append(cum[-1] + math.hypot(v[0] - u[0], v[1] - u[1]))
    Ltot = cum[-1]
    Tm = (Ltot + BODY_LEN) / SPEED
    T = Tm + HOLD
    th = Ltot / SPEED                      # head reaches the last cell
    d_path = "M" + " L".join(f"{f2(x)} {f2(y)}" for x, y in track)

    # when the head passes each cell
    eat_t, idx = {}, 0
    for cell, (bx, by) in zip(order, base):
        best, bd = idx, 1e18
        for k in range(idx, min(len(track), idx + 140)):
            d = (track[k][0] - bx) ** 2 + (track[k][1] - by) ** 2
            if d < bd:
                best, bd = k, d
        idx = best
        eat_t[cell] = cum[best] / SPEED

    # cells, back to front
    draw = []
    for (i, j), (cnt, lvl) in sorted(cells.items(), key=lambda kv: (centre(*kv[0])[1], centre(*kv[0])[0])):
        cx, cy = centre(i, j)
        g = [cube(cx, cy, 1.5, PALETTE[0], 0.44)]
        if lvl > 0:
            t = eat_t[(i, j)]
            kt = f"0;{t / T:.4f};{(t + .16) / T:.4f};{(T - .7) / T:.4f};1"
            g.append(
                f'<g><animate attributeName="opacity" dur="{T:.2f}s" repeatCount="indefinite" keyTimes="{kt}" values="1;1;0;0;1"/>'
                f'<animateTransform attributeName="transform" type="translate" dur="{T:.2f}s" repeatCount="indefinite" '
                f'keyTimes="0;{t / T:.4f};{(t + .16) / T:.4f};1" values="0 0;0 0;0 -9;0 -9"/>'
                f'{cube(cx, cy, HEIGHTS[lvl], PALETTE[lvl])}</g>'
            )
        draw.append("".join(g))

    # body: stacked head-anchored strokes (long+thin ... short+thick) = tapered tube
    N = 30
    far = int(Ltot * 10)
    layers = []
    for k in range(N):
        f = k / (N - 1)
        ln = BODY_LEN * (1 - 0.9 * f ** 0.8)
        w = MIN_W + (MAX_W - MIN_W) * (f ** 0.7)
        col = mix(f)
        off0, off1 = ln, ln - (Ltot + BODY_LEN)
        kt = f"0;{Tm / T:.4f};1"
        dash = (f'stroke-dasharray="{ln:.0f} {far}" stroke-linecap="round" stroke-linejoin="round" fill="none"')
        anim = (f'<animate attributeName="stroke-dashoffset" dur="{T:.2f}s" repeatCount="indefinite" '
                f'keyTimes="{kt}" values="{off0:.1f};{off1:.1f};{off1:.1f}"/>')
        layers.append(f'<use href="#sp" stroke="{col}" stroke-width="{w:.1f}" {dash}>{anim}</use>')
        layers.append(
            f'<use href="#sp" stroke="#ffffff" stroke-opacity=".30" stroke-width="{w * .30:.1f}" '
            f'transform="translate(0 {-w * .22:.1f})" {dash}>{anim}</use>'
        )
    shadow = (
        f'<use href="#sp" stroke="#000" stroke-opacity=".38" stroke-width="{MAX_W:.1f}" transform="translate(3 9)" filter="url(#soft)" '
        f'stroke-dasharray="{BODY_LEN:.0f} {far}" stroke-linecap="round" stroke-linejoin="round" fill="none">'
        f'<animate attributeName="stroke-dashoffset" dur="{T:.2f}s" repeatCount="indefinite" keyTimes="0;{Tm / T:.4f};1" '
        f'values="{BODY_LEN:.1f};{BODY_LEN - Ltot - BODY_LEN:.1f};{BODY_LEN - Ltot - BODY_LEN:.1f}"/></use>'
    )
    head = (
        f'<g><animateMotion dur="{T:.2f}s" repeatCount="indefinite" rotate="auto" calcMode="linear" '
        f'keyPoints="0;1;1" keyTimes="0;{th / T:.4f};1" path="{d_path}"/>'
        f'<path d="M14 0 H22 M22 0 L26 -3 M22 0 L26 3" stroke="#FF4D6D" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" fill="none">'
        f'<animate attributeName="opacity" values="1;1;0;0;1" keyTimes="0;.3;.4;.7;1" dur="0.9s" repeatCount="indefinite"/></path>'
        f'<ellipse cx="3" cy="0" rx="12" ry="8.6" fill="url(#hd)" stroke="#8a2a63" stroke-width="1"/>'
        f'<ellipse cx="2" cy="-2.8" rx="7.5" ry="2.6" fill="#fff" fill-opacity=".28"/>'
        f'<circle cx="6" cy="-4.2" r="2.6" fill="#fff"/><circle cx="6" cy="4.2" r="2.6" fill="#fff"/>'
        f'<circle cx="7" cy="-4.2" r="1.35" fill="#0a0e17"/><circle cx="7" cy="4.2" r="1.35" fill="#0a0e17"/>'
        f'<circle cx="13" cy="-2" r=".9" fill="#8a2a63"/><circle cx="13" cy="2" r=".9" fill="#8a2a63"/></g>'
    )
    fade = f"0;{.12 / T:.4f};{(Tm - .15) / T:.4f};{Tm / T:.4f};1"
    snake = (
        f'<g><animate attributeName="opacity" dur="{T:.2f}s" repeatCount="indefinite" keyTimes="{fade}" values="0;1;1;0;0"/>'
        f'{shadow}<g filter="url(#glow)">{"".join(layers)}{head}</g></g>'
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
    defs = f"""<path id="sp" d="{d_path}" fill="none"/>
<radialGradient id="hd" cx=".4" cy=".35" r=".8"><stop offset="0" stop-color="#FF8FC7"/><stop offset="1" stop-color="#E2549F"/></radialGradient>
<filter id="soft" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="2.4"/></filter>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0a0e17"/><stop offset="1" stop-color="#120d1f"/></linearGradient>
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
