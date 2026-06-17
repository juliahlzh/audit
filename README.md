# Fraud Early Warning System (FEWS) - Dana Masuk

Sistem FEWS lokal untuk memeriksa apakah dana masuk dari customer sudah sesuai dengan input cabang.

## Fitur Inti

- Input dua sumber data:
  - Input Cabang
  - Mutasi Bank (Dana Masuk)
- Auto matching dengan aturan:
  - Nominal
  - Fuzzy matching nama pengirim/customer
  - Kode unik/invoice dari deskripsi mutasi
  - Rentang tanggal transfer `+-2 hari`
- Status otomatis:
  - `MATCHED` (hijau)
  - `NEED REVIEW` (kuning)
  - `UNMATCHED` (merah)
- Risk scoring otomatis:
  - Nama beda: `+2`
  - Nominal beda jauh: `+3`
  - Tanggal beda jauh: `+3`
  - Input cabang tanpa mutasi: `+4`
  - Mutasi tanpa input cabang: `+4`
  - `Total skor > 7 => High Alert`
- Deteksi pola mencurigakan:
  - Double Input
  - Double Transfer
  - Transfer tanpa identitas jelas
  - Selisih aneh `+100/+500`
- Dashboard FEWS Dana Masuk:
  - Total input cabang
  - Total mutasi masuk
  - Total matched / need review / unmatched
  - Daftar transaksi mencurigakan
  - Tren harian
- Alert Center + export laporan Excel/PDF

## Login Default

- Admin: `admin` / `admin123`
- Auditor: `auditor` / `auditor123`
- Viewer: `viewer` / `viewer123`

## Jalankan Sistem Lokal

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe run.py
```

Atau:

```powershell
python run.py
```

Lalu buka `http://127.0.0.1:8000`.

Launcher siap pakai:

- [start_fews.bat](D:\audit\start_fews.bat): mode standar (port default 8000)
- [start_fews_autoport.bat](D:\audit\start_fews_autoport.bat): otomatis cari port kosong (8000-8100)
- [start_fews_lan.bat](D:\audit\start_fews_lan.bat): akses dari laptop lain dalam jaringan LAN

## Alur Penggunaan

1. Buka menu `Input Cabang` dan masukkan data customer.
   Atau upload file Excel/CSV massal di halaman yang sama. Header bersifat fleksibel (menggunakan alias nama kolom).
2. Buka menu `Mutasi Bank` dan masukkan data dana masuk.
   Bisa juga upload Excel/CSV mutasi bank langsung dari halaman `Mutasi Bank`.
3. Sistem otomatis menjalankan matching setiap ada data baru.
4. Buka `Alert Center` untuk investigasi mismatch/high alert.
5. Gunakan `Run Matching` untuk rekonsiliasi ulang massal.

## Integrasi Google Sheets / AppSheet / Local AI

Panduan lengkap ada di:

- [Panduan FEWS Dana Masuk](D:\audit\docs\fews_dana_masuk_guide.md)
- [Script Google Apps Script](D:\audit\docs\google_apps_script_fews.gs)

## Struktur Data Utama

- `branch_inputs` (Input Cabang)
- `bank_mutations` (Mutasi Bank)
- `matching_results` (Hasil matching + risiko)
- `audit_logs`
- `users`
