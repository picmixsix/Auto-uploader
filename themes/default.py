"""Tema bawaan: kartu foto 3D, stiker harga, lencana keunggulan."""
import math
from PIL import Image, ImageDraw
from themes._base import *

INFO = {'name': 'Bawaan', 'desc': 'Kartu foto 3D berputar, stiker harga merah, lencana hijau.'}


class Theme:
    def __init__(self, p, photos, scenes, total):
        self.p, self.sc, self.total = p, scenes, total
        self.assets = []
        for pth in photos:
            im = Image.open(pth).convert('RGB')
            self.assets.append((make_bg(im), make_card(im)))
        self.sticker = make_sticker(p['price'][:20])
        self.pills = {}
        for s in scenes:
            if s['badge'] is not None and s['badge'] < len(p['points']):
                self.pills[s['badge']] = make_pill('✔ ' + p['points'][s['badge']][:60], (0, 150, 90))
        self.cta = make_pill('LINK DI KOMENTAR PERTAMA', (255, 120, 0), 960)
        self.bokeh = make_bokeh()
        d0 = ImageDraw.Draw(Image.new('L', (1, 1)))
        self.lines = [wrap_words(d0, s['text'], font(54), 880) for s in scenes]
        self.title = wrap_words(d0, p['name'][:100], font(66), 920)[:3]
        self.head = p['name'][:42] + ('…' if len(p['name']) > 42 else '')

    def scene_at(self, t):
        for i, s in enumerate(self.sc):
            if t < s['t0'] + s['dur']: return i
        return len(self.sc) - 1

    def bg(self, k, local, dur, t):
        big = self.assets[k % len(self.assets)][0]
        z = 1 + 0.10 * clamp(local / dur)
        cw, ch = 1296 / (1.2 * z), 2304 / (1.2 * z)
        cx, cy = 648 + 36 * math.sin(t * 0.5), 1152 + 30 * math.cos(t * 0.4)
        return big.crop((int(cx - cw / 2), int(cy - ch / 2), int(cx + cw / 2), int(cy + ch / 2))).resize((W, H), Image.BILINEAR)

    def text_c(self, fr, text, f, y, fill, alpha=1.0, dx=0):
        d = ImageDraw.Draw(fr)
        x = (W - d.textlength(text, font=f)) / 2 + dx
        d.text((x + 3, y + 3), text, font=f, fill=(0, 0, 0))
        d.text((x, y), text, font=f, fill=fill)

    def frame(self, t):
        i = self.scene_at(t); s = self.sc[i]; local = t - s['t0']
        fr = self.bg(i, local, s['dur'], t)
        if local < 0.3 and i > 0 and len(self.assets) > 1:
            prev = self.bg(i - 1, self.sc[i - 1]['dur'], self.sc[i - 1]['dur'], t)
            fr = Image.blend(prev, fr, clamp(local / 0.3))
        off = int((t * 70) % H)
        win = self.bokeh.crop((0, off, W, off + H))
        fr.paste(win, (0, 0), win)

        # judul
        d = ImageDraw.Draw(fr)
        if i == 0:
            a = eb(local / 0.6)
            chip = 'REKOMENDASI HARI INI'
            self.text_c(fr, chip, font(50), 150 - int((1 - a) * 80), (255, 214, 10))
            for n, ln in enumerate(self.title):
                aa = eb((local - 0.15 - 0.12 * n) / 0.6)
                self.text_c(fr, ' '.join(ln), font(66), 225 + n * 84 + int((1 - aa) * 90), (255, 255, 255))
        else:
            self.text_c(fr, '★ ' + self.head, font(46), 215, (255, 214, 10))

        # kartu 3D
        card = self.assets[i % len(self.assets)][1]
        sgn = 1 if i % 2 == 0 else -1
        enter = -sgn * (1 - eb(local / 0.65)) * math.radians(78)
        sway = math.radians(9) * math.sin(2 * math.pi * local / 3.4 + i)
        phi = math.radians(4) * math.sin(2 * math.pi * local / 2.8)
        sc = 0.88 * clamp(0.6 + 0.4 * eb(local / 0.55), 0.3, 1.1)
        cy = 905 + 14 * math.sin(2 * math.pi * local / 2.4)
        layer, pos = warp(card, enter + sway * eo(local / 0.8), phi, sc, W / 2, cy)
        fr.paste(layer, pos, layer)

        # stiker harga
        if i >= 1:
            t1 = t - (self.sc[1]['t0'] + 0.35)
            if t1 > 0:
                k = 0.82 * eb(t1 / 0.5)
                if k > 0.02:
                    rot = 7 * math.sin(2 * math.pi * t1 / 2.6) * eo(t1 / 0.8)
                    st = self.sticker.rotate(rot, resample=Image.BICUBIC).resize((max(2, int(340 * k)),) * 2, Image.BILINEAR)
                    fr.paste(st, (830 - st.width // 2, 590 - st.height // 2), st)

        # lencana keunggulan / tombol link
        last = i == len(self.sc) - 1
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

        # subtitle dengan sorotan kata
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
                col = (255, 214, 10, int(255 * a)) if n == cur - 1 else (255, 255, 255, int(255 * a))
                od.text((x, 20 + r * lh), w, font=font(54), fill=col)
                x += od.textlength(w + ' ', font=font(54)); n += 1
        fr.paste(ov, (0, 1655 - bh), ov)

        # bar kemajuan
        d = ImageDraw.Draw(fr)
        d.rounded_rectangle((60, 70, W - 60, 82), radius=6, fill=(255, 255, 255))
        d.rounded_rectangle((60, 70, 60 + max(12, int((W - 120) * t / self.total)), 82), radius=6, fill=(255, 214, 10))
        return fr
