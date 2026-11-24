"""Tema Studio 3D: semua elemen diproyeksikan dengan perspektif kamera sungguhan.
Kartu foto bertebal (coverflow) + pantulan lantai, teks timbul, plat harga yang berputar,
lantai grid perspektif, kubus dan oktahedron melayang. Warna aksen diambil dari foto."""
import math, colorsys, random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from themes._base import W, H, FPS, SR, font, clamp, eo, wrap_words

INFO = {'name': 'Studio 3D', 'desc': 'Visual 3D penuh: kartu foto tebal berputar dengan pantulan lantai, teks timbul, grid perspektif, bentuk 3D melayang.'}

F = 1400.0          # jarak fokus kamera
FLOOR = 250.0       # tinggi lantai (sumbu y ke bawah)
MX = 80
SUB_BOTTOM = 1630
LIGHT = np.array([-0.4, -0.6, -0.7]); LIGHT /= np.linalg.norm(LIGHT)
CARD_Y = -230.0
CARD_T = 26.0
_R = {}


def font_r(sz):
    if sz not in _R:
        try: _R[sz] = ImageFont_truetype(sz)
        except Exception: _R[sz] = font(sz)
    return _R[sz]


def ImageFont_truetype(sz):
    from PIL import ImageFont
    return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', sz)


def eio(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------ matematika 3D
def rotm(rx, ry, rz):
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def proj(p, camx):
    s = F / np.maximum(F + p[..., 2], 60.0)
    return W / 2 + (p[..., 0] - camx) * s, H / 2 + p[..., 1] * s, s


def at(sx, sy, z, camx):
    """Koordinat dunia agar titik jatuh di (sx, sy) layar pada kedalaman z."""
    s = F / (F + z)
    return ((sx - W / 2) / s + camx, (sy - H / 2) / s, z)


def coeffs(out, inp):
    A, B = [], []
    for (x, y), (u, v) in zip(out, inp):
        A.append([x, y, 1, 0, 0, 0, -x * u, -y * u]); B.append(u)
        A.append([0, 0, 0, x, y, 1, -x * v, -y * v]); B.append(v)
    return np.linalg.solve(np.array(A, float), np.array(B, float))


def warp(tex, P):
    xs, ys = [p[0] for p in P], [p[1] for p in P]
    x0, y0 = int(math.floor(min(xs))) - 2, int(math.floor(min(ys))) - 2
    bw, bh = int(math.ceil(max(xs))) + 2 - x0, int(math.ceil(max(ys))) + 2 - y0
    if bw < 3 or bh < 3 or bw > 3200 or bh > 3200: return None
    tw, th = tex.size
    try: c = coeffs([(p[0] - x0, p[1] - y0) for p in P], [(0, 0), (tw, 0), (tw, th), (0, th)])
    except np.linalg.LinAlgError: return None
    return tex.transform((bw, bh), Image.PERSPECTIVE, tuple(c), Image.BILINEAR), x0, y0


def poly(fr, pts, fill, alpha=1.0):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, y0 = int(min(xs)) - 1, int(min(ys)) - 1
    bw, bh = int(max(xs)) + 2 - x0, int(max(ys)) + 2 - y0
    if bw <= 0 or bh <= 0 or bw > 3200 or bh > 3200: return
    m = Image.new('L', (bw * 3, bh * 3), 0)
    ImageDraw.Draw(m).polygon([((x - x0) * 3, (y - y0) * 3) for x, y in pts], fill=255)
    m = m.resize((bw, bh), Image.BOX)
    if alpha < 1: m = m.point(lambda v: int(v * alpha))
    fr.paste(Image.new('RGB', (bw, bh), fill), (x0, y0), m)


def dim(img, k):
    if k >= 0.995: return img
    r, g, b, a = img.split()
    lut = [min(255, int(i * k)) for i in range(256)]
    return Image.merge('RGBA', (r.point(lut), g.point(lut), b.point(lut), a))


def fadea(img, k):
    if k >= 0.995: return img
    out = img.copy(); out.putalpha(img.getchannel('A').point(lambda v: int(v * clamp(k)))); return out


FACES = [((0, 1, 2, 3), (0, 0, -1)), ((4, 5, 6, 7), (0, 0, 1)), ((0, 1, 5, 4), (0, -1, 0)),
         ((3, 2, 6, 7), (0, 1, 0)), ((0, 3, 7, 4), (-1, 0, 0)), ((1, 2, 6, 5), (1, 0, 0))]


def slab(fr, tex, c, rot, T, camx, side, bright=1.0, tex_alpha=1.0):
    """Gambar papan 3D bertekstur: sisi tebal (bila T>0) lalu muka depan dengan perspektif."""
    tw, th = tex.size; hw, hh = tw / 2, th / 2
    loc = np.array([[-hw, -hh, 0], [hw, -hh, 0], [hw, hh, 0], [-hw, hh, 0],
                    [-hw, -hh, T], [hw, -hh, T], [hw, hh, T], [-hw, hh, T]], float)
    R = rotm(*rot); w = loc @ R.T + np.array(c, float)
    X, Y, S = proj(w, camx); P = list(zip(X, Y))
    cam = np.array([camx, 0, -F])
    if T > 0:
        vis = []
        for idx, n in FACES[2:]:
            nr = R @ np.array(n, float); ctr = w[list(idx)].mean(0)
            if nr @ (ctr - cam) < 0: vis.append((ctr[2], idx, nr))
        for _, idx, nr in sorted(vis, key=lambda a: -a[0]):
            k = (0.3 + 0.7 * max(0.0, nr @ LIGHT)) * bright
            poly(fr, [P[i] for i in idx], tuple(min(255, int(v * k)) for v in side))
    nr = R @ np.array([0, 0, -1.0]); ctr = w[:4].mean(0)
    if nr @ (ctr - cam) >= 0: return
    k = bright * (0.78 + 0.22 * max(0.0, nr @ LIGHT))
    r = warp(tex, P[:4])
    if not r: return
    img, x0, y0 = r
    img = fadea(dim(img, k), tex_alpha)
    fr.paste(img, (x0, y0), img)


def reflect(fr, tex, c, rot, camx, bright, fadeh=420):
    tw, th = tex.size; hw, hh = tw / 2, th / 2
    loc = np.array([[-hw, -hh, 0], [hw, -hh, 0], [hw, hh, 0], [-hw, hh, 0]], float)
    w = loc @ rotm(*rot).T + np.array(c, float); w[:, 1] = 2 * FLOOR - w[:, 1]
    X, Y, S = proj(w, camx)
    r = warp(tex, list(zip(X, Y)))
    if not r: return
    img, x0, y0 = r
    a = np.asarray(img.getchannel('A'), np.float32)
    ys = np.arange(a.shape[0]) + y0
    a *= (np.clip(1 - (ys - Y.min()) / (fadeh * float(S.mean())), 0, 1) * 0.34 * bright)[:, None]
    img = dim(img, 0.8); img.putalpha(Image.fromarray(a.astype(np.uint8)))
    fr.paste(img, (x0, y0), img)


# ------------------------------------------------------------------ bentuk 3D
def cube_faces():
    out = []
    for ax in range(3):
        for sg in (-1, 1):
            n = np.zeros(3); n[ax] = sg
            u = np.zeros(3); v = np.zeros(3); u[(ax + 1) % 3] = 1; v[(ax + 2) % 3] = 1
            out.append((n, np.array([n + u + v, n - u + v, n - u - v, n + u - v])))
    return out


def octa_faces():
    out = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                n = np.array([sx, sy, sz], float) / math.sqrt(3)
                out.append((n, np.array([[sx, 0, 0], [0, sy, 0], [0, 0, sz]], float) * 1.25))
    return out


MESH = {'cube': cube_faces(), 'octa': octa_faces()}


def sprite(kind, s, rot, color, ss=3):
    R = rotm(*rot); n = max(8, int(s * 2.8)); size = n * ss
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    items = []
    for nrm, q in MESH[kind]:
        nr = R @ nrm
        if nr[2] >= 0: continue
        pts = q @ R.T; items.append((pts[:, 2].mean(), nr, pts))
    for _, nr, pts in sorted(items, key=lambda a: -a[0]):
        k = 0.28 + 0.72 * max(0.0, nr @ LIGHT)
        col = tuple(min(255, int(c * k)) for c in color) + (255,)
        edge = tuple(min(255, int(c * k * 1.35 + 40)) for c in color) + (255,)
        d.polygon([(size / 2 + p[0] * s * ss, size / 2 + p[1] * s * ss) for p in pts], fill=col, outline=edge)
    return im.resize((n, n), Image.BOX)


# ------------------------------------------------------------------ warna, latar, tekstur
def hue_rgb(h, s=0.78, v=1.0):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))


def palette(im):
    px = list(im.convert('RGB').resize((24, 24)).getdata()); sc = []
    for r, g, b in px:
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        sc.append((s * v if v > 0.25 else 0, h))
    sc.sort(reverse=True)
    if sc[0][0] < 0.18: return 0.55
    hs = [h for _, h in sc[:40]]
    return (math.atan2(sum(math.sin(2 * math.pi * h) for h in hs), sum(math.cos(2 * math.pi * h) for h in hs)) / (2 * math.pi)) % 1.0


def make_bg(acc):
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    x = np.linspace(0, 1, W, dtype=np.float32)[None, :, None]
    a = np.array([5, 7, 18], np.float32) + (np.array([13, 16, 36], np.float32) - np.array([5, 7, 18], np.float32)) * y
    arr = np.broadcast_to(a, (H, W, 3)).copy()
    d2 = (((x - 0.5) * W / 650) ** 2 + ((y - 0.38) * H / 700) ** 2)
    arr += np.exp(-d2) * 0.30 * np.array(acc, np.float32) * 0.6
    arr += np.exp(-(((y * H - 1010) / 80) ** 2)) * 0.16 * np.array(acc, np.float32)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def make_card_tex(im):
    k = min(780 / im.width, 690 / im.height)
    ph = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS)
    pad, m = 12, 2
    cw, ch = ph.width + 2 * pad, ph.height + 2 * pad
    tex = Image.new('RGBA', (cw + 2 * m, ch + 2 * m), (0, 0, 0, 0))
    ImageDraw.Draw(tex).rounded_rectangle((m, m, m + cw - 1, m + ch - 1), radius=24, fill=(246, 248, 252, 255))
    mk = Image.new('L', ph.size, 0)
    ImageDraw.Draw(mk).rounded_rectangle((0, 0, ph.width - 1, ph.height - 1), radius=14, fill=255)
    tex.paste(ph, (m + pad, m + pad), mk)
    return tex


def sheen_tex(tex, pos):
    """Kilau cahaya diagonal yang menyapu permukaan kartu."""
    a = np.asarray(tex, np.float32); h, w = a.shape[:2]
    gx = np.arange(w, dtype=np.float32)[None, :] + np.arange(h, dtype=np.float32)[:, None] * 0.45
    band = np.exp(-(((gx - pos) / (0.07 * w)) ** 2)) * 0.5 * (a[..., 3] / 255.0)
    a[..., :3] += (255 - a[..., :3]) * band[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def spaced(d, xy, text, f, fill, gap=5):
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=f, fill=fill); x += d.textlength(ch, font=f) + gap
    return x


def text_img(txt, f, fill, pad=4):
    d0 = ImageDraw.Draw(Image.new('L', (1, 1)))
    l, t, r, b = d0.textbbox((0, 0), txt, font=f)
    im = Image.new('RGBA', (r - l + 2 * pad, b - t + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((pad - l, pad - t), txt, font=f, fill=fill + (255,))
    return im


def extrude(im, depth, col, dx=0.7, dy=1.0):
    """Teks timbul: salinan bertumpuk makin gelap ke belakang, lalu muka depan."""
    out = Image.new('RGBA', (im.width + int(depth * dx) + 4, im.height + int(depth * dy) + 4), (0, 0, 0, 0))
    a = im.getchannel('A')
    for k in range(depth, 0, -1):
        f = 0.4 + 0.6 * (1 - k / depth)
        ly = Image.new('RGBA', im.size, tuple(int(c * f) for c in col) + (255,)); ly.putalpha(a)
        out.alpha_composite(ly, (int(k * dx), int(k * dy)))
    out.alpha_composite(im, (0, 0))
    return out


def fit(txt, start, maxw, lo=22):
    d0 = ImageDraw.Draw(Image.new('L', (1, 1))); sz = start
    while sz > lo and d0.textlength(txt, font=font(sz)) > maxw: sz -= 2
    return font(sz)


def glass(w, h, border, fill=(12, 18, 38, 255), radius=26):
    m = 3; im = Image.new('RGBA', (w + 2 * m, h + 2 * m), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((m, m, m + w - 1, m + h - 1), radius=radius, fill=fill, outline=border + (255,), width=3)
    d.rounded_rectangle((m + 4, m + 4, m + w - 5, m + h // 2), radius=radius - 4, fill=(255, 255, 255, 14))
    return im


def make_title(name, acc):
    d0 = ImageDraw.Draw(Image.new('L', (1, 1)))
    lines = wrap_words(d0, name[:100], font(60), W - 150)
    over = len(lines) > 2; lines = lines[:2]
    if over: lines[-1] = lines[-1][:-1] + [lines[-1][-1].rstrip('.,;:') + '…']
    im = Image.new('RGBA', (W - 100, len(lines) * 76 + 10), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for n, ln in enumerate(lines):
        d.text((im.width / 2, 4 + n * 76), ' '.join(ln), font=font(60), fill=(255, 255, 255, 255), anchor='ma')
    return extrude(im, 16, tuple(int(c * 0.5) for c in acc))


def make_price(price, acc):
    w, h = 400, 136
    im = glass(w, h, acc); d = ImageDraw.Draw(im)
    spaced(d, (34, 22), 'HARGA', font(24), acc, gap=5)
    f = fit(price, 64, w - 70, 30)
    face = text_img(price, f, (255, 255, 255))
    im.alpha_composite(extrude(face, 8, tuple(int(c * 0.55) for c in acc)), (30, 56))
    return im


def make_point(text, acc):
    w, h = 480, 136
    im = glass(w, h, (120, 140, 175)); d = ImageDraw.Draw(im)
    cy = h // 2 + 3
    d.ellipse((30, cy - 30, 90, cy + 30), fill=(24, 170, 112, 255))
    d.line([(46, cy), (56, cy + 11), (76, cy - 12)], fill=(255, 255, 255, 255), width=7, joint='curve')
    sz = 36
    while True:
        lines = wrap_words(d, text[:90], font(sz), w - 130 - 24)
        if len(lines) <= 2 or sz <= 26: break
        sz -= 2
    lines = lines[:2]; lh = sz + 10; y0 = cy - len(lines) * lh / 2 + 2
    for n, ln in enumerate(lines):
        d.text((112, y0 + n * lh), ' '.join(ln), font=font(sz), fill=(255, 255, 255, 255))
    return im


def make_cta(acc):
    w, h = 880, 136
    im = glass(w, h, hue_rgb(0, 0, 1), fill=tuple(int(c * 0.9) for c in acc) + (255,))
    txt = 'LINK PRODUK ADA DI KOMENTAR PERTAMA'
    face = text_img(txt, fit(txt, 46, w - 90, 28), (255, 255, 255))
    im.alpha_composite(extrude(face, 8, tuple(int(c * 0.4) for c in acc)), (int((w - face.width) / 2) + 3, int((h - face.height) / 2) - 4))
    return im


# ------------------------------------------------------------------ tema
class Theme:
    def __init__(self, p, photos, scenes, total):
        self.p, self.sc, self.total = p, scenes, total
        self.assets = []
        for pth in photos:
            im = Image.open(pth).convert('RGB')
            h = palette(im); a = hue_rgb(h)
            self.assets.append({'bg': make_bg(a), 'tex': make_card_tex(im), 'acc': a, 'h': h})
        self.acc = self.assets[0]['acc']; self.h = self.assets[0]['h']
        acc = self.acc
        self.acc2 = hue_rgb(self.h + 0.12, 0.7, 1.0)
        self.title = make_title(p['name'], acc)
        self.price = make_price(p['price'][:20], acc)
        self.pts = p.get('points', [])
        self.cta = make_cta(acc)
        self.show, cur = [], 0
        for s in scenes:
            if s['badge'] is not None and s['badge'] < len(self.pts): cur = s['badge']
            self.show.append(cur)
        self.point = {k: make_point(self.pts[k], acc) for k in set(self.show)} if self.pts else {}
        d0 = ImageDraw.Draw(Image.new('L', (1, 1))); self.lines = []
        for s in scenes:
            sz = 48
            while True:
                ln = wrap_words(d0, s['text'], font(sz), W - 2 * MX - 80)
                if len(ln) <= 3 or sz <= 40: break
                sz -= 2
            self.lines.append((ln, sz))
        sh = Image.new('RGBA', (600, 140), (0, 0, 0, 0))
        ImageDraw.Draw(sh).ellipse((40, 30, 560, 110), fill=(0, 0, 0, 190))
        self.shadow = sh.filter(ImageFilter.GaussianBlur(18))
        rnd = random.Random(7)
        cols = [self.acc, self.acc2, (226, 232, 245), tuple(int(c * 0.6) for c in self.acc)]
        self.shapes = []
        for n in range(12):
            sg = -1 if n % 2 else 1; front = n % 3 == 0
            self.shapes.append({'x': sg * (rnd.uniform(560, 660) if front else rnd.uniform(430, 1000)),
                                'y': rnd.uniform(-650, 380), 'z': rnd.uniform(120, 300) if front else rnd.uniform(900, 2200),
                                'k': 'cube' if n % 2 else 'octa', 's': rnd.uniform(46, 70) if front else rnd.uniform(60, 110),
                                'c': cols[n % 4], 'front': front,
                                'v': [rnd.uniform(0.3, 0.9) * rnd.choice((-1, 1)) for _ in range(3)], 'ph': rnd.uniform(0, 6)})
        self.dust = [(rnd.uniform(-1000, 1000), rnd.uniform(-900, 900), rnd.uniform(0, 2600), rnd.uniform(0, 1)) for _ in range(46)]

    def scene_at(self, t):
        for i, s in enumerate(self.sc):
            if t < s['t0'] + s['dur']: return i
        return len(self.sc) - 1

    # -------------------------------------------------------------- lapisan latar
    def floor(self, fr, t, camx):
        y0, hh = 960, 540
        ov = Image.new('RGBA', (W // 2, hh // 2), (0, 0, 0, 0)); d = ImageDraw.Draw(ov); a = self.acc
        scroll = (t * 240) % 400
        for k in range(18):
            z = -650 + k * 400 - scroll
            s = F / (F + z); y = (H / 2 + FLOOR * s - y0) / 2
            al = int(200 * clamp(1 - (z + 650) / 6500))
            d.line((0, y, W // 2, y), fill=a + (al,), width=1)
        for m in range(-16, 17):
            xw = m * 420; pts = []
            for z in (-650, 7000):
                s = F / (F + z); pts.append(((W / 2 + (xw - camx) * s) / 2, (H / 2 + FLOOR * s - y0) / 2))
            d.line(pts, fill=a + (110,), width=1)
        glow = ov.filter(ImageFilter.GaussianBlur(3)).resize((W, hh), Image.BILINEAR)
        up = ov.resize((W, hh), Image.BILINEAR)
        fr.paste(glow, (0, y0), glow); fr.paste(up, (0, y0), up)

    def particles(self, fr, t, camx):
        d = ImageDraw.Draw(fr)
        for x, y, z, ph in self.dust:
            yy = ((y - t * (30 + 40 * ph) + 900) % 1800) - 900
            X, Y, S = proj(np.array([x + 20 * math.sin(t + ph * 6), yy, z]), camx)
            r = max(1.0, 3.2 * float(S)); k = 0.35 + 0.4 * ph
            col = tuple(int(c * k + 40) for c in self.acc)
            d.ellipse((X - r, Y - r, X + r, Y + r), fill=col)

    def draw_shapes(self, fr, t, camx, front=False):
        for sh in sorted([q for q in self.shapes if q['front'] == front], key=lambda a: -a['z']):
            rot = (t * sh['v'][0] + sh['ph'], t * sh['v'][1] + sh['ph'] * 2, t * sh['v'][2])
            y = sh['y'] + 22 * math.sin(t * 0.9 + sh['ph'])
            X, Y, S = proj(np.array([sh['x'], y, sh['z']]), camx)
            sp = sprite(sh['k'], sh['s'], rot, sh['c'])
            k = float(S); sp = sp.resize((max(4, int(sp.width * k)), max(4, int(sp.height * k))), Image.BILINEAR)
            sp = dim(sp, 0.55 + 0.45 * float(S))
            fr.paste(sp, (int(X - sp.width / 2), int(Y - sp.height / 2)), sp)

    # -------------------------------------------------------------- kartu foto
    def cards(self, fr, i, local, t, camx):
        N = len(self.assets)
        if N == 1: items = [(i, 0.0)]
        else:
            prev = i - 1 if i > 0 else 0
            pos = prev + (i - prev) * eio(local / 0.75)
            lim = 2.2 if N >= 3 else 1.4
            items = [(j, j - pos) for j in range(int(pos) - 3, int(pos) + 5) if abs(j - pos) <= lim]
        items.sort(key=lambda a: -abs(a[1]))
        prm = []
        for j, dd in items:
            ad = abs(dd); sg = 1 if dd > 0 else -1; m1 = min(ad, 1.0); mid = 1 - m1
            xo = sg * (560 * m1 + 200 * max(0, ad - 1)); zo = 330 * m1 + 140 * max(0, ad - 1)
            ry = sg * math.radians(58) * m1 + mid * math.radians(13) * math.sin(t * 0.8)
            rx = math.radians(3) * math.sin(t * 0.6) * mid
            y = CARD_Y + 9 * math.sin(t * 1.5) * mid
            br = 1 - 0.4 * m1; ia = 1.0
            if i == 0 and ad < 0.5 and local < 1.1:
                k = eo(local / 1.1); zo += (1 - k) * 1500; ry -= (1 - k) * math.radians(80); ia = clamp(k * 1.6)
            prm.append((self.assets[j % N]['tex'], (xo, y, zo), (rx, ry, 0), br, ia, ad))
        for tex, c, rot, br, ia, ad in [(a[0], a[1], a[2], a[3], a[4], a[5]) for a in prm]:
            reflect(fr, tex, c, rot, camx, br * ia)
        for tex, c, rot, br, ia, ad in [(a[0], a[1], a[2], a[3], a[4], a[5]) for a in prm]:
            if ad < 0.6:
                X, Y, S = proj(np.array([c[0], FLOOR, c[2]]), camx)
                w = int(tex.width * float(S) * 1.05); h = max(8, int(w * 0.23))
                shd = fadea(self.shadow.resize((max(8, w), h), Image.BILINEAR), ia * (1 - ad / 0.6) * 0.9)
                fr.paste(shd, (int(X - w / 2), int(Y - h / 2)), shd)
        for tex, c, rot, br, ia, ad in [(a[0], a[1], a[2], a[3], a[4], a[5]) for a in prm]:
            tx = tex
            if ad < 0.3:
                cyc = (t % 3.6) / 1.2
                if cyc < 1: tx = sheen_tex(tex, -0.2 * tex.width + cyc * 1.5 * tex.width)
            slab(fr, tx, c, rot, CARD_T, camx, (210, 218, 235), br, ia)

    # -------------------------------------------------------------- judul dan plat
    def head(self, fr, i, local, t, camx):
        k = eo(local / 0.8) if i == 0 else 1.0
        c = at(W / 2, 255 + (1 - k) * -60, (1 - k) * 700, camx)
        slab(fr, self.title, c, (math.radians(4) * math.sin(t * 0.8), math.radians(9) * math.sin(t * 1.1), 0), 0, camx,
             (0, 0, 0), 1.0, k)

    def plate(self, fr, tex, sx, sy, rx, t, camx, ph, side):
        if abs(rx) > math.radians(84): return
        c = at(sx, sy + 5 * math.sin(t * 1.4 + ph), -80, camx)
        slab(fr, tex, c, (rx + math.radians(4) * math.sin(t * 0.9 + ph), math.radians(9) * math.sin(t * 1.2 + ph), 0),
             18, camx, side, 1.0)

    def plates(self, fr, i, local, t, camx):
        last = i == len(self.sc) - 1; R = math.radians
        out = R(-90) * eio(local / 0.3)
        pin = R(90) * (1 - eio((local - 0.6) / 0.6)) if i == 0 else 0.0
        bin_ = R(90) * (1 - eio((local - 0.85) / 0.6)) if i == 0 else 0.0
        side = tuple(int(c * 0.6) for c in self.acc)
        if last:
            self.plate(fr, self.price, 280, 1215, out, t, camx, 0.0, side)
            if self.pts: self.plate(fr, self.point[self.show[i]], 760, 1215, out, t, camx, 1.7, (40, 48, 74))
            self.plate(fr, self.cta, W / 2, 1215, R(90) * (1 - eio((local - 0.35) / 0.6)), t, camx, 0.8,
                       tuple(int(c * 0.6) for c in self.acc))
            return
        self.plate(fr, self.price, 280, 1215, pin, t, camx, 0.0, side)
        if not self.pts: return
        k = self.show[i]; new = i > 0 and self.show[i - 1] != k
        if new and local < 0.3:
            self.plate(fr, self.point[self.show[i - 1]], 760, 1215, R(-90) * eio(local / 0.3), t, camx, 1.7, (40, 48, 74))
        elif new:
            self.plate(fr, self.point[k], 760, 1215, R(90) * (1 - eio((local - 0.3) / 0.5)), t, camx, 1.7, (40, 48, 74))
        else:
            self.plate(fr, self.point[k], 760, 1215, bin_, t, camx, 1.7, (40, 48, 74))

    # -------------------------------------------------------------- 2D di atas segalanya
    def subtitle(self, fr, i, local):
        s = self.sc[i]; lines, sz = self.lines[i]
        words = [w for ln in lines for w in ln]
        total_c = max(1, sum(len(w) + 1 for w in words))
        prog = clamp((local - s['lead']) / max(0.1, s['vd']))
        cur = acc = 0
        for n, w in enumerate(words):
            acc += len(w) + 1
            if acc / total_c <= prog + 0.001: cur = n + 1
        f = font(sz); lh = sz + 16; bh = len(lines) * lh + 44
        a = eio(local / 0.35)
        ov = Image.new('RGBA', (W, bh), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
        od.rounded_rectangle((MX, 0, W - MX, bh - 1), radius=28, fill=(8, 12, 28, int(214 * a)),
                             outline=self.acc + (int(255 * a),), width=2)
        n = 0
        for r, ln in enumerate(lines):
            x = (W - od.textlength(' '.join(ln), font=f)) / 2
            for w in ln:
                col = self.acc if n == cur - 1 else ((255, 255, 255) if n < cur else (150, 160, 182))
                od.text((x, 22 + r * lh), w, font=f, fill=col + (int(255 * a),))
                x += od.textlength(w + ' ', font=f); n += 1
        fr.paste(ov, (0, SUB_BOTTOM - bh - 8 + int((1 - a) * 14)), ov)

    def frame(self, t):
        i = self.scene_at(t); s = self.sc[i]; local = t - s['t0']
        camx = 70 * math.sin(t * 0.45)
        N = len(self.assets)
        fr = self.assets[i % N]['bg'].copy()
        if i > 0 and N > 1 and local < 0.7:
            fr = Image.blend(self.assets[(i - 1) % N]['bg'], fr, eio(local / 0.7))
        self.floor(fr, t, camx)
        self.particles(fr, t, camx)
        self.draw_shapes(fr, t, camx)
        self.cards(fr, i, local, t, camx)
        self.draw_shapes(fr, t, camx, True)
        self.head(fr, i, local, t, camx)
        self.plates(fr, i, local, t, camx)
        self.subtitle(fr, i, local)
        d = ImageDraw.Draw(fr)
        spaced(d, (W / 2 - 205, 104), 'REKOMENDASI PILIHAN', font(28), self.acc, gap=6)
        d.rounded_rectangle((MX, 58, W - MX, 64), radius=3, fill=(34, 42, 66))
        d.rounded_rectangle((MX, 58, MX + max(8, int((W - 2 * MX) * t / self.total)), 64), radius=3, fill=self.acc)
        return fr
