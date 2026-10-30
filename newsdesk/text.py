"""Text drawing with automatic font fallback, so Hindi (Devanagari) and English names mix on one line."""
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import ImageFont

from .config import ROOT

FONTS = ROOT / "assets" / "fonts"
_cmaps = {}


def _cmap(path):
    if path not in _cmaps:
        _cmaps[path] = set(TTFont(path).getBestCmap())
    return _cmaps[path]


class Font:
    """Noto Sans Devanagari first (for Hindi), Noto Sans for Latin letters and symbols."""

    def __init__(self, size, bold=False):
        w = "Bold" if bold else "Regular"
        self.paths = [str(FONTS / f"NotoSansDevanagari-{w}.ttf"), str(FONTS / f"NotoSans-{w}.ttf")]
        self.fonts = [ImageFont.truetype(p, size) for p in self.paths]
        self.size = size
        self.ascent = max(f.getmetrics()[0] for f in self.fonts)

    def runs(self, text):
        out, cur, cur_i = [], "", None
        for ch in text:
            if ch.isspace() and cur_i is not None:
                cur += ch
                continue
            i = next((k for k, p in enumerate(self.paths) if ord(ch) in _cmap(p)), len(self.paths) - 1)
            if cur_i is None or i == cur_i:
                cur, cur_i = cur + ch, i
            else:
                out.append((cur, self.fonts[cur_i]))
                cur, cur_i = ch, i
        if cur:
            out.append((cur, self.fonts[cur_i or 0]))
        return out

    def length(self, draw, text):
        return sum(draw.textlength(t, font=f) for t, f in self.runs(text))

    def draw(self, draw, xy, text, fill):
        x, y = xy
        for t, f in self.runs(text):
            draw.text((x, y + self.ascent), t, font=f, fill=fill, anchor="ls")
            x += draw.textlength(t, font=f)


def wrap(draw, text, f, width, max_lines):
    lines, cur = [], ""
    for w in text.split():
        trial = f"{cur} {w}".strip()
        if f.length(draw, trial) <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        while lines[-1] and f.length(draw, lines[-1] + "…") > width:
            lines[-1] = lines[-1][:-1]
        lines[-1] = lines[-1].rstrip() + "…"
    return [l for l in lines if l]
