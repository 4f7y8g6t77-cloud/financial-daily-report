"""Inventario Silenzioso — rilievo assonometrico di una stanza. Genera SVG/HTML e PNG."""
import math, os, sys

FONTS = "/root/.claude/skills/canvas-design/canvas-fonts"
OUT = os.path.dirname(os.path.abspath(__file__))
W, H = 1500, 1860
S = 62.0
C = math.cos(math.radians(30))
CX, CY = 750.0, 640.0

PAPER = "#F2EFE8"
INK = "#24272C"
GREY = "#8E9196"
HAIR = "#C9C6BE"
COBALT = "#2B4C86"
BLACK = "#0E0F11"


def P(x, y, z=0.0):
    return (CX + (x - y) * C * S, CY + (x + y) * 0.5 * S - z * S)


def pts(*ps):
    return " ".join(f"{a:.2f},{b:.2f}" for a, b in ps)


out = []


def poly(ps, fill=PAPER, stroke=INK, sw=1.2, extra=""):
    out.append(f'<polygon points="{pts(*ps)}" fill="{fill}" stroke="{stroke}" '
               f'stroke-width="{sw}" stroke-linejoin="round" {extra}/>')


def line(a, b, stroke=INK, sw=1.0, extra=""):
    out.append(f'<line x1="{a[0]:.2f}" y1="{a[1]:.2f}" x2="{b[0]:.2f}" y2="{b[1]:.2f}" '
               f'stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round" {extra}/>')


def box(x0, x1, y0, y1, z0, z1, fill=PAPER, top=None, sw=1.2):
    """Visible faces for a viewer at +x,+y,+z."""
    top = top or fill
    poly([P(x1, y0, z0), P(x1, y1, z0), P(x1, y1, z1), P(x1, y0, z1)], fill, sw=sw)  # x=x1
    poly([P(x0, y1, z0), P(x1, y1, z0), P(x1, y1, z1), P(x0, y1, z1)], fill, sw=sw)  # y=y1
    poly([P(x0, y0, z1), P(x1, y0, z1), P(x1, y1, z1), P(x0, y1, z1)], top, sw=sw)   # top


# Affine transforms that map plane coords (u, v) -> screen, v pointing "down" on the plane.
def m_rightwall(y=0.0):   # plane y = const, u = x, v = -z
    ox, oy = P(0, y, 0)
    return f"matrix({C*S:.4f},{0.5*S:.4f},0,{S:.4f},{ox:.2f},{oy:.2f})"


def m_leftwall(x=0.0):    # plane x = const, u = -y, v = -z
    ox, oy = P(x, 0, 0)
    return f"matrix({C*S:.4f},{-0.5*S:.4f},0,{S:.4f},{ox:.2f},{oy:.2f})"


def m_floor(z=0.0):       # plane z = const, u = x, v = y
    ox, oy = P(0, 0, z)
    return f"matrix({C*S:.4f},{0.5*S:.4f},{-C*S:.4f},{0.5*S:.4f},{ox:.2f},{oy:.2f})"


def group(transform, inner):
    out.append(f'<g transform="{transform}">{inner}</g>')


ROOM, WALL = 10.0, 6.2

# ---------------------------------------------------------------- room shell
# floor grid (hairline), walls
poly([P(0, 0), P(ROOM, 0), P(ROOM, ROOM), P(0, ROOM)], fill=PAPER, stroke=INK, sw=1.6)
for i in range(1, 10):
    line(P(i, 0), P(i, ROOM), HAIR, 0.6)
    line(P(0, i), P(ROOM, i), HAIR, 0.6)
poly([P(0, 0, 0), P(ROOM, 0, 0), P(ROOM, 0, WALL), P(0, 0, WALL)], fill="#ECE8E0", stroke=INK, sw=1.6)
poly([P(0, 0, 0), P(0, ROOM, 0), P(0, ROOM, WALL), P(0, 0, WALL)], fill="#E6E2D9", stroke=INK, sw=1.6)
# wall hairlines (vertical modules)
for i in range(1, 10):
    line(P(i, 0, 0), P(i, 0, WALL), HAIR, 0.5)
    line(P(0, i, 0), P(0, i, WALL), HAIR, 0.5)
line(P(0, 0, 0), P(0, 0, WALL), INK, 1.6)

# ---------------------------------------------------------------- left wall: door (09) + blackboard (04)
# door opening
poly([P(0, 8.5, 0), P(0, 9.7, 0), P(0, 9.7, 4.4), P(0, 8.5, 4.4)], fill=PAPER, stroke=INK, sw=1.2)
line(P(0, 8.62, 0), P(0, 8.62, 4.3), GREY, 0.6)
line(P(0, 9.58, 0), P(0, 9.58, 4.3), GREY, 0.6)
line(P(0, 8.62, 4.3), P(0, 9.58, 4.3), GREY, 0.6)

# blackboard: three scenario bars summing to 100, swan blot outside frame
bb = []
bb.append('<rect x="-7.0" y="-5.3" width="4.6" height="2.9" fill="#F7F5F0" stroke="#24272C" stroke-width="0.035"/>')
bb.append('<rect x="-6.92" y="-5.22" width="4.44" height="2.74" fill="none" stroke="#8E9196" stroke-width="0.012"/>')
bars = [(0.50, 0.95), (0.30, 0.55), (0.20, 0.25)]  # share, opacity
yy = -4.85
for share, op in bars:
    w = 3.6 * share
    bb.append(f'<rect x="-6.6" y="{yy:.2f}" width="{w:.3f}" height="0.34" fill="#2B4C86" fill-opacity="{op}"/>')
    bb.append(f'<text x="{-6.6 + w + 0.1:.3f}" y="{yy + 0.26:.2f}" font-family="DM Mono" font-size="0.22" fill="#24272C">{int(share*100)}</text>')
    yy += 0.62
bb.append('<line x1="-6.6" y1="-2.95" x2="-3.0" y2="-2.95" stroke="#24272C" stroke-width="0.018"/>')
bb.append('<text x="-3.0" y="-2.66" text-anchor="end" font-family="DM Mono" font-size="0.2" fill="#24272C">Σ 100</text>')
for k in range(11):
    xk = -6.6 + 0.36 * k
    bb.append(f'<line x1="{xk:.2f}" y1="-2.95" x2="{xk:.2f}" y2="-3.03" stroke="#24272C" stroke-width="0.012"/>')
# black swan: outside the frame, unquantified
bb.append('<circle cx="-1.85" cy="-3.05" r="0.22" fill="#0E0F11"/>')
bb.append('<circle cx="-1.6" cy="-2.86" r="0.05" fill="#0E0F11"/>')
bb.append('<circle cx="-2.06" cy="-3.3" r="0.03" fill="#0E0F11"/>')
bb.append('<text x="-1.85" y="-2.55" text-anchor="middle" font-family="DM Mono" font-size="0.15" fill="#8E9196">n.q.</text>')
group(m_leftwall(), "".join(bb))

# ---------------------------------------------------------------- right wall: bookshelf (07), rule plaque (10), mirror (05)
# rule plaque, inscribed on wall
pl = ('<rect x="2.9" y="-5.55" width="4.2" height="0.62" fill="#F7F5F0" stroke="#24272C" stroke-width="0.03"/>'
      '<text x="5.0" y="-5.18" text-anchor="middle" font-family="Italiana" font-size="0.15" '
      'letter-spacing="0.035" fill="#24272C">MAI ELIMINARE SENZA APPROVAZIONE</text>')
group(m_rightwall(), pl)

# mirror A on right wall, facing in
poly([P(8.1, 0, 0.9), P(9.5, 0, 0.9), P(9.5, 0, 4.9), P(8.1, 0, 4.9)], fill="#F7F5F0", stroke=INK, sw=1.2)
for k in range(7):
    t = 0.12 + k * 0.5
    a = P(8.1 + min(t, 1.4), 0, 4.9 - max(0, t - 1.4))
    b = P(8.1 + max(0, t - 4.0), 0, 4.9 - min(t, 4.0))
    line(a, b, HAIR, 0.6)
mm = '<text x="8.8" y="-0.55" text-anchor="middle" font-family="DM Mono" font-size="0.17" fill="#8E9196">AUDIT · INPUT</text>'
group(m_rightwall(), mm)

# bookshelf against right wall
box(0.4, 2.7, 0.0, 0.8, 0.0, 5.0, fill="#EFEBE3")
# shelves & books on the front face (y=0.8)
for zs in (1.25, 2.5, 3.75):
    line(P(0.4, 0.8, zs), P(2.7, 0.8, zs), INK, 1.0)
import random
random.seed(1930)
for zi, zs in enumerate((0.0, 1.25, 2.5, 3.75)):
    x = 0.52
    while x < 2.55:
        bw = random.choice((0.09, 0.11, 0.13, 0.16))
        bh = random.uniform(0.75, 1.08)
        hi = (zi == 2 and 1.2 < x < 1.6)
        fill = COBALT if hi else (INK if random.random() < 0.18 else "#DAD5CB")
        poly([P(x, 0.8, zs), P(x + bw, 0.8, zs), P(x + bw, 0.8, zs + bh), P(x, 0.8, zs + bh)],
             fill=fill, stroke=INK, sw=0.5)
        x += bw + 0.025

# ---------------------------------------------------------------- desk with three monitors (01)
box(3.0, 7.2, 0.6, 2.2, 2.2, 2.38)               # desktop
for lx, ly in ((3.15, 2.05), (7.05, 2.05)):        # legs (front)
    box(lx - 0.07, lx + 0.07, ly - 0.07, ly + 0.07, 0.0, 2.2)
box(3.08, 3.22, 0.68, 0.82, 0.0, 2.2)
box(6.98, 7.12, 0.68, 0.82, 0.0, 2.2)
box(3.0, 7.2, 0.6, 2.2, 2.2, 2.38)               # redraw top over legs


def monitor(x0, x1, inner):
    box(x0 + (x1 - x0) / 2 - 0.05, x0 + (x1 - x0) / 2 + 0.05, 0.95, 1.05, 2.38, 2.75)
    box(x0, x1, 0.85, 0.95, 2.75, 4.05, fill=INK, top=INK, sw=1.0)
    # screen on y=0.95 face — draw inner content via plane transform at y=0.95
    group(m_rightwall(0.95), inner)


def screen_bg(x0, x1):
    return (f'<rect x="{x0+0.07:.2f}" y="-3.98" width="{x1-x0-0.14:.2f}" height="1.16" '
            f'fill="#F7F5F0" stroke="none"/>')


# left screen: the daily PDF
x0, x1 = 3.15, 4.45
inner = screen_bg(x0, x1)
inner += f'<rect x="{x0+0.3:.2f}" y="-3.88" width="0.7" height="0.96" fill="#FFFFFF" stroke="#8E9196" stroke-width="0.01"/>'
for k in range(9):
    w = 0.52 if k % 4 else 0.3
    inner += f'<line x1="{x0+0.38:.2f}" y1="{-3.76+k*0.095:.3f}" x2="{x0+0.38+w:.2f}" y2="{-3.76+k*0.095:.3f}" stroke="#24272C" stroke-width="0.012"/>'
inner += f'<text x="{x0+0.65:.2f}" y="-2.86" text-anchor="middle" font-family="DM Mono" font-size="0.07" fill="#8E9196">.pdf</text>'
monitor(x0, x1, inner)

# center screen: UST curve
x0, x1 = 4.45 + 0.0, 5.75
inner = screen_bg(x0, x1)
mats = [0, 0.08, 0.16, 0.3, 0.45, 0.62, 0.8, 1.0]
ylds = [0.62, 0.56, 0.5, 0.47, 0.5, 0.58, 0.68, 0.74]
cpts = []
for m, yv in zip(mats, ylds):
    cpts.append((x0 + 0.17 + m * (x1 - x0 - 0.34), -2.92 - yv * 0.95))
inner += '<polyline points="' + " ".join(f"{a:.3f},{b:.3f}" for a, b in cpts) + \
         '" fill="none" stroke="#2B4C86" stroke-width="0.03" stroke-linejoin="round"/>'
for a, b in cpts:
    inner += f'<circle cx="{a:.3f}" cy="{b:.3f}" r="0.02" fill="#2B4C86"/>'
inner += f'<line x1="{x0+0.17:.2f}" y1="-2.92" x2="{x1-0.17:.2f}" y2="-2.92" stroke="#8E9196" stroke-width="0.01"/>'
monitor(x0 + 0.04, x1, inner)

# right screen: BTP-Bund spread bars
x0, x1 = 5.79, 7.05
inner = screen_bg(x0, x1)
random.seed(7)
for k in range(14):
    h = 0.25 + 0.55 * (0.5 + 0.5 * math.sin(k * 0.55)) * random.uniform(0.85, 1.0)
    inner += f'<rect x="{x0+0.16+k*0.068:.3f}" y="{-2.92-h:.3f}" width="0.045" height="{h:.3f}" fill="#24272C" fill-opacity="0.82"/>'
inner += f'<line x1="{x0+0.14:.2f}" y1="-2.92" x2="{x1-0.12:.2f}" y2="-2.92" stroke="#8E9196" stroke-width="0.01"/>'
monitor(x0, x1, inner)

# ---------------------------------------------------------------- one chair
box(4.75, 5.55, 2.9, 3.7, 1.3, 1.42)
box(4.75, 5.55, 3.62, 3.72, 1.42, 2.65)
box(5.08, 5.22, 3.22, 3.36, 0.18, 1.3)
box(4.8, 5.5, 3.25, 3.33, 0.0, 0.14)
box(5.11, 5.19, 2.95, 3.65, 0.0, 0.14)

# ---------------------------------------------------------------- trolley by the door (09)
box(0.35, 1.15, 7.3, 7.85, 0.06, 1.55, fill="#E4DFD5")
line(P(1.15, 7.45, 1.55), P(1.15, 7.45, 2.15), INK, 1.3)
line(P(1.15, 7.7, 1.55), P(1.15, 7.7, 2.15), INK, 1.3)
line(P(1.15, 7.45, 2.15), P(1.15, 7.7, 2.15), INK, 1.3)
for zz in (0.5, 1.0):
    line(P(1.15, 7.3, zz), P(1.15, 7.85, zz), GREY, 0.6)

# ---------------------------------------------------------------- light table with tiered cards (02)
box(1.6, 4.1, 4.4, 6.0, 0.0, 1.15, fill="#EFEBE3", top="#FBFAF6")
lt = []
cols = [(1.85, "#24272C", 4), (2.6, "#5A5E65", 4), (3.3, "#A3A6AB", 3)]
for cx_, col, n in cols:
    for k in range(n):
        lt.append(f'<rect x="{cx_:.2f}" y="{4.6+k*0.33:.2f}" width="0.55" height="0.24" fill="none" stroke="{col}" stroke-width="0.022"/>')
        lt.append(f'<line x1="{cx_+0.07:.2f}" y1="{4.68+k*0.33:.2f}" x2="{cx_+0.4:.2f}" y2="{4.68+k*0.33:.2f}" stroke="{col}" stroke-width="0.012"/>')
for i, lab in enumerate(("T1", "T1-N", "T2")):
    lt.append(f'<text x="{cols[i][0]+0.275:.2f}" y="4.52" text-anchor="middle" font-family="DM Mono" font-size="0.13" fill="#24272C">{lab}</text>')
group(m_floor(1.15), "".join(lt))
# sealed bin (escluse), apart
box(4.5, 5.0, 6.5, 7.0, 0.0, 0.7, fill="#E4DFD5")
line(P(4.5, 6.75, 0.7), P(5.0, 6.75, 0.7), INK, 0.8)
line(P(4.75, 6.5, 0.7), P(4.75, 7.0, 0.7), INK, 0.8)
line(P(5.0, 6.62, 0.25), P(5.0, 6.88, 0.45), INK, 0.8)
line(P(5.0, 6.62, 0.45), P(5.0, 6.88, 0.25), INK, 0.8)

# ---------------------------------------------------------------- holding / trust file stack (06)
for k, (dx, dy) in enumerate(((0, 0), (0.05, -0.04), (-0.03, 0.05), (0.02, 0.0))):
    z0 = k * 0.13
    box(5.6 + dx, 6.7 + dx, 4.4 + dy, 5.2 + dy, z0, z0 + 0.12, fill="#E9E4DA" if k % 2 else "#F3F0EA", sw=0.9)
fl = ('<text x="0" y="0" font-family="DM Mono" font-size="0.12" fill="#24272C" '
      'transform="translate(5.78,4.86)">HOLDING · TRUST</text>')
group(m_floor(0.52), fl)

# ---------------------------------------------------------------- real-estate folder on floor (08)
box(6.0, 7.2, 7.1, 7.9, 0.0, 0.05, fill="#F7F5F0", sw=1.0)
fp = ('<rect x="6.150" y="7.220" width="0.55" height="0.42" fill="none" stroke="#2B4C86" stroke-width="0.02"/>'
      '<polyline points="6.150,7.380 6.425,7.180 6.700,7.380" fill="none" stroke="#2B4C86" stroke-width="0.02"/>'
      '<line x1="6.800" y1="7.320" x2="7.080" y2="7.320" stroke="#8E9196" stroke-width="0.014"/>'
      '<line x1="6.800" y1="7.440" x2="7.080" y2="7.440" stroke="#8E9196" stroke-width="0.014"/>'
      '<line x1="6.800" y1="7.560" x2="7.000" y2="7.560" stroke="#8E9196" stroke-width="0.014"/>')
group(m_floor(0.05), fp)

# ---------------------------------------------------------------- mirror B, free-standing, facing the room (05)
box(8.5, 9.9, 5.0, 5.08, 0.0, 3.4, fill="#F7F5F0", sw=1.1)
for k in range(6):
    t = 0.15 + k * 0.55
    a = P(8.5 + min(t, 1.4), 5.08, 3.4 - max(0, t - 1.4))
    b = P(8.5 + max(0, t - 3.4), 5.08, 3.4 - min(t, 3.4))
    line(a, b, HAIR, 0.6)
mb = '<text x="9.2" y="-0.35" text-anchor="middle" font-family="DM Mono" font-size="0.15" fill="#8E9196">SELF · AUDIT</text>'
group(m_rightwall(5.08), mb)

# ---------------------------------------------------------------- ruler on the floor (03)
box(1.6, 7.6, 8.55, 8.85, 0.0, 0.06, fill="#F7F5F0", sw=1.0)
rl = []
for k in range(61):
    xk = 1.7 + k * 0.095
    ln = 0.15 if k % 10 == 0 else (0.1 if k % 5 == 0 else 0.055)
    rl.append(f'<line x1="{xk:.3f}" y1="8.56" x2="{xk:.3f}" y2="{8.56+ln:.3f}" stroke="#24272C" stroke-width="0.008"/>')
for k, lab in ((0, "±3bp"), (20, "0,5%"), (40, "1,5%")):
    rl.append(f'<text x="{1.7+k*0.095+0.03:.3f}" y="8.82" font-family="DM Mono" font-size="0.085" fill="#2B4C86">{lab}</text>')
group(m_floor(0.06), "".join(rl))

# ---------------------------------------------------------------- the missing safe: dashed, N/D (11)
d = 'stroke-dasharray="5 5"'
x0_, x1_, y0_, y1_, z1_ = 8.5, 9.6, 7.2, 8.3, 1.25
for a, b in (((x1_, y0_, 0), (x1_, y1_, 0)), ((x0_, y1_, 0), (x1_, y1_, 0)),
             ((x1_, y0_, 0), (x1_, y0_, z1_)), ((x1_, y1_, 0), (x1_, y1_, z1_)), ((x0_, y1_, 0), (x0_, y1_, z1_)),
             ((x0_, y0_, z1_), (x1_, y0_, z1_)), ((x1_, y0_, z1_), (x1_, y1_, z1_)),
             ((x1_, y1_, z1_), (x0_, y1_, z1_)), ((x0_, y1_, z1_), (x0_, y0_, z1_))):
    line(P(*a), P(*b), GREY, 1.0, d)

# ---------------------------------------------------------------- callouts
callouts = [
    ("01", P(7.2, 2.2, 2.38), (1150, 1010)),
    ("02", P(2.85, 5.2, 1.15), (330, 1020)),
    ("03", P(3.0, 8.85, 0.06), (420, 1260)),
    ("04", P(0, 4.6, 5.3), (470, 300)),
    ("05", P(8.8, 0, 4.9), (1270, 470)),
    ("06", P(6.7, 5.2, 0.52), (1060, 1350)),
    ("07", P(1.55, 0.4, 5.0), (640, 230)),
    ("08", P(6.6, 7.9, 0.05), (700, 1345)),
    ("09", P(0, 9.1, 4.4), (180, 720)),
    ("10", P(5.0, 0, 5.55), (1060, 220)),
    ("11", P(9.6, 8.3, 0.0), (1230, 1250)),
]
for num, anchor, lab in callouts:
    out.append(f'<circle cx="{anchor[0]:.1f}" cy="{anchor[1]:.1f}" r="2.6" fill="{INK}"/>')
    line(anchor, lab, GREY, 0.7)
    col = GREY if num == "11" else INK
    out.append(f'<circle cx="{lab[0]}" cy="{lab[1]}" r="15" fill="{PAPER}" stroke="{col}" stroke-width="1"/>')
    out.append(f'<text x="{lab[0]}" y="{lab[1]+4.3}" text-anchor="middle" font-family="DM Mono" '
               f'font-size="12" fill="{col}">{num}</text>')

# ---------------------------------------------------------------- legend & titling
items = [
    ("01", "scrivania · tre monitor · una sedia"),
    ("02", "tavolo luminoso · fonti per tier"),
    ("03", "righello · soglie di concordanza"),
    ("04", "lavagna · scenari Σ 100 · coda n.q."),
    ("05", "due specchi · utente / analista"),
    ("06", "fascicolo · holding · trust"),
    ("07", "scaffale · value e geopolitica"),
    ("08", "cartellina · immobili"),
    ("09", "trolley · accanto alla porta"),
    ("10", "regola · sulla parete"),
]
LX0, LX1, LY = 150, 800, 1480
for i, (n, t) in enumerate(items):
    col, row = divmod(i, 5)
    x = LX0 + col * (LX1 - LX0)
    y = LY + row * 40
    out.append(f'<text x="{x}" y="{y}" font-family="DM Mono" font-size="14" fill="{COBALT}">{n}</text>')
    out.append(f'<text x="{x+44}" y="{y}" font-family="Instrument Sans" font-size="16" fill="{INK}" letter-spacing="0.2">{t}</text>')
out.append(f'<line x1="150" y1="1432" x2="1350" y2="1432" stroke="{INK}" stroke-width="0.8"/>')
out.append(f'<line x1="150" y1="1690" x2="1350" y2="1690" stroke="{HAIR}" stroke-width="0.8"/>')
out.append(f'<text x="{LX0}" y="1734" font-family="DM Mono" font-size="14" fill="{GREY}">11</text>')
out.append(f'<text x="{LX0+44}" y="1734" font-family="Instrument Serif" font-style="italic" font-size="19" fill="{GREY}">'
           f'cassaforte — N/D. L’inventario registra anche ciò che non può vedere.</text>')

head = f'''
<text x="150" y="104" font-family="Italiana" font-size="54" fill="{INK}" letter-spacing="3">Stanza vuota</text>
<text x="1350" y="84" text-anchor="end" font-family="DM Mono" font-size="12" fill="{GREY}" letter-spacing="1.5">INVENTARIO · RILIEVO ASSONOMETRICO</text>
<text x="1350" y="104" text-anchor="end" font-family="DM Mono" font-size="12" fill="{GREY}" letter-spacing="1.5">OGGETTI 10 + 1 · 17.XI.2026</text>
<line x1="150" y1="130" x2="1350" y2="130" stroke="{INK}" stroke-width="0.8"/>
<text x="1350" y="1800" text-anchor="end" font-family="DM Mono" font-size="11" fill="{GREY}" letter-spacing="1.2">FATTO · CLAIM · NARRATIVA</text>
<text x="150" y="1800" font-family="DM Mono" font-size="11" fill="{GREY}" letter-spacing="1.2">TAV. I</text>
'''

fontface = "\n".join(
    f"@font-face{{font-family:'{fam}';src:url('file://{FONTS}/{f}');{extra}}}"
    for fam, f, extra in (
        ("Italiana", "Italiana-Regular.ttf", ""),
        ("DM Mono", "DMMono-Regular.ttf", ""),
        ("Instrument Sans", "InstrumentSans-Regular.ttf", ""),
        ("Instrument Serif", "InstrumentSerif-Italic.ttf", "font-style:italic;"),
    ))

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
       f'<rect width="{W}" height="{H}" fill="{PAPER}"/>' + head + "".join(out) + "</svg>")
html = f"<!doctype html><html><head><meta charset='utf-8'><style>{fontface} html,body{{margin:0;background:{PAPER}}}</style></head><body>{svg}</body></html>"
with open(os.path.join(OUT, "stanza.html"), "w") as fh:
    fh.write(html)
print("html ok")
