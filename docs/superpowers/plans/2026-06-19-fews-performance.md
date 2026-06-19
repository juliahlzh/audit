# FEWS Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mempercepat cold start dan perpindahan menu FEWS tanpa mengubah aturan deteksi fraud.

**Architecture:** Migration schema dijalankan eksplisit sebelum deploy, bukan pada startup serverless. Dashboard memakai agregasi SQL, daftar approval memakai pagination, dan indeks mendukung filter serta urutan yang sering digunakan.

**Tech Stack:** FastAPI, SQLAlchemy, Jinja, SQLite, PostgreSQL/Supabase, Vercel.

---

### Task 1: Lindungi cold start Vercel

**Files:** `app/main.py`, `tests/test_query_performance.py`

- [ ] Tambahkan tes bahwa startup Vercel tidak memanggil `init_db`.
- [ ] Tambahkan kondisi startup agar migration tetap berjalan lokal tetapi dilewati di Vercel.
- [ ] Jalankan tes startup.

### Task 2: Optimalkan Dashboard

**Files:** `app/main.py`, `tests/test_query_performance.py`

- [ ] Tambahkan tes bahwa Dashboard tidak memuat seluruh entitas transaksi.
- [ ] Ganti query penuh dengan `COUNT`, `GROUP BY`, kolom JSON minimum, dan `LIMIT 15` untuk prioritas.
- [ ] Verifikasi angka ringkasan dan batas query.

### Task 3: Pagination Data Approval

**Files:** `app/main.py`, `app/templates/branch_inputs.html`, `tests/test_persistence_logout.py`

- [ ] Tambahkan tes 25 data hanya menampilkan 20 data pada halaman pertama.
- [ ] Implementasikan parameter `page` dan `per_page` beserta navigasi.
- [ ] Verifikasi halaman berikutnya dan jumlah total.

### Task 4: Indeks dan migration eksplisit

**Files:** `app/main.py`, `scripts/migrate_database.py`, `tests/test_query_performance.py`

- [ ] Tambahkan tes indeks idempotent.
- [ ] Tambahkan indeks untuk data aktif/tanggal, tanggal input, serta urutan risiko.
- [ ] Buat entrypoint migration yang dapat dijalankan sebelum deploy.

### Task 5: Ringankan deployment dan tambah observability

**Files:** `requirements.txt`, `app/main.py`, `tests/test_query_performance.py`

- [ ] Hapus paket OCR lama yang tidak dirujuk aplikasi single-source.
- [ ] Tambahkan header `Server-Timing` dan log request lambat.
- [ ] Jalankan seluruh tes dan compile check.

### Task 6: Production rollout

- [ ] Tarik environment production sementara tanpa menyimpan secret ke Git.
- [ ] Jalankan migration terhadap Supabase dan verifikasi indeks.
- [ ] Deploy ke Vercel, arahkan `fews-audit.vercel.app`, lakukan smoke test, dan cek runtime errors.
- [ ] Commit perubahan dengan working tree bersih.
