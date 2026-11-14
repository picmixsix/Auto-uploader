import os, sys, json, time, base64, random, re, datetime as dt, requests
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
    d = tag(d if BASE in d else (d + '\n\n' + BASE).strip(), name, x['id'])
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


def fetch(quiet=False):
    pull()
    try:
        s = load('stock.json', {'offset': 0, 'items': []})
        chat = os.environ.get('TG_CHAT_ID'); n = skip = other = 0
        r = requests.get(API + '/getUpdates', params={'offset': s['offset']}).json()
        if not r.get('ok'): raise Exception('Telegram: ' + str(r.get('description')) + ' (jika 409: ada bot lain yang memakai token ini)')
        for u in r['result']:
            s['offset'] = u['update_id'] + 1
            m = u.get('message') or u.get('channel_post') or {}
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
        save('stock.json', s)
        msg = f"{n} video baru, stok {len(s['items'])}"
        if skip: msg += f", {skip} video diabaikan karena Chat ID tidak cocok"
        if other: msg += f", {other} pesan bukan video"
        if not quiet or n or skip or other: status(True, msg)
    except Exception as e:
        status(False, str(e)[:200])
    git('bot: ambil video telegram')


def clean(*lists):
    ref = {x['id'] for l in lists for x in l} | {x['id'] for x in load('stock.json', {'items': []})['items']}
    if os.path.isdir('thumbs'):
        for f in os.listdir('thumbs'):
            if f[:-4] not in ref: os.remove('thumbs/' + f)


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
    ts = cfg.get('templates') or ([cfg['template']] if cfg.get('template') else [])
    if ts:
        t = random.choice(ts)
        return {k: str(t.get(k, '')).replace('{caption}', v.get('caption', '')) for k in ('description', 'hashtags', 'comment')}
    return gemini(v, cfg)


def auto():
    cfg = load('auto.json', {})
    if not cfg.get('enabled'): return
    fetch(quiet=True)
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
    auto()
    run()


{'fetch': fetch, 'run': jalan}[sys.argv[1]]()
