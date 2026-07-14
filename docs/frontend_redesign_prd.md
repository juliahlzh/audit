# FEWS Monitoring PRD — Pembaruan 14 Juli 2026

## Tujuan

Memperbarui FEWS menjadi layar monitoring audit berbasis Wilayah → Area → Lokasi yang mengikuti SOP dan layout FEWS terbaru. Aplikasi tetap memakai FastAPI, Jinja, SQLAlchemy, CSS, dan JavaScript ringan.

## Navigasi dan hak akses

- Admin/auditor: **Dashboard** dan **Laporan**.
- Akun wilayah read-only: **Dashboard**, **Laporan**, dan **Alert Center**.
- Satu akun dibuat untuk setiap 15 wilayah pada master organisasi.
- Detail KPI, grafik, laporan, temuan, ekspor, dan Alert Center akun wilayah hanya memuat data wilayah tersebut.
- Ranking wilayah pada Dashboard bersifat dashboard umum/nasional dan tetap dapat dilihat akun wilayah tanpa membuka invoice atau detail wilayah lain.
- Hanya admin/auditor yang dapat mengubah status verifikasi atau tindak lanjut.
- Tombol **Info** mempertahankan ringkasan fungsi dashboard lama.
- Manual input dan upload Excel tidak tersedia di UI operasional.

## Master organisasi

Sumber struktur adalah `D:\Audit\Wilayah, Area, dan Lokasi.pptx`:

- 15 wilayah;
- 41 area;
- 165 cabang/lokasi belajar.

Nama `Cabang Serang` pada baris Kramatwatu dinormalisasi sebagai `Area Serang` agar konsisten dengan rekap tiga area wilayah Banten. Master versi aplikasi disimpan di `app/services/organization.py` dan dipakai untuk akun, opsi filter, serta pemetaan lokasi.

## Filter

Dashboard dan Laporan memakai filter konsisten:

- wilayah;
- area;
- lokasi;
- periode bulanan;
- jenis kesalahan/indikator;
- status verifikasi (`Sudah Diverifikasi` atau `Belum Diverifikasi`).

Alert Center menyediakan filter wilayah/area serta filter risiko dan tindak lanjut yang sudah ada. Wilayah pada akun regional selalu terkunci.

## Definisi data

- **Wilayah** menaungi satu atau lebih area.
- **Area** menaungi satu atau lebih lokasi/cabang.
- **Lokasi** memakai `branch_name`.
- **Sudah Diverifikasi** berarti `follow_up_status = RESOLVED`.
- **Belum Diverifikasi** berarti status selain `RESOLVED`.
- Ranking menurun berdasarkan total skor, lalu high alert, need review, jumlah temuan, dan nama.
- Risiko: skor `> 7` tinggi, `4–7` sedang, dan `0–3` rendah.

## SOP dan visualisasi

Aturan indikator tetap mengikuti `app/services/rule_config.py`, termasuk batas input maksimal H+2 hari kerja dari tanggal bank dan warning merah setelah lebih dari H+10. Layout memuat:

- tabel ID Unix, kesalahan, jumlah kesalahan, dan skor;
- grafik per indikator dan lokasi;
- grafik garis perbandingan bulanan;
- ranking wilayah/lokasi per periode;
- akses detail berbasis wilayah.

## Data pengujian

- `UJI`: data ringkas untuk regression test.
- `REALISTIS`: data sintetis menyerupai pola operasional, bukan data produksi atau temuan audit nyata.

Loader harus idempoten, memetakan area dari master lokasi, dan tidak otomatis mengisi database produksi.

## Ekspor

Ekspor PDF dan Excel harus mengikuti filter aktif dan selalu dibatasi ke satu wilayah. Akun wilayah otomatis memakai wilayah yang terkunci pada akunnya; admin/auditor wajib memilih wilayah dan ekspor nasional tanpa wilayah ditolak. Excel berbentuk tabel, memiliki autofilter/freeze pane, memuat Wilayah–Area–Lokasi, serta diurutkan dari risiko terparah hingga terendah.

## Kriteria penerimaan

- Master berisi tepat 15 wilayah, 41 area, dan 165 lokasi.
- Semua akun wilayah dibuat idempoten dengan role `viewer` dan wilayah terkunci.
- Akun wilayah hanya melihat detail wilayahnya pada Dashboard, Laporan, ekspor, dan Alert Center.
- Ranking nasional tetap terlihat pada Dashboard akun wilayah.
- Akun wilayah tidak dapat memverifikasi atau mengubah tindak lanjut.
- Admin tetap hanya melihat Dashboard/Laporan pada navigasi; akun wilayah juga melihat Alert Center.
- Tidak ada tombol/form upload atau manual input pada UI.
- Filter area memengaruhi data secara nyata.
- Grafik garis, ranking, status verifikasi, dataset sintetis, dan ekspor tetap berfungsi.
- Regression test serta QA desktop/mobile lulus tanpa error console atau overflow kritis.

## Batasan

- Tidak ada integrasi sumber produksi baru pada perubahan ini.
- Data sintetis tidak boleh disebut sebagai data real produksi.
- Route legacy input/upload boleh dipertahankan hanya sebagai redirect/response aman dan tidak boleh muncul sebagai fungsi yang dapat digunakan.
