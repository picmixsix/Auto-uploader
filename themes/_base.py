"""Helper visual bersama untuk semua tema. File berawalan _ tidak dianggap tema."""
import math, random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS, SR = 1080, 1920, 30, 44100
FB = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
_F = {}


def font(sz):
    if sz not in _F: _F[sz] = ImageFont.truetype(FB, sz)
    return _F[sz]


def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))


def eo(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def eb(t):
    t = clamp(t); c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def make_bg(im):
    s = max(1296 / im.width, 2304 / im.height)
    b = im.resize((int(im.width * s) + 1, int(im.height * s) + 1))
    x, y = (b.width - 1296) // 2, (b.height - 2304) // 2
    b = b.crop((x, y, x + 1296, y + 2304))
    b = b.resize((324, 576), Image.BILINEAR).filter(ImageFilter.GaussianBlur(10)).resize((1296, 2304), Image.BILINEAR)
    return b.point(lambda v: int(v * 0.5))


def make_card(im, size=880):
    k = min(size / im.width, size / im.height)
    ph = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS)
    pad, S = 16, 60
    cw, ch = ph.width + 2 * pad, ph.height + 2 * pad
    cv = Image.new('RGBA', (cw + 2 * S, ch + 2 * S), (0, 0, 0, 0))
    sh = Image.new('RGBA', cv.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((S + 8, S + 22, S + cw + 8, S + ch + 22), radius=34, fill=(0, 0, 0, 150))
    cv.alpha_composite(sh.filter(ImageFilter.GaussianBlur(22)))
    ImageDraw.Draw(cv).rounded_rectangle((S, S, S + cw, S + ch), radius=30, fill=(255, 255, 255, 255))
    m = Image.new('L', ph.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, ph.width - 1, ph.height - 1), radius=20, fill=255)
    cv.paste(ph, (S + pad, S + pad), m)
    return cv


def make_sticker(price):
    S = 340
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse((6, 6, S - 6, S - 6), fill=(255, 59, 48, 255))
    d.ellipse((22, 22, S - 22, S - 22), outline=(255, 255, 255, 255), width=5)
    d.text((S / 2, 98), 'HARGA', font=font(40), fill=(255, 255, 255, 255), anchor='mm')
    sz = 84
    while sz > 28 and d.textlength(price, font=font(sz)) > S - 80: sz -= 4
    d.text((S / 2, S / 2 + 24), price, font=font(sz), fill=(255, 235, 59, 255), anchor='mm')
    return im


def make_pill(text, color, maxw=900):
    d0 = ImageDraw.Draw(Image.new('L', (1, 1)))
    sz = 54
    while sz > 30 and d0.textlength(text, font=font(sz)) + 90 > maxw: sz -= 2
    w, h = int(d0.textlength(text, font=font(sz))) + 90, 104
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=color + (245,), outline=(255, 255, 255, 255), width=4)
    d.text((w / 2, h / 2 + 2), text, font=font(sz), fill=(255, 255, 255, 255), anchor='mm')
    return im


def make_bokeh():
    sh = Image.new('RGBA', (W, H * 2), (0, 0, 0, 0)); d = ImageDraw.Draw(sh); rng = random.Random(7)
    for _ in range(20):
        r, x, y, a = rng.randint(18, 70), rng.randint(0, W), rng.randint(0, H - 1), rng.randint(16, 40)
        for dy in (0, H):
            d.ellipse((x - r, y + dy - r, x + r, y + dy + r), fill=(255, 255, 255, a))
    return sh.filter(ImageFilter.GaussianBlur(3))


def persp_coeffs(dst, src):
    A, B = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -x * u, -y * u]); B.append(u)
        A.append([0, 0, 0, x, y, 1, -x * v, -y * v]); B.append(v)
    return tuple(np.linalg.solve(np.array(A, float), np.array(B, float)))


def warp(card, theta, phi, scale, cx, cy):
    cw, ch = card.size; F = 2200.0
    pts = []
    for x, y in ((-cw / 2, -ch / 2), (cw / 2, -ch / 2), (cw / 2, ch / 2), (-cw / 2, ch / 2)):
        x1 = x * math.cos(theta); z1 = -x * math.sin(theta)
        y2 = y * math.cos(phi) - z1 * math.sin(phi); z2 = y * math.sin(phi) + z1 * math.cos(phi)
        k = F / (F + z2)
        pts.append((cx + scale * k * x1, cy + scale * k * y2))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, y0, x1_, y1_ = int(min(xs)) - 2, int(min(ys)) - 2, int(max(xs)) + 3, int(max(ys)) + 3
    co = persp_coeffs([(px - x0, py - y0) for px, py in pts], [(0, 0), (cw, 0), (cw, ch), (0, ch)])
    return card.transform((x1_ - x0, y1_ - y0), Image.PERSPECTIVE, co, Image.BICUBIC), (x0, y0)


def wrap_words(d, text, f, width):
    lines, cur = [], []
    for w in text.split():
        if not cur or d.textlength(' '.join(cur + [w]), font=f) <= width: cur.append(w)
        else: lines.append(cur); cur = [w]
    if cur: lines.append(cur)
    return lines


def draw_subtitle(fr, lines, s, local, box=(0, 0, 0, 150), txt=(255, 255, 255), hi=(255, 214, 10),
                  hi_bg=None, outline=None, bottom=1655):
    """Subtitle per adegan dengan sorotan kata yang mengikuti suara. Dipakai bersama oleh tema."""
    words = [w for ln in lines for w in ln]
    total_c = max(1, sum(len(w) + 1 for w in words))
    prog = clamp((local - s['lead']) / max(0.1, s['vd']))
    cur = acc = 0
    for n, w in enumerate(words):
        acc += len(w) + 1
        if acc / total_c <= prog + 0.001: cur = n + 1
    lh = 68; bh = len(lines) * lh + 40
    a = clamp(local / 0.25)
    ov = Image.new('RGBA', (W, bh), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
    od.rounded_rectangle((70, 0, W - 70, bh - 1), radius=36, fill=tuple(box[:3]) + (int(box[3] * a),),
                         outline=(tuple(outline) + (int(255 * a),)) if outline else None, width=4)
    f = font(54); n = 0
    for r, ln in enumerate(lines):
        x = (W - od.textlength(' '.join(ln), font=f)) / 2
        for w in ln:
            on = n == cur - 1
            if on and hi_bg:
                od.rounded_rectangle((x - 8, 20 + r * lh - 2, x + od.textlength(w, font=f) + 8, 20 + r * lh + 62),
                                     radius=16, fill=tuple(hi_bg) + (int(255 * a),))
            od.text((x, 20 + r * lh), w, font=f, fill=tuple(hi if on else txt) + (int(255 * a),))
            x += od.textlength(w + ' ', font=f); n += 1
    fr.paste(ov, (0, bottom - bh), ov)
