# FEWS Approval Monitoring

FEWS adalah aplikasi monitoring audit untuk mendeteksi indikator fraud, memeringkat wilayah/area/lokasi, membandingkan tren risiko, memverifikasi temuan, dan mengekspor laporan.

## Fitur

- Dashboard ranking wilayah per periode, KPI, dan grafik garis enam bulan.
- Filter wilayah, area, lokasi, bulan, jenis kesalahan, dan status verifikasi.
- Ranking lokasi dari total skor terparah hingga terendah.
- Tabel `ID Unix–Kesalahan–Jumlah–Skor` sesuai layout SOP.
- Ekspor tabel Excel dengan ranking, autofilter, freeze pane, dan konteks filter.
- Master organisasi dari `Wilayah, Area, dan Lokasi.pptx`: 15 wilayah, 41 area, dan 165 lokasi.
- Satu akun read-only per wilayah. Dashboard detail, Laporan, dan Alert Center otomatis dibatasi ke wilayah akun.
- Ranking wilayah nasional tetap terlihat pada dashboard akun wilayah tanpa membuka detail temuan wilayah lain.
- Navigasi admin/auditor: **Dashboard** dan **Laporan**. Akun wilayah mendapat tambahan **Alert Center**.
- Data uji dan data realistis sintetis untuk QA.

Manual input dan upload Excel melalui UI sudah dinonaktifkan. Data produksi harus masuk melalui integrasi terkontrol di luar antarmuka FEWS. Perubahan status/verifikasi hanya dapat dilakukan oleh admin atau auditor; akun wilayah hanya melihat data.

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

- Admin: `admin` / `admin123`
- Auditor nasional: `auditor` / `auditor123`
- Viewer nasional: `viewer` / `viewer123`
- Akun wilayah menggunakan password lokal `wilayah123`:
  `sumbagut`, `sumbagsel`, `banten`, `mega_barat1`, `mega_barat2`, `mega_selatan`, `mega_utara`, `mega_timur`, `mega_timur_plus`, `bekasi_plus`, `bekasi_kota`, `jabartara`, `bogor_plus`, `bandung_raya`, dan `jatijaya`.

Ganti seluruh password default sebelum memakai data produksi. Kredensial tidak ditampilkan pada halaman login.

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

Test mencakup rule SOP, persistence, pembatasan wilayah, master organisasi, mode read-only, Alert Center, filter, verifikasi, ranking, Excel, loader data, performa query, dan route legacy yang dinonaktifkan.

## Deploy

- Database lokal: `storage/fews_dana_masuk.db`.
- Untuk Vercel/produksi, set `DATABASE_URL` ke Postgres/Supabase agar data persisten.
- Set `SESSION_SECRET` yang kuat dan ganti password akun sebelum produksi.
- Jalankan `scripts/migrate_database.py` saat memperbarui database lama agar kolom `region`, `area`, dan `data_type` tersedia.
