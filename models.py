"""Struktur database (tabel) aplikasi Checklist OB.

Satu class = satu tabel. Kalau mau tambah kolom/tabel baru, ubah file ini,
lalu hapus instance/ob.db dan jalankan ulang `python seed.py` (selama masih tahap awal).
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "pengguna"
    id = db.Column(db.Integer, primary_key=True)
    kode = db.Column(db.String(10), unique=True)          # U01, U02, ...
    nama = db.Column(db.String(100), nullable=False)
    jabatan = db.Column(db.String(20))                     # SPV / Crew / Gardener
    peran = db.Column(db.String(12), nullable=False)       # supervisor / ob
    divisi = db.Column(db.String(12))                      # cleaning / taman
    username = db.Column(db.String(40), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    aktif = db.Column(db.Boolean, default=True, nullable=False)
    must_change = db.Column(db.Boolean, default=True, nullable=False)  # wajib ganti password saat login pertama


class Lokasi(db.Model):
    __tablename__ = "lokasi"
    id = db.Column(db.Integer, primary_key=True)
    kode = db.Column(db.String(10), unique=True)           # L001, ...
    gedung = db.Column(db.String(40))
    lantai = db.Column(db.String(10))
    nama = db.Column(db.String(120), nullable=False)
    jenis = db.Column(db.String(30), nullable=False)       # menentukan checklist (lihat Template.jenis)
    kelompok = db.Column(db.String(12))                    # cleaning / taman
    status_data = db.Column(db.String(40))


class Template(db.Model):
    """Butir checklist baku per jenis ruangan. Diubah SPV lewat menu Checklist."""
    __tablename__ = "template_tugas"
    id = db.Column(db.Integer, primary_key=True)
    jenis = db.Column(db.String(30), nullable=False)
    urutan = db.Column(db.Integer, default=1)
    nama_tugas = db.Column(db.String(150), nullable=False)
    frekuensi = db.Column(db.String(10), default="harian")  # harian / mingguan / bulanan
    sumber = db.Column(db.String(30))
    aktif = db.Column(db.Boolean, default=True, nullable=False)


class Penugasan(db.Model):
    """Ruangan ini tanggung jawab OB siapa (tetap, sampai diubah SPV)."""
    __tablename__ = "penugasan"
    id = db.Column(db.Integer, primary_key=True)
    lokasi_id = db.Column(db.Integer, db.ForeignKey("lokasi.id"), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("pengguna.id"), nullable=False)
    lokasi = db.relationship("Lokasi")
    user = db.relationship("User")


class Laporan(db.Model):
    """Satu baris = satu ruangan pada satu tanggal. Foto menempel di sini, bukan per butir tugas."""
    __tablename__ = "laporan"
    id = db.Column(db.Integer, primary_key=True)
    tanggal = db.Column(db.Date, nullable=False)
    lokasi_id = db.Column(db.Integer, db.ForeignKey("lokasi.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("pengguna.id"), nullable=False)
    status = db.Column(db.String(10), default="belum", nullable=False)  # belum / proses / selesai / dicek
    waktu_mulai = db.Column(db.DateTime)
    waktu_selesai = db.Column(db.DateTime)
    diperiksa_oleh_id = db.Column(db.Integer, db.ForeignKey("pengguna.id"))
    waktu_periksa = db.Column(db.DateTime)
    catatan_spv = db.Column(db.Text)

    lokasi = db.relationship("Lokasi")
    user = db.relationship("User", foreign_keys=[user_id])
    pemeriksa = db.relationship("User", foreign_keys=[diperiksa_oleh_id])
    items = db.relationship("LaporanItem", cascade="all, delete-orphan", order_by="LaporanItem.urutan")
    fotos = db.relationship("Foto", cascade="all, delete-orphan", order_by="Foto.id")
    __table_args__ = (db.UniqueConstraint("tanggal", "lokasi_id", name="uq_laporan_hari_ruang"),)


class LaporanItem(db.Model):
    """Butir checklist pada laporan tertentu. Nama tugas disalin supaya riwayat tidak berubah bila template diubah."""
    __tablename__ = "laporan_item"
    id = db.Column(db.Integer, primary_key=True)
    laporan_id = db.Column(db.Integer, db.ForeignKey("laporan.id"), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey("template_tugas.id"))
    urutan = db.Column(db.Integer, default=1)
    nama_tugas = db.Column(db.String(150), nullable=False)
    selesai = db.Column(db.Boolean, default=False, nullable=False)


class Foto(db.Model):
    __tablename__ = "foto"
    id = db.Column(db.Integer, primary_key=True)
    laporan_id = db.Column(db.Integer, db.ForeignKey("laporan.id"), nullable=False)
    jenis = db.Column(db.String(10), nullable=False)       # before / process / after
    nama_file = db.Column(db.String(120), nullable=False)  # file disimpan di instance/uploads, DB hanya nama file
    waktu_ambil = db.Column(db.DateTime)                   # waktu foto diunggah


class RequestPembersihan(db.Model):
    """Permintaan pembersihan ruangan dadakan dari pihak client/pengguna fasilitas."""
    __tablename__ = "request_pembersihan"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("pengguna.id"), nullable=False)
    lokasi_id = db.Column(db.Integer, db.ForeignKey("lokasi.id"), nullable=False)
    waktu_buat = db.Column(db.DateTime, nullable=False)
    catatan = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="menunggu", nullable=False)  # menunggu / proses / selesai
    waktu_selesai = db.Column(db.DateTime)
    catatan_selesai = db.Column(db.Text)

    user = db.relationship("User")
    lokasi = db.relationship("Lokasi")

