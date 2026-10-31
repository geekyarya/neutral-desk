"""Meme-style sticker pop-ups: a bouncy yellow label with bold outlined text, shown for a couple of seconds."""
import math

from PIL import Image, ImageDraw

from .text import Font, wrap

MEME_SECONDS = 2.4


def make_sticker(text, font_px=54):
    """A slightly tilted yellow sticker with black outline and bold text (RGBA)."""
    f = Font(font_px, True)
    tmp = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lines = wrap(tmp, text, f, font_px * 12, 2)
    lh = int(font_px * 1.45)
    w = max(int(f.length(tmp, ln)) for ln in lines) + font_px
    h = lh * len(lines) + int(font_px * 0.6)
    pad = 14
    img = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([pad + 6, pad + 8, pad + w + 6, pad + h + 8], radius=22, fill=(0, 0, 0, 110))  # shadow
    d.rounded_rectangle([pad, pad, pad + w, pad + h], radius=22, fill=(255, 221, 51), outline=(20, 20, 20), width=6)
    y = pad + int(font_px * 0.3)
    for ln in lines:
        f.draw(d, (pad + (w - f.length(d, ln)) / 2, y), ln, (20, 20, 20))
        y += lh
    return img.rotate(-4, expand=True, resample=Image.BICUBIC)


def paste_sticker(img, sticker, t, total, center):
    """Pop in with a bounce over 0.3s, wiggle, then shrink away in the last 0.3s. img: RGBA."""
    if t < 0.3:
        x = t / 0.3
        scale = 1.18 * math.sin(x * math.pi / 2) + (0.0 if x < 1 else 0)
        scale = min(scale, 1.18) if x < 0.8 else 1.18 - 0.18 * ((x - 0.8) / 0.2)
    elif t > total - 0.3:
        scale = max(0.05, (total - t) / 0.3)
    else:
        scale = 1.0 + 0.03 * math.sin(t * 14)
    w, h = sticker.size
    sw, sh = max(1, int(w * scale)), max(1, int(h * scale))
    st = sticker.resize((sw, sh), Image.BICUBIC).rotate(3 * math.sin(t * 9), expand=True, resample=Image.BICUBIC)
    out = img.copy()
    out.alpha_composite(st, (int(center[0] - st.width / 2), int(center[1] - st.height / 2)))
    return out
