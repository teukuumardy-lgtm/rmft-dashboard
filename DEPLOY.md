# Deploy ke Railway (dapat URL publik, bisa dibuka dari HP)

Cari opsi **gratis**? Lihat **[`DEPLOY_FREE.md`](./DEPLOY_FREE.md)** (Neon + Render) —
struktur service-nya sama, kompromi utamanya backend "tidur" setelah 15 menit idle.

Panduan ini men-deploy 3 komponen aplikasi (PostgreSQL, backend FastAPI, frontend React)
sebagai 3 service terpisah dalam satu project Railway. Railway **tidak** membaca
`docker-compose.yml` secara otomatis — servicenya harus dibuat manual lewat dashboard,
tapi masing-masing tetap memakai `backend/Dockerfile` dan `frontend/Dockerfile` yang
sudah ada di repo ini, jadi tidak perlu menulis ulang apa pun.

Perkiraan biaya: Railway memberi trial credit $5 sekali pakai (tanpa perlu kartu di
awal untuk sebagian akun), lalu berlanjut ke paket berbayar berbasis pemakaian
(kira-kira setara $5-10/bulan untuk 3 service kecil seperti ini, jalan 24 jam). Data
di PostgreSQL Railway **tidak ada batas 30 hari** seperti tier gratis Render — cocok
untuk data funding/pipeline yang harus tetap tersimpan.

## 1. Push kode ke GitHub

Railway men-deploy dari repo GitHub. Di folder `rmft-dashboard/`:

```bash
git init
git add .
git commit -m "Initial commit"
```

Buat repo baru (privat) di https://github.com/new, lalu:

```bash
git remote add origin https://github.com/<username-anda>/rmft-dashboard.git
git branch -M main
git push -u origin main
```

## 2. Buat project Railway

1. Buka https://railway.com, daftar/login (bisa pakai akun GitHub).
2. **New Project** → **Empty Project**.

## 3. Tambahkan PostgreSQL

**+ New** → **Database** → **Add PostgreSQL**. Selesai — Railway otomatis
menyediakan `DATABASE_URL` yang bisa dipakai service lain lewat *reference variable*.

## 4. Tambahkan service Backend

**+ New** → **GitHub Repo** → pilih repo yang baru di-push.

Di pengaturan service ini:
- **Settings → Root Directory**: `backend`
- **Settings → Networking**: klik **Generate Domain**, port isi `8000` (sesuai
  `EXPOSE 8000` di `backend/Dockerfile`). Catat URL publiknya, misalnya
  `https://rmft-backend-production.up.railway.app` — dibutuhkan di langkah 5.
- **Variables**, tambahkan:
  - `DATABASE_URL` → klik "reference variable", pilih service Postgres,
    pilih `DATABASE_URL` (jadi nilainya otomatis `${{Postgres.DATABASE_URL}}`
    dan ikut berubah kalau kredensial Postgres pernah di-rotate)
  - `JWT_SECRET` → isi string acak panjang (jangan pakai nilai default di kode)

Railway akan build otomatis dari `backend/Dockerfile`. Tunggu sampai status **Active**.

## 5. Tambahkan service Frontend

**+ New** → **GitHub Repo** → pilih repo yang sama lagi (jadi 1 repo dipakai 2 service,
masing-masing dengan Root Directory berbeda).

- **Settings → Root Directory**: `frontend`
- **Settings → Networking**: **Generate Domain**, port isi `80` (sesuai nginx di
  `frontend/Dockerfile`). Inilah URL yang nanti dibuka dari HP.
- **Variables**, tambahkan:
  - `VITE_API_BASE_URL` → isi URL publik backend dari langkah 4, contoh
    `https://rmft-backend-production.up.railway.app`
    (Frontend baru bisa tahu alamat ini kalau di-set sebelum proses build — Dockerfile-nya
    sudah saya siapkan supaya membaca variable ini sebagai build argument.)

Redeploy service frontend (Railway biasanya otomatis build ulang begitu variable
disimpan; kalau tidak, klik **Deploy** manual).

## 6. Selesai

Buka URL frontend dari langkah 5 di HP atau browser mana saja — itulah link publik
dashboard-nya. Login pertama kali pakai `admin` / `admin123`, lalu **segera ganti
password** lewat Admin → User (atau buat user admin baru dan nonaktifkan yang demo).

## Setelah live

- Set baseline MTD bulan berjalan: buka `<url-backend>/docs`, **Authorize** dengan
  akun admin, jalankan `POST /funding/baseline`.
- Upload data funding sungguhan lewat menu **Upload Data**.
- Kalau ingin domain sendiri (misal `dashboard.namabank.co.id`) alih-alih subdomain
  `*.up.railway.app`, Railway mendukung custom domain lewat
  **Settings → Networking → Custom Domain** pada service frontend.

## Kalau ada error

- **Frontend terbuka tapi data tidak muncul / gagal login** → cek `VITE_API_BASE_URL`
  sudah benar dan service frontend sudah di-redeploy setelah variable itu diisi
  (env `VITE_*` dibaca saat *build*, bukan saat runtime, jadi mengubah variable
  saja tidak cukup tanpa build ulang).
- **Backend gagal start** → buka tab **Deployments → Logs** pada service backend;
  penyebab tersering adalah `DATABASE_URL` belum ter-reference dengan benar ke
  service Postgres.
- Detail lain (demo login, struktur fitur, known limitations) ada di `README.md`.
