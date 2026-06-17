# FEWS Approval Monitoring

FEWS Approval Monitoring adalah aplikasi lokal untuk upload Excel approval/setoran bank, mendeteksi indikator fraud, dan membantu auditor menindaklanjuti temuan.

## Fitur Inti

- Upload satu file Excel approval dengan format setoran bank asli.
- Mendukung header dua baris seperti `kodelokasi`, `idunix`, `tgl_bukubesar`, `jumlah_setor`, `tgl_bank`, `waktu_bank`, dan `created_at`.
- Deteksi otomatis setelah upload.
- Data aktif lama diarsipkan saat upload batch baru, bukan dihapus permanen.
- Alert Center dengan filter, indikator, skor, rincian alasan, dan status tindak lanjut.
- Dashboard ringkas untuk total data, need review, high alert, tren, dan indikator paling sering.
- Export laporan Excel/PDF.

## Indikator Aktif

- Input pada rentang waktu perhatian.
- Input sebelum pembayaran diterima.
- Keterlambatan input data setor transfer/tunai.
- Tanggal input dan tanggal setor tidak konsisten.
- Jumlah biaya tidak sesuai jumlah setor.

Khusus keterlambatan input lebih dari 10 hari kerja, hasil dinaikkan menjadi warning merah (`UNMATCHED`).

## Login Default

- Admin: `admin` / `admin123`
- Auditor: `auditor` / `auditor123`
- Viewer: `viewer` / `viewer123`

## Jalankan Lokal

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

Atau gunakan launcher:

```powershell
.\start_fews.bat
```

Lalu buka:

```text
http://127.0.0.1:8000
```

## Deploy / Pindah Device

- Untuk pindah device, extract folder project lalu jalankan instalasi dependency seperti langkah lokal.
- Untuk Vercel, gunakan repo/folder ini dengan `vercel.json` yang sudah tersedia.
- Jika memakai database persistent di Vercel, set environment variable `DATABASE_URL` ke Postgres/Supabase.
- Database lokal tersimpan di `storage\fews_dana_masuk.db`.

## Struktur Utama

- `app/`: aplikasi FastAPI, template, static CSS, rule engine.
- `api/`: entrypoint Vercel.
- `docs/`: dokumen pendukung dan PRD frontend.
- `tests/`: regression test.
- `storage/`: database lokal dan upload lokal.
- `run.py`: launcher Python lokal.
