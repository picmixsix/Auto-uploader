import os, re, math, random, wave, asyncio, subprocess, importlib
import numpy as np
from PIL import Image
from themes._base import W, H, FPS, SR

THEME_DEFAULT = 'default'


def list_themes():
    """Nama semua tema di folder themes/ (file .py tanpa awalan _)."""
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'themes')
    return sorted(f[:-3] for f in os.listdir(d) if f.endswith('.py') and not f.startswith('_')) if os.path.isdir(d) else [THEME_DEFAULT]


def pick_theme(want, seed=''):
    """want: nama tema, 'acak'/'random', atau kosong (= bawaan). Acak dipilih stabil berdasarkan seed."""
    want = str(want or '').strip().lower()
    if want in ('acak', 'random'):
        ts = list_themes()
        return random.Random(str(seed)).choice(ts) if ts else THEME_DEFAULT
    return want or THEME_DEFAULT


def load_theme(name):
    """Muat themes/<name>.py. Kalau gagal, pakai tema bawaan dan kembalikan peringatan."""
    name = re.sub(r'[^a-z0-9_-]', '', str(name or THEME_DEFAULT).lower()) or THEME_DEFAULT
    try:
        return importlib.import_module('themes.' + name), None
    except Exception as e:
        if name == THEME_DEFAULT: raise
        return importlib.import_module('themes.' + THEME_DEFAULT), f'tema "{name}" gagal dimuat ({str(e)[:80]}), memakai tema bawaan'


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
    return re.sub(r'Rp\.?\s?(\d(?:[\d.,]*\d)?)', lambda m: speak_price(m.group(1)), t)


def sentences(text):
    out = []
    for line in (text or '').splitlines():
        for s in re.split(r'(?<=[.!?])\s+', line.strip()):
            if s.strip(): out.append(s.strip())
    return out


def _tok(s):
    return {w for w in re.findall(r'[a-z0-9]+', s.lower()) if len(w) >= 4}


def _overlap(a, b):
    ta, tb = _tok(a), _tok(b)
    return sum(1 for x in ta if any(x.startswith(y) or y.startswith(x) for y in tb))


def assign_badges(pts, texts, skip):
    n = len(texts) - 1  # kalimat terakhir (link) tidak diberi lencana
    badge = [None] * len(texts)
    pending = []
    for k, pt in enumerate(pts):
        best, bi = 0, None
        for i in range(n):
            if badge[i] is not None or i in skip: continue
            o = _overlap(pt, texts[i])
            if o > best: best, bi = o, i
        if bi is not None: badge[bi] = k
        else: pending.append(k)
    free = [i for i in range(n) if badge[i] is None and i not in skip]
    free = [i for i in free if i != 0] + [i for i in free if i == 0]
    for k, i in zip(pending, free): badge[i] = k
    return badge


def _lc(x): return x[:1].lower() + x[1:] if x[1:2].islower() else x


def auto_narasi(p):
    """Narasi otomatis dari data produk. Netral: tidak mengarang klaim (terlaris, viral, diskon, dst)."""
    r = random.Random(str(p.get('id', p['name'])))
    pts = [x.strip().rstrip('.') for x in p.get('points', []) if x.strip()][:4]
    out = [r.choice([f"Lagi butuh {p['name']}? Coba lihat ini.", f"Kenalan dulu dengan {p['name']}.",
                     f"Rekomendasi hari ini: {p['name']}.", f"Ini dia {p['name']} untuk kamu."]),
           r.choice([f"Harganya {p['price']}.", f"Harga {p['price']}.", f"Dibanderol {p['price']}."])]
    for i, t in enumerate(pts):
        short = len(t.split()) <= 2
        if i == 0: out.append(f'Nilai plusnya, {_lc(t)}.' if short else r.choice([f'{t}.', f'Nilai plusnya, {_lc(t)}.', f'Keunggulan pertama, {_lc(t)}.']))
        elif short: out.append(r.choice([f'Selain itu, {_lc(t)}.', f'Juga {_lc(t)}.']))
        elif i == len(pts) - 1 and len(pts) > 2: out.append(f'Dan {_lc(t)}.')
        else: out.append(r.choice([f'{t}.', f'Selain itu, {_lc(t)}.', f'Juga, {_lc(t)}.']))
    out.append(r.choice(['Link produknya ada di komentar pertama.', 'Cek detailnya lewat link di komentar pertama.']))
    return ' '.join(out)


def build_scenes(p):
    pts = [x for x in p.get('points', [])][:5]
    nar = (p.get('narasi') or '').strip() or auto_narasi(p)
    price = p['price']
    items = [(s, say_text(s)) for s in sentences(nar)[:8]]
    PR = r'harga|rupiah|Rp\.?\s?\d|\bribu\b|\bjuta\b|dibanderol'
    if not any(re.search(PR, s, re.I) for s, _ in items):
        items.insert(min(1, len(items)), (f'Harganya {price}.', f'Harganya {speak_price(price)}.'))
    skip = {i for i, (s, _) in enumerate(items) if re.search(PR, s, re.I)}
    if not any('link' in s.lower() for s, _ in items):
        items.append(('Link produknya ada di komentar pertama.', 'Link produknya ada di komentar pertama.'))
    bd = assign_badges(pts, [s for s, _ in items], skip)
    return [{'text': s, 'say': v, 'badge': bd[i]} for i, (s, v) in enumerate(items)]


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


def make_video(p, photos, out, thumb, voice='id-ID-GadisNeural', music=True, work='/tmp/studio', theme=THEME_DEFAULT):
    os.makedirs(work, exist_ok=True)
    warn = []
    tm, tw = load_theme(theme)
    if tw: warn.append(tw)
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
    try:
        studio = tm.Theme(p, photos, sc, total)
        studio.frame(sc[min(1, len(sc) - 1)]['t0'] + 0.6)  # uji satu frame sebelum merender semuanya
    except Exception as e:
        if tm.__name__.endswith('.' + THEME_DEFAULT): raise
        warn.append(f'tema "{theme}" error saat dirender ({str(e)[:80]}), memakai tema bawaan')
        tm = importlib.import_module('themes.' + THEME_DEFAULT)
        studio = tm.Theme(p, photos, sc, total)

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
    return {'warn': warn, 'duration': total, 'narasi': ' '.join(x['text'] for x in sc)}
