# Panduan Implementasi FEWS Dana Masuk

Panduan ini melengkapi aplikasi lokal (`FastAPI`) dengan setup Google Sheets + AppSheet + Local AI.

## 1) Struktur Sheet

Buat 4 sheet:

- `Cabang`
- `Mutasi`
- `Matching`
- `Dashboard`

### Sheet `Cabang`

Kolom:

1. `A` ID
2. `B` Tanggal transaksi
3. `C` Nama cabang
4. `D` Nama customer
5. `E` Nominal harus bayar
6. `F` Nominal input cabang
7. `G` Metode pembayaran
8. `H` Kode unik/invoice
9. `I` Keterangan

### Sheet `Mutasi`

Kolom:

1. `A` ID
2. `B` Tanggal dana masuk
3. `C` Nama pengirim
4. `D` Nominal masuk
5. `E` Rekening perusahaan
6. `F` Deskripsi mutasi
7. `G` Keterangan

### Sheet `Matching`

Kolom output:

1. `A` Branch ID
2. `B` Mutasi ID
3. `C` Status
4. `D` Risiko
5. `E` Jenis Ketidaksesuaian
6. `F` Similarity Nama
7. `G` Selisih Nominal
8. `H` Selisih Hari
9. `I` Confidence
10. `J` Ringkasan

## 2) Formula Dasar (Alternatif cepat tanpa script)

Di `Cabang`, contoh lookup nominal mutasi berdasarkan invoice di deskripsi:

```excel
=IFERROR(INDEX(Mutasi!D:D, MATCH("*"&H2&"*", Mutasi!F:F, 0)), "")
```

Status sederhana:

```excel
=IF(J2="", "UNMATCHED", IF(ABS(F2-J2)<=1000, "NEED REVIEW", "MATCHED"))
```

Catatan: formula murni kurang kuat untuk fuzzy name, jadi direkomendasikan Apps Script.

## 3) Apps Script (Direkomendasikan)

- Pakai file: [google_apps_script_fews.gs](D:\audit\docs\google_apps_script_fews.gs)
- Fungsi utama: `runFEWSMatching()`
- Trigger otomatis:
  - `onEdit` untuk sheet `Cabang` dan `Mutasi`
  - atau time-driven (setiap 5/10 menit)

Output otomatis:

- `MATCHED / NEED REVIEW / UNMATCHED`
- Risk score dan mismatch type
- Daftar kasus `Belum Masuk` dan `Tidak Diinput`

## 4) Rule Risk Scoring

- Match: `0`
- Nama beda: `+2`
- Nominal beda: `+3`
- Tanggal beda jauh: `+3`
- Tidak ditemukan di mutasi: `+4`
- Dana masuk tidak ada input: `+4`
- `Score > 7 => High Alert`

## 5) Conditional Formatting

Di `Matching!C:C`:

- Text `MATCHED` => hijau
- Text `NEED REVIEW` => kuning
- Text `UNMATCHED` => merah

Di `Matching!D:D`:

- Nilai `>7` => merah tebal

## 6) AppSheet Setup

Gunakan Google Sheet yang sama sebagai source:

- Table `Cabang` (editable)
- Table `Mutasi` (editable/import)
- Table `Matching` (read only, hasil engine)

View yang disarankan:

- `Input Cabang` (Form)
- `Input Mutasi` (Form)
- `Alert Center` (Table + filter status != MATCHED)
- `Dashboard` (Chart matched/unmatched + high alert)

Automation AppSheet:

- Event: ketika row baru di `Cabang`/`Mutasi`
- Task: panggil webhook Apps Script / Apps Script API `runFEWSMatching`

## 7) Local AI Rule Engine

Untuk local AI ringan:

- Gunakan model kecil lokal untuk normalisasi nama (opsional)
- Engine rule tetap deterministic (lebih audit-friendly)
- Simpan log keputusan (`why matched`, `why alert`) untuk audit

Aplikasi lokal FEWS yang ada di repo ini sudah menerapkan rule engine deterministic + fuzzy match dan dashboard alert.
