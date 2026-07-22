# FEWS Approval Monitoring

FEWS adalah aplikasi monitoring audit untuk mendeteksi indikator fraud, memeringkat wilayah/area/lokasi, membandingkan tren risiko, memverifikasi temuan, dan mengekspor laporan.

## Fitur

- Dashboard ranking wilayah per periode, KPI, grafik garis enam periode, grafik indikator, dan grafik lokasi.
- Menu Info memuat indikator, aturan skor, tren approval, indikator teratas, prioritas investigasi, dan aktivitas dari dashboard awal.
- Filter wilayah, area, lokasi, periode bulanan/mingguan, jenis kesalahan, dan status verifikasi.
- Ranking lokasi lengkap serta tabel 10 risiko terparah dan 10 risiko terendah.
- Tabel `ID Unix–Kesalahan–Jumlah–Skor` sesuai layout SOP.
- Ekspor PDF dan Excel per wilayah dengan konteks filter, grafik tren/indikator/lokasi, top/bottom 10, dan tabel detail; ekspor nasional tanpa wilayah ditolak.
- Master organisasi: 15 wilayah, 41 area, dan 166 lokasi dengan kode lokasi SIL resmi.
- Kode SIL seperti `278` otomatis dipetakan menjadi lokasi, wilayah, dan area (contoh: `278` → Merduati → Area Aceh → Sumatera Bagian Utara).
- Satu akun Admin Wilayah read-only untuk masing-masing dari 15 wilayah. Dashboard detail, Laporan, dan Alert Center otomatis dibatasi ke wilayah akun.
- Ranking wilayah nasional tetap terlihat pada dashboard akun wilayah tanpa membuka detail temuan wilayah lain.
- Admin Pusat memiliki **Dashboard**, **Info**, **Laporan**, **Alert Center**, dan **Upload Data** serta dapat melihat seluruh wilayah.
- Admin Wilayah hanya memiliki **Dashboard**, **Laporan**, dan **Alert Center** dalam mode view-only.
- Data uji dan data realistis sintetis untuk QA.

Manual input tetap dinonaktifkan. Upload Excel/CSV hanya tersedia untuk Admin Pusat; kode lokasi SIL divalidasi dan dipetakan otomatis. Upload harian menambahkan histori, sedangkan `idunix` yang sudah ada diperlakukan sebagai koreksi: versi sebelumnya diarsipkan dan versi baru menjadi aktif. Perubahan status/verifikasi hanya dapat dilakukan oleh admin atau auditor; akun wilayah hanya melihat data.

## Aturan SOP aktif

- Input pada rentang waktu perhatian 00.01–05.00.
- Input sebelum pembayaran diterima.
- Input maksimal H+2 hari kerja dari tanggal bank.
- Keterlambatan H+3 dan seterusnya dinilai bertingkat; lebih dari H+10 menjadi warning merah.
- Tanggal input dan tanggal setor tidak konsisten.
- Jumlah biaya tidak sesuai jumlah setor.

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
- batas bawaan upload adalah 15 MB, 25.000 baris, dan 100 MB ukuran workbook setelah diekstrak. Batas dapat diubah melalui `FEWS_MAX_UPLOAD_BYTES`, `FEWS_MAX_UPLOAD_ROWS`, dan `FEWS_MAX_XLSX_UNCOMPRESSED_BYTES`.

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

Test mencakup rule SOP, persistence, pembatasan wilayah, master organisasi, mode read-only, akses upload Admin Pusat, pemetaan kode SIL, Alert Center, filter, verifikasi, ranking, Excel, loader data, performa query, dan route legacy yang dinonaktifkan.

## Deploy

- Database lokal: `storage/fews_dana_masuk.db`.
- Untuk Vercel/produksi, set `DATABASE_URL` ke Postgres/Supabase agar data persisten.
- Set `FEWS_SESSION_SECRET` yang kuat dan password seed production sebelum deployment pertama.
- Jalankan `scripts/migrate_database.py` saat memperbarui database lama agar kolom `location_code`, `region`, `area`, dan `data_type` tersedia serta kode SIL lama dipetakan ulang.
