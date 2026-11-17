"""Tema Dinamis: sinar berputar sewarna foto, kartu 3D bergantian, konfeti, kilau kaca, sapuan warna.
File ini mandiri: tidak butuh file lain di folder themes/. Untuk membuat tema baru cukup salin file ini."""
import math, random, re, colorsys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

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


# ---------------------------------------------------------------- aset visual
def make_bg(im):
    s = max(1296 / im.width, 2304 / im.height)
    b = im.resize((int(im.width * s) + 1, int(im.height * s) + 1))
    x, y = (b.width - 1296) // 2, (b.height - 2304) // 2
    b = b.crop((x, y, x + 1296, y + 2304))
    b = b.resize((324, 576), Image.BILINEAR).filter(ImageFilter.GaussianBlur(10)).resize((1296, 2304), Image.BILINEAR)
    return b.point(lambda v: int(v * 0.5))


def make_card(im, size=920):
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
    body = Image.new('L', cv.size, 0)
    ImageDraw.Draw(body).rounded_rectangle((S, S, S + cw, S + ch), radius=30, fill=255)
    return cv, body


def make_sticker(price, ref=None):
    ref = ref or price
    S = 340
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse((6, 6, S - 6, S - 6), fill=(255, 59, 48, 255))
    d.ellipse((22, 22, S - 22, S - 22), outline=(255, 255, 255, 255), width=5)
    d.text((S / 2, 98), 'HARGA', font=font(40), fill=(255, 255, 255, 255), anchor='mm')
    sz = 84
    while sz > 28 and d.textlength(ref, font=font(sz)) > S - 80: sz -= 4
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


PAL = [(255, 214, 10), (255, 59, 48), (0, 200, 140), (60, 140, 255), (255, 255, 255), (255, 120, 0)]


def pick_tint(im):
    """Warna paling mencolok dari foto, dipakai untuk sinar dan transisi."""
    best, bs = None, 0.18
    for r, g, b in im.resize((24, 24)).getdata():
        h, sa, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if sa * v > bs: bs, best = sa * v, h
    if best is None: return (255, 190, 40)
    r, g, b = colorsys.hsv_to_rgb(best, 0.8, 1.0)
    return (int(r * 255), int(g * 255), int(b * 255))


def make_rays(size=1800, n=16, peak=95):
    c = size / 2
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    dx, dy = xx - c, yy - c
    r = np.sqrt(dx * dx + dy * dy)
    wedge = np.clip((np.sin(np.arctan2(dy, dx) * n) - 0.1) * 4, 0, 1)
    fade = np.clip(1 - r / (c * 0.95), 0, 1) ** 1.3 * np.clip(r / 120, 0, 1)
    return Image.fromarray((wedge * fade * peak).astype(np.uint8), 'L')


def make_vignette():
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    a = np.clip((y - 0.55) / 0.45, 0, 1) ** 1.5 * 150 + np.clip((0.18 - y) / 0.18, 0, 1) * 90
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    im.putalpha(Image.fromarray(np.repeat(a, W, axis=1).astype(np.uint8), 'L'))
    return im


def text_layer(text, f, fill):
    d0 = ImageDraw.Draw(Image.new('L', (1, 1)))
    im = Image.new('RGBA', (int(d0.textlength(text, font=f)) + 14, f.size + 26), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.text((9, 9), text, font=f, fill=(0, 0, 0, 255))
    d.text((6, 6), text, font=f, fill=fill + (255,))
    return im

INFO = {'name': 'Dinamis', 'desc': 'Sinar berputar, kartu 3D bergantian, konfeti, kilau kaca, sapuan warna.'}


class Theme:
    def __init__(self, p, photos, scenes, total):
        self.p, self.sc, self.total = p, scenes, total
        self.assets = []
        for pth in photos:
            im = Image.open(pth).convert('RGB')
            card, body = make_card(im)
            self.assets.append((make_bg(im), card, body, pick_tint(im)))
        self.sticker = make_sticker(p['price'][:20])
        m = re.fullmatch(r'Rp([\d.]+)', p['price'].strip())
        self.pn = int(m.group(1).replace('.', '')) if m else None
        self.pills = {}
        for s in scenes:
            if s['badge'] is not None and s['badge'] < len(p['points']):
                self.pills[s['badge']] = make_pill('✔ ' + p['points'][s['badge']][:60], (0, 150, 90))
        self.cta = make_pill('LINK DI KOMENTAR PERTAMA', (255, 120, 0), 960)
        self.bokeh = make_bokeh()
        self.rays = make_rays()
        self.vig = make_vignette()
        rng = random.Random(5)
        self.spk = [(rng.randint(60, 1020), rng.randint(330, 1450), rng.uniform(0, 6.28), rng.randint(22, 44)) for _ in range(10)]
        d0 = ImageDraw.Draw(Image.new('L', (1, 1)))
        self.lines = [wrap_words(d0, s['text'], font(54), 880) for s in scenes]
        self.title = wrap_words(d0, p['name'][:100], font(66), 920)[:3]
        # judul pembuka: tiap kata muncul sendiri-sendiri (kinetic typography)
        f66 = font(66); sp = d0.textlength(' ', font=f66); self.title_w = []
        for n, ln in enumerate(self.title):
            wd = [d0.textlength(w, font=f66) for w in ln]
            x = (W - (sum(wd) + sp * (len(ln) - 1))) / 2
            for w, ww in zip(ln, wd):
                self.title_w.append((text_layer(w, f66, (255, 255, 255)), int(x) - 6, 225 + n * 84 - 6))
                x += ww + sp
        # judul atas untuk scene berikutnya: 1 baris bila muat, kalau tidak 2 baris (tidak pernah terpotong)
        name = p['name'][:100]; self.head_fs = 46
        while self.head_fs > 40 and d0.textlength('★ ' + name, font=font(self.head_fs)) > 940: self.head_fs -= 2
        if d0.textlength('★ ' + name, font=font(self.head_fs)) <= 940:
            self.head = ['★ ' + name]
        else:
            hl = [' '.join(l) for l in wrap_words(d0, name, font(40), 900)]
            if len(hl) > 2:
                hl = hl[:2]
                while len(hl[1]) > 4 and d0.textlength(hl[1] + '…', font=font(40)) > 900: hl[1] = hl[1][:-1]
                hl[1] = hl[1].rstrip() + '…'
            self.head, self.head_fs = ['★ ' + hl[0]] + hl[1:], 40

    def scene_at(self, t):
        for i, s in enumerate(self.sc):
            if t < s['t0'] + s['dur']: return i
        return len(self.sc) - 1

    def bg(self, k, local, dur, t):
        big = self.assets[k % len(self.assets)][0]
        z = 1 + 0.10 * clamp(local / dur) + 0.12 * (1 - eo(local / 0.3))  # zoom pelan + hentakan di awal scene
        cw, ch = 1296 / (1.2 * z), 2304 / (1.2 * z)
        cx, cy = 648 + 36 * math.sin(t * 0.5), 1152 + 30 * math.cos(t * 0.4)
        return big.crop((int(cx - cw / 2), int(cy - ch / 2), int(cx + cw / 2), int(cy + ch / 2))).resize((W, H), Image.BILINEAR)

    def text_c(self, fr, text, f, y, fill, alpha=1.0, dx=0):
        d = ImageDraw.Draw(fr)
        x = (W - d.textlength(text, font=f)) / 2 + dx
        d.text((x + 3, y + 3), text, font=f, fill=(0, 0, 0))
        d.text((x, y), text, font=f, fill=fill)

    # ------------------------------------------------------------ efek
    def sparkles(self, fr, t):
        d = ImageDraw.Draw(fr)
        for x, y, ph, sz in self.spk:
            r = sz * max(0.0, math.sin(t * 3.2 + ph)) ** 3
            if r < 4: continue
            q = r * 0.22
            d.polygon([(x, y - r), (x + q, y - q), (x + r, y), (x + q, y + q), (x, y + r), (x - q, y + q), (x - r, y), (x - q, y - q)], fill=(255, 255, 255))

    def burst(self, fr, t, ox, oy, seed, n=50, life=1.5, power=1.0, tint=None):
        if t < 0 or t > life: return
        rng = random.Random(seed); d = ImageDraw.Draw(fr)
        cols = PAL + ([tint] if tint else [])
        k = (1 - math.exp(-3.2 * t)) / 3.2
        for j in range(n):
            a, v = rng.uniform(0, 6.2832), rng.uniform(250, 900) * power
            col, sz = rng.choice(cols), rng.uniform(10, 24)
            rot, spin = rng.uniform(0, 6.28), rng.uniform(-9, 9)
            x, y = ox + math.cos(a) * v * k, oy + math.sin(a) * v * k + 520 * t * t
            sz *= clamp((life - t) / 0.4)
            if sz < 2: continue
            if j % 3 == 0:
                d.ellipse((x - sz / 2, y - sz / 2, x + sz / 2, y + sz / 2), fill=col)
            else:
                r = rot + spin * t; c, sn = math.cos(r), math.sin(r); w, h = sz, sz * 0.55
                d.polygon([(x + c * px - sn * py, y + sn * px + c * py) for px, py in ((-w, -h), (w, -h), (w, h), (-w, h))], fill=col)

    def chevrons(self, fr, t):
        d = ImageDraw.Draw(fr)
        for k in range(3):
            b = max(0.0, math.sin(math.pi * ((t * 2.2 - k * 0.22) % 1.0)))
            y = 1408 + k * 30 + 8 * math.sin(t * 6)
            d.line([(492, y), (540, y + 28), (588, y)], fill=(255, int(120 + 135 * b), int(255 * b)), width=12, joint='curve')

    def shine(self, card, body, p):
        cw, ch = card.size
        x = -260 + p * (cw + 520); sk = 320
        band = Image.new('L', card.size, 0); d = ImageDraw.Draw(band)
        d.polygon([(x + sk, 0), (x + sk + 200, 0), (x + 200, ch), (x, ch)], fill=90)
        d.polygon([(x + sk + 55, 0), (x + sk + 125, 0), (x + 125, ch), (x + 55, ch)], fill=255)
        wh = Image.new('RGBA', card.size, (255, 255, 255, 0))
        wh.putalpha(ImageChops.multiply(band, body).point(lambda v: int(v * 0.6)))
        return Image.alpha_composite(card, wh)

    def wipe(self, fr, i, local, dur):
        SK = 220; last = i == len(self.sc) - 1
        if i > 0 and local < 0.3:  # buka: warna menyapu ke kanan, memperlihatkan scene baru
            xr = -SK + eo(local / 0.3) * (W + 2 * SK)
            m = Image.new('L', (W, H), 0); ImageDraw.Draw(m).polygon([(xr + SK, 0), (W + 2 * SK, 0), (W + 2 * SK, H), (xr - SK, H)], fill=255)
            mw = Image.new('L', (W, H), 0); ImageDraw.Draw(mw).polygon([(xr + SK - 60, 0), (xr + SK, 0), (xr - SK, H), (xr - SK - 60, H)], fill=255)
            fr.paste((255, 255, 255), (0, 0), mw); fr.paste(self.assets[i % len(self.assets)][3], (0, 0), m)
        elif not last and local > dur - 0.16:  # tutup: warna menyapu masuk menutupi scene lama
            xl = -SK + eo((local - (dur - 0.16)) / 0.16) * (W + 2 * SK)
            m = Image.new('L', (W, H), 0); ImageDraw.Draw(m).polygon([(-1000, 0), (xl + SK, 0), (xl - SK, H), (-1000, H)], fill=255)
            mw = Image.new('L', (W, H), 0); ImageDraw.Draw(mw).polygon([(xl + SK, 0), (xl + SK + 60, 0), (xl - SK + 60, H), (xl - SK, H)], fill=255)
            fr.paste((255, 255, 255), (0, 0), mw); fr.paste(self.assets[(i + 1) % len(self.assets)][3], (0, 0), m)

    # ------------------------------------------------------------ frame
    def frame(self, t):
        i = self.scene_at(t); s = self.sc[i]; local = t - s['t0']
        last = i == len(self.sc) - 1
        asset = self.assets[i % len(self.assets)]
        fr = self.bg(i, local, s['dur'], t)
        if local < 0.3 and i > 0 and len(self.assets) > 1:
            prev = self.bg(i - 1, self.sc[i - 1]['dur'], self.sc[i - 1]['dur'], t)
            fr = Image.blend(prev, fr, clamp(local / 0.3))
        # sinar berputar sewarna foto, bokeh, vinyet, kilau bintang
        fr.paste(asset[3], (0, 0), self.rays.rotate(-t * 10, resample=Image.BILINEAR).crop((360, -50, 1440, 1870)))
        off = int((t * 70) % H)
        win = self.bokeh.crop((0, off, W, off + H))
        fr.paste(win, (0, 0), win)
        fr.paste(self.vig, (0, 0), self.vig)
        self.sparkles(fr, t)

        # judul
        if i == 0:
            a = eb(local / 0.6)
            self.text_c(fr, 'REKOMENDASI HARI INI', font(50), 150 - int((1 - a) * 80), (255, 214, 10))
            for k, (im, x, y) in enumerate(self.title_w):
                aa = min(1.05, eb((local - 0.12 - 0.07 * k) / 0.45))
                if aa <= 0.02: continue
                w2, h2 = max(2, int(im.width * aa)), max(2, int(im.height * aa))
                lay = im if abs(aa - 1) < 0.01 else im.resize((w2, h2), Image.BILINEAR)
                fr.paste(lay, (x + (im.width - w2) // 2, y + (im.height - h2) // 2 + int((1 - clamp(aa)) * 70)), lay)
            self.burst(fr, local - 0.5, W / 2, 880, 1, n=50, tint=asset[3])
        else:
            y0 = 215 if len(self.head) == 1 else 190
            for n, tx in enumerate(self.head):
                self.text_c(fr, tx, font(self.head_fs), y0 + n * 52, (255, 214, 10))

        # kartu 3D: gaya masuk bergantian, kilau kaca, keluar menyamping
        card = asset[1]
        if 0.55 < local < 1.25: card = self.shine(card, asset[2], (local - 0.55) / 0.7)
        sgn = 1 if i % 2 == 0 else -1
        e = eb(local / 0.65)
        base, cx = 0.9, W / 2
        cy = 905 + 14 * math.sin(2 * math.pi * local / 2.4)
        sway = math.radians(9) * math.sin(2 * math.pi * local / 3.4 + i) * eo(local / 0.8)
        theta, phi, scl = sway, 0.0, base
        style = i % 4
        if style == 0:
            theta = -sgn * (1 - e) * math.radians(78) + sway
            scl = base * clamp(0.6 + 0.4 * eb(local / 0.55), 0.3, 1.1)
        elif style == 1:
            cx += sgn * (1 - e) * 950
            theta = -sgn * (1 - e) * math.radians(35) + sway * 0.6
        elif style == 2:
            scl = base * clamp(0.25 + 0.75 * e, 0.2, 1.15)
            phi = math.radians(10) * (1 - eo(local / 0.6))
            theta = sway * 0.8
        else:
            cy -= (1 - e) * 900
            phi = -(1 - e) * math.radians(40)
            theta = sway * 0.6
        phi += math.radians(4) * math.sin(2 * math.pi * local / 2.8)
        if not last:
            tx = local - (s['dur'] - 0.25)
            if tx > 0:
                x = eo(tx / 0.25)
                cx += sgn * x * 1000
                theta += sgn * x * math.radians(25)
        layer, pos = warp(card, theta, phi, scl, cx, cy)
        fr.paste(layer, pos, layer)

        # stiker harga: hitung naik, gelombang kejut, konfeti
        if i >= 1:
            t1 = t - (self.sc[1]['t0'] + 0.35)
            if t1 > 0:
                k = 0.82 * eb(t1 / 0.5)
                if k > 0.02:
                    rot = 7 * math.sin(2 * math.pi * t1 / 2.6) * eo(t1 / 0.8)
                    stk = self.sticker
                    if self.pn is not None and t1 < 0.9:
                        stk = make_sticker('Rp' + f'{int(self.pn * eo(t1 / 0.9)):,}'.replace(',', '.'), ref=self.p['price'][:20])
                    stk = stk.rotate(rot, resample=Image.BICUBIC).resize((max(2, int(340 * k)),) * 2, Image.BILINEAR)
                    if t1 < 0.6:
                        R = 60 + 260 * eo(t1 / 0.6)
                        ring = Image.new('RGBA', (700, 700), (0, 0, 0, 0))
                        ImageDraw.Draw(ring).ellipse((350 - R, 350 - R, 350 + R, 350 + R), outline=(255, 255, 255, int(255 * (1 - t1 / 0.6))), width=10)
                        fr.paste(ring, (830 - 350, 590 - 350), ring)
                    fr.paste(stk, (830 - stk.width // 2, 590 - stk.height // 2), stk)
                    self.burst(fr, t1, 830, 590, 2, n=40, life=1.2, power=0.8)

        # lencana keunggulan / tombol link
        pill = self.cta if last else (self.pills.get(s['badge']) if s['badge'] is not None else None)
        if pill is not None:
            tb = local - 0.5
            if tb > 0:
                a = eb(tb / 0.45)
                x = int((W - pill.width) / 2 - (1 - a) * 700)
                if last:
                    sc2 = 1 + 0.05 * math.sin(2 * math.pi * tb / 0.9)
                    pl = pill.resize((int(pill.width * sc2), int(pill.height * sc2)), Image.BILINEAR)
                    fr.paste(pl, ((W - pl.width) // 2, 1285 - (pl.height - pill.height) // 2), pl)
                else:
                    fr.paste(pill, (x, 1285), pill)
        if last:
            if local > 0.7: self.chevrons(fr, local)
            self.burst(fr, local - 0.5, W / 2, 1337, 3, n=70, life=1.6, power=1.2, tint=asset[3])

        # subtitle: kata yang sedang diucapkan disorot kotak kuning
        lines = self.lines[i]
        words = [w for ln in lines for w in ln]
        total_c = sum(len(w) + 1 for w in words)
        prog = clamp((local - s['lead']) / max(0.1, s['vd']))
        cur = 0; acc = 0
        for n, w in enumerate(words):
            acc += len(w) + 1
            if acc / total_c <= prog + 0.001: cur = n + 1
        lh = 68; bh = len(lines) * lh + 40
        a = clamp(local / 0.25)
        ov = Image.new('RGBA', (W, bh), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
        od.rounded_rectangle((70, 0, W - 70, bh - 1), radius=36, fill=(0, 0, 0, int(150 * a)))
        n = 0
        for r, ln in enumerate(lines):
            txt = ' '.join(ln); x = (W - od.textlength(txt, font=font(54))) / 2
            for w in ln:
                tw = od.textlength(w, font=font(54)); hot = n == cur - 1
                if hot:
                    od.rounded_rectangle((x - 10, 20 + r * lh - 2, x + tw + 10, 20 + r * lh + 66), radius=18, fill=(255, 214, 10, int(255 * a)))
                od.text((x, 20 + r * lh), w, font=font(54), fill=(20, 20, 20, int(255 * a)) if hot else (255, 255, 255, int(255 * a)))
                x += od.textlength(w + ' ', font=font(54)); n += 1
        fr.paste(ov, (0, 1655 - bh + int((1 - eo(local / 0.3)) * 40)), ov)

        self.wipe(fr, i, local, s['dur'])

        # bar kemajuan
        d = ImageDraw.Draw(fr)
        d.rounded_rectangle((60, 70, W - 60, 82), radius=6, fill=(255, 255, 255))
        d.rounded_rectangle((60, 70, 60 + max(12, int((W - 120) * t / self.total)), 82), radius=6, fill=(255, 214, 10))
        return fr
