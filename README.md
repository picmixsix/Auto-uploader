# Auto-uploader# Auto-uploader

Autopilot Facebook Reels untuk afiliasi Shopee. Berjalan sepenuhnya di GitHub Actions, tanpa server.
Telegram dipakai sebagai kotak masuk, folder `data/` sebagai database, dan `index.html` (GitHub Pages) sebagai dashboard.

## Cara kerja

Workflow `bot.yml` berjalan tiap 15 menit dan menjalankan `bot.py run` dengan urutan:

1. **fetch**: ambil video dan foto produk dari Telegram.
2. **render**: buat video produk dari foto (`studio.py`), kirim pratinjau ke Telegram, masukkan ke stok.
3. **auto**: jadwalkan video dari stok ke slot jam di Autopilot.
4. **run**: unggah video yang sudah jatuh tempo ke fanspage lewat Graph API, lalu posting komentar pertama berisi link.

Tiap hari pukul 20:00 WIB `report.py` mengirim laporan ke Telegram.

## Setup

1. Aktifkan GitHub Pages untuk repo ini (Settings, Pages, branch `main`).
2. Buat bot lewat @BotFather dan buat token GitHub fine-grained dengan izin Contents, Actions, dan Secrets (read/write).
3. Buka dashboard, menu **Profil & Token**, isi data, lalu **Simpan & sinkronkan ke GitHub**. Secret berikut dibuat otomatis:
   - `TG_TOKEN`: token bot Telegram
   - `TG_CHAT_ID`: ID chat yang diizinkan
   - `PAGES_KEY`: kata sandi enkripsi token fanspage
   - `GEMINI_KEY`: kunci Gemini (opsional, tambahkan manual di Settings, Secrets)
4. Menu **Fanspage**: tempel JSON `[{id, name, token}]` atau hasil `/me/accounts` dari Graph API Explorer.
5. Menu **Autopilot**: atur jam posting, jumlah fanspage per video, dan template caption.

## Menambah konten

- **Video jadi**: kirim ke bot Telegram, lalu ketuk "Ambil video dari Telegram".
- **Produk baru**: kirim foto dengan keterangan (urutan bebas), atau isi lewat menu **Produk Baru** di dashboard.

```
Rak Piring Stainless
Rp39.000
Tidak karat; Muat 10 piring
https://s.shopee.co.id/xxxx
```

Bot membuat video lengkap dengan narasi suara dan menunggu di stok sampai dijadwalkan.

## Catatan penting

- **Jangan ganti `PAGES_KEY` sembarangan.** Token fanspage terenkripsi dengan kunci ini. Kalau berubah, semua token harus ditambahkan ulang. Simpan salinannya.
- Repo ini publik: isi `data/` bisa dilihat siapa saja. Keamanan token bergantung pada `PAGES_KEY` yang panjang dan acak.
- Hanya satu token bot Telegram per bot. Jangan jalankan program lain yang memakai token yang sama (error 409).
- Video lebih dari 20 MB tidak bisa diunduh bot dari Telegram.
- Upload yang terputus ditandai **Gagal** di Antrian. Cek fanspage dulu, lalu **Simpan perubahan** untuk mencoba lagi (fanspage yang sudah berhasil dilewati).

## File

| File | Fungsi |
|---|---|
| `bot.py` | fetch, render, jadwal, upload |
| `studio.py` | pembuat video (PIL, ffmpeg, edge-tts) |
| `report.py` | laporan harian ke Telegram |
| `index.html` | dashboard admin |
| `data/` | database JSON (stok, antrian, produk, fanspage, pengaturan) |
