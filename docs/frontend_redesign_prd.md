# FEWS Monitoring PRD — Pembaruan 14 Juli 2026

## Tujuan

Memperbarui FEWS menjadi layar monitoring audit berbasis Wilayah → Area → Lokasi yang mengikuti SOP dan layout FEWS terbaru. Aplikasi tetap memakai FastAPI, Jinja, SQLAlchemy, CSS, dan JavaScript ringan.

## Navigasi dan hak akses

- Admin/auditor: **Dashboard** dan **Laporan**.
- Akun wilayah read-only: **Dashboard**, **Laporan**, dan **Alert Center**.
- Satu akun dibuat untuk setiap 15 wilayah pada master organisasi.
- Detail KPI, grafik, laporan, temuan, ekspor, dan Alert Center akun wilayah hanya memuat data wilayah tersebut.
- Ranking wilayah pada Dashboard bersifat dashboard umum/nasional dan tetap dapat dilihat akun wilayah tanpa membuka invoice atau detail wilayah lain.
- Seluruh indikator dan informasi dashboard awal dipindahkan ke menu `Info`; modal ringkasan lama dihapus. Menu ini mengikuti pembatasan wilayah akun dan tidak mengembalikan upload/manual input yang sudah dinonaktifkan.
- Hanya admin/auditor yang dapat mengubah status verifikasi atau tindak lanjut.
- Menu **Info** mempertahankan seluruh informasi monitoring dashboard lama dalam halaman terpisah.
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
- jenis periode (`bulanan` atau `mingguan`);
- bulan (`YYYY-MM`) saat periode bulanan aktif;
- minggu ISO (`YYYY-Www`) saat periode mingguan aktif;
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
- grafik batang per indikator dan per lokasi;
- grafik garis perbandingan enam periode bulanan atau mingguan beserta analisis perubahan periode terakhir;
- ranking wilayah/lokasi per periode;
- dua tabel ranking lokasi yang eksplisit: 10 risiko terparah dan 10 risiko terendah;
- akses detail berbasis wilayah.

## Data pengujian

- `UJI`: data ringkas untuk regression test.
- `REALISTIS`: data sintetis menyerupai pola operasional, bukan data produksi atau temuan audit nyata.

Loader harus idempoten, memetakan area dari master lokasi, dan tidak otomatis mengisi database produksi.

## Ekspor

Ekspor PDF dan Excel harus mengikuti filter aktif dan selalu dibatasi ke satu wilayah. Akun wilayah otomatis memakai wilayah yang terkunci pada akunnya; admin/auditor wajib memilih wilayah dan ekspor nasional tanpa wilayah ditolak. Keduanya memuat konteks periode, ringkasan, grafik tren, grafik indikator, grafik lokasi, ranking 10 risiko terparah dan 10 risiko terendah, serta tabel detail ID Unix–kesalahan–jumlah–skor. Excel memakai tabel terstruktur, autofilter, freeze pane, dan chart Excel yang dapat diedit. PDF memakai grafik vektor dan tabel yang dapat berlanjut ke halaman berikutnya.

## Kriteria penerimaan

- Master berisi tepat 15 wilayah, 41 area, dan 165 lokasi.
- Semua akun wilayah dibuat idempoten dengan role `viewer` dan wilayah terkunci.
- Akun wilayah hanya melihat detail wilayahnya pada Dashboard, Laporan, ekspor, dan Alert Center.
- Ranking nasional tetap terlihat pada Dashboard akun wilayah.
- Akun wilayah tidak dapat memverifikasi atau mengubah tindak lanjut.
- Admin melihat Dashboard/Info/Laporan pada navigasi; akun wilayah juga melihat Alert Center.
- Tidak ada tombol/form upload atau manual input pada UI.
- Filter area memengaruhi data secara nyata.
- Filter mingguan dan bulanan memengaruhi data secara nyata dan konsisten pada Dashboard, Laporan, PDF, dan Excel.
- Grafik garis, grafik indikator/lokasi, top/bottom 10, tabel detail, status verifikasi, dataset sintetis, dan ekspor tetap berfungsi.
- Informasi yang tampil pada Dashboard dan Laporan mempunyai padanan data pada PDF dan Excel untuk filter wilayah yang sama.
- Regression test serta QA desktop/mobile lulus tanpa error console atau overflow kritis.

## Batasan

- Tidak ada integrasi sumber produksi baru pada perubahan ini.
- Data sintetis tidak boleh disebut sebagai data real produksi.
- Route legacy input/upload boleh dipertahankan hanya sebagai redirect/response aman dan tidak boleh muncul sebagai fungsi yang dapat digunakan.
