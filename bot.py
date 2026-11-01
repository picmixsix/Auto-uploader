import os, sys, json, time, base64, random, datetime as dt, requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

TG = os.environ.get('TG_TOKEN', '')
API = f'https://api.telegram.org/bot{TG}'
GV = 'https://graph.facebook.com/v25.0'


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


def post(page, tok, x):
    n = os.path.getsize('v.mp4')
    a = requests.post(f'{GV}/{page}/video_reels', data={'upload_phase': 'start', 'access_token': tok}).json()
    if 'video_id' not in a: raise Exception(a)
    r = requests.post(a['upload_url'], headers={'Authorization': 'OAuth ' + tok, 'offset': '0', 'file_size': str(n)},
                      data=open('v.mp4', 'rb'))
    if r.status_code != 200: raise Exception(r.text)
    d = (x.get('description', '') + '\n\n' + x.get('hashtags', '')).strip()
    f = requests.post(f'{GV}/{page}/video_reels', data={'upload_phase': 'finish', 'video_id': a['video_id'],
                      'video_state': 'PUBLISHED', 'description': d, 'access_token': tok}).json()
    if not f.get('success'): raise Exception(f)
    st = {}
    for _ in range(12):  # tunggu Facebook memproses video, maks ~2 menit
        time.sleep(10)
        st = requests.get(f"{GV}/{a['video_id']}", params={'fields': 'status', 'access_token': tok}).json().get('status', {})
        if st.get('video_status') in ('ready', 'error', 'upload_failed', 'expired'): break
    if st.get('video_status') in ('error', 'upload_failed', 'expired'): raise Exception('Facebook: ' + json.dumps(st)[:250])
    if x.get('comment'):
        c = requests.post(f"{GV}/{a['video_id']}/comments", data={'message': x['comment'], 'access_token': tok}).json()
        if 'id' not in c: return 'ok (komentar gagal)'
    return 'ok'


def status(ok, msg):
    s = load('status.json', {})
    s['fetch'] = {'at': dt.datetime.now(dt.timezone.utc).isoformat(), 'ok': ok, 'msg': msg}
    save('status.json', s)


def fetch():
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
        status(True, msg)
    except Exception as e:
        status(False, str(e)[:200])
    git('bot: ambil video telegram')


def clean(*lists):
    ref = {x['id'] for l in lists for x in l} | {x['id'] for x in load('stock.json', {'items': []})['items']}
    if os.path.isdir('thumbs'):
        for f in os.listdir('thumbs'):
            if f[:-4] not in ref: os.remove('thumbs/' + f)


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
                try: res[pid] = post(pid, dec(p['token']), x)
                except Exception as e: res[pid] = 'gagal: ' + str(e)[:200]
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


{'fetch': fetch, 'run': run}[sys.argv[1]]()
