"""Tema Aurora: tampilan sinematik berbasis kaca dan cahaya.

- Aurora prosedural yang warnanya diambil otomatis dari foto produk (tiap produk punya suasana sendiri).
- Kartu kaca 3D dengan lapisan hologram pelangi dan kilau menyapu.
- Cincin HUD berputar, kurung bidik "mengunci" ke produk, dan garis pindai AI.
- Judul muncul huruf demi huruf (kabur menjadi tajam), subtitle gaya karaoke.
- Cahaya berdenyut mengikuti ketukan musik bawaan (104 BPM).

File ini mandiri: tidak butuh file lain di folder themes/. Untuk tema baru cukup salin file ini.
"""
import math, random, re, colorsys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

INFO = {'name': 'Aurora', 'desc': 'Sinematik: aurora sewarna foto, kartu kaca hologram, cincin HUD, pindai AI, subtitle karaoke.'}

W, H = 1080, 1920
FB = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
_F = {}
BEAT = 60 / 104  # ketukan musik bawaan


def font(sz):
    if sz not in _F: _F[sz] = ImageFont.truetype(FB, sz)
    return _F[sz]


def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def eo(t): t = clamp(t); return 1 - (1 - t) ** 3
def eio(t): t = clamp(t); return t * t * (3 - 2 * t)
def lerp(a, b, k): return a + (b - a) * k


def eb(t):
    t = clamp(t); c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def mixc(c1, c2, k): return tuple(int(lerp(a, b, k)) for a, b in zip(c1, c2))
def lighten(c, k=0.5): return mixc(c, (255, 255, 255), k)


_LUT = {}


def lut(k):
    k = round(clamp(k) * 32)
    if k not in _LUT: _LUT[k] = [int(i * k / 32) for i in range(256)]
    return _LUT[k]


def pa(fr, sp, pos, k=1.0):
    """Tempel sprite RGBA dengan kekuatan alpha k."""
    if k <= 0.01: return
    a = sp.getchannel('A')
    if k < 0.99: a = a.point(lut(k))
    fr.paste(sp, (int(pos[0]), int(pos[1])), a)


def wrap_words(d, text, f, width):
    lines, cur = [], []
    for w in text.split():
        if not cur or d.textlength(' '.join(cur + [w]), font=f) <= width: cur.append(w)
        else: lines.append(cur); cur = [w]
    if cur: lines.append(cur)
    return lines


# ---------------------------------------------------------------- warna
def palette(im):
    """Tiga warna paling khas dari foto (abu-abu diabaikan), disegarkan agar menyala di latar gelap."""
    sm = im.resize((48, 48)).quantize(colors=8, method=Image.MEDIANCUT)
    pal = sm.getpalette()[:24]; cands = []
    for c, idx in sm.getcolors():
        r, g, b = pal[idx * 3: idx * 3 + 3]
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        cands.append((c * (0.25 + s) * (0.3 + v), h, s))
    cands.sort(reverse=True); hues = []
    for _, h, s in cands:
        if s < 0.14: continue
        if all(min(abs(h - x), 1 - abs(h - x)) > 0.07 for x in hues): hues.append(h)
    if not hues: hues = [0.56]
    while len(hues) < 3: hues.append((hues[0] + (0.14 if len(hues) == 1 else -0.2)) % 1)
    return [tuple(int(255 * x) for x in colorsys.hsv_to_rgb(h, 0.70, 1.0)) for h in hues[:3]]


# ---------------------------------------------------------------- 3D
def persp_coeffs(dst, src):
    A, B = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -x * u, -y * u]); B.append(u)
        A.append([0, 0, 0, x, y, 1, -x * v, -y * v]); B.append(v)
    return tuple(np.linalg.solve(np.array(A, float), np.array(B, float)))


def warp(card, theta, phi, scale, cx, cy):
    cw, ch = card.size; F = 2200.0; pts = []
    for x, y in ((-cw / 2, -ch / 2), (cw / 2, -ch / 2), (cw / 2, ch / 2), (-cw / 2, ch / 2)):
        x1 = x * math.cos(theta); z1 = -x * math.sin(theta)
        y2 = y * math.cos(phi) - z1 * math.sin(phi); z2 = y * math.sin(phi) + z1 * math.cos(phi)
        k = F / (F + z2); pts.append((cx + scale * k * x1, cy + scale * k * y2))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, y0, x1_, y1_ = int(min(xs)) - 2, int(min(ys)) - 2, int(max(xs)) + 3, int(max(ys)) + 3
    co = persp_coeffs([(px - x0, py - y0) for px, py in pts], [(0, 0), (cw, 0), (cw, ch), (0, ch)])
    return card.transform((x1_ - x0, y1_ - y0), Image.PERSPECTIVE, co, Image.BILINEAR), (x0, y0)


# ---------------------------------------------------------------- sprite cahaya
_G = {}


def glow(r, color, peak=255, power=2.0):
    key = (int(r), color, int(peak), power)
    if key not in _G:
        n = int(r * 2); y, x = np.mgrid[0:n, 0:n].astype(np.float32)
        d = np.hypot(x - r + 0.5, y - r + 0.5) / r
        a = np.clip(1 - d, 0, 1) ** power
        arr = np.zeros((n, n, 4), np.uint8); arr[..., 0], arr[..., 1], arr[..., 2] = color
        arr[..., 3] = (a * peak).astype(np.uint8)
        _G[key] = Image.fromarray(arr, 'RGBA')
    return _G[key]


def make_foil(sz=1700):
    """Pelangi diagonal pastel untuk lapisan hologram."""
    y, x = np.mgrid[0:sz, 0:sz].astype(np.float32)
    h6 = (((x * 0.8 + y * 0.5) / 650.0) % 1.0) * 6
    i = np.floor(h6).astype(int) % 6; f = h6 - np.floor(h6); s_, v = 0.55, 1.0
    p_, q, t_ = v * (1 - s_), v * (1 - f * s_), v * (1 - (1 - f) * s_)
    sel = [i == k for k in range(6)]
    r = np.select(sel, [v, q, p_, p_, t_, v]); g = np.select(sel, [t_, v, v, q, p_, p_]); b = np.select(sel, [p_, p_, t_, v, v, q])
    return Image.fromarray((np.stack([r, g, b], -1) * 255).astype(np.uint8), 'RGB')


def make_hud(size, R, accent, seed, wd=4):
    """Cincin tipis berbusur putus-putus dan bertanda skala, gaya antarmuka teknologi."""
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0)); d = ImageDraw.Draw(im); c = size / 2; rng = random.Random(seed)
    ang = 0
    while ang < 360:
        L = rng.choice([8, 14, 26, 44]); gap = rng.choice([6, 10, 16])
        d.arc((c - R, c - R, c + R, c + R), ang, ang + L, fill=accent + (170,), width=wd); ang += L + gap
    for a in range(0, 360, 6):
        r1, r2 = R - 8 * wd // 2, R - (17 * wd // 2 if a % 30 == 0 else 12 * wd // 2); ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        d.line((c + r1 * ca, c + r1 * sa, c + r2 * ca, c + r2 * sa), fill=(255, 255, 255, 100 if a % 30 == 0 else 55), width=max(1, wd // 2))
    return im


def make_coin_ring(S, cols):
    """Cincin gradien kerucut (tiga warna foto) untuk koin harga."""
    y, x = np.mgrid[0:S, 0:S].astype(np.float32); dx, dy = x - S / 2 + 0.5, y - S / 2 + 0.5
    ang = (np.arctan2(dy, dx) / (2 * np.pi) + 0.5) * 3; idx = np.floor(ang).astype(int) % 3; fr_ = ang - np.floor(ang)
    cs = np.array([lighten(c, 0.25) for c in cols], np.float32)
    col = cs[idx] * (1 - fr_[..., None]) + cs[(idx + 1) % 3] * fr_[..., None]
    d = np.hypot(dx, dy); R = S / 2 - 8
    a = np.clip((R - d) / 1.6, 0, 1) * np.clip((d - (R - 17)) / 1.6, 0, 1)
    arr = np.dstack([col, a * 255]).astype(np.uint8)
    return Image.fromarray(arr, 'RGBA')


# ---------------------------------------------------------------- komponen UI
def glass_chip(text, accent, maxw=900, fs=52, icon=True, fill=None):
    """Chip kaca gelap dengan ikon centang; ukuran menyesuaikan teks."""
    d0 = ImageDraw.Draw(Image.new('L', (1, 1))); pad, left = 30, (92 if icon else 44)
    while fs > 30 and d0.textlength(text, font=font(fs)) + left + 44 > maxw: fs -= 2
    w, h = int(d0.textlength(text, font=font(fs))) + left + 44, 104
    base = Image.new('RGBA', (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    gl = Image.new('RGBA', base.size, accent + (0,)); ImageDraw.Draw(gl).rounded_rectangle((pad, pad, pad + w, pad + h), radius=h // 2, fill=accent + (150,))
    base = Image.alpha_composite(base, gl.filter(ImageFilter.GaussianBlur(14)))
    d = ImageDraw.Draw(base)
    d.rounded_rectangle((pad, pad, pad + w, pad + h), radius=h // 2, fill=fill or (10, 14, 32, 215), outline=lighten(accent, 0.2) + (235,), width=3)
    d.arc((pad + 6, pad + 6, pad + w - 6, pad + h - 6), 200, 320, fill=(255, 255, 255, 90), width=2)
    if icon:
        cx, cy = pad + 52, pad + h // 2
        d.ellipse((cx - 28, cy - 28, cx + 28, cy + 28), fill=accent + (255,))
        d.line([(cx - 13, cy + 1), (cx - 3, cy + 12), (cx + 15, cy - 11)], fill=(255, 255, 255, 255), width=7, joint='curve')
    d.text((pad + left, pad + h / 2 + 2), text, font=font(fs), fill=(255, 255, 255, 255), anchor='lm')
    return base


def cta_button(text, c1, c2, maxw=960):
    d0 = ImageDraw.Draw(Image.new('L', (1, 1))); fs = 54
    while fs > 30 and d0.textlength(text, font=font(fs)) + 120 > maxw: fs -= 2
    w, h, pad = int(d0.textlength(text, font=font(fs))) + 120, 118, 40
    g = np.linspace(0, 1, w, dtype=np.float32)[None, :, None]
    col = (np.array(lighten(c1, 0.1), np.float32) * (1 - g) + np.array(lighten(c2, 0.1), np.float32) * g)
    grad = Image.fromarray(np.repeat(col, h, axis=0).astype(np.uint8), 'RGB')
    m = Image.new('L', (w, h), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=255)
    base = Image.new('RGBA', (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    gl = Image.new('RGBA', base.size, c1 + (0,)); ImageDraw.Draw(gl).rounded_rectangle((pad, pad, pad + w, pad + h), radius=h // 2, fill=c1 + (190,))
    base = Image.alpha_composite(base, gl.filter(ImageFilter.GaussianBlur(18)))
    btn = Image.new('RGBA', (w, h), (0, 0, 0, 0)); btn.paste(grad, (0, 0), m)
    d = ImageDraw.Draw(btn); d.rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, outline=(255, 255, 255, 230), width=4)
    d.text((w / 2 + 2, h / 2 + 5), text, font=font(fs), fill=(0, 0, 0, 90), anchor='mm')
    d.text((w / 2, h / 2 + 2), text, font=font(fs), fill=(255, 255, 255, 255), anchor='mm')
    base.alpha_composite(btn, (pad, pad)); return base, m, pad


def char_sprites(ch, f, accent):
    """Tiga versi huruf: tajam bergradien + cahaya, kabur (untuk awal animasi), dan terang (untuk kilau)."""
    d0 = ImageDraw.Draw(Image.new('L', (1, 1))); pad = 26
    size = (int(d0.textlength(ch, font=f)) + 2 * pad, int(f.size * 1.3) + 2 * pad)
    m = Image.new('L', size, 0); ImageDraw.Draw(m).text((pad, pad), ch, font=f, fill=255)
    g = np.linspace(0, 1, size[1], dtype=np.float32)[:, None, None]
    top, bot = np.array((255, 255, 255), np.float32), np.array(lighten(accent, 0.55), np.float32)
    grad = Image.fromarray(np.repeat((top * (1 - g) + bot * g), size[0], axis=1).astype(np.uint8), 'RGB')
    gl = Image.new('RGBA', size, accent + (0,)); gl.putalpha(m.filter(ImageFilter.GaussianBlur(11)).point(lambda v: min(255, int(v * 2.2))))
    sharp = Image.new('RGBA', size, (0, 0, 0, 0)); sharp.paste(grad, (0, 0), m); sharp = Image.alpha_composite(gl, sharp)
    bright = Image.new('RGBA', size, (0, 0, 0, 0)); bright.paste(Image.new('RGB', size, lighten(accent, 0.75)), (0, 0), m)
    bright = Image.alpha_composite(gl, bright)
    return sharp, sharp.filter(ImageFilter.GaussianBlur(10)), bright, pad


# ---------------------------------------------------------------- aurora
GW, GH = 108, 192
_X = np.linspace(0, 1, GW, dtype=np.float32)[None, :]
_Y = np.linspace(0, 1, GH, dtype=np.float32)[:, None]
_VIG = np.clip(1.08 - np.clip(np.hypot((_X - 0.5) / 0.5, (_Y - 0.5) / 0.5) - 0.5, 0, 2) * 0.75, 0.25, 1).astype(np.float32)


def aurora_img(t, cols, ph0, gain):
    out = np.zeros((GH, GW, 3), np.float32)
    for k, col in enumerate(cols):
        ph = ph0 * 1.3 + k * 2.1
        cy = 0.26 + 0.17 * k + 0.07 * np.sin(_X * (5.0 + k) + t * (0.5 + 0.18 * k) + ph) + 0.045 * np.sin(_X * 11 - t * 0.8 + ph * 1.7)
        wd = 0.085 + 0.035 * np.sin(_X * 3 + t * 0.4 + ph)
        a = np.exp(-((_Y - cy) / wd) ** 2) * (0.62 + 0.38 * np.sin(_X * 24 + t * 1.1 + k * 3 + ph) ** 2)  # tirai bergaris vertikal
        out += a[:, :, None] * (np.array(col, np.float32) / 255.0)[None, None, :]
    low = np.exp(-((1 - _Y) / 0.2) ** 2) * (0.5 + 0.2 * math.sin(t * 0.9))  # cahaya horizon di bawah
    out += low[:, :, None] * (np.array(cols[0], np.float32) / 255.0)[None, None, :] * 0.28
    out = (1 - np.exp(-out * 1.7 * gain)) * _VIG[:, :, None]
    return Image.fromarray((out * 255).astype(np.uint8), 'RGB').resize((W // 2, H // 2), Image.BICUBIC)


# ---------------------------------------------------------------- tema
class Theme:
    def __init__(self, p, photos, scenes, total):
        self.p, self.sc, self.total = p, scenes, total
        d0 = ImageDraw.Draw(Image.new('L', (1, 1)))
        self.assets = []
        for pth in photos:
            im = Image.open(pth).convert('RGB'); cols = palette(im)
            self.assets.append(self.build_asset(im, cols))
        self.foil = make_foil()
        self.pn = None
        m = re.fullmatch(r'Rp([\d.]+)', p['price'].strip())
        if m: self.pn = int(m.group(1).replace('.', ''))
        self.lines = [wrap_words(d0, s['text'], font(54), 880) for s in scenes]
        pr_ = random.Random(9); self.parts = []
        for _ in range(64):
            z = pr_.uniform(0.15, 1.0)
            self.parts.append((pr_.uniform(0, W), pr_.uniform(0, H), z, pr_.uniform(-12, 12) * z, pr_.uniform(26, 90) * z, pr_.uniform(0, 6.28), pr_.randrange(4)))
        # judul pembuka: per huruf
        name = p['name'][:100]; f, ty0, step = font(68), 250, 92
        allw = wrap_words(d0, name, f, 940)
        if len(allw) > 2: f, ty0, step = font(58), 238, 78; allw = wrap_words(d0, name, f, 940)  # judul panjang: lebih kecil, tidak menyentuh kartu
        self.tlines = allw[:3]
        if len(allw) > 3:
            l3 = list(self.tlines[2])
            while len(l3) > 1 and d0.textlength(' '.join(l3) + '…', font=f) > 940: l3 = l3[:-1]
            l3[-1] += '…'; self.tlines[2] = l3
        self.chars = []
        c0 = self.assets[0]['cols'][0]
        for n, ln in enumerate(self.tlines):
            txt = ' '.join(ln); x0 = (W - d0.textlength(txt, font=f)) / 2
            for k, ch in enumerate(txt):
                if ch == ' ': continue
                sh, bl, br, pad = char_sprites(ch, f, c0)
                x = x0 + d0.textlength(txt[:k], font=f)
                self.chars.append((sh, bl, br, int(x) - pad, ty0 + n * step - pad, x + d0.textlength(ch, font=f) / 2))
        self.kick = glass_chip('REKOMENDASI HARI INI', c0, 800, 44, icon=False)
        # judul kecil untuk adegan berikutnya (maks 2 baris)
        hl = [' '.join(l) for l in wrap_words(d0, name, font(42), 800)]
        if len(hl) > 2:
            hl = hl[:2]
            while len(hl[1]) > 4 and d0.textlength(hl[1] + '…', font=font(42)) > 800: hl[1] = hl[1][:-1]
            hl[1] = hl[1].rstrip() + '…'
        self.head = self.head_chip(hl, c0)
        self.points = {}
        for s in scenes:
            if s['badge'] is not None and s['badge'] < len(p['points']): self.points[s['badge']] = p['points'][s['badge']][:60]

    # -------------------------------------------------------- aset per foto
    def build_asset(self, im, cols):
        s = max(648 / im.width, 1152 / im.height); b = im.resize((int(im.width * s) + 1, int(im.height * s) + 1))
        x, y = (b.width - 648) // 2, (b.height - 1152) // 2; b = b.crop((x, y, x + 648, y + 1152))
        b = b.resize((162, 288), Image.BILINEAR).filter(ImageFilter.GaussianBlur(5)).resize((648, 1152), Image.BILINEAR)
        bg = Image.blend(b.point(lambda v: int(v * 0.42)), Image.new('RGB', b.size, (5, 7, 20)), 0.55)
        yy, xx = np.mgrid[0:1152, 0:648].astype(np.float32); vg = np.clip(1.05 - np.clip(np.hypot((xx - 324) / 324, (yy - 576) / 576) - 0.5, 0, 2) * 0.7, 0.3, 1)
        bg = Image.fromarray((np.asarray(bg, np.float32) * vg[:, :, None]).astype(np.uint8), 'RGB')
        k = min(800 / im.width, 900 / im.height)
        ph = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS)
        mg, S = 22, 64; pw, phh = ph.width + 2 * mg, ph.height + 2 * mg
        sp = Image.new('RGBA', (pw + 2 * S, phh + 2 * S), (0, 0, 0, 0))
        sh = Image.new('RGBA', sp.size, cols[0] + (0,)); ImageDraw.Draw(sh).rounded_rectangle((S, S + 18, S + pw, S + phh + 18), radius=40, fill=cols[0] + (140,))
        sp = Image.alpha_composite(sp, sh.filter(ImageFilter.GaussianBlur(34)))
        dk = Image.new('RGBA', sp.size, (0, 0, 0, 0)); ImageDraw.Draw(dk).rounded_rectangle((S + 6, S + 26, S + pw + 6, S + phh + 26), radius=38, fill=(0, 0, 0, 120))
        sp = Image.alpha_composite(sp, dk.filter(ImageFilter.GaussianBlur(20)))
        gl = Image.new('RGBA', sp.size, (0, 0, 0, 0)); gd = ImageDraw.Draw(gl)
        gd.rounded_rectangle((S, S, S + pw, S + phh), radius=38, fill=(255, 255, 255, 46), outline=(255, 255, 255, 120), width=3)  # pelat kaca
        gd.arc((S + 5, S + 5, S + pw - 5, S + phh - 5), 190, 300, fill=(255, 255, 255, 170), width=3)  # kilau tepi
        sp = Image.alpha_composite(sp, gl)
        mk = Image.new('L', ph.size, 0); ImageDraw.Draw(mk).rounded_rectangle((0, 0, ph.width - 1, ph.height - 1), radius=26, fill=255)
        sp.paste(ph, (S + mg, S + mg), mk)
        body = Image.new('L', sp.size, 0); ImageDraw.Draw(body).rounded_rectangle((S, S, S + pw, S + phh), radius=38, fill=255)
        scan = Image.new('RGBA', (pw, 170), (0, 0, 0, 0)); sa = np.linspace(0, 1, 170, dtype=np.float32) ** 2.2
        arr = np.zeros((170, pw, 4), np.uint8); arr[..., :3] = lighten(cols[0], 0.5); arr[..., 3] = (sa[:, None] * 130).astype(np.uint8)
        scan = Image.fromarray(arr, 'RGBA')
        return {'bg': bg, 'cols': cols, 'sprite': sp, 'rgb': sp.convert('RGB'), 'body': body, 'pw': pw, 'ph': phh, 'scan': scan,
                'hud': (make_hud(580, 285, lighten(cols[0], 0.2), 1, 2), make_hud(490, 235, lighten(cols[1], 0.2), 2, 2)),
                'ring': make_coin_ring(300, cols)}

    def head_chip(self, lines, accent):
        d0 = ImageDraw.Draw(Image.new('L', (1, 1))); f = font(42)
        w = int(max(d0.textlength(l, font=f) for l in lines)) + 110; h = len(lines) * 52 + 34; pad = 26
        base = Image.new('RGBA', (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0)); d = ImageDraw.Draw(base)
        d.rounded_rectangle((pad, pad, pad + w, pad + h), radius=min(40, h // 2), fill=(10, 14, 32, 190), outline=lighten(accent, 0.2) + (210,), width=3)
        d.ellipse((pad + 26, pad + h / 2 - 9, pad + 44, pad + h / 2 + 9), fill=accent + (255,))
        for n, l in enumerate(lines): d.text((pad + 66, pad + 18 + n * 52), l, font=f, fill=(255, 255, 255, 255))
        return base

    def scene_at(self, t):
        for i, s in enumerate(self.sc):
            if t < s['t0'] + s['dur']: return i
        return len(self.sc) - 1

    def bg(self, ass, local, dur, t):
        z = 1 + 0.08 * clamp(local / dur) + 0.05 * (1 - eo(local / 0.4))
        cw, ch = 648 / (1.2 * z), 1152 / (1.2 * z); cx, cy = 324 + 15 * math.sin(t * 0.45), 576 + 13 * math.cos(t * 0.35)
        return ass['bg'].crop((int(cx - cw / 2), int(cy - ch / 2), int(cx + cw / 2), int(cy + ch / 2))).resize((W // 2, H // 2), Image.BILINEAR)

    # -------------------------------------------------------- efek
    def particles(self, fr, t, cols):
        cs = [lighten(c, 0.45) for c in cols] + [(255, 255, 255)]
        for x0, y0, z, vx, vy, ph, ci in self.parts:
            x, y = (x0 + vx * t) % W, (y0 - vy * t) % H
            tw = 0.5 + 0.5 * math.sin(t * 2.2 + ph); lv = (0.3 + 0.7 * z) * (0.35 + 0.65 * tw)
            r = int(4 + 15 * z); sp = glow(r, cs[ci], 255 * round(lv * 4) / 4 or 64, 1.8)
            fr.paste(sp, (int(x - r), int(y - r)), sp)

    def burst(self, fr, t, ox, oy, seed, cols, n=50, life=1.4, power=1.0):
        if t < 0 or t > life: return
        rng = random.Random(seed); k = (1 - math.exp(-3.4 * t)) / 3.4; cs = [lighten(c, 0.5) for c in cols] + [(255, 255, 255)]
        for _ in range(n):
            a, v, col = rng.uniform(0, 6.2832), rng.uniform(260, 880) * power, rng.choice(cs)
            x, y = ox + math.cos(a) * v * k, oy + math.sin(a) * v * k + 420 * t * t
            r = int(rng.uniform(5, 13) * clamp((life - t) / 0.5))
            if r < 2: continue
            sp = glow(r, col, 255, 1.5); fr.paste(sp, (int(x - r), int(y - r)), sp)

    def coin(self, ass, t1, t, pulse):
        S = 300; im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.ellipse((8, 8, S - 8, S - 8), fill=(8, 10, 26, 232))
        im = Image.alpha_composite(im, ass['ring'].rotate(-t * 70, resample=Image.BILINEAR)); d = ImageDraw.Draw(im)
        d.ellipse((30, 30, S - 30, S - 30), outline=(255, 255, 255, 70), width=2)
        price = self.p['price'][:20]
        if self.pn is not None and t1 < 0.9: price = 'Rp' + f'{int(self.pn * eo(t1 / 0.9)):,}'.replace(',', '.')
        ref = self.p['price'][:20]; sz = 72
        while sz > 26 and d.textlength(ref, font=font(sz)) > S - 96: sz -= 3
        d.text((S / 2, 92), 'HARGA', font=font(34), fill=(255, 255, 255, 190), anchor='mm')
        d.text((S / 2 + 2, S / 2 + 30), price, font=font(sz), fill=(0, 0, 0, 110), anchor='mm')
        d.text((S / 2, S / 2 + 27), price, font=font(sz), fill=(255, 241, 190, 255), anchor='mm')
        return im

    def brackets(self, fr, cx, cy, pw, ph, local, cols, pulse):
        q = eo((local - 0.5) / 0.45)
        if q <= 0: return
        pad = 16 + (1 - q) * 120 + 3 * pulse; L, wd = 76, 9; x0, y0, x1, y1 = cx - pw / 2 - pad, cy - ph / 2 - pad, cx + pw / 2 + pad, cy + ph / 2 + pad
        bx, by = int(x0 - 24), int(y0 - 24); lay = Image.new('RGBA', (int(x1 - x0) + 48, int(y1 - y0) + 48), (0, 0, 0, 0)); d = ImageDraw.Draw(lay); a = int(255 * clamp(q * 1.4))
        col = lighten(cols[0], 0.6) + (a,)
        for (px, py, sx, sy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
            px, py = px - bx, py - by
            d.line([(px, py + sy * L), (px, py), (px + sx * L, py)], fill=col, width=wd, joint='curve')
            d.ellipse((px - 9, py - 9, px + 9, py + 9), fill=(255, 255, 255, a))
        fr.paste(lay, (bx, by), lay)

    def scanline(self, fr, ass, cx, cy, local):
        p = (local - 0.55) / 0.75
        if not 0 <= p <= 1: return
        pw, ph = ass['pw'], ass['ph']; top, bot = cy - ph / 2, cy + ph / 2; y = top + (bot - top) * eio(p)
        tr = ass['scan']; h0 = max(0, int(top - (y - 170))); sub = tr.crop((0, h0, pw, 170))
        if sub.height > 0: fr.paste(sub, (int(cx - pw / 2), int(max(top, y - 170))), sub)
        ln = Image.new('RGBA', (pw, 14), (255, 255, 255, 0)); dd = ImageDraw.Draw(ln)
        dd.rectangle((0, 5, pw, 8), fill=(255, 255, 255, int(255 * math.sin(math.pi * p))))
        ln = ln.filter(ImageFilter.GaussianBlur(1.5)); fr.paste(ln, (int(cx - pw / 2), int(y - 7)), ln)

    def card(self, ass, local, t, k_fade):
        sp = ass['sprite']; rgb = ass['rgb']; body = ass['body']
        ox = int(min(max(0, 220 + 170 * math.sin(t * 0.7)), self.foil.width - sp.width))
        oy = int(min(max(0, 300 + 150 * math.cos(t * 0.55)), self.foil.height - sp.height))
        foil = self.foil.crop((ox, oy, ox + sp.width, oy + sp.height))
        hm = body.point(lut(0.16))  # sheen pelangi tipis di seluruh kartu
        ps = ((local - 0.45) % 2.8) / 0.75  # pita hologram + kilau menyapu berkala
        band = None
        if 0 <= ps <= 1:
            cw, chh = sp.size; x = -300 + ps * (cw + 600); band = Image.new('L', sp.size, 0); dd = ImageDraw.Draw(band)
            dd.polygon([(x + 300, 0), (x + 480, 0), (x + 180, chh), (x, chh)], fill=70)
            dd.polygon([(x + 350, 0), (x + 420, 0), (x + 120, chh), (x + 50, chh)], fill=200)
            hm = ImageChops.lighter(hm, ImageChops.multiply(band.filter(ImageFilter.GaussianBlur(18)).point(lambda v: min(255, v * 2)), body).point(lut(0.8)))
        rgb = Image.composite(ImageChops.soft_light(rgb, foil), rgb, hm)
        if band is not None:
            rgb = Image.composite(Image.new('RGB', sp.size, (255, 255, 255)), rgb, ImageChops.multiply(band, body).point(lut(0.55)))
        out = rgb.convert('RGBA'); a = sp.getchannel('A')
        out.putalpha(a if k_fade >= 0.99 else a.point(lut(k_fade)))
        return out

    def subtitle(self, fr, lines, s, local, acc):
        words = [w for ln in lines for w in ln]; total_c = max(1, sum(len(w) + 1 for w in words))
        prog = clamp((local - s['lead']) / max(0.1, s['vd'])); cur = acc_c = 0
        for n, w in enumerate(words):
            acc_c += len(w) + 1
            if acc_c / total_c <= prog + 0.001: cur = n + 1
        lh = 68; bh = len(lines) * lh + 52; a = clamp(local / 0.25); A = lambda v: int(v * a)
        ov = Image.new('RGBA', (W, bh), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
        od.rounded_rectangle((70, 0, W - 70, bh - 1), radius=38, fill=(8, 10, 24, A(185)), outline=(255, 255, 255, A(40)), width=2)
        od.rounded_rectangle((100, bh - 16, 100 + max(8, int((W - 200) * prog)), bh - 10), radius=3, fill=lighten(acc, 0.15) + (A(255),))
        gl = Image.new('RGBA', (W, bh), (0, 0, 0, 0)); gd = ImageDraw.Draw(gl); n = 0; f = font(54)
        for r, ln in enumerate(lines):
            x = (W - od.textlength(' '.join(ln), font=f)) / 2
            for w in ln:
                if n == cur: gd.text((x, 18 + r * lh), w, font=f, fill=lighten(acc, 0.25) + (255,))
                x += od.textlength(w + ' ', font=f); n += 1
        gl = gl.filter(ImageFilter.GaussianBlur(11)); ov = Image.alpha_composite(ov, gl); n = 0
        od = ImageDraw.Draw(ov)
        for r, ln in enumerate(lines):
            x = (W - od.textlength(' '.join(ln), font=f)) / 2
            for w in ln:
                if n < cur: col = (255, 255, 255, A(255))
                elif n == cur: col = lighten(acc, 0.3) + (A(255),)
                else: col = (255, 255, 255, A(120))
                od.text((x, 18 + r * lh), w, font=f, fill=col); x += od.textlength(w + ' ', font=f); n += 1
        fr.paste(ov, (0, 1655 - bh + int((1 - eo(local / 0.3)) * 40)), ov)

    def chroma(self, fr, px):
        if px < 1: return fr
        r, g, b = fr.split()
        return Image.merge('RGB', (ImageChops.offset(r, px, 0), g, ImageChops.offset(b, -px, 0)))

    # -------------------------------------------------------- frame
    def frame(self, t):
        i = self.scene_at(t); s = self.sc[i]; local = t - s['t0']; dur = s['dur']; last = i == len(self.sc) - 1
        n = len(self.assets); ass = self.assets[i % n]; cols = ass['cols']; acc = cols[0]
        pulse = math.exp(-((t % BEAT) / BEAT) * 5.0)
        # latar + aurora (palet bercampur halus saat pergantian adegan)
        bg = self.bg(ass, local, dur, t); ce = cols
        if i > 0 and local < 0.45 and n > 1:
            pv = self.assets[(i - 1) % n]; k = eo(local / 0.45); ce = [mixc(a, b, k) for a, b in zip(pv['cols'], cols)]
            bg = Image.blend(self.bg(pv, self.sc[i - 1]['dur'], self.sc[i - 1]['dur'], t), bg, k)
        fr = ImageChops.screen(bg, aurora_img(t, ce, i, 1.0 + 0.3 * pulse)).resize((W, H), Image.BILINEAR)
        cx0, cy0 = W / 2, 955
        # cincin HUD berputar
        k_hud = eo(local / 0.7) * 0.85
        h1, h2 = ass['hud']
        for im, ang in ((h1, t * 9), (h2, -t * 14)):
            r = im.rotate(ang, resample=Image.BILINEAR).resize((im.width * 2, im.height * 2), Image.BILINEAR)
            pa(fr, r, (cx0 - r.width / 2, cy0 - r.height / 2), k_hud)
        self.particles(fr, t, cols)
        pool = glow(450, acc, 140, 2.0).resize((960, 300), Image.BILINEAR); pa(fr, pool, (cx0 - 480, cy0 + 335), 0.8 + 0.2 * pulse)

        # kartu 3D: gaya masuk berganti tiap adegan
        sgn = 1 if i % 2 == 0 else -1; e = eb(local / 0.7); cx, cy = cx0, cy0 + 12 * math.sin(2 * math.pi * local / 2.6)
        sway = math.radians(8) * math.sin(2 * math.pi * local / 3.4 + i) * eo(local / 0.9)
        theta, phi, scl = sway, math.radians(3) * math.sin(2 * math.pi * local / 2.9), 1.0; style = i % 4
        if style == 0: scl = 0.45 + 0.55 * e; theta = -sgn * (1 - e) * math.radians(75) + sway
        elif style == 1: cx += sgn * (1 - e) * 900; theta = -sgn * (1 - e) * math.radians(40) + sway * 0.6
        elif style == 2: cy -= (1 - e) * 900; phi += -(1 - e) * math.radians(38)
        else: scl = 1.6 - 0.6 * eo(local / 0.6); phi += (1 - eo(local / 0.6)) * math.radians(12)
        scl *= 1 + 0.006 * pulse; k_fade = eo(local / 0.3)
        if not last and local > dur - 0.25:
            x = eo((local - (dur - 0.25)) / 0.25); scl *= 1 + 0.18 * x; k_fade *= 1 - x
        layer, pos = warp(self.card(ass, local, t, k_fade), theta, phi, scl, cx, cy)
        fr.paste(layer, pos, layer)
        if local > 0.5 and k_fade > 0.9:
            self.brackets(fr, cx, cy, ass['pw'] * scl, ass['ph'] * scl, local, cols, pulse)
            self.scanline(fr, ass, cx, cy, local)

        # koin harga holografik
        if i >= 1:
            t1 = t - (self.sc[1]['t0'] + 0.35)
            if t1 > 0:
                kk = 0.9 * eb(t1 / 0.5)
                if kk > 0.03:
                    cxx = min(W - 175, cx0 + ass['pw'] / 2 - 20); cyy = max(540, cy0 - ass['ph'] / 2 + 70)
                    halo = glow(210, acc, 200, 1.8); pa(fr, halo, (cxx - 210, cyy - 210), (0.55 + 0.25 * pulse) * min(1, kk))
                    coin = self.coin(ass, t1, t, pulse).rotate(5 * math.sin(2 * math.pi * t1 / 2.8) * eo(t1 / 0.8), resample=Image.BICUBIC)
                    sz = max(2, int(300 * kk * (1 + 0.025 * pulse))); coin = coin.resize((sz, sz), Image.BILINEAR)
                    fr.paste(coin, (int(cxx - sz / 2), int(cyy - sz / 2)), coin)
                    self.burst(fr, t1, cxx, cyy, 2, cols, n=36, life=1.1, power=0.75)

        # chip keunggulan / tombol link
        tb = local - 0.5
        if last and tb > 0:
            if not hasattr(self, '_cta'): self._cta = cta_button('LINK DI KOMENTAR PERTAMA', cols[0], cols[1])
            sp, m, pad = self._cta; a = eb(tb / 0.45); sc2 = (1 + 0.04 * math.sin(2 * math.pi * tb / 1.0)) * clamp(a, 0, 1.1)
            lay = sp.copy(); sh = (tb * 0.9 % 1.6) * (m.width + 400) - 200; band = Image.new('L', m.size, 0)
            ImageDraw.Draw(band).polygon([(sh, 0), (sh + 90, 0), (sh + 20, m.height), (sh - 70, m.height)], fill=150)
            white = Image.new('RGBA', m.size, (255, 255, 255, 0)); white.putalpha(ImageChops.multiply(band, m)); lay.alpha_composite(white, (pad, pad))
            if abs(sc2 - 1) > 0.002: lay = lay.resize((int(lay.width * sc2), int(lay.height * sc2)), Image.BILINEAR)
            fr.paste(lay, (int(W / 2 - lay.width / 2), int(1337 - lay.height / 2)), lay)
            if local > 0.7:  # panah ke bawah
                dd = ImageDraw.Draw(fr)
                for j in range(3):
                    b = max(0.0, math.sin(math.pi * ((tb * 2.2 - j * 0.22) % 1.0))); y = 1430 + j * 28 + 6 * math.sin(t * 6)
                    dd.line([(494, y), (540, y + 26), (586, y)], fill=(255, int(150 + 105 * b), int(200 + 55 * b)), width=11, joint='curve')
            self.burst(fr, tb, W / 2, 1337, 3, cols, n=64, life=1.5, power=1.15)
        elif not last and s['badge'] is not None and s['badge'] in self.points and tb > 0:
            key = ('chip', id(ass), s['badge'])
            if key not in _G: _G[key] = glass_chip(self.points[s['badge']], acc)
            ch = _G[key]; a = eb(tb / 0.45)
            fr.paste(ch, (int(W / 2 - ch.width / 2), int(1285 - 26 + (1 - clamp(a, 0, 1)) * 150)), ch) if a > 0.02 else None

        self.subtitle(fr, self.lines[i], s, local, acc)

        # judul
        if i == 0:
            a = eb(local / 0.6); pa(fr, self.kick, ((W - self.kick.width) / 2, 84 - (1 - clamp(a, 0, 1)) * 80), clamp(a * 1.2))
            sx = -150 + (local - 1.3) / 0.9 * (W + 300)
            for k, (sh, bl, br, x, y, cxm) in enumerate(self.chars):
                p = clamp((local - 0.25 - 0.035 * k) / 0.5)
                if p <= 0: continue
                dy = int((1 - eo(p)) * 70); sc3 = 1 + (1 - eo(p)) * 0.7
                if sc3 > 1.005:
                    sh2 = sh.resize((int(sh.width * sc3), int(sh.height * sc3)), Image.BILINEAR); bl2 = bl.resize(sh2.size, Image.BILINEAR)
                    ox, oy = x - (sh2.width - sh.width) // 2, y - (sh2.height - sh.height) // 2 + dy
                else: sh2, bl2, ox, oy = sh, bl, x, y
                pa(fr, bl2, (ox, oy), (1 - p) * 0.9); pa(fr, sh2, (ox, oy), p)
                if p >= 1 and 0 < local - 1.3 < 1.0:
                    kb = clamp(1 - abs(cxm - sx) / 170) * 0.85
                    if kb > 0.02: pa(fr, br, (x, y), kb)
            self.burst(fr, local - 0.55, W / 2, 320, 1, cols, n=44, life=1.3)
        else:
            pa(fr, self.head, ((W - self.head.width) / 2, 150 + (1 - eo(local / 0.4)) * -40), eo(local / 0.35))

        # transisi: kilatan, gelombang kejut, goresan lensa, aberasi kromatik
        if i > 0 and local < 0.5:
            f = clamp(1 - local / 0.22)
            if f > 0: fr.paste((255, 255, 255), (0, 0), Image.new('L', (W, H), int(85 * f * f)))
            R = 120 + 900 * eo(local / 0.5); lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); dd = ImageDraw.Draw(lay)
            for wdt, al in ((30, 40), (14, 90), (5, 230)):
                dd.ellipse((cx0 - R, cy0 - R, cx0 + R, cy0 + R), outline=lighten(acc, 0.6) + (int(al * (1 - local / 0.5)),), width=wdt)
            fr.paste(lay, (0, 0), lay)
            sw = int(W * 1.3 * eo(local / 0.35)); st = Image.new('RGBA', (max(2, sw), 40), (0, 0, 0, 0)); ImageDraw.Draw(st).rectangle((0, 16, st.width, 22), fill=(255, 255, 255, 255))
            st = st.filter(ImageFilter.GaussianBlur(5)); pa(fr, st, (cx0 - st.width / 2, cy0 - 20), 1 - local / 0.5)
            fr = self.chroma(fr, int(20 * (1 - local / 0.4) ** 2) if local < 0.4 else 0)
        elif not last and local > dur - 0.18:
            fr = self.chroma(fr, int(16 * eo((local - (dur - 0.18)) / 0.18)))

        # bar kemajuan
        d = ImageDraw.Draw(fr); d.rounded_rectangle((60, 70, W - 60, 78), radius=4, fill=(255, 255, 255))
        xw = 60 + max(8, int((W - 120) * t / self.total))
        d.rounded_rectangle((60, 70, xw, 78), radius=4, fill=lighten(acc, 0.1))
        hg = glow(26, (255, 255, 255), 230, 1.6); fr.paste(hg, (xw - 26, 74 - 26), hg)
        return fr
