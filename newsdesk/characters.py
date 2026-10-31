"""Original cartoon characters for the cute Reels: a toddler ("Golu") and a bear couple ("Laddoo" & "Jalebi").

Each draw_* function returns an RGBA sprite; pose parameters make simple animation possible
(expression, blink, arm raise, squash/stretch).
"""
from PIL import Image, ImageDraw

S = 2  # supersampling for smooth edges

OUTLINE = (60, 40, 35)


class Pen:
    def __init__(self, w, h):
        self.img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)
        self.w, self.h = w, h

    def ell(self, cx, cy, rx, ry, fill, outline=OUTLINE, width=4):
        self.d.ellipse([(cx - rx) * S, (cy - ry) * S, (cx + rx) * S, (cy + ry) * S], fill=fill,
                       outline=outline, width=width * S if outline else 0)

    def rrect(self, x0, y0, x1, y1, r, fill, outline=OUTLINE, width=4):
        self.d.rounded_rectangle([x0 * S, y0 * S, x1 * S, y1 * S], radius=r * S, fill=fill,
                                 outline=outline, width=width * S if outline else 0)

    def arc(self, cx, cy, rx, ry, start, end, color=OUTLINE, width=5):
        self.d.arc([(cx - rx) * S, (cy - ry) * S, (cx + rx) * S, (cy + ry) * S], start, end, fill=color,
                   width=width * S)

    def poly(self, pts, fill, outline=OUTLINE, width=4):
        self.d.polygon([(x * S, y * S) for x, y in pts], fill=fill)
        if outline:
            self.d.line([(x * S, y * S) for x, y in pts + pts[:1]], fill=outline, width=width * S, joint="curve")

    def limb(self, x0, y0, x1, y1, width, fill):
        for col, wd in ((OUTLINE, width + 8), (fill, width)):
            self.d.line([(x0 * S, y0 * S), (x1 * S, y1 * S)], fill=col, width=int(wd * S))
            for x, y in ((x0, y0), (x1, y1)):
                r = wd / 2
                self.d.ellipse([(x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S], fill=col)

    def done(self):
        return self.img.resize((self.w, self.h), Image.LANCZOS)


def _eyes(p, cx, cy, gap, r, expr, blink):
    for ex in (cx - gap, cx + gap):
        if blink or expr in ("happy", "laugh"):
            p.arc(ex, cy + r * 0.3, r, r * 0.8, 200, 340, width=5)  # closed, smiling eyes
        elif expr == "angry":
            p.ell(ex, cy, r * 0.75, r * 0.75, (30, 20, 20), outline=None)
            p.d.line([((ex - r) * S, (cy - r * 1.6 + (6 if ex < cx else -6)) * S),
                      ((ex + r) * S, (cy - r * 1.6 - (6 if ex < cx else -6)) * S)], fill=OUTLINE, width=6 * S)
        else:
            p.ell(ex, cy, r, r * 1.15, (30, 20, 20), outline=None)
            p.ell(ex + r * 0.35, cy - r * 0.4, r * 0.38, r * 0.38, (255, 255, 255), outline=None)
            p.ell(ex - r * 0.3, cy + r * 0.35, r * 0.15, r * 0.15, (255, 255, 255), outline=None)
            if expr == "sad":
                p.ell(ex + r * 0.2, cy + r * 1.6, r * 0.25, r * 0.4, (120, 190, 255), outline=None)  # tear


def _mouth(p, cx, cy, size, expr):
    if expr in ("happy", "love"):
        p.arc(cx, cy - size * 0.3, size, size * 0.8, 20, 160, width=5)
    elif expr == "laugh":
        p.d.chord([(cx - size) * S, (cy - size * 0.6) * S, (cx + size) * S, (cy + size * 1.1) * S], 0, 180,
                  fill=(150, 40, 50), outline=OUTLINE, width=4 * S)
        p.ell(cx, cy + size * 0.55, size * 0.45, size * 0.25, (240, 110, 120), outline=None)
    elif expr == "sad":
        p.arc(cx, cy + size * 0.6, size * 0.7, size * 0.5, 200, 340, width=5)
    elif expr == "angry":
        p.d.line([((cx - size * 0.6) * S, (cy + 4) * S), ((cx + size * 0.6) * S, (cy - 2) * S)], fill=OUTLINE,
                 width=5 * S)
    elif expr == "shock":
        p.ell(cx, cy + size * 0.2, size * 0.45, size * 0.6, (150, 40, 50))
    else:  # neutral
        p.arc(cx, cy - size * 0.1, size * 0.5, size * 0.35, 30, 150, width=5)


# ------------------------------------------------------------------ the kid
SKIN = (255, 214, 180)
SKIN_SH = (240, 180, 150)


def draw_kid(expr="neutral", blink=False, arm=0.0, shirt=(255, 196, 61), squash=0.0, w=520, h=700):
    """Golu: a chubby toddler with a big head and a hair tuft. arm: 0 down .. 1 waving. squash: -1..1 bounce."""
    p = Pen(w, h)
    cx = w / 2
    sq = 1 + squash * 0.06
    top = 372
    # legs + shoes
    for lx in (cx - 52, cx + 52):
        p.rrect(lx - 27, 575, lx + 27, 655, 20, SKIN)
        p.ell(lx, 660, 44, 20, (230, 70, 90))
    # arms (behind the body): left always down, right swings from down (0) to waving (1)
    p.limb(cx - 92, top + 50, cx - 128, top + 150, 46, shirt)
    p.ell(cx - 130, top + 170, 25, 25, SKIN)
    hx, hy_ = cx + 128 + 40 * arm, top + 150 - 230 * arm
    p.limb(cx + 92, top + 50, hx, hy_ - 20 * (1 - arm), 46, shirt)
    p.ell(hx, hy_ + 20 * (1 - arm) - 25 * arm, 25, 25, SKIN)
    # shorts + shirt
    p.rrect(cx - 102, 540, cx + 102, 610, 26, (70, 120, 220))
    p.rrect(cx - 112 * sq, top, cx + 112 * sq, 572, 70, shirt)
    _star(p, cx, top + 90, 22, (255, 255, 255))
    # head (overlaps the shirt collar, so it sits on the body)
    hy = 228 - squash * 8
    p.ell(cx - 158, hy + 12, 30, 36, SKIN)  # ears
    p.ell(cx + 158, hy + 12, 30, 36, SKIN)
    p.ell(cx, hy, 165 * sq, 158 / sq, SKIN)
    # hair: soft fringe of tufts + a cowlick on top
    hair = (60, 38, 30)
    p.d.chord([(cx - 160) * S, (hy - 158) * S, (cx + 160) * S, (hy + 40) * S], 200, 340, fill=hair,
              outline=OUTLINE, width=4 * S)
    for tx, ty, r in ((-105, -95, 46), (-50, -118, 50), (10, -126, 52), (70, -114, 48), (118, -88, 40)):
        p.ell(cx + tx, hy + ty, r, r * 0.8, hair, outline=None)
    p.poly([(cx - 8, hy - 168), (cx + 26, hy - 222), (cx + 40, hy - 160)], hair, outline=None)  # cowlick
    # face
    _eyes(p, cx, hy + 18, 62, 22, expr, blink)
    p.ell(cx - 105, hy + 70, 26, 15, (255, 150, 160), outline=None)  # rosy cheeks
    p.ell(cx + 105, hy + 70, 26, 15, (255, 150, 160), outline=None)
    p.ell(cx, hy + 50, 9, 7, SKIN_SH, outline=None)  # button nose
    _mouth(p, cx, hy + 90, 30, expr)
    if expr == "love":
        for hx2 in (cx - 62, cx + 62):  # heart eyes
            _heart(p, hx2, hy + 18, 26, (240, 60, 90))
    return p.done()


def _star(p, cx, cy, r, color):
    import math
    pts = []
    for k in range(10):
        a = -math.pi / 2 + k * math.pi / 5
        rr = r if k % 2 == 0 else r * 0.45
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    p.poly(pts, color, outline=None)


# ------------------------------------------------------------------ the bears
LADDOO = {"fur": (214, 150, 86), "inner": (245, 214, 170), "acc": (220, 50, 60)}     # caramel bear, red scarf
JALEBI = {"fur": (196, 186, 226), "inner": (245, 238, 252), "acc": (255, 140, 180)}  # lavender bear, flower


def _heart(p, cx, cy, r, color):
    p.ell(cx - r * 0.5, cy - r * 0.2, r * 0.55, r * 0.55, color, outline=None)
    p.ell(cx + r * 0.5, cy - r * 0.2, r * 0.55, r * 0.55, color, outline=None)
    p.poly([(cx - r * 1.02, cy - r * 0.05), (cx + r * 1.02, cy - r * 0.05), (cx, cy + r * 1.0)], color, outline=None)


def draw_bear(who="laddoo", expr="neutral", blink=False, arm=0.0, squash=0.0, facing=0, w=440, h=520):
    """who: 'laddoo' (him) or 'jalebi' (her). arm: 0 down .. 1 raised/hugging. facing: -1 left, 0 front, 1 right."""
    c = LADDOO if who == "laddoo" else JALEBI
    p = Pen(w, h)
    cx = w / 2 + facing * 6
    sq = 1 + squash * 0.07
    # feet + body
    for fx in (cx - 60, cx + 60):
        p.ell(fx, 485, 46, 28, c["fur"])
        p.ell(fx, 490, 24, 14, c["inner"], outline=None)
    p.ell(cx, 390, 130 * sq, 112 / sq, c["fur"])
    p.ell(cx, 405, 78, 70, c["inner"], outline=None)
    # arms
    for side in (-1, 1):
        a = arm if side == (1 if facing >= 0 else -1) else arm * 0.3
        p.limb(cx + side * 100, 345, cx + side * (135 + 30 * a), 420 - 190 * a, 54, c["fur"])
    # head + ears
    hy = 190 - squash * 8
    for ex in (cx - 108, cx + 108):
        p.ell(ex, hy - 95, 46, 46, c["fur"])
        p.ell(ex, hy - 95, 24, 24, c["inner"], outline=None)
    p.ell(cx, hy, 150 * sq, 128 / sq, c["fur"])
    p.ell(cx + facing * 10, hy + 42, 60, 44, c["inner"])  # muzzle
    p.ell(cx + facing * 10, hy + 22, 18, 12, (60, 40, 35), outline=None)  # nose
    _eyes(p, cx + facing * 14, hy - 18, 54, 16, expr, blink)
    p.ell(cx - 92, hy + 30, 22, 13, (255, 150, 170), outline=None)
    p.ell(cx + 92, hy + 30, 22, 13, (255, 150, 170), outline=None)
    _mouth(p, cx + facing * 10, hy + 62, 20, expr)
    if expr == "love":
        for hx in (cx - 54 + facing * 14, cx + 54 + facing * 14):
            _heart(p, hx, hy - 18, 20, (240, 60, 90))
    # accessories
    if who == "laddoo":  # red scarf
        p.rrect(cx - 110, 288, cx + 110, 322, 16, c["acc"])
        p.rrect(cx + 50, 300, cx + 86, 380, 12, c["acc"])
    else:  # flower on the ear
        fx, fy = cx + 108, hy - 120
        for k in range(5):
            import math
            a = k * 2 * math.pi / 5
            p.ell(fx + 22 * math.cos(a), fy + 22 * math.sin(a), 16, 16, c["acc"])
        p.ell(fx, fy, 12, 12, (255, 220, 90))
    return p.done()


def preview(path):
    """A sheet of the characters in a few expressions, to review the designs."""
    sheet = Image.new("RGB", (2200, 1300), (255, 243, 232))
    kids = [draw_kid(e) for e in ("neutral", "happy", "laugh", "sad")] + [draw_kid("love", arm=1)]
    for i, k in enumerate(kids):
        sheet.paste(k, (i * 440 - 30, 0), k)
    bears = [draw_bear("laddoo", "happy"), draw_bear("jalebi", "love", facing=-1),
             draw_bear("laddoo", "shock"), draw_bear("jalebi", "angry"), draw_bear("laddoo", "sad")]
    for i, b in enumerate(bears):
        sheet.paste(b, (i * 440, 760), b)
    sheet.save(path)
