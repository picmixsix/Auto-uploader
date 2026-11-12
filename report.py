import os, json, base64, datetime as dt, requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

TG = os.environ['TG_TOKEN']; CHAT = os.environ['TG_CHAT_ID']
GV = 'https://graph.facebook.com/v25.0'
WIB = dt.timezone(dt.timedelta(hours=7))


def load(f, d):
    try: return json.load(open('data/' + f))
    except Exception: return d


def dec(t):
    k = PBKDF2HMAC(hashes.SHA256(), 32, b'kantor-ai', 100000).derive(os.environ['PAGES_KEY'].encode())
    b = base64.b64decode(t)
    return AESGCM(k).decrypt(b[:12], b[12:], None).decode()


now = dt.datetime.now(dt.timezone.utc)
done, queue = load('done.json', []), load('queue.json', [])
stock, pages = load('stock.json', {'items': []})['items'], load('pages.json', [])

hari = [x for x in done if x.get('finished') and now - dt.datetime.fromisoformat(x['finished']) < dt.timedelta(hours=24)]
ok = sum(1 for x in hari for v in x.get('results', {}).values() if str(v).startswith('ok'))
gagal = [x for x in queue if x['status'] == 'failed']
tunggu = [x for x in queue if x['status'] == 'pending']
jadwal = sorted(x['at'] for x in tunggu if x.get('at'))

bad = []
for p in pages:
    try:
        r = requests.get(f'{GV}/me', params={'fields': 'id', 'access_token': dec(p['token'])}, timeout=20).json()
        if 'id' not in r: bad.append(p['name'])
    except Exception:
        bad.append(p['name'])

w = []
if bad: w.append('⚠️ Token bermasalah: ' + ', '.join(bad))
if gagal: w.append(f'⚠️ {len(gagal)} upload gagal, buka Antrian di web')
if len(stock) + len(tunggu) < 3: w.append('⚠️ Stok hampir habis, kirim video baru ke bot')

t = dt.datetime.now(WIB).strftime('%d/%m %H:%M')
msg = [f'Laporan Auto-uploader ({t} WIB)', '',
       f'Video terupload 24 jam terakhir: {len(hari)} ({ok} posting ke fanspage)',
       f'Gagal: {len(gagal)}', f'Menunggu di antrian: {len(tunggu)}', f'Stok video: {len(stock)}']
if jadwal:
    msg.append('Jadwal berikutnya: ' + dt.datetime.fromisoformat(jadwal[0].replace('Z', '+00:00')).astimezone(WIB).strftime('%d/%m %H:%M') + ' WIB')
if w: msg += [''] + w
else: msg += ['', '✅ Semua aman']

requests.post(f'https://api.telegram.org/bot{TG}/sendMessage', data={'chat_id': CHAT, 'text': '\n'.join(msg)})
