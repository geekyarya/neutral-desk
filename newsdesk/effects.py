"""Mood effects for the anchor: a blazing fire ring for bad news, an icy frost ring + snow for good news."""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def fire_ring(diameter, pad, n=16):
    """Looping animated flames around a circle (RGBA frames), flames licking upwards."""
    D = diameter + 2 * pad
    y, x = np.mgrid[0:D, 0:D].astype(np.float32) - D / 2
    r = np.hypot(x, y)
    th = np.arctan2(y, x)
    R0 = diameter / 2
    up = 1 + 0.6 * np.clip(-np.sin(th), 0, 1)  # taller flames at the top
    frames = []
    for k in range(n):
        t = 2 * np.pi * k / n
        noise = (0.5 + 0.5 * (0.5 * np.sin(5 * th + 3 * t) + 0.3 * np.sin(11 * th - 5 * t + 1.3)
                              + 0.2 * np.sin(23 * th + 7 * t + 0.7)))
        h = pad * (0.45 + 0.55 * noise) * up
        i = np.clip(1 - (r - R0) / h, 0, 1) * (r > R0 - 8)
        i = i ** 1.3
        rgb = np.dstack([np.full_like(i, 255), 255 * i ** 0.9 * 0.85, 90 * i ** 4]).astype(np.uint8)
        a = (np.clip(i * 1.6, 0, 1) * 255).astype(np.uint8)
        img = Image.fromarray(np.dstack([rgb, a]), "RGBA").filter(ImageFilter.GaussianBlur(1.2))
        frames.append(img)
    return frames


def ice_ring(diameter, pad, seed=5):
    """A frosty ring of ice crystals around a circle (RGBA)."""
    D = diameter + 2 * pad
    img = Image.new("RGBA", (D, D), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c, R0 = D / 2, diameter / 2
    d.ellipse([c - R0 - 10, c - R0 - 10, c + R0 + 10, c + R0 + 10], outline=(190, 235, 255, 230), width=14)
    rng = np.random.default_rng(seed)
    for a in np.linspace(0, 2 * np.pi, 46, endpoint=False) + rng.uniform(0, 0.1, 46):
        L = R0 + 8 + rng.uniform(14, pad * 0.9)
        w = rng.uniform(0.04, 0.08)
        pts = [(c + (R0 + 4) * np.cos(a - w), c + (R0 + 4) * np.sin(a - w)),
               (c + L * np.cos(a), c + L * np.sin(a)),
               (c + (R0 + 4) * np.cos(a + w), c + (R0 + 4) * np.sin(a + w))]
        d.polygon(pts, fill=(225, 245, 255, 220), outline=(140, 200, 240, 255))
    return img.filter(ImageFilter.GaussianBlur(0.8))


def vignette(W, H, color, strength=110):
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    dist = np.hypot((x - W / 2) / (W / 2), (y - H / 2) / (H / 2))
    a = (np.clip((dist - 0.55) / 0.6, 0, 1) * strength).astype(np.uint8)
    return Image.fromarray(np.dstack([np.full((H, W, 3), color, np.uint8), a]), "RGBA")


class Particles:
    """Deterministic falling snow (good news) or rising embers (bad news) for the whole frame."""

    def __init__(self, W, H, kind, n=60, seed=11):
        rng = np.random.default_rng(seed)
        self.W, self.H, self.kind = W, H, kind
        self.x = rng.uniform(0, W, n)
        self.y0 = rng.uniform(0, H, n)
        self.v = rng.uniform(40, 120, n) * (1 if kind == "snow" else -1.4)
        self.size = rng.uniform(2, 6 if kind == "snow" else 4, n)
        self.sway = rng.uniform(0, 6.28, n)

    def draw(self, img, t):
        d = ImageDraw.Draw(img)
        ys = (self.y0 + self.v * t) % self.H
        xs = self.x + 14 * np.sin(t * 1.5 + self.sway)
        for x, y, s in zip(xs, ys, self.size):
            if self.kind == "snow":
                d.ellipse([x - s, y - s, x + s, y + s], fill=(240, 248, 255))
            else:
                d.ellipse([x - s, y - s, x + s, y + s], fill=(255, int(120 + 60 * (y / self.H)), 30))
