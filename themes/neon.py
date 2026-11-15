"""Tema Neon: latar gelap, bingkai foto bercahaya, label harga miring, garis pindai."""
import math
from PIL import Image, ImageDraw, ImageFilter
from themes._base import *

INFO = {'name': 'Neon', 'desc': 'Gelap dan mencolok: bingkai cyan-magenta bercahaya, grid bergerak.'}

CYAN, MAG, YEL, INK = (0, 229, 255), (255, 0, 200), (255, 230, 0), (10, 6, 26)


def dark_bg(im):
    s = max(W / im.width, H / im.height)
    b = im.resize((int(im.width * s) + 1, int(im.height * s) + 1))
    x, y = (b.width - W) // 2, (b.height - H) // 2
    b = b.crop((x, y, x + W, y + H)).resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(8)).resize((W, H), Image.BILINEAR)
    return Image.blend(b, Image.new('RGB', (W, H), INK), 0.82)


def neon_card(im, size=860):
    k = min(size / im.width, size / im.height)
    ph = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS)
    bw, S = 10, 70
    cw, ch = ph.width + 2 * bw, ph.height + 2 * bw
    cv = Image.new('RGBA', (cw + 2 * S, ch + 2 * S), (0, 0, 0, 0))
    glow = Image.new('RGBA', cv.size, (0, 0, 0, 0)); gd = ImageDraw.Draw(glow)
    gd.rounded_rectangle((S, S, S + cw, S + ch), radius=30, outline=MAG + (255,), width=26)
    gd.rounded_rectangle((S + 14, S + 14, S + cw - 14, S + ch - 14), radius=22, outline=CYAN + (255,), width=14)
    cv.alpha_composite(glow.filter(ImageFilter.GaussianBlur(20)))
    ImageDraw.Draw(cv).rounded_rectangle((S, S, S + cw, S + ch), radius=26, fill=CYAN + (255,))
    ImageDraw.Draw(cv).rounded_rectangle((S + 5, S + 5, S + cw - 5, S + ch - 5), radius=22, fill=MAG + (255,))
    m = Image.new('L', ph.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, ph.width - 1, ph.height - 1), radius=16, fill=255)
    cv.paste(ph, (S + bw, S + bw), m)
    return cv


def make_tag(price):
    d0 = ImageDraw.Draw(Image.new('L', (1, 1)))
    sz = 88
    while sz > 30 and d0.textlength(price, font=font(sz)) + 120 > 620: sz -= 4
    w, h = int(d0.textlength(price, font=font(sz))) + 120, 180
    im = Image.new('RGBA', (w + 40, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.polygon([(40, 0), (w + 40, 0), (w, h), (0, h)], fill=MAG + (255,), outline=(255, 255, 255, 255), width=5)
    d.text((w / 2 + 20, 38), 'HARGA', font=font(34), fill=(255, 255, 255, 255), anchor='mm')
    d.text((w / 2 + 20, 112), price, font=font(sz), fill=YEL + (255,), anchor='mm')
    return im


def make_chip(text, maxw=900):
    d0 = ImageDraw.Draw(Image.new('L', (1, 1)))
    sz = 50
    while sz > 30 and d0.textlength(text, font=font(sz)) + 90 > maxw: sz -= 2
    w, h = int(d0.textlength(text, font=font(sz))) + 90, 100
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=INK + (235,), outline=CYAN + (255,), width=5)
    d.text((w / 2, h / 2 + 2), text, font=font(sz), fill=CYAN + (255,), anchor='mm')
    return im


def make_grid():
    g = Image.new('RGBA', (W, H * 2), (0, 0, 0, 0)); d = ImageDraw.Draw(g)
    for y in range(0, H * 2, 120): d.line((0, y, W, y), fill=MAG + (40,), width=3)
    for x in range(0, W + 1, 120): d.line((x, 0, x, H * 2), fill=CYAN + (28,), width=3)
    return g


def make_scan():
    sc = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(sc)
    for y in range(0, H, 6): d.line((0, y, W, y), fill=(0, 0, 0, 34), width=2)
    return sc


class Theme:
    def __init__(self, p, photos, scenes, total):
        self.p, self.sc, self.total = p, scenes, total
        self.assets = []
        for pth in photos:
            im = Image.open(pth).convert('RGB')
            self.assets.append((dark_bg(im), neon_card(im)))
        self.tag = make_tag(p['price'][:20])
        self.chips = {}
        for s in scenes:
            if s['badge'] is not None and s['badge'] < len(p['points']):
                self.chips[s['badge']] = make_chip('✔ ' + p['points'][s['badge']][:60])
        self.cta = make_pill('LINK DI KOMENTAR PERTAMA', MAG, 960)
        self.grid, self.scan = make_grid(), make_scan()
        d0 = ImageDraw.Draw(Image.new('L', (1, 1)))
        self.lines = [wrap_words(d0, s['text'], font(54), 880) for s in scenes]
        self.title = wrap_words(d0, p['name'][:100].upper(), font(66), 920)[:3]
        self.head = p['name'][:42].upper() + ('…' if len(p['name']) > 42 else '')

    def scene_at(self, t):
        for i, s in enumerate(self.sc):
            if t < s['t0'] + s['dur']: return i
        return len(self.sc) - 1

    def glow_text(self, fr, text, f, y, fill, shadow=MAG, dx=0):
        d = ImageDraw.Draw(fr)
        x = (W - d.textlength(text, font=f)) / 2 + dx
        d.text((x + 4, y + 4), text, font=f, fill=shadow)
        d.text((x, y), text, font=f, fill=fill)

    def frame(self, t):
        i = self.scene_at(t); s = self.sc[i]; local = t - s['t0']
        fr = self.assets[i % len(self.assets)][0].copy()
        if local < 0.3 and i > 0 and len(self.assets) > 1:
            fr = Image.blend(self.assets[(i - 1) % len(self.assets)][0], fr, clamp(local / 0.3))
        off = int((t * 90) % H)
        win = self.grid.crop((0, off, W, off + H)); fr.paste(win, (0, 0), win)

        if i == 0:
            a = eb(local / 0.6)
            chip = make_chip('PILIHAN HARI INI', 760)
            fr.paste(chip, ((W - chip.width) // 2, 120 - int((1 - a) * 90)), chip)
            for n, ln in enumerate(self.title):
                aa = eb((local - 0.15 - 0.12 * n) / 0.6)
                self.glow_text(fr, ' '.join(ln), font(66), 270 + n * 84 + int((1 - aa) * 90), (255, 255, 255))
        else:
            self.glow_text(fr, self.head, font(46), 215, CYAN)

        card = self.assets[i % len(self.assets)][1]
        e = eb(local / 0.6)
        jit = int(14 * math.sin(local * 90)) if local < 0.25 else 0
        k = clamp(0.55 + 0.45 * e, 0.3, 1.08) * (1 + 0.012 * math.sin(2 * math.pi * local / 3.0))
        cd = card.resize((max(2, int(card.width * k)), max(2, int(card.height * k))), Image.BILINEAR)
        cx = int(W / 2 - cd.width / 2 + jit)
        cy = int(900 + (1 - clamp(e, 0, 1)) * 500 + 10 * math.sin(2 * math.pi * local / 2.6) - cd.height / 2)
        fr.paste(cd, (cx, cy), cd)

        if i >= 1:
            t1 = t - (self.sc[1]['t0'] + 0.35)
            if t1 > 0:
                kk = eb(t1 / 0.5)
                if kk > 0.02:
                    tg = self.tag.resize((max(2, int(self.tag.width * kk)), max(2, int(self.tag.height * kk))), Image.BILINEAR)
                    fr.paste(tg, (60, 520 - tg.height // 2), tg)

        last = i == len(self.sc) - 1
        pill = self.cta if last else (self.chips.get(s['badge']) if s['badge'] is not None else None)
        if pill is not None:
            tb = local - 0.5
            if tb > 0:
                a = eb(tb / 0.45)
                if last:
                    sc2 = 1 + 0.05 * math.sin(2 * math.pi * tb / 0.9)
                    pl = pill.resize((int(pill.width * sc2), int(pill.height * sc2)), Image.BILINEAR)
                    fr.paste(pl, ((W - pl.width) // 2, 1285 - (pl.height - pill.height) // 2), pl)
                else:
                    fr.paste(pill, (int((W - pill.width) / 2 - (1 - a) * 700), 1285), pill)

        draw_subtitle(fr, self.lines[i], s, local, box=(10, 6, 26, 215), txt=(255, 255, 255), hi=INK, hi_bg=YEL, outline=CYAN)
        fr.paste(self.scan, (0, 0), self.scan)
        d = ImageDraw.Draw(fr)
        d.rounded_rectangle((60, 70, W - 60, 82), radius=6, fill=(40, 30, 80))
        d.rounded_rectangle((60, 70, 60 + max(12, int((W - 120) * t / self.total)), 82), radius=6, fill=CYAN)
        return fr
