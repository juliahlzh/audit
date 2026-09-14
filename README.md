# FEWS Approval Monitoring

FEWS adalah aplikasi monitoring audit untuk mendeteksi indikator fraud, memeringkat wilayah/area/lokasi, membandingkan tren risiko, memverifikasi temuan, dan mengekspor laporan.

## Fitur

- Dashboard ringkas dengan grafik tren temuan per wilayah/lokasi yang dapat di-zoom dan di-scroll, KPI utama, penyebab per lokasi, dan detail prioritas.
- Menu Info memuat indikator, aturan skor, tren approval, indikator teratas, prioritas investigasi, dan aktivitas dari dashboard awal.
- Filter wilayah, area, lokasi, periode bulanan/mingguan, jenis kesalahan, dan status verifikasi.
- Ranking lokasi lengkap serta tabel 10 risiko tertinggi dan 10 risiko terendah.
- Tabel `ID Unix–Kesalahan–Jumlah–Skor` sesuai layout SOP.
- Ekspor PDF dan Excel per wilayah dengan konteks filter, grafik tren/indikator/lokasi, top/bottom 10, dan tabel detail; ekspor nasional tanpa wilayah ditolak.
- Master organisasi: 15 wilayah, 41 area, dan 166 lokasi dengan kode lokasi SIL resmi.
- Kode SIL seperti `278` otomatis dipetakan menjadi lokasi, wilayah, dan area (contoh: `278` → Merduati → Area Aceh → Sumatera Bagian Utara).
- Satu akun Admin Wilayah read-only untuk masing-masing dari 15 wilayah. Dashboard detail, Laporan, dan Alert Center otomatis dibatasi ke wilayah akun.
- Ranking wilayah nasional tetap terlihat pada dashboard akun wilayah tanpa membuka detail temuan wilayah lain.
- Admin Pusat memiliki **Dashboard**, **Info**, **Laporan**, **Alert Center**, dan **Upload Data** serta dapat melihat seluruh wilayah.
- Admin Wilayah hanya memiliki **Dashboard**, **Laporan**, dan **Alert Center** dalam mode view-only.
- Data uji dan data realistis sintetis untuk QA.
- Central Collection Monitoring memisahkan status pembayaran VA dari aktivitas follow-up staff, menyediakan Need Attention nasional, histori reminder, dan akses collection yang dibatasi per wilayah.

Manual input tetap dinonaktifkan. Upload Excel/CSV hanya tersedia untuk Admin Pusat; kode lokasi SIL divalidasi dan dipetakan otomatis. Upload harian menambahkan histori, sedangkan `idunix` yang sudah ada diperlakukan sebagai koreksi: versi sebelumnya diarsipkan dan versi baru menjadi aktif. Perubahan status/verifikasi hanya dapat dilakukan oleh admin atau auditor; akun wilayah hanya melihat data.

Dashboard tidak memuat form upload. Admin Pusat menggunakan menu **Upload Data**, sedangkan menu **Laporan** memuat tabel lengkap, verifikasi, ranking, serta export PDF/Excel.

## Aturan SOP aktif

- Input pada rentang waktu perhatian 00.01–05.00.
- Input sebelum pembayaran diterima.
- Input maksimal H+2 hari kerja dari tanggal bank.
- Keterlambatan H+3 dan seterusnya dinilai bertingkat; lebih dari H+10 menjadi warning merah.
- Tanggal input dan tanggal setor tidak konsisten.
- Jumlah biaya tidak sesuai jumlah setor.
- Double Input Bukti Transfer: fingerprint transaksi dan referensi bukti transfer yang sama ditemukan lebih dari satu kali.

Detail scope dan kriteria penerimaan ada di [`docs/frontend_redesign_prd.md`](docs/frontend_redesign_prd.md). Implementasi rule ada di [`app/services/rule_config.py`](app/services/rule_config.py).

## Jalankan lokal

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

Buka `http://127.0.0.1:8000`.

## Akun pengembangan lokal

- Admin Pusat: `admin` / `admin123`
- Auditor nasional: `auditor` / `auditor123`
- Viewer nasional: `viewer` / `viewer123`
- 15 akun Admin Wilayah menggunakan password lokal `wilayah123`:
  `sumbagut`, `sumbagsel`, `banten`, `mega_barat1`, `mega_barat2`, `mega_selatan`, `mega_utara`, `mega_timur`, `mega_timur_plus`, `bekasi_plus`, `bekasi_kota`, `jabartara`, `bogor_plus`, `bandung_raya`, dan `jatijaya`.

Default tersebut hanya berlaku pada pengembangan lokal. Kredensial tidak ditampilkan pada halaman login dan tidak boleh dipakai untuk production.

Pada environment production, proses seed akun baru mewajibkan variabel berikut dengan password minimal 12 karakter:

- `FEWS_ADMIN_PASSWORD`
- `FEWS_AUDITOR_PASSWORD`
- `FEWS_VIEWER_PASSWORD`
- `FEWS_REGIONAL_PASSWORD`

Konfigurasi keamanan deployment minimum:

- `FEWS_SESSION_SECRET` berupa nilai acak panjang dan stabil;
- `FEWS_COOKIE_SECURE=true` untuk HTTPS;
- `DATABASE_URL` Postgres/Supabase agar data persisten;
- `FEWS_VA_WEBHOOK_SECRET` untuk autentikasi header `X-FEWS-VA-Secret` pada sinkronisasi pembayaran;
- `CRON_SECRET` untuk runner reminder harian Vercel;
- `FEWS_COLLECTION_REMINDER_DAYS` bila threshold H+1, H+3, H+7, H+14 perlu diubah (format contoh: `1,3,7,14`);
- batas bawaan upload adalah 15 MB, 25.000 baris, dan 100 MB ukuran workbook setelah diekstrak. Batas dapat diubah melalui `FEWS_MAX_UPLOAD_BYTES`, `FEWS_MAX_UPLOAD_ROWS`, dan `FEWS_MAX_XLSX_UNCOMPRESSED_BYTES`.

## Integrasi Collection dari Virtual Account

Kirim `POST /api/collection/va` dengan header `X-FEWS-VA-Secret`. Endpoint menerima satu objek, array, atau `{ "items": [...] }`, maksimal 5.000 item per request. `external_id` wajib stabil untuk satu siswa dan cicilan agar kiriman ulang memperbarui data yang sama.

```json
{
  "external_id": "VA-134-S001-03",
  "student_id": "S001",
  "student_name": "Nama Siswa",
  "location": "134",
  "staff_pic": "PIC Lokasi",
  "installment_number": "3",
  "amount_due": 1500000,
  "due_date": "2026-09-01",
  "outstanding": 500000,
  "last_payment_at": "2026-09-10T08:30:00Z"
}
```

Vercel memanggil `GET /api/collection/reminders/run` setiap hari pukul 08.00 WIB. Route memverifikasi `Authorization: Bearer <CRON_SECRET>` dan tidak membuat reminder ganda untuk task dan level yang sama.

## Data QA

Dataset berikut sepenuhnya sintetis dan bukan data produksi:

- `sample_data/fews_uji.csv` — kasus ringkas untuk pengujian fitur.
- `sample_data/fews_realistis.csv` — pola operasional lintas wilayah Januari–Juni 2026.

Muat secara eksplisit dan idempoten:

```powershell
.\.venv\Scripts\python.exe scripts\load_sample_data.py uji
.\.venv\Scripts\python.exe scripts\load_sample_data.py realistis
# atau keduanya
.\.venv\Scripts\python.exe scripts\load_sample_data.py semua
```

Loader tidak berjalan otomatis dan tidak mengganti status verifikasi data yang sudah ada.

## Test

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Test mencakup rule SOP, persistence, pembatasan wilayah, master organisasi, mode read-only audit, akses upload Admin Pusat, pemetaan kode SIL, Alert Center, filter, verifikasi, ranking, Excel, loader data, performa query, route legacy yang dinonaktifkan, sinkronisasi VA, collection wilayah, follow-up, reminder, dan penyelesaian otomatis pembayaran.

## Deploy

- Di Vercel, pilih **Framework Preset: FastAPI** dan arahkan **Root Directory** ke root repository yang memuat `index.py`, `requirements.txt`, dan `vercel.json`.
- Jangan menambahkan catch-all rewrite ke `/api/index.py`; entrypoint root `index.py` membuat Vercel meneruskan path asli seperti `/login`, `/dashboard`, dan `/reports` langsung ke router FastAPI.
- Jalankan `scripts/migrate_database.py` satu kali sebelum deploy production. Migrasi tidak dijalankan saat cold-start Vercel agar beberapa instance tidak memperbarui skema/data secara bersamaan.
- Database lokal: `storage/fews_dana_masuk.db`.
- Untuk Vercel/produksi, set `DATABASE_URL` ke Postgres/Supabase agar data persisten.
- Set `FEWS_SESSION_SECRET` yang kuat dan password seed production sebelum deployment pertama.
- Jalankan `scripts/migrate_database.py` saat memperbarui database lama agar kolom `location_code`, `region`, `area`, dan `data_type` tersedia serta kode SIL lama dipetakan ulang.
