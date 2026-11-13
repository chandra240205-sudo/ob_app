# Checklist OB ITSB

Aplikasi web manajemen dan checklist kebersihan ruangan untuk tim Office Boy (OB) dan fasilitas kampus Institut Teknologi Sains Bandung (ITSB), dilengkapi dengan bukti foto (*sebelum*, *proses*, *sesudah*), sistem peran pengguna (Supervisor, OB, dan Client), serta integrasi database.

---

## 🌟 Fitur Utama

Aplikasi ini memiliki 3 sudut pandang/peran utama:

### 1. 🛡️ Supervisor (SPV)
* **Dashboard Pemantauan:** Progres pembersihan harian per staf OB secara *real-time* dan rekap status seluruh ruangan (*Belum*, *Dikerjakan*, *Selesai*, *Sudah diperiksa*).
* **Verifikasi Laporan & Foto:** Meninjau dokumentasi 3 jenis foto per ruangan, menyetujui laporan kebersihan (*Tandai sudah diperiksa*), atau mengembalikannya ke OB dengan catatan evaluasi.
* **Pengaturan Penugasan:** Menugaskan staf OB ke ruangan/lokasi tertentu per gedung dan lantai.
* **Kelola Checklist Template:** Menambah atau mengatur butir tugas kebersihan per jenis ruangan (Harian, Mingguan tiap Senin, Bulanan tiap tanggal 1).
* **Kelola Permintaan Klien:** Memantau tiket pembersihan dadakan dari klien, mengubah status (*Sedang Diproses* / *Selesai*), dan memberikan catatan penanganan.
* **Manajemen Pengguna:** Reset password dan aktivasi/nonaktifkan akun staf.

### 2. 🧹 Office Boy (OB / Cleaning Crew & Gardener)
* **Tugas Hari Ini:** Daftar ruangan yang ditugaskan khusus untuk OB yang bersangkutan pada tanggal berjalan.
* **Checklist Pekerjaan:** Mencentang butir tugas kebersihan yang sudah selesai.
* **Dokumentasi 3 Jenis Foto:** Wajib mengunggah foto *Sebelum* (*Before*), *Proses* (*Process*), dan *Sesudah* (*After*). Foto dikompresi otomatis agar hemat kuota dan penyimpanan.
* **Penyelesaian Ruangan:** Ruangan hanya dapat diselesaikan jika seluruh butir checklist tercentang dan ketiga jenis foto telah lengkap diunggah.
* **Peringatan Tiket Klien:** Muncul tanda peringatan langsung pada ruangan yang mendapatkan permintaan kebersihan khusus dari klien.

### 3. 🏢 Client (Klien / Dosen / Pengguna Fasilitas)
* **Overview Klien:** Dashboard ringkasan total permintaan pembersihan (*Menunggu*, *Diproses*, *Selesai*).
* **Pengajuan Request Pembersihan:** Mengajukan permintaan kebersihan ruangan dadakan (pilih ruangan + tulis catatan/keluhan).
* **Pantau Riwayat Permintaan:** Memantau tindak lanjut permintaan secara langsung beserta catatan dari supervisor/petugas.
* **Status Ruangan Hari Ini:** Memeriksa apakah ruangan di kampus sudah selesai dibersihkan atau belum, lengkap dengan filter gedung/lantai dan akses melihat foto bukti (*view-only*).

### 4. 🔑 Fitur Autentikasi & Registrasi
* **Pendaftaran Akun Baru (`/register`):** Pengguna baru dapat membuat akun mandiri dengan memilih peran (*Client*, *Crew OB*, *Gardener*, atau *Supervisor*).
* **Keamanan Sesi & CSRF:** Dilengkapi proteksi CSRF di seluruh form dan enkripsi password menggunakan *scrypt*.

---

## 👥 Akun Bawaan (Siap Pakai)

Semua akun awal menggunakan password: **`admin123`**

| Peran | Username | Password | Deskripsi |
| :--- | :--- | :--- | :--- |
| **Supervisor** | `admin` / `aditiya` | `admin123` | Akses penuh dashboard, checklist, penugasan, dan tiket |
| **OB (Crew Cleaning)** | `indri`, `dewi`, `neni`, `tia`, `dendi`, `reno`, `ayat`, `suwondo`, `aliyyu` | `admin123` | Checklist ruangan & upload foto harian |
| **OB (Gardener/Taman)** | `iwan`, `saepudin`, `muhamad` | `admin123` | Tugas kebersihan area taman kampus |
| **Client** | `client` | `admin123` | Request pembersihan & cek status ruangan |

> *Catatan:* Anda juga dapat mendaftar akun baru melalui tombol **"Daftar di sini"** pada halaman login.

---

## 🚀 Panduan Menjalankan Aplikasi

### Persyaratan Sistem
* Python 3.10 atau versi lebih baru.
* Sistem operasi Windows, macOS, atau Linux.

---

### Opsi A: Menggunakan Python Standar / Virtual Environment (Disarankan)

1. **Buka terminal** di dalam folder `ob_app`:
   ```bash
   cd ob_app
   ```

2. **Buat dan aktifkan Virtual Environment:**
   * **Windows (PowerShell):**
     ```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```
   * **macOS / Linux:**
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. **Install Dependensi:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Konfigurasi Environment (`.env`):**
   Salin atau sesuaikan file `.env` di folder utama aplikasi:
   ```env
   SUPABASE_URL=https://proyek-anda.supabase.co
   SUPABASE_KEY=sb_publishable_kunci_anda...
   ```

5. **Inisialisasi Database (Hanya saat pertama kali / reset):**
   ```bash
   python seed.py --demo
   ```
   *(Gunakan `--demo` untuk mengisi data contoh penugasan dan ruangan awal).*

6. **Jalankan Aplikasi:**
   ```bash
   python app.py
   ```
   Buka browser di **`http://localhost:5000`** (atau dari HP di jaringan WiFi yang sama via `http://IP-LAPTOP:5000`).

---

### Opsi B: Menjalankan Menggunakan Python QGIS / OSGeo4W (Windows)

Jika di komputer Anda menggunakan Python bawaan QGIS:
```powershell
# Uji koneksi Supabase & konfigurasi
$env:PYTHONHOME = "C:\Program Files\QGIS 4.2.3\apps\Python312"
& "C:\Program Files\QGIS 4.2.3\bin\python.exe" test_supabase.py

# Jalankan aplikasi Flask
$env:PYTHONHOME = "C:\Program Files\QGIS 4.2.3\apps\Python312"
& "C:\Program Files\QGIS 4.2.3\bin\python.exe" app.py
```

---

## 📁 Struktur Direktori

```text
ob_app/
├── app.py                # Kode backend Flask utama, routing, dan logika bisnis
├── models.py             # Model database SQLAlchemy (User, Lokasi, Template, Laporan, Foto, RequestPembersihan)
├── seed.py               # Skrip untuk mengisi data awal dari file CSV
├── test_app.py           # Unit testing dan pengujian alur utama otomatis
├── test_supabase.py      # Skrip verifikasi koneksi & keamanan Supabase
├── supabase_client.py    # Modul inisialisasi client Supabase
├── requirements.txt      # Daftar dependensi Python
├── .env                  # Konfigurasi variabel lingkungan (URL & API Key) [Terlindungi]
├── .gitignore            # Daftar file yang diabaikan oleh Git
├── data/                 # Dataset awal CSV (lokasi.csv, pengguna.csv, template_tugas.csv)
├── instance/             # Database SQLite lokal (ob.db), kunci rahasia, dan folder uploads foto
├── static/
│   └── style.css         # Styling CSS responsif (mobile-friendly)
└── templates/            # Template tampilan HTML Jinja2
    ├── base.html         # Kerangka layout utama dan navbar
    ├── login.html        # Halaman masuk
    ├── register.html     # Halaman registrasi akun baru
    ├── dashboard.html    # Dashboard monitoring supervisor
    ├── hari_ini.html     # Halaman tugas harian staf OB
    ├── laporan.html      # Rincian checklist, foto bukti & verifikasi SPV
    ├── penugasan.html    # Halaman atur penugasan ruangan
    ├── checklist.html    # Halaman kelola butir checklist template
    ├── pengguna.html     # Halaman manajemen pengguna
    ├── client_overview.html # Dashboard overview & form tiket client
    ├── client_ruangan.html  # Status kebersihan seluruh ruangan untuk client
    ├── spv_request.html  # Halaman kelola tiket permintaan klien bagi SPV
    └── ganti_password.html # Halaman ganti password
```

---

## 🔒 Keamanan & Praktik Terbaik

1. **Proteksi File `.env`:** File `.env` dan folder `instance/` sudah terdaftar di `.gitignore` agar kredensial API dan database lokal tidak bocor ke repositori publik.
2. **Kunci Supabase:** Gunakan `anon` / `publishable key` untuk client aplikasi, bukan `service_role secret`.
3. **Produksi:** Untuk deployment server, gunakan WSGI server seperti Gunicorn:
   ```bash
   gunicorn -w 4 -b 0.0.0.0:5000 app:app
   ```
4. **Privasi Foto:** Foto dokumentasi menampilkan lingkungan kampus dan staf; pastikan izin operasional sesuai dengan regulasi pihak ITSB.
