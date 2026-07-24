# FEWS Monitoring PRD — Pembaruan 24 Juli 2026

## Tujuan

Memperbarui FEWS menjadi layar monitoring audit berbasis Wilayah → Area → Lokasi yang mengikuti SOP dan layout FEWS terbaru. Aplikasi tetap memakai FastAPI, Jinja, SQLAlchemy, CSS, dan JavaScript ringan.

## Navigasi dan hak akses

- **Admin Pusat**: Dashboard Pusat, Info, Laporan, Alert Center, dan Upload Data Excel.
- **Admin Wilayah**: Dashboard Wilayah, Laporan, dan Alert Center dalam mode view-only.
- Satu akun Admin Wilayah dibuat untuk setiap 15 wilayah pada master organisasi.
- Admin Pusat dapat melihat seluruh wilayah dan menjadi satu-satunya tipe akun yang dapat mengunggah Excel approval ke FEWS.
- Upload harian bersifat append untuk `idunix` baru. Jika `idunix` sudah ada, versi lama diarsipkan sebagai audit trail dan versi baru menjadi data aktif.
- Admin Wilayah tidak dapat upload, input manual, mengarsipkan data, mengubah verifikasi, atau mengubah tindak lanjut.
- Detail KPI, grafik, laporan, temuan, ekspor, dan Alert Center akun wilayah hanya memuat data wilayah tersebut.
- Ranking wilayah pada Dashboard bersifat dashboard umum/nasional dan tetap dapat dilihat akun wilayah tanpa membuka invoice atau detail wilayah lain.
- Seluruh indikator dan informasi dashboard awal dipindahkan ke menu `Info`; modal ringkasan lama dihapus. Menu ini hanya tersedia untuk Admin Pusat dan tidak mengembalikan input manual yang sudah dinonaktifkan.
- Hanya admin/auditor yang dapat mengubah status verifikasi atau tindak lanjut.
- Tindak lanjut baru ditentukan otomatis dari skor: `INVESTIGATION` untuk skor > 7, `CLARIFICATION` untuk skor 4–7, `OPEN` untuk skor 1–3, dan `RESOLVED` untuk skor 0. Admin Pusat dapat mengoreksi status maupun catatan; koreksi ditandai sebagai manual dan dipertahankan saat matching dijalankan ulang.
- Menu **Info** mempertahankan seluruh informasi monitoring dashboard lama dalam halaman terpisah.
- Manual input tetap tidak tersedia. Upload Excel hanya tampil dan dapat dipakai oleh Admin Pusat.
- Dashboard tidak memuat form upload. Admin Pusat mengunggah data hanya melalui menu `Upload Data`, sehingga Dashboard dan Laporan mempunyai fungsi yang jelas dan berbeda.

## Master organisasi

Sumber struktur area adalah `D:\Audit\Wilayah, Area, dan Lokasi.pptx`, dilengkapi daftar kode lokasi SIL terbaru:

- 15 wilayah;
- 41 area;
- 166 cabang/lokasi belajar berkode SIL.

Nama `Cabang Serang` pada baris Kramatwatu dinormalisasi sebagai `Area Serang` agar konsisten dengan rekap tiga area wilayah Banten. Daftar kode SIL terbaru menjadi sumber identitas lokasi; `Graha Mustika Media` ditambahkan ke Area Kabupaten Bogor sehingga total master menjadi 166 lokasi. Master versi aplikasi disimpan di `app/services/organization.py` dan dipakai untuk akun, opsi filter, pemetaan lokasi/area, dashboard, dan export.

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
- **Kode Lokasi** memakai kode numerik SIL dan disimpan di `location_code`.
- **Lokasi** memakai nama kanonis `branch_name`; input berupa kode SIL otomatis dinormalisasi.
- **Sudah Diverifikasi** berarti `follow_up_status = RESOLVED`.
- **Belum Diverifikasi** berarti status selain `RESOLVED`.
- Ranking menurun berdasarkan total skor, lalu high alert, need review, jumlah temuan, dan nama.
- Risiko: skor `> 7` tinggi, `4–7` sedang, dan `0–3` rendah.

## SOP dan visualisasi

Aturan indikator tetap mengikuti `app/services/rule_config.py`, termasuk batas input maksimal H+2 hari kerja dari tanggal bank dan warning merah setelah lebih dari H+10. Layout memuat:

- indikator `Double Input Bukti Transfer`: dua atau lebih data aktif dengan nomor bukti, nominal setor, tanggal transaksi, jenis transaksi, dan lokasi yang sama; perbedaan ID Unix, waktu input, customer, atau petugas tidak membatalkan deteksi;
- seluruh transaksi yang masuk ke fingerprint Double Input yang sama ditampilkan sebagai satu grup agar dapat diverifikasi auditor;
- Dashboard memakai struktur Executive Dashboard yang dapat dipahami dalam waktu kurang dari 30 detik: KPI Cards → Grafik Analisis → Indikator Risiko Tertinggi dan Terendah → Risk Ranking → Detail Data;
- Dashboard tidak menampilkan tabel detail pada bagian atas halaman;
- KPI Admin Pusat mencakup total wilayah, lokasi, temuan, high/medium/low risk, total dan rata-rata skor nasional, wilayah paling berisiko, dan lokasi paling berisiko;
- KPI Admin Wilayah mencakup total lokasi, temuan, high/medium/low risk, total dan rata-rata skor wilayah, serta lokasi paling berisiko di wilayah;
- grafik Admin Pusat menampilkan distribusi risiko, total skor, dan jumlah temuan per wilayah, tren risiko nasional, serta komposisi high/medium/low;
- grafik Admin Wilayah memakai data lokasi di wilayahnya untuk distribusi, total skor, dan jumlah temuan, ditambah tren serta komposisi risiko wilayah;
- Dashboard menampilkan grafik batang vertikal jumlah kemunculan untuk seluruh indikator SOP sesuai filter aktif;
- Dashboard menampilkan perkembangan jumlah kemunculan indikator selama enam periode. Pilihan `bulanan` mengelompokkan data bulan per bulan dan pilihan `mingguan` mengelompokkan data minggu ISO per minggu sampai periode filter yang dipilih;
- daftar lengkap jenis indikator SOP, kategori, jumlah kemunculan, dan total skor indikator ditempatkan tepat di bawah grafik indikator;
- Dashboard Pusat memakai satu grafik batang vertikal **Skor Risiko 15 Wilayah** sebagai sorotan utama tepat setelah filter. Grafik selalu mempertahankan seluruh 15 wilayah, mengikuti filter periode/indikator/verifikasi, dan menandai wilayah yang sedang dipilih tanpa menyembunyikan wilayah lain;
- setelah grafik nasional, Dashboard hanya memuat ringkasan KPI, perkembangan periode, jumlah per indikator, serta **Ranking Lokasi Nasional** yang terdiri dari 10 lokasi berisiko tertinggi dan 10 lokasi berisiko terendah;
- setiap baris ranking lokasi menampilkan alasan skor berupa indikator penyebab dan frekuensinya. Skor nol dijelaskan sebagai tidak adanya indikator risiko pada filter aktif;
- tabel ID Unix, grup Double Input, search/sort/pagination detail lokasi, dan detail transaksi tidak ditampilkan pada Dashboard; seluruh pemeriksaan mendalam tersebut tersedia pada menu Laporan;
- Laporan memakai grafik visual yang sama dengan Dashboard, dimulai dari perbandingan 15 wilayah, lalu dilengkapi grafik indikator, perkembangan indikator, komposisi indikator per lokasi/wilayah, distribusi risiko, total skor, jumlah temuan, tren, dan daftar indikator SOP;
- tabel detail Laporan menampilkan ID Unix, tanggal, wilayah, area, kode lokasi, lokasi, kesalahan, jumlah kesalahan, skor, dan tipe data tanpa kolom Status Verifikasi maupun Aksi;
- grafik wilayah/lokasi berupa horizontal bar chart berbasis jumlah temuan, bukan skor, dan selalu merender seluruh kategori hasil filter tanpa batas top-10;
- grafik batang mendukung tooltip jumlah temuan dan total skor, scroll internal horizontal/vertikal, serta kontrol zoom in, zoom out, dan reset;
- panel Lokasi Paling Berisiko dan Lokasi Paling Aman memuat skor, jumlah temuan, level risiko, serta seluruh indikator penyebab yang diurutkan berdasarkan frekuensi;
- seluruh daftar peringkat menggunakan istilah Risk Ranking; rank #1 selalu berarti prioritas investigasi tertinggi;
- Admin Pusat melihat top/bottom 10 lokasi dan wilayah serta halaman Ranking Nasional Lokasi dan Wilayah;
- Admin Wilayah melihat top/bottom 10 lokasi miliknya dan ringkasan peringkat nasional wilayah tanpa detail lokasi atau temuan wilayah lain;
- tabel detail agregat lokasi berada paling bawah dan menyediakan search, filter risiko, sorting, pagination, serta export Excel/PDF/CSV yang tetap mengikuti pembatasan satu wilayah;
- tabel ID Unix, kesalahan, jumlah kesalahan, dan skor;
- grafik batang per indikator dan per lokasi;
- grafik garis perbandingan enam periode bulanan atau mingguan beserta analisis perubahan periode terakhir;
- ranking wilayah/lokasi per periode;
- dua tabel ranking lokasi yang eksplisit: 10 risiko tertinggi dan 10 risiko terendah;
- akses detail berbasis wilayah.

## Data pengujian

- `UJI`: data ringkas untuk regression test.
- `REALISTIS`: data sintetis menyerupai pola operasional, bukan data produksi atau temuan audit nyata.

Loader harus idempoten, memetakan area dari master lokasi, dan tidak otomatis mengisi database produksi.

## Ekspor

Ekspor PDF dan Excel harus mengikuti filter aktif dan selalu dibatasi ke satu wilayah. Akun wilayah otomatis memakai wilayah yang terkunci pada akunnya; admin/auditor wajib memilih wilayah dan ekspor nasional tanpa wilayah ditolak. Keduanya memuat konteks periode, ringkasan, grafik tren, grafik indikator, grafik lokasi, ranking 10 risiko tertinggi dan 10 risiko terendah, serta tabel detail ID Unix–kesalahan–jumlah–skor. Excel memakai tabel terstruktur, autofilter, freeze pane, dan chart Excel yang dapat diedit. PDF memakai grafik vektor dan tabel yang dapat berlanjut ke halaman berikutnya.

## Kriteria penerimaan

- Master berisi tepat 15 wilayah, 41 area, dan 166 lokasi berkode SIL.
- Semua akun wilayah dibuat idempoten dengan role `viewer` dan wilayah terkunci.
- Akun wilayah hanya melihat detail wilayahnya pada Dashboard, Laporan, ekspor, dan Alert Center.
- Ranking nasional tetap terlihat pada Dashboard akun wilayah.
- Akun wilayah tidak dapat memverifikasi atau mengubah tindak lanjut.
- Tindak lanjut otomatis mengikuti tingkatan skor dan koreksi manual Admin Pusat tidak ditimpa oleh proses matching berikutnya.
- Admin Pusat melihat Dashboard/Info/Laporan/Alert Center/Upload Data; Admin Wilayah hanya melihat Dashboard/Laporan/Alert Center.
- Form upload hanya tersedia bagi Admin Pusat; tidak ada form input manual untuk akun mana pun.
- Dashboard tidak menampilkan form upload; menu `Upload Data` tetap tersedia khusus Admin Pusat.
- Dashboard menampilkan KPI sebelum grafik, ringkasan indikator risiko setelah grafik, dan tabel hanya pada bagian paling bawah.
- Seluruh KPI, grafik, panel risiko, ranking, dan detail berubah mengikuti filter aktif.
- Grafik indikator vertikal memuat semua indikator SOP dan tren jumlah indikator berubah konsisten antara agregasi bulanan dan mingguan.
- Grafik utama Dashboard Pusat menampilkan tepat 15 wilayah sekaligus; Ranking Lokasi Nasional menampilkan tepat 10 risiko tertinggi dan 10 risiko terendah beserta alasan skor; Dashboard tidak memuat tabel detail transaksi.
- Laporan menampilkan grafik 15 wilayah dan rangkaian grafik analisis yang konsisten dengan Dashboard dalam versi lebih lengkap; tabel detail tidak memuat kolom Status Verifikasi atau Aksi.
- Admin Pusat mendapat seluruh KPI dan analitik nasional; Admin Wilayah hanya mendapat analitik detail wilayahnya dengan ringkasan ranking wilayah nasional yang aman.
- Risk Ranking #1 selalu merupakan lokasi/wilayah dengan total skor tertinggi; daftar teraman diurutkan dari skor terendah.
- Halaman Ranking Nasional Lokasi dan Wilayah tersedia tanpa membuka detail lintas wilayah bagi akun regional.
- Tabel detail lokasi menyediakan search, filter risiko, sorting, pagination, dan export wilayah Excel/PDF/CSV.
- Grafik dashboard dapat di-zoom, di-reset, dan di-scroll tanpa menimbulkan overflow halaman pada desktop maupun mobile.
- Double Input terdeteksi saat nomor bukti, nominal, tanggal transaksi, jenis transaksi, dan lokasi sama, termasuk jika ID Unix atau metadata lainnya berbeda.
- Transaksi Double Input ditampilkan berkelompok berdasarkan fingerprint duplikat.
- Upload `.xlsx`/`.csv` memvalidasi tipe file, ukuran, ukuran ekstraksi workbook, jumlah baris, duplikasi `idunix`, dan kode lokasi sebelum mutasi data.
- Upload hari berikutnya mempertahankan histori hari sebelumnya; koreksi dengan `idunix` sama tidak menghasilkan dua versi aktif.
- Matching upload hanya memproses batch baru/koreksi dan tidak menghapus status tindak lanjut data historis.
- Response memakai header keamanan dasar dan session cookie production memakai `Secure`, `SameSite=Lax`, serta secret dari environment.
- Filter area memengaruhi data secara nyata.
- Filter mingguan dan bulanan memengaruhi data secara nyata dan konsisten pada Dashboard, Laporan, PDF, dan Excel.
- Grafik batang wilayah/lokasi, grafik garis tren periode, grafik indikator, top/bottom 10, tabel detail, tindak lanjut otomatis, dataset sintetis, dan ekspor tetap berfungsi.
- Informasi yang tampil pada Dashboard dan Laporan mempunyai padanan data pada PDF dan Excel untuk filter wilayah yang sama.
- Regression test serta QA desktop/mobile lulus tanpa error console atau overflow kritis.

## Batasan

- Tidak ada integrasi sumber produksi baru pada perubahan ini.
- Data sintetis tidak boleh disebut sebagai data real produksi.
- Route legacy input/upload boleh dipertahankan hanya sebagai redirect/response aman dan tidak boleh muncul sebagai fungsi yang dapat digunakan.
