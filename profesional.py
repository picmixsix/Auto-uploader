"""Tema Profesional: tata letak bersih ala katalog, tanpa efek 3D, konfeti, atau sinar.
Gerak hanya fade halus, geser pendek, dan zoom sangat pelan. Warna tetap (navy + oranye)."""
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from themes._base import W, H, FPS, SR, font, clamp, eo, wrap_words

INFO = {'name': 'Profesional', 'desc': 'Bersih dan rapi: latar terang, kartu foto statis, panel harga, subtitle bersih. Tanpa 3D.'}

INK, ACC, GRN = (15, 27, 45), (238, 77, 45), (18, 128, 92)
GREY, SOFT, LINE, PAPER = (107, 114, 128), (156, 163, 175), (229, 231, 235), (245, 246, 248)
MX = 80                       # margin kiri-kanan
CARD_BOX = (880, 730)         # area foto maksimum
CARD_CY = 780                 # titik tengah kartu
PANEL = (MX, 1195, W - MX, 1335)
SUB_BOTTOM = 1630             # tepi bawah subtitle (di atas area tombol Reels)

_R = {}


def font_r(sz):
    """Font reguler; kalau tidak ada, pakai tebal."""
    if sz not in _R:
        try: _R[sz] = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', sz)
        except Exception: _R[sz] = font(sz)
    return _R[sz]


def eio(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def spaced(d, xy, text, f, fill, gap=5):
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=f, fill=fill)
        x += d.textlength(ch, font=f) + gap
    return x


def fit_font(d, text, maxw, start, lo=24, bold=True):
    sz = start
    mk = font if bold else font_r
    while sz > lo and d.textlength(text, font=mk(sz)) > maxw: sz -= 2
    return mk(sz)


def fade(layer, k):
    """Salinan layer RGBA dengan transparansi dikali k (0..1)."""
    if k >= 0.999: return layer
    out = layer.copy()
    out.putalpha(layer.getchannel('A').point(lambda v: int(v * clamp(k))))
    return out


def make_base(im):
    """Latar terang dengan semburat warna foto yang sangat tipis."""
    s = max(W / im.width, H / im.height)
    b = im.resize((int(im.width * s) + 1, int(im.height * s) + 1))
    x, y = (b.width - W) // 2, (b.height - H) // 2
    b = b.crop((x, y, x + W, y + H)).resize((W // 8, H // 8), Image.BILINEAR)
    b = b.filter(ImageFilter.GaussianBlur(6)).resize((W, H), Image.BILINEAR)
    return Image.blend(Image.new('RGB', (W, H), PAPER), b, 0.13)


def make_card(im):
    k = min(CARD_BOX[0] / im.width, CARD_BOX[1] / im.height)
    ph = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS)
    pad, S = 12, 50
    cw, ch = ph.width + 2 * pad, ph.height + 2 * pad
    cv = Image.new('RGBA', (cw + 2 * S, ch + 2 * S), (0, 0, 0, 0))
    sh = Image.new('RGBA', cv.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((S, S + 14, S + cw, S + ch + 14), radius=26, fill=(15, 27, 45, 52))
    cv.alpha_composite(sh.filter(ImageFilter.GaussianBlur(20)))
    ImageDraw.Draw(cv).rounded_rectangle((S, S, S + cw, S + ch), radius=26, fill=(255, 255, 255, 255))
    m = Image.new('L', ph.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, ph.width - 1, ph.height - 1), radius=16, fill=255)
    cv.paste(ph, (S + pad, S + pad), m)
    return cv


def make_header(name):
    """Label kecil + nama produk (maksimal 2 baris), rata kiri."""
    im = Image.new('RGBA', (W, 380), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((MX, 146, MX + 44, 152), radius=3, fill=ACC)
    spaced(d, (MX + 62, 130), 'REKOMENDASI PILIHAN', font(30), ACC, gap=5)
    lines = wrap_words(d, name[:100], font(56), W - 2 * MX)
    over = len(lines) > 2
    lines = lines[:2]
    if over: lines[-1] = lines[-1][:-1] + [lines[-1][-1].rstrip('.,;:') + '…']
    for n, ln in enumerate(lines):
        d.text((MX, 190 + n * 72), ' '.join(ln), font=font(56), fill=INK + (255,))
    return im


def make_panel_bg():
    """Panel putih tempat harga dan keunggulan (dengan bayangan lembut)."""
    x0, y0, x1, y1 = PANEL; S = 40
    im = Image.new('RGBA', (x1 - x0 + 2 * S, y1 - y0 + 2 * S), (0, 0, 0, 0))
    sh = Image.new('RGBA', im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((S, S + 8, S + x1 - x0, S + y1 - y0 + 8), radius=26, fill=(15, 27, 45, 34))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14)))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((S, S, S + x1 - x0, S + y1 - y0), radius=26, fill=(255, 255, 255, 255), outline=LINE + (255,), width=2)
    return im, S


def make_price(price, with_badge):
    """Blok harga di kiri panel."""
    pw = 400 if with_badge else PANEL[2] - PANEL[0]
    ph = PANEL[3] - PANEL[1]
    im = Image.new('RGBA', (pw, ph), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    f = fit_font(d, price, pw - 80, 64, 30)
    cx = pw / 2 if not with_badge else 40
    anc = 'mm' if not with_badge else 'lm'
    spaced_w = sum(d.textlength(c, font=font(26)) + 5 for c in 'HARGA')
    lx = (pw - spaced_w) / 2 if not with_badge else 40
    spaced(d, (lx, 28), 'HARGA', font(26), GREY, gap=5)
    d.text((cx, ph / 2 + 20), price, font=f, fill=ACC + (255,), anchor=anc)
    if with_badge:
        d.line((pw - 1, 28, pw - 1, ph - 28), fill=LINE + (255,), width=2)
    return im


def make_point(text):
    """Baris keunggulan (ikon centang + teks, maksimal 2 baris) di kanan panel."""
    pw, ph = PANEL[2] - PANEL[0] - 400, PANEL[3] - PANEL[1]
    im = Image.new('RGBA', (pw, ph), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    tx, tw = 104, pw - 104 - 36
    sz = 38
    while True:
        lines = wrap_words(d, text[:90], font(sz), tw)
        if len(lines) <= 2 or sz <= 28: break
        sz -= 2
    lines = lines[:2]
    lh = sz + 10; y0 = (ph - len(lines) * lh) / 2 + 2
    cy = ph / 2
    d.ellipse((38, cy - 25, 88, cy + 25), fill=GRN + (255,))
    d.line([(52, cy), (60, cy + 9), (75, cy - 10)], fill=(255, 255, 255, 255), width=6, joint='curve')
    for n, ln in enumerate(lines):
        d.text((tx, y0 + n * lh), ' '.join(ln), font=font(sz), fill=INK + (255,))
    return im


def make_cta():
    """Panel penuh berwarna untuk ajakan akhir."""
    pw, ph = PANEL[2] - PANEL[0], PANEL[3] - PANEL[1]
    im = Image.new('RGBA', (pw, ph), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, pw - 1, ph - 1), radius=26, fill=ACC + (255,))
    f = fit_font(d, 'LINK PRODUK ADA DI KOMENTAR PERTAMA', pw - 120, 44, 28)
    d.text((pw / 2, ph / 2), 'LINK PRODUK ADA DI KOMENTAR PERTAMA', font=f, fill=(255, 255, 255, 255), anchor='mm')
    return im


class Theme:
    def __init__(self, p, photos, scenes, total):
        self.p, self.sc, self.total = p, scenes, total
        self.assets = []
        for pth in photos:
            im = Image.open(pth).convert('RGB')
            self.assets.append((make_base(im), make_card(im)))
        self.header = make_header(p['name'])
        self.panel, self.panel_s = make_panel_bg()
        self.pts = p.get('points', [])
        wb = bool(self.pts)
        self.price = make_price(p['price'][:20], wb)
        self.point_img = {}
        # keunggulan yang tampil di tiap adegan: bertahan sampai ada keunggulan berikutnya
        self.show, cur = [], 0
        for s in scenes:
            if s['badge'] is not None and s['badge'] < len(self.pts): cur = s['badge']
            self.show.append(cur)
        for k in set(self.show) if wb else []:
            self.point_img[k] = make_point(self.pts[k])
        self.cta = make_cta()
        d0 = ImageDraw.Draw(Image.new('L', (1, 1)))
        self.lines = []
        for s in scenes:
            sz = 48
            while True:
                ln = wrap_words(d0, s['text'], font(sz), W - 2 * MX - 80)
                if len(ln) <= 3 or sz <= 40: break
                sz -= 2
            self.lines.append((ln, sz))

    def scene_at(self, t):
        for i, s in enumerate(self.sc):
            if t < s['t0'] + s['dur']: return i
        return len(self.sc) - 1

    # ------------------------------------------------------------ bagian-bagian frame
    def card(self, fr, k, t, alpha):
        c = self.assets[k % len(self.assets)][1]
        z = 1 + 0.025 * (t / self.total)  # zoom sangat pelan
        cd = c.resize((int(c.width * z), int(c.height * z)), Image.BILINEAR)
        cd = fade(cd, alpha)
        fr.paste(cd, (int(W / 2 - cd.width / 2), int(CARD_CY - cd.height / 2)), cd)

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
        od.rounded_rectangle((MX, 0, W - MX, bh - 1), radius=28, fill=(255, 255, 255, int(244 * a)),
                             outline=LINE + (int(255 * a),), width=2)
        n = 0
        for r, ln in enumerate(lines):
            x = (W - od.textlength(' '.join(ln), font=f)) / 2
            for w in ln:
                col = ACC if n == cur - 1 else (INK if n < cur else GREY)
                od.text((x, 22 + r * lh), w, font=f, fill=col + (int(255 * a),))
                x += od.textlength(w + ' ', font=f); n += 1
        fr.paste(ov, (0, SUB_BOTTOM - bh - 8 + int((1 - a) * 14)), ov)

    # ------------------------------------------------------------ frame utama
    def frame(self, t):
        i = self.scene_at(t); s = self.sc[i]; local = t - s['t0']
        last = i == len(self.sc) - 1
        multi = len(self.assets) > 1
        fr = self.assets[i % len(self.assets)][0].copy()
        x_in = eio(local / 0.4)
        if i > 0 and multi and local < 0.4:  # pergantian foto: crossfade
            fr = Image.blend(self.assets[(i - 1) % len(self.assets)][0], fr, x_in)

        # header (muncul halus di adegan pertama saja)
        h = self.header
        if i == 0:
            k = eo(local / 0.6)
            h = fade(h, k)
            fr.paste(h, (0, int((1 - k) * 18)), h)
        else:
            fr.paste(h, (0, 0), h)

        # kartu foto
        if i > 0 and multi and local < 0.4:
            self.card(fr, i - 1, t, 1 - x_in)
            self.card(fr, i, t, x_in)
        else:
            self.card(fr, i, t, eo(local / 0.6) if i == 0 else 1.0)

        # panel harga / keunggulan, atau ajakan di akhir
        pa = eo((local - (0.25 if i == 0 else 0.0)) / 0.5)
        px, py = PANEL[0], PANEL[1]
        if last:
            kk = eo((local - 0.2) / 0.5)
            c = fade(self.cta, kk)
            fr.paste(c, (px, py + int((1 - kk) * 14)), c)
        else:
            pn = fade(self.panel, pa)
            fr.paste(pn, (px - self.panel_s, py - self.panel_s + int((1 - pa) * 14)), pn)
            pr = fade(self.price, pa)
            fr.paste(pr, (px, py + int((1 - pa) * 14)), pr)
            if self.pts:
                k = self.show[i]; pimg = self.point_img[k]
                new = s['badge'] is not None  # keunggulan baru: fade-in; kalau lanjutan: tetap
                pk = eo((local - 0.3) / 0.45) if new and i > 0 else pa
                pp = fade(pimg, pk)
                fr.paste(pp, (px + 400, py + int((1 - pk) * 10)), pp)

        self.subtitle(fr, i, local)

        # bar kemajuan tipis
        d = ImageDraw.Draw(fr)
        d.rounded_rectangle((MX, 60, W - MX, 66), radius=3, fill=LINE)
        d.rounded_rectangle((MX, 60, MX + max(8, int((W - 2 * MX) * t / self.total)), 66), radius=3, fill=ACC)
        return fr
