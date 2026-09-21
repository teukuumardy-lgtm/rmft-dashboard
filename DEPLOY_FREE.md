# Deploy gratis (Rp0/bulan) ke Neon + Render

Kombinasi ini benar-benar gratis (bukan trial) dan tidak perlu kartu kredit untuk
databasenya, dengan satu kompromi: **backend "tidur" setelah 15 menit tidak diakses**,
dan permintaan pertama setelahnya butuh ±30-60 detik sebelum responsif lagi (lalu
normal selama masih aktif dipakai). Untuk dashboard internal yang dibuka beberapa
kali sehari, ini biasanya trade-off yang wajar.

Kalau nanti butuh performa selalu-siap tanpa jeda ini, lihat **[`DEPLOY.md`](./DEPLOY.md)**
(Railway, berbayar kecil ~$5-10/bulan) — struktur service-nya sama persis, tinggal
pindah host kapan saja karena kodenya tidak berubah.

## 1. Buat database gratis di Neon

1. Daftar di https://neon.com (tanpa kartu kredit).
2. Buat project baru, beri nama misalnya `rmft-dashboard`.
3. Di dashboard project, buka **Connection Details** dan salin **Connection string**
   — bentuknya seperti:
   `postgresql://<user>:<password>@<host>.neon.tech/<dbname>?sslmode=require`
4. Simpan string ini — dipakai sebagai `DATABASE_URL` di langkah 3.

## 2. Push kode ke GitHub

Sama seperti opsi Railway — di folder `rmft-dashboard/`:

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

(Lewati langkah ini kalau repo sudah ada dari percobaan Railway sebelumnya.)

## 3. Deploy backend ke Render (Web Service, paket Free)

1. Daftar/login di https://render.com.
2. **New +** → **Web Service** → hubungkan repo GitHub dari langkah 2.
3. Isi pengaturan:
   - **Root Directory**: `backend`
   - **Environment**: Docker (Render akan otomatis memakai `backend/Dockerfile`)
   - **Instance Type**: **Free**
4. Tambahkan **Environment Variables**:
   - `DATABASE_URL` → tempel connection string dari Neon (langkah 1)
   - `JWT_SECRET` → isi string acak panjang sendiri
5. **Create Web Service**, tunggu build selesai. Catat URL publiknya, misalnya
   `https://rmft-backend.onrender.com` — dibutuhkan di langkah 4.

`backend/Dockerfile` sudah disiapkan untuk otomatis memakai port yang diberikan
Render (`$PORT`), jadi tidak perlu pengaturan port manual di sini.

## 4. Deploy frontend ke Render (Static Site, gratis & selalu aktif)

Static Site di Render **tidak pernah tidur** (beda dengan Web Service) karena hanya
menyajikan file statis — jadi tampilan dashboard-nya selalu langsung terbuka; yang
"tidur" hanya bagian backend/API-nya.

1. **New +** → **Static Site** → pilih repo yang sama.
2. Isi pengaturan:
   - **Root Directory**: `frontend`
   - **Build Command**: `npm install && npm run build`
   - **Publish Directory**: `dist`
3. Tambahkan **Environment Variable**:
   - `VITE_API_BASE_URL` → isi URL backend dari langkah 3, contoh
     `https://rmft-backend.onrender.com`
4. Tambahkan **Redirect/Rewrite Rule** (penting, supaya menu-menu di dashboard
   tidak 404 saat direfresh — ini aplikasi single-page):
   - Source: `/*`
   - Destination: `/index.html`
   - Action: **Rewrite**
5. **Create Static Site**, tunggu build selesai. URL yang muncul (contoh
   `https://rmft-dashboard.onrender.com`) itulah link publiknya — bisa dibuka
   dari HP atau perangkat mana pun.

## 5. Selesai — buka dan uji

Buka URL dari langkah 4. Kalau baru pertama kali (atau sudah lama tidak dibuka),
tunggu ±30-60 detik saat pertama kali login — backend sedang "bangun". Login pakai
`admin` / `admin123`, **langsung ganti password** lewat Admin → User.

Lanjutkan seperti biasa: set baseline MTD lewat `<url-backend>/docs` →
`POST /funding/baseline`, lalu upload data funding sungguhan.

## Kalau ada error

- **Frontend terbuka tapi tidak bisa login / data tidak muncul** → pastikan
  `VITE_API_BASE_URL` benar dan Static Site sudah di-**rebuild** setelah variable
  itu diisi (dibaca saat build, bukan runtime — sama seperti opsi Railway).
- **Menu selain Home menampilkan halaman kosong/404 saat direfresh** → cek aturan
  Rewrite di langkah 4 poin 4 sudah tersimpan.
- **Backend error "could not connect to server" / database** → cek `DATABASE_URL`
  dari Neon disalin lengkap termasuk `?sslmode=require` di akhir.
- **Halaman lambat/blank sesaat lalu normal** → ini normal, backend baru
  "bangun" dari mode tidur — bukan bug.
- Detail fitur, demo login, dan known limitations lain ada di `README.md`.
