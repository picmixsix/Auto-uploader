import os, sys, json, time, base64, random, re, datetime as dt, requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

TG = os.environ.get('TG_TOKEN', '')
API = f'https://api.telegram.org/bot{TG}'
GV = 'https://graph.facebook.com/v25.0'
BASE = 'https://part-selanjutnya.github.io/Klik-disini'
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
ZP = "zoompan=z='min(zoom+0.0006,1.07)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=90:s=1080x1920:fps=30,format=yuv420p"


def load(f, d):
    try: return json.load(open('data/' + f))
    except Exception: return d


def save(f, d):
    os.makedirs('data', exist_ok=True)
    json.dump(d, open('data/' + f, 'w'), ensure_ascii=False, indent=1)


def pull(): os.system('git pull -q --rebase -X theirs --autostash')


def git(m):
    os.system('git config user.name bot; git config user.email bot@users.noreply.github.com; git add -A; '
              f'git diff --cached --quiet || git commit -qm "{m}"')
    for _ in range(4):
        if os.system('git pull -q --rebase -X theirs --autostash && git push -q') == 0: break


def tgfile(fid, path):
    p = requests.get(API + '/getFile', params={'file_id': fid}).json()
    if not p.get('ok'): raise Exception('Telegram: ' + str(p.get('description')))
    open(path, 'wb').write(requests.get(f'https://api.telegram.org/file/bot{TG}/' + p['result']['file_path']).content)


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


def parse_product(cap):
    m = re.search(r'https?://\S+', cap or '')
    if not m or '|' not in cap: return None
    link = m.group(0)
    parts = [x.strip() for x in cap.replace(link, '').split('|')]
    parts = [x for x in parts if x]
    if len(parts) < 3: return None
    return {'name': parts[0], 'price': parts[1],
            'points': [x.strip() for x in parts[2].split(';') if x.strip()], 'link': link}


def fetch(quiet=False):
    pull()
    try:
        s = load('stock.json', {'offset': 0, 'items': []})
        prods = load('products.json', [])
        chat = os.environ.get('TG_CHAT_ID'); n = np_ = skip = other = 0
        r = requests.get(API + '/getUpdates', params={'offset': s['offset']}).json()
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
                pr = parse_product(cap)
                if not pr: other += 1; continue
                i = ph[-1]['file_unique_id']
                if any(q['id'] == i for q in prods): continue
                prods.append({**pr, 'id': i, 'gid': gid, 'photos': [ph[-1]['file_id']], 'status': 'new'})
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
        msg = f"{n} video baru, stok {len(s['items'])}"
        if np_: msg += f", {np_} produk baru menunggu dirender"
        if skip: msg += f", {skip} pesan diabaikan karena Chat ID tidak cocok"
        if other: msg += f", {other} pesan lain"
        if not quiet or n or np_ or skip or other: status(True, msg)
    except Exception as e:
        status(False, str(e)[:200])
    git('bot: ambil telegram')


def clean(*lists):
    ref = {x['id'] for l in lists for x in l} | {x['id'] for x in load('stock.json', {'items': []})['items']}
    if os.path.isdir('thumbs'):
        for f in os.listdir('thumbs'):
            if f[:-4] not in ref: os.remove('thumbs/' + f)


def wrap(d, text, font, width):
    out, cur = [], ''
    for w in text.split():
        t = (cur + ' ' + w).strip()
        if d.textlength(t, font=font) <= width: cur = t
        else:
            if cur: out.append(cur)
            cur = w
    if cur: out.append(cur)
    return out


def scene(photo, top, bot, path):
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    W, H = 1080, 1920
    im = Image.open(photo).convert('RGB')
    s = max(W / im.width, H / im.height)
    bg = im.resize((int(im.width * s) + 1, int(im.height * s) + 1))
    bg = bg.crop(((bg.width - W) // 2, (bg.height - H) // 2, (bg.width + W) // 2, (bg.height + H) // 2))
    bg = bg.filter(ImageFilter.GaussianBlur(40)).point(lambda v: int(v * 0.45))
    k = min(920 / im.width, 900 / im.height)
    fg = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))))
    bg.paste(fg, ((W - fg.width) // 2, 430 + (900 - fg.height) // 2))
    d = ImageDraw.Draw(bg)

    def put(text, size, y, fill):
        f = ImageFont.truetype(FONT, size)
        for ln in wrap(d, text, f, 960):
            x = (W - d.textlength(ln, font=f)) / 2
            d.text((x + 3, y + 3), ln, font=f, fill='black')
            d.text((x, y), ln, font=f, fill=fill)
            y += int(size * 1.25)

    put(top[0], top[1], 200, 'yellow')
    put(bot[0], bot[1], 1400, 'white')
    bg.save(path)
    return bg


def render_product(p):
    d = '/tmp/r' + re.sub(r'\W', '', p['id'])[:10]
    os.makedirs(d, exist_ok=True)
    ph = []
    for i, fid in enumerate(p['photos'][:5]):
        tgfile(fid, f'{d}/p{i}.jpg'); ph.append(f'{d}/p{i}.jpg')
    sc = [(('REKOMENDASI HARI INI', 56), (p['name'][:90], 72)), (('HARGA', 56), (p['price'][:30], 120))]
    for t in p['points'][:4]: sc.append((('KEUNGGULAN', 56), ('✔ ' + t[:80], 68)))
    sc.append((('MAU TAHU LEBIH LANJUT?', 56), ('Link ada di komentar pertama', 72)))
    lst = []
    for i, (top, bot) in enumerate(sc):
        png, mp = f'{d}/s{i}.png', f'{d}/s{i}.mp4'
        img = scene(ph[i % len(ph)], top, bot, png)
        if i == 0:
            os.makedirs('thumbs', exist_ok=True)
            img.resize((540, 960)).save(f"thumbs/{p['id']}.jpg")
        if os.system(f'ffmpeg -y -loglevel error -i {png} -vf "{ZP}" -c:v libx264 -preset veryfast {mp}') != 0:
            raise Exception('ffmpeg gagal membuat adegan')
        lst.append(f"file '{mp}'")
    open(f'{d}/list.txt', 'w').write('\n'.join(lst))
    out = f'{d}/out.mp4'
    if os.system(f'ffmpeg -y -loglevel error -f concat -safe 0 -i {d}/list.txt -f lavfi -i anullsrc=r=44100:cl=stereo '
                 f'-shortest -c:v copy -c:a aac -movflags +faststart {out}') != 0:
        raise Exception('ffmpeg gagal menggabungkan video')
    chat = os.environ.get('TG_CHAT_ID')
    r = requests.post(API + '/sendVideo', data={'chat_id': chat, 'supports_streaming': 'true', 'width': 1080, 'height': 1920},
                      files={'video': open(out, 'rb')}, timeout=300).json()
    if not r.get('ok'): raise Exception('Telegram: ' + str(r.get('description')))
    v = r['result']['video']
    return v['file_id'], v.get('duration', 0), v.get('file_size', os.path.getsize(out))


def render():
    pull()
    prods = load('products.json', [])
    todo = [p for p in prods if p.get('status') == 'new'][:3]
    if not todo: return
    os.system('command -v ffmpeg >/dev/null || (sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg); '
              'fc-list | grep -qi dejavu || sudo apt-get install -y -qq fonts-dejavu-core')
    stock = load('stock.json', {'offset': 0, 'items': []})
    chat = os.environ.get('TG_CHAT_ID')
    for p in todo:
        try:
            fid, dur, size = render_product(p)
            cap = f"{p['name']}\nHarga {p['price']}\n" + '\n'.join('✔ ' + x for x in p['points'][:4])
            stock['items'].append({'id': p['id'], 'file_id': fid, 'caption': cap, 'duration': dur, 'size': size,
                                   'thumb': True, 'link': p['link'], 'product': p['name']})
            p['status'] = 'done'
        except Exception as e:
            p['status'] = 'error'; p['error'] = str(e)[:200]
            try:
                requests.post(API + '/sendMessage', data={'chat_id': chat,
                              'text': 'Gagal membuat video produk "' + p['name'][:40] + '": ' + str(e)[:200]})
            except Exception: pass
    save('stock.json', stock); save('products.json', prods[-200:])
    git('bot: render video produk')


def gemini(x, cfg):
    base = {'description': x.get('caption', ''), 'hashtags': '', 'comment': ''}
    key = os.environ.get('GEMINI_KEY', '')
    if not key: return base
    try:
        parts = [{'text': 'Kamu ahli Facebook Reels Indonesia. Teks bawaan video: "' + (x.get('caption') or '-') +
                  '". Lihat gambar cuplikan video ini, lalu balas JSON {"description","hashtags","comment"}: '
                  'deskripsi menarik maksimal 150 karakter yang sesuai isi video (jangan menjanjikan hal yang tidak ada di video), '
                  '3-5 tagar relevan, dan komentar pertama yang mengajak berinteraksi. Bahasa Indonesia.'}]
        try:
            d = base64.b64encode(open(f"thumbs/{x['id']}.jpg", 'rb').read()).decode()
            parts.append({'inline_data': {'mime_type': 'image/jpeg', 'data': d}})
        except Exception: pass
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
        o = json.loads(r.json()['candidates'][0]['content']['parts'][0]['text'])
        h = o.get('hashtags', '')
        return {'description': o.get('description', ''), 'hashtags': ' '.join(h) if isinstance(h, list) else h,
                'comment': o.get('comment', '')}
    except Exception as e:
        print('GEMINI GAGAL:', str(e)[:200])
        return base


def caption(v, cfg):
    if v.get('link'):  # video produk
        ts = cfg.get('product_templates') or [{'description': '{caption}',
                                               'hashtags': '#rekomendasi #rekomendasishopee #ad',
                                               'comment': 'Link produk (afiliasi): {link}'}]
    else:
        ts = cfg.get('templates') or ([cfg['template']] if cfg.get('template') else [])
        if not ts: return gemini(v, cfg)
    t = random.choice(ts)
    return {k: str(t.get(k, '')).replace('{caption}', v.get('caption', '')).replace('{link}', v.get('link', ''))
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


{'fetch': fetch, 'run': jalan}[sys.argv[1]]()
