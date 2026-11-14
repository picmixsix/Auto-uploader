import os, re, math, random, wave, asyncio, subprocess
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


# ---------------------------------------------------------------- teks & adegan
def speak_price(price):
    s = price or ''
    d = re.sub(r'\D', '', s)
    if not d: return s
    n = int(d)
    if re.search(r'(juta|jt)\b', s, re.I): return f'{n} juta rupiah'
    if re.search(r'(ribu|rb|k)\b', s, re.I): return f'{n} ribu rupiah'
    if n >= 1000000:
        v = f'{n / 1000000:.2f}'.rstrip('0').rstrip('.').replace('.', ' koma ')
        return v + ' juta rupiah'
    if n >= 1000 and n % 1000 == 0: return f'{n // 1000} ribu rupiah'
    return f'{n} rupiah'


def say_text(t):
    return re.sub(r'Rp\.?\s?([\d.,]+)', lambda m: speak_price(m.group(1)), t)


def sentences(text):
    out = []
    for line in (text or '').splitlines():
        for s in re.split(r'(?<=[.!?])\s+', line.strip()):
            if s.strip(): out.append(s.strip())
    return out


def build_scenes(p):
    pts = [x for x in p.get('points', [])][:5]
    nar = (p.get('narasi') or '').strip()
    sc = []
    if nar:
        ss = sentences(nar)[:9]
        if not any('link' in s.lower() for s in ss): ss.append('Link produknya ada di komentar pertama.')
        for i, s in enumerate(ss):
            k = i - 1
            b = k if (0 <= k < len(pts) and i < len(ss) - 1) else None
            sc.append({'text': s, 'say': say_text(s), 'badge': b})
    else:
        sc.append({'text': f"Rekomendasi hari ini, {p['name']}.", 'say': f"Rekomendasi hari ini, {p['name']}.", 'badge': None})
        sc.append({'text': f"Harganya {p['price']}.", 'say': f"Harganya {speak_price(p['price'])}.", 'badge': None})
        for i, t in enumerate(pts):
            t = t.rstrip('. ') + '.'
            sc.append({'text': t, 'say': t, 'badge': i})
        sc.append({'text': 'Link produknya ada di komentar pertama.', 'say': 'Link produknya ada di komentar pertama.', 'badge': None})
    return sc


# ---------------------------------------------------------------- audio
def synth_whoosh():
    n = int(0.5 * SR); x = np.random.default_rng(1).standard_normal(n)
    t = np.linspace(0, 1, n); a = 0.02 + 0.5 * t ** 2
    y = np.zeros(n); prev = 0.0
    for i in range(n):
        prev += a[i] * (x[i] - prev); y[i] = prev
    y *= np.sin(np.pi * t) ** 1.5
    return y / (np.max(np.abs(y)) + 1e-9) * 0.55


def synth_pop():
    n = int(0.2 * SR); t = np.arange(n) / SR
    ph = 2 * np.pi * np.cumsum(700 * np.exp(-t * 18) + 180) / SR
    return np.sin(ph) * np.exp(-t * 22) * 0.8


def synth_ding(f0=1320.0, d=0.9):
    n = int(d * SR); t = np.arange(n) / SR
    y = sum(a * np.sin(2 * np.pi * f0 * k * t) for k, a in ((1, 1.0), (2.0, 0.35), (3.01, 0.15))) * np.exp(-t * 5.5)
    y[:40] *= np.linspace(0, 1, 40)
    return y / (np.max(np.abs(y)) + 1e-9) * 0.5


def synth_chime():
    y = np.zeros(int(1.4 * SR))
    for i, f in enumerate((880.0, 1108.7, 1318.5, 1760.0)):
        d = synth_ding(f, 0.9); s = int(i * 0.09 * SR)
        y[s:s + len(d)] += d[:len(y) - s]
    return y / (np.max(np.abs(y)) + 1e-9) * 0.55


def add(buf, sig, t):
    s = int(t * SR)
    if s >= len(buf) or s < 0: return
    e = min(len(buf), s + len(sig))
    buf[s:e] += sig[:e - s]


def synth_music(dur):
    bpm = 104; beat = 60 / bpm; bar = beat * 4
    chords = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (261.63, 329.63, 392.0), (196.0, 246.94, 293.66)]
    nb = int(math.ceil(dur / bar)) + 1
    y = np.zeros(int(nb * bar * SR) + SR)
    rng = np.random.default_rng(3)
    for b in range(nb):
        t0 = b * bar; ch = chords[b % 4]
        n = int(bar * SR); t = np.arange(n) / SR
        env = np.minimum(t / 0.25, 1) * np.minimum((bar - t) / 0.4, 1)
        pad = sum(np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t) for f in ch) * env * 0.06
        add(y, pad, t0)
        for k in (0, 2):  # bass
            nn = int(beat * 1.9 * SR); tt = np.arange(nn) / SR
            add(y, np.sin(2 * np.pi * ch[0] / 2 * tt) * np.exp(-tt * 3.2) * 0.30, t0 + k * beat)
        for k in range(4):  # kick
            nn = int(0.22 * SR); tt = np.arange(nn) / SR
            ph = 2 * np.pi * np.cumsum(130 * np.exp(-tt * 22) + 46) / SR
            add(y, np.sin(ph) * np.exp(-tt * 12) * 0.38, t0 + k * beat)
        for k in range(4):  # hat di ketukan lemah
            nn = int(0.05 * SR); tt = np.arange(nn) / SR
            nz = np.diff(rng.standard_normal(nn + 1))
            add(y, nz * np.exp(-tt * 70) * 0.07, t0 + k * beat + beat / 2)
        pat = [0, 1, 2, 1, 0, 1, 2, 1]
        for k, ix in enumerate(pat):  # arpeggio
            nn = int(0.35 * SR); tt = np.arange(nn) / SR
            f = ch[ix] * 2
            add(y, (np.sin(2 * np.pi * f * tt) + 0.25 * np.sin(2 * np.pi * 2 * f * tt)) * np.exp(-tt * 7) * 0.075, t0 + k * beat / 2)
    return y / (np.max(np.abs(y)) + 1e-9) * 0.9


def read_wav(path):
    with wave.open(path) as w:
        n = w.getnframes(); ch = w.getnchannels()
        d = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768
    return d.reshape(-1, ch).mean(1) if ch > 1 else d


async def _tts(text, path, voice, rate):
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=rate).save(path)


def tts_save(text, path, voice, rate='+4%'):
    asyncio.run(_tts(text, path, voice, rate))


def make_voice(text, base, voice):
    mp3, wav = base + '.mp3', base + '.wav'
    tts_save(text, mp3, voice)
    r = subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', mp3, '-ar', str(SR), '-ac', '1', wav])
    if r.returncode != 0: raise Exception('ffmpeg gagal mengubah suara')
    v = read_wav(wav)
    if len(v) < SR * 0.3: raise Exception('suara kosong')
    return v


# ---------------------------------------------------------------- aset visual
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


# ---------------------------------------------------------------- perender
class Studio:
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


def make_video(p, photos, out, thumb, voice='id-ID-GadisNeural', music=True, work='/tmp/studio'):
    os.makedirs(work, exist_ok=True)
    warn = []
    sc = build_scenes(p)
    voices, ok = [], True
    for i, s in enumerate(sc):
        v = None
        if ok:
            for _ in range(2):
                try:
                    v = make_voice(s['say'], f'{work}/v{i}', voice); break
                except Exception as e:
                    err = str(e)[:120]
            if v is None:
                ok = False; warn.append('suara gagal dibuat (' + err + '), video dibuat tanpa suara')
        voices.append(v)
    t, lead = 0.0, 0.4
    for i, s in enumerate(sc):
        vd = len(voices[i]) / SR if voices[i] is not None else max(1.6, len(s['say'].split()) * 0.36)
        s.update(t0=t, lead=lead, vd=vd, dur=max(2.6, vd + lead + 0.5) + (0.7 if i == len(sc) - 1 else 0))
        t += s['dur']
    total = t + 0.2
    studio = Studio(p, photos, sc, total)

    # audio
    n = int(total * SR) + SR
    mix = np.zeros(n)
    vt = np.zeros(n)
    for i, s in enumerate(sc):
        if voices[i] is not None: add(vt, voices[i], s['t0'] + s['lead'])
    if music:
        mf = [os.path.join('music', x) for x in sorted(os.listdir('music'))] if os.path.isdir('music') else []
        mf = [x for x in mf if x.lower().endswith(('.mp3', '.wav', '.m4a', '.ogg'))]
        m = None
        if mf:
            try:
                subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', random.choice(mf), '-ar', str(SR), '-ac', '1', f'{work}/m.wav'], check=True)
                m = read_wav(f'{work}/m.wav')
                m = np.tile(m, int(math.ceil(n / len(m))))[:n]
            except Exception:
                m = None
        if m is None: m = synth_music(total)[:n]
        m = np.pad(m, (0, max(0, n - len(m))))[:n] * 0.17
        w = int(0.12 * SR); cs = np.cumsum(np.abs(vt)); env = np.zeros(n)
        env[w:] = (cs[w:] - cs[:-w]) / w
        m *= 1 - 0.65 * np.clip(env / 0.04, 0, 1)
        fade = np.ones(n); fi, fo = int(0.5 * SR), int(0.9 * SR); e = int(total * SR)
        fade[:fi] = np.linspace(0, 1, fi); fade[max(0, e - fo):e] = np.linspace(1, 0, len(fade[max(0, e - fo):e])); fade[e:] = 0
        mix += m * fade
    mix += vt
    wh, po, di, ch = synth_whoosh(), synth_pop(), synth_ding(), synth_chime()
    for i, s in enumerate(sc):
        add(mix, wh * 0.6, s['t0'])
        if i == 1: add(mix, po * 0.7, s['t0'] + 0.35)
        if i == len(sc) - 1: add(mix, ch * 0.6, s['t0'] + 0.5)
        elif s['badge'] is not None: add(mix, di * 0.5, s['t0'] + 0.5)
    pk = np.max(np.abs(mix))
    if pk > 0.92: mix *= 0.92 / pk
    pcm = (mix[:int(total * SR)] * 32767).astype(np.int16)
    with wave.open(f'{work}/a.wav', 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())

    # video
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
           '-i', f'{work}/a.wav', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '24', '-maxrate', '3500k', '-bufsize', '7000k',
           '-pix_fmt', 'yuv420p', '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', '-c:a', 'aac', '-b:a', '160k', '-ac', '2', '-movflags', '+faststart', '-shortest', out]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    nf = int(total * FPS)
    tt = sc[0]['t0'] + 1.3
    try:
        for f in range(nf):
            fr = studio.frame(f / FPS)
            if f == int(tt * FPS):
                os.makedirs(os.path.dirname(thumb) or '.', exist_ok=True)
                fr.resize((540, 960), Image.LANCZOS).save(thumb, quality=85)
            pr.stdin.write(fr.tobytes())
    finally:
        pr.stdin.close(); rc = pr.wait()
    if rc != 0: raise Exception('ffmpeg gagal membuat video')
    return {'warn': warn, 'duration': total}
