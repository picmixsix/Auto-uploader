import os, sys, json, time, base64, random, re, hashlib, datetime as dt, requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

TG = os.environ.get('TG_TOKEN', '')
API = f'https://api.telegram.org/bot{TG}'
GV = 'https://graph.facebook.com/v25.0'
BASE = 'https://part-selanjutnya.github.io/Klik-disini'


def load(f, d):
    try: return json.load(open('data/' + f))
    except Exception: return d


def save(f, d):
    os.makedirs('data', exist_ok=True)
    json.dump(d, open('data/' + f, 'w'), ensure_ascii=False, indent=1)


def pull(): os.system('git pull -q --rebase -X theirs --autostash')


def git(m):
    os.system('git config user.name bot; git config user.email bot@users.noreply.github.com; '
              'git rm -r -q --cached --ignore-unmatch __pycache__ v.mp4 >/dev/null 2>&1; git add -A; '
              f'git diff --cached --quiet || git commit -qm "{m}"')
    for _ in range(4):
        if os.system('git pull -q --rebase -X theirs --autostash && git push -q') == 0: break


def http(method, url, tries=4, **kw):
    """requests dengan timeout + coba ulang untuk koneksi putus (ConnectionReset, timeout)."""
    kw.setdefault('timeout', 60)
    for i in range(tries):
        try:
            return requests.request(method, url, **kw)
        except (requests.ConnectionError, requests.Timeout):
            if i == tries - 1: raise
            time.sleep(3 * 2 ** i)


def tgfile(fid, path):
    p = http('GET', API + '/getFile', params={'file_id': fid}).json()
    if not p.get('ok'): raise Exception('Telegram: ' + str(p.get('description')))
    r = http('GET', f'https://api.telegram.org/file/bot{TG}/' + p['result']['file_path'], timeout=180)
    if r.status_code != 200: raise Exception('Telegram: unduh file gagal (%s)' % r.status_code)
    open(path, 'wb').write(r.content)


def dec(t):
    k = PBKDF2HMAC(hashes.SHA256(), 32, b'kantor-ai', 100000).derive(os.environ['PAGES_KEY'].encode())
    b = base64.b64decode(t)
    return AESGCM(k).decrypt(b[:12], b[12:], None).decode()


def kode(n): return re.sub(r'[^a-z0-9]+', '-', n.lower()).strip('-')


def tag(t, name, vid):
    return re.sub(re.escape(BASE) + r'/?(\?\S*)?', f'{BASE}/?p={kode(name)}&v={vid[:6]}', t or '')


def post(page, tok, x, name=''):
    n = os.path.getsize('v.mp4')
    a = requests.post(f'{GV}/{page}/video_reels', data={'upload_phase': 'start', 'access_token': tok}).json()
    if 'video_id' not in a: raise Exception(a)
    r = requests.post(a['upload_url'], headers={'Authorization': 'OAuth ' + tok, 'offset': '0', 'file_size': str(n)},
                      data=open('v.mp4', 'rb'))
    if r.status_code != 200: raise Exception(r.text)
    d = (x.get('description', '') + '\n\n' + x.get('hashtags', '')).strip()
    if x.get('link'):
        if x['link'] not in d: d = (d + '\n\n' + x['link']).strip()
    elif BASE not in d:
        d = (d + '\n\n' + BASE).strip()
    d = tag(d, name, x['id'])
    f = requests.post(f'{GV}/{page}/video_reels', data={'upload_phase': 'finish', 'video_id': a['video_id'],
                      'video_state': 'PUBLISHED', 'description': d, 'access_token': tok}).json()
    if not f.get('success'): raise Exception(f)
    st = {}
    for _ in range(12):  # tunggu Facebook memproses video, maks ~2 menit
        time.sleep(10)
        try:
            st = requests.get(f"{GV}/{a['video_id']}", params={'fields': 'status', 'access_token': tok}).json().get('status', {})
        except Exception:
            break  # video sudah terkirim, jangan diulang hanya karena gagal mengecek status
        if st.get('video_status') in ('ready', 'error', 'upload_failed', 'expired'): break
    if st.get('video_status') in ('error', 'upload_failed', 'expired'): raise Exception('Facebook: ' + json.dumps(st)[:250])
    if x.get('comment'):
        try:
            c = requests.post(f"{GV}/{a['video_id']}/comments", data={'message': tag(x['comment'], name, x['id']), 'access_token': tok}).json()
            if 'id' not in c: return 'ok (komentar gagal)'
        except Exception:
            return 'ok (komentar gagal)'
    return 'ok'


def status(ok, msg):
    s = load('status.json', {})
    s['fetch'] = {'at': dt.datetime.now(dt.timezone.utc).isoformat(), 'ok': ok, 'msg': msg}
    save('status.json', s)


URL_RE = re.compile(r'https?://\S+', re.I)
P_RP = re.compile(r'\brp\.?\s?(\d[\d.,]*)\s*(rb|ribu|k|jt|juta)?(?![a-z])', re.I)
P_SEP = re.compile(r'^(?:harga\s*:?\s*)?(\d{1,3}(?:[.,]\d{3})+)()$', re.I)
P_UNIT = re.compile(r'^(?:harga\s*:?\s*)?(\d+(?:[.,]\d+)?)\s?(rb|ribu|k|jt|juta)$', re.I)


def to_rupiah(num, unit):
    s = num.strip('.,')
    unit = (unit or '').lower()
    if unit:
        v = float(s.replace(',', '.')) if re.fullmatch(r'\d+[.,]\d{1,2}', s) else float(re.sub(r'[.,]', '', s))
        return int(round(v * (1000 if unit in ('rb', 'ribu', 'k') else 1000000)))
    return int(re.sub(r'[.,]', '', s))


def fmt_rp(n): return 'Rp' + f'{n:,}'.replace(',', '.')


def tgsay(text):
    chat = os.environ.get('TG_CHAT_ID')
    if not chat: return
    try: requests.post(API + '/sendMessage', data={'chat_id': chat, 'text': text[:3500]}, timeout=30)
    except Exception: pass


CONTOH = ('Contoh keterangan (urutan bebas):\n'
          'Rak Piring Stainless\nRp39.000\nTidak karat; Muat 10 piring\nhttps://s.shopee.co.id/xxxx')


def parse_product(cap):
    """Kembalikan (produk, daftar_yang_kurang). Urutan bebas; wajib: link, harga, nama."""
    cap = cap or ''
    m = URL_RE.search(cap)
    link = re.sub(r'^https?', lambda x: x.group(0).lower(), m.group(0), flags=re.I) if m else ''
    text = cap.replace(m.group(0), '\n') if m else cap
    tema, mt = '', re.search(r'^[ \t]*tema[ \t]*:[ \t]*([A-Za-z0-9_-]+)[ \t]*$', text, re.I | re.M)
    if mt: tema = mt.group(1).lower(); text = text[:mt.start()] + '\n' + text[mt.end():]
    price, mp = None, P_RP.search(text)
    if mp:
        price = to_rupiah(mp.group(1), mp.group(2)); text = text[:mp.start()] + '\n' + text[mp.end():]
    lines = [l.strip(' \t-•:,') for l in text.splitlines()]
    nar, mode, segs = [], False, []
    for l in lines:
        if not l: continue
        mm = re.match(r'^narasi\b[\s:\-]*(.*)$', l, re.I)
        if mm: mode = True; l = mm.group(1).strip()
        if mode:
            if l: nar.append(l)
            continue
        for x in re.split(r'[|;]', l):
            x = x.strip(' \t-•:,')
            if x and x.lower() != 'harga': segs.append(x)
    if price is None:
        for i, x in enumerate(segs):
            mm = P_SEP.match(x) or P_UNIT.match(x)
            if mm: price = to_rupiah(mm.group(1), mm.group(2)); segs.pop(i); break
    name, pts = '', []
    for x in segs:
        if not name: name = x[:100]
        elif len(x.split()) >= 9: nar.append(x)
        else: pts.append(x)
    miss = [k for k, v in (('nama produk', name), ('harga', price), ('link Shopee', link)) if not v]
    if miss: return None, miss
    return {'name': name, 'price': fmt_rp(price), 'points': pts[:5], 'link': link, 'narasi': ' '.join(nar), 'theme': tema}, []


def fetch(quiet=False):
    pull()
    try:
        s = load('stock.json', {'offset': 0, 'items': []})
        prods = load('products.json', [])
        chat = os.environ.get('TG_CHAT_ID'); n = np_ = skip = other = 0; newp = []
        r = http('GET', API + '/getUpdates', params={'offset': s['offset']}).json()
        if not r.get('ok'): raise Exception('Telegram: ' + str(r.get('description')) + ' (jika 409: ada bot lain yang memakai token ini)')
        for u in r['result']:
            s['offset'] = u['update_id'] + 1
            m = u.get('message') or u.get('channel_post') or {}
            ph = m.get('photo')
            if ph:
                if chat and str(m['chat']['id']) != chat: skip += 1; continue
                gid, cap = m.get('media_group_id'), m.get('caption', '')
                tgt = next((q for q in prods if gid and q.get('gid') == gid), None)
                if tgt and not cap:
                    if tgt['status'] == 'new': tgt['photos'].append(ph[-1]['file_id'])
                    continue
                if not cap.strip():
                    if not gid: tgsay('⚠️ Foto diterima tanpa keterangan, jadi tidak diproses.\n\n' + CONTOH)
                    other += 1; continue
                pr, miss = parse_product(cap)
                if not pr:
                    tgsay('⚠️ Foto belum bisa diproses. Yang belum ada: ' + ', '.join(miss) + '.\n\n' + CONTOH)
                    other += 1; continue
                i = ph[-1]['file_unique_id'] + '-' + hashlib.md5(cap.encode()).hexdigest()[:4]
                if any(q['id'] == i for q in prods): continue
                item = {**pr, 'id': i, 'gid': gid, 'photos': [ph[-1]['file_id']], 'status': 'new'}
                prods.append(item); newp.append(item)
                np_ += 1
                continue
            v = m.get('video') or (m.get('document') if 'video' in (m.get('document') or {}).get('mime_type', '') else None)
            if not v: other += 1; continue
            if chat and str(m['chat']['id']) != chat: skip += 1; continue
            i = v['file_unique_id']
            if any(k['id'] == i for k in s['items']): continue
            t = (v.get('thumbnail') or v.get('thumb') or {}).get('file_id')
            if t:
                os.makedirs('thumbs', exist_ok=True)
                tgfile(t, f'thumbs/{i}.jpg')
            s['items'].append({'id': i, 'file_id': v['file_id'], 'caption': m.get('caption', ''),
                               'duration': v.get('duration', 0), 'size': v.get('file_size', 0), 'thumb': bool(t)})
            n += 1
        save('stock.json', s); save('products.json', prods)
        for q in newp:
            tgsay('✅ Diterima: ' + q['name'] + '\nHarga: ' + q['price'] + '\nKeunggulan: ' + ('; '.join(q['points']) or '-') +
                  '\nFoto: ' + str(len(q['photos'])) + '\nNarasi: ' + ('dari kamu' if q['narasi'] else 'dibuat otomatis') + '\nTema: ' + (q.get('theme') or 'bawaan') +
                  '\nVideo siap dalam sekitar 10 menit.')
        msg = f"{n} video baru, stok {len(s['items'])}"
        if np_: msg += f", {np_} produk baru menunggu dirender"
        if skip: msg += f", {skip} pesan diabaikan karena Chat ID tidak cocok"
        if other: msg += f", {other} pesan lain"
        prev = load('status.json', {}).get('fetch', {})
        if not quiet or n or np_ or skip or other or not prev.get('ok', True): status(True, msg)
    except Exception as e:
        status(False, str(e)[:200])
    git('bot: ambil telegram')


def clean(*lists):
    ref = {x['id'] for l in lists for x in l} | {x['id'] for x in load('stock.json', {'items': []})['items']}
    if os.path.isdir('thumbs'):
        for f in os.listdir('thumbs'):
            if f[:-4] not in ref: os.remove('thumbs/' + f)


def render_product(p):
    import studio
    d = '/tmp/r' + re.sub(r'\W', '', p['id'])[:14]
    os.makedirs(d, exist_ok=True)
    ph = []
    for i, fid in enumerate(p['photos'][:8]):
        tgfile(fid, f'{d}/p{i}.jpg'); ph.append(f'{d}/p{i}.jpg')
    cfg = load('auto.json', {})
    out = f'{d}/out.mp4'
    if not p.get('narasi'):
        nr = gemini_narasi(p, cfg)
        if nr: p = {**p, 'narasi': nr}
    theme = studio.pick_theme(p.get('theme') or cfg.get('theme'), p['id'])
    info = studio.make_video(p, ph, out, f"thumbs/{p['id']}.jpg", voice=cfg.get('voice', 'id-ID-GadisNeural'),
                             music=cfg.get('music', True), work=d + '/w', theme=theme)
    size = os.path.getsize(out)
    if size > 19000000: raise Exception('video terlalu besar (%.1f MB)' % (size / 1e6))
    warn = '; '.join(info['warn'])
    cap = 'Pratinjau: ' + p['name'][:80] + '\nTema: ' + theme + '\n\nNarasi: ' + info['narasi'] + (('\n\n⚠ ' + warn) if warn else '')
    r = requests.post(API + '/sendVideo', data={'chat_id': os.environ.get('TG_CHAT_ID'), 'supports_streaming': 'true',
                      'width': 1080, 'height': 1920, 'caption': cap[:1000]},
                      files={'video': open(out, 'rb')}, timeout=300).json()
    if not r.get('ok'): raise Exception('Telegram: ' + str(r.get('description')))
    v = r['result']['video']
    return v['file_id'], v.get('duration', 0), v.get('file_size', size)


def render():
    pull()
    prods = load('products.json', [])
    todo = [p for p in prods if p.get('status') == 'new'][:2]
    if not todo: return
    os.system('command -v ffmpeg >/dev/null || (sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg); '
              'fc-list | grep -qi dejavu || sudo apt-get install -y -qq fonts-dejavu-core')
    chat = os.environ.get('TG_CHAT_ID')
    made, res = [], {}
    for p in todo:
        try:
            fid, dur, size = render_product(p)
            cap = f"{p['name']}\nHarga {p['price']}\n" + '\n'.join('✔ ' + x for x in p['points'][:4])
            made.append({'id': p['id'], 'file_id': fid, 'caption': cap, 'duration': dur, 'size': size,
                         'thumb': True, 'link': p['link'], 'product': p['name']})
            res[p['id']] = {'status': 'done'}
        except Exception as e:
            res[p['id']] = {'status': 'error', 'error': str(e)[:200]}
            try:
                requests.post(API + '/sendMessage', data={'chat_id': chat,
                              'text': 'Gagal membuat video produk "' + p['name'][:40] + '": ' + str(e)[:200]})
            except Exception: pass
    # render memakan waktu: ambil data terbaru dulu supaya produk/stok yang ditambah lewat web tidak tertimpa
    pull()
    prods = load('products.json', [])
    for q in prods:
        if q['id'] in res: q.update(res[q['id']])
    stock = load('stock.json', {'offset': 0, 'items': []})
    have = {x['id'] for x in stock['items']}
    stock['items'].extend(x for x in made if x['id'] not in have)
    save('stock.json', stock); save('products.json', prods[-200:])
    git('bot: render video produk')


def gjson(parts, cfg):
    key = os.environ.get('GEMINI_KEY', '')
    if not key: raise Exception('GEMINI_KEY kosong')
    model = cfg.get('model', 'gemini-2.5-flash')
    for i in range(2):
        r = requests.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                          params={'key': key}, timeout=90,
                          json={'contents': [{'parts': parts}], 'generationConfig': {'responseMimeType': 'application/json'}})
        if r.status_code == 404 and i == 0:
            m = requests.get('https://generativelanguage.googleapis.com/v1beta/models',
                             params={'pageSize': 200, 'key': key}, timeout=30).json()
            c = sorted([k['name'].replace('models/', '') for k in m.get('models', [])
                        if 'generateContent' in k.get('supportedGenerationMethods', []) and 'flash' in k['name']
                        and not re.search('lite|image|tts|live|audio|preview|exp', k['name'])], reverse=True)
            if c: model = c[0]; continue
        break
    return json.loads(r.json()['candidates'][0]['content']['parts'][0]['text'])


def gemini(x, cfg):
    base = {'description': x.get('caption', ''), 'hashtags': '', 'comment': ''}
    if not os.environ.get('GEMINI_KEY'): return base
    try:
        parts = [{'text': 'Kamu ahli Facebook Reels Indonesia. Teks bawaan video: "' + (x.get('caption') or '-') +
                  '". Lihat gambar cuplikan video ini, lalu balas JSON {"description","hashtags","comment"}: '
                  'deskripsi menarik maksimal 150 karakter yang sesuai isi video (jangan menjanjikan hal yang tidak ada di video), '
                  '3-5 tagar relevan, dan komentar pertama yang mengajak berinteraksi. Bahasa Indonesia.'}]
        try:
            d = base64.b64encode(open(f"thumbs/{x['id']}.jpg", 'rb').read()).decode()
            parts.append({'inline_data': {'mime_type': 'image/jpeg', 'data': d}})
        except Exception: pass
        o = gjson(parts, cfg)
        h = o.get('hashtags', '')
        return {'description': o.get('description', ''), 'hashtags': ' '.join(h) if isinstance(h, list) else h,
                'comment': o.get('comment', '')}
    except Exception as e:
        print('GEMINI GAGAL:', str(e)[:200])
        return base


BANNED = r'terlaris|terjual|best ?seller|viral|diskon|promo|gratis|garansi|testimoni|termurah|nomor satu|ori(?:ginal)?\b'


def gemini_narasi(p, cfg):
    """Narasi voice over dari AI (opsional). Hanya dipakai kalau lolos pemeriksaan; selain itu '' (pakai narasi template)."""
    if not cfg.get('narasi_ai') or not os.environ.get('GEMINI_KEY'): return ''
    try:
        facts = f"Nama: {p['name']}\nHarga: {p['price']}\nKeunggulan: " + '; '.join(p['points'])
        o = gjson([{'text': 'Tulis narasi voice over iklan produk untuk video Reels, bahasa Indonesia santai, 5 sampai 7 kalimat pendek '
                    '(maksimal 14 kata per kalimat). Urutan: pembuka singkat, harga, satu kalimat untuk tiap keunggulan, '
                    'penutup yang mengarahkan ke link di komentar pertama. Gunakan HANYA fakta berikut. Jangan mengarang klaim, '
                    'angka, diskon, jumlah terjual, atau testimoni.\n' + facts + '\nBalas JSON {"narasi": "..."}'}], cfg)
        t = str(o.get('narasi', '')).strip()
        ss = [x for x in re.split(r'(?<=[.!?])\s+', t) if x.strip()]
        if not (3 <= len(ss) <= 9) or 'link' not in t.lower(): return ''
        if set(re.findall(r'\d+', t)) - set(re.findall(r'\d+', facts)): return ''
        bad = re.findall(BANNED, t, re.I)
        if any(w.lower() not in facts.lower() for w in bad): return ''
        return t
    except Exception as e:
        print('NARASI AI GAGAL:', str(e)[:200])
        return ''


STOP = set('untuk dan yang dengan atau dari the new baru murah promo terbaru original ori premium bahan ukuran isi pcs set paket'.split())
CATS = [(r'jas hujan|payung|raincoat', ['#jashujan', '#perlengkapanhujan']),
        (r'skincare|sunscreen|serum|pelembab|moisturizer|toner|wajah|facial|kulit|sabun muka|lip|bedak|foundation', ['#skincare', '#perawatankulit']),
        (r'rak |dapur|piring|panci|wajan|spatula|talenan|sendok|gelas|botol|toples|kompor', ['#peralatandapur', '#dapur']),
        (r'gamis|hijab|jilbab|khimar|kerudung|abaya|mukena|koko', ['#fashionmuslim', '#ootd']),
        (r'baju|kemeja|kaos|dress|rok |celana|jaket|hoodie|sweater|blouse|outer', ['#fashion', '#ootd']),
        (r'tas |ransel|totebag|tote bag|dompet|backpack', ['#tas', '#fashionwanita']),
        (r'sepatu|sandal|sneakers|selop', ['#sepatu', '#fashion']),
        (r'kopi|teh|susu|snack|makanan|minuman|cemilan', ['#kulinerindonesia', '#cemilan']),
        (r'hp |ponsel|charger|kabel|earphone|headset|speaker|powerbank|casing', ['#aksesorishp', '#gadget']),
        (r'lampu|kipas|setrika|blender|rice cooker|elektronik', ['#elektronik', '#peralatanrumah']),
        (r'mainan|anak|bayi|baby|stroller', ['#perlengkapananak', '#mainananak']),
        (r'motor|helm|mobil|otomotif|jok', ['#otomotif', '#aksesorismotor']),
        (r'sprei|bantal|selimut|kasur|gorden|karpet|handuk|organizer|keranjang', ['#perlengkapanrumah', '#homedecor'])]


def product_tags(v, limit=6):
    """Tagar otomatis dari nama produk: tagar nama + kategori + tagar tetap. Tidak memakai klaim (viral, murah, dst)."""
    name = (v.get('product') or v.get('name') or (v.get('caption') or '').split('\n')[0]).strip()
    low = ' ' + name.lower() + ' '
    out = []
    ws = [w for w in re.findall(r'[A-Za-z]+', name) if len(w) >= 3 and w.lower() not in STOP]
    if len(ws) >= 2: out.append('#' + ''.join(w.capitalize() for w in ws[:2]))
    if ws and len(ws[0]) >= 4: out.append('#' + ws[0].capitalize())
    for rx, tg in CATS:
        if re.search(rx, low):
            out += tg; break
    out += ['#rekomendasishopee', '#ad']
    seen, res = set(), []
    for t in out:
        if t.lower() not in seen: seen.add(t.lower()); res.append(t)
    keep = res[:limit - 2] + ['#rekomendasishopee', '#ad']
    return ' '.join(dict.fromkeys(keep))


def caption(v, cfg):
    if v.get('link'):  # video produk
        ts = cfg.get('product_templates') or [{'description': '{caption}',
                                               'hashtags': '{tagar}',
                                               'comment': 'Link produk (afiliasi): {link}'}]
    else:
        ts = cfg.get('templates') or ([cfg['template']] if cfg.get('template') else [])
        if not ts: return gemini(v, cfg)
    t = random.choice(ts)
    return {k: str(t.get(k, '')).replace('{caption}', v.get('caption', '')).replace('{link}', v.get('link', '')).replace('{tagar}', product_tags(v) if v.get('link') else '')
            for k in ('description', 'hashtags', 'comment')}


def auto():
    cfg = load('auto.json', {})
    if not cfg.get('enabled'): return
    pull()
    stock = load('stock.json', {'offset': 0, 'items': []})
    queue = load('queue.json', [])
    pages = sorted(str(p['id']) for p in load('pages.json', []))
    want = cfg.get('pages', 'all')
    if isinstance(want, list): pages = [p for p in pages if p in [str(w) for w in want]]
    if not pages or not stock['items']: return
    now = dt.datetime.now(dt.timezone.utc)
    wib = dt.timezone(dt.timedelta(hours=7))
    taken = {x.get('slot') for x in queue if x.get('slot')}
    st = load('autostate.json', {'cursor': 0})
    k = max(1, min(int(cfg.get('pages_per_video', 3)), len(pages)))
    slots = []
    for d in range(int(cfg.get('days_ahead', 2)) + 1):
        day = (now.astimezone(wib) + dt.timedelta(days=d)).date()
        for s in cfg.get('slots', ['12:00', '17:00', '20:00']):
            h, m = map(int, s.split(':'))
            t = dt.datetime(day.year, day.month, day.day, h, m, tzinfo=wib).astimezone(dt.timezone.utc)
            if t > now + dt.timedelta(minutes=15): slots.append(t)
    n = 0
    for t in sorted(slots):
        key = t.isoformat()
        if key in taken: continue
        v = next((x for x in stock['items'] if x.get('size', 0) <= 20000000), None)
        if not v: break
        stock['items'].remove(v)
        sel = [pages[(st['cursor'] + i) % len(pages)] for i in range(k)]
        st['cursor'] = (st['cursor'] + k) % len(pages)
        at = t + dt.timedelta(minutes=random.randint(0, 20))
        queue.append({**v, **caption(v, cfg), 'pages': sel, 'at': at.isoformat(), 'slot': key, 'status': 'pending'})
        n += 1
    if n:
        save('stock.json', stock); save('queue.json', queue); save('autostate.json', st)
        git(f'bot: autopilot jadwalkan {n} video')


def run():
    pull()
    now = dt.datetime.now(dt.timezone.utc)
    pages = {p['id']: p for p in load('pages.json', [])}
    q = load('queue.json', [])
    # hanya satu job 'main' berjalan sekaligus, jadi 'processing' di sini pasti sisa job yang terputus/timeout
    stale = [x for x in q if x['status'] == 'processing']
    for x in stale:
        x['status'] = 'failed'
        x['error'] = 'Proses sebelumnya terputus. Cek fanspage, lalu Simpan perubahan di Antrian untuk mencoba lagi'
    if stale: save('queue.json', q); git('bot: tandai upload terputus')
    due = [x for x in q if x['status'] == 'pending' and
           (not x.get('at') or dt.datetime.fromisoformat(x['at'].replace('Z', '+00:00')) <= now)]
    if not due: return
    for x in due: x['status'] = 'processing'
    save('queue.json', q); git('bot: mulai upload')
    out = {}
    for x in due:
        try:
            tgfile(x['file_id'], 'v.mp4')
            res = x.get('results', {})
            for pid in x['pages']:
                if str(res.get(pid, '')).startswith('ok'): continue
                p = pages.get(pid)
                if not p: res[pid] = 'fanspage sudah dihapus'; continue
                for t in range(3):  # coba ulang otomatis, maksimal 3 kali
                    try:
                        res[pid] = post(pid, dec(p['token']), x, p.get('name', pid)); break
                    except Exception as e:
                        res[pid] = 'gagal: ' + str(e)[:200]
                        if 'OAuth' in str(e) or t == 2: break  # token bermasalah tidak perlu diulang
                        time.sleep(60)
                time.sleep(random.randint(30, 120))  # jeda acak antar fanspage
            x['results'] = res
            x['status'] = 'done' if all(str(v).startswith('ok') for v in res.values()) else 'failed'
            x.pop('error', None)
        except Exception as e:
            x['status'] = 'failed'; x['error'] = str(e)[:200]
        out[x['id']] = x
    pull()
    keep, d = [], load('done.json', [])
    for x in load('queue.json', []):
        y = out.get(x['id'])
        if y is None: keep.append(x)
        elif y['status'] == 'done': y['finished'] = now.isoformat(); d.insert(0, y)
        else: keep.append(y)
    d = d[:10]
    save('queue.json', keep); save('done.json', d); clean(keep, d)
    git('bot: selesai upload')


def jalan():
    if load('auto.json', {}).get('enabled'): fetch(quiet=True)
    render()
    auto()
    run()


if __name__ == '__main__':
    {'fetch': fetch, 'run': jalan}[sys.argv[1]]()
