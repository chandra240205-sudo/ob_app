"""Mengisi database dengan data awal dari folder data/ (hasil dataset dari supervisor).

  python seed.py          -> buat database + isi pengguna, lokasi, template tugas
  python seed.py --demo   -> sama, ditambah penugasan CONTOH (hanya untuk mencoba aplikasi)
  python seed.py --reset  -> hapus database lama dulu (data laporan ikut hilang!)
"""
import csv
import os
import re
import sys

from werkzeug.security import generate_password_hash

from app import DEFAULT_PASSWORD, INSTANCE, UPLOADS, app
from models import Lokasi, Penugasan, Template, User, db

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def baca(nama):
    with open(os.path.join(DATA, nama), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def buat_username(nama, dipakai):
    dasar = re.sub(r"[^a-z]", "", nama.lower().split()[0]) or "user"
    uname, n = dasar, 2
    while uname in dipakai:
        uname, n = f"{dasar}{n}", n + 1
    dipakai.add(uname)
    return uname


def main():
    if "--reset" in sys.argv:
        path = os.path.join(INSTANCE, "ob.db")
        if os.path.exists(path):
            os.remove(path)
    with app.app_context():
        db.create_all()
        if User.query.count() == 0:
            dipakai = set()
            pw = generate_password_hash(DEFAULT_PASSWORD)
            for r in baca("pengguna.csv"):
                db.session.add(User(kode=r["id_pengguna"], nama=r["nama"], jabatan=r["jabatan"], peran=r["peran_aplikasi"],
                                    divisi=r["divisi"], aktif=(r["aktif"] == "ya"), username=buat_username(r["nama"], dipakai),
                                    password_hash=pw, must_change=True))
            for r in baca("lokasi.csv"):
                db.session.add(Lokasi(kode=r["id_lokasi"], gedung=r["gedung"], lantai=r["lantai"], nama=r["nama_ruangan"],
                                      jenis=r["jenis_lokasi"], kelompok=r["kelompok"], status_data=r["status_data"]))
            for r in baca("template_tugas.csv"):
                db.session.add(Template(jenis=r["jenis_lokasi"], urutan=int(r["urutan"]), nama_tugas=r["nama_tugas"],
                                        frekuensi=r["frekuensi"], sumber=r["sumber"], aktif=True))
            db.session.commit()
            print("Data awal terisi.")
        else:
            print("Database sudah berisi; dilewati (pakai --reset untuk mengulang).")

        if "--demo" in sys.argv and Penugasan.query.count() == 0:
            # CONTOH SAJA. Pembagian kerja asli diisi SPV lewat menu Penugasan.
            demo = {("Gedung Utama", "3"): "Indri Andriyani", ("Gedung Utama", "4"): "Dewi Darsiah"}
            for (gedung, lantai), nama in demo.items():
                ob = User.query.filter_by(nama=nama).first()
                for lok in Lokasi.query.filter_by(gedung=gedung, lantai=lantai, kelompok="cleaning"):
                    db.session.add(Penugasan(lokasi_id=lok.id, user_id=ob.id))
            db.session.commit()
            print("Penugasan contoh dibuat (Gedung Utama lt 3 -> Indri, lt 4 -> Dewi).")

        print(f"\nPengguna: {User.query.count()} | Lokasi: {Lokasi.query.count()} | Butir template: {Template.query.count()}")
        print(f"Password awal semua akun: {DEFAULT_PASSWORD} (wajib diganti saat login pertama)")
        print("Username: " + ", ".join(f"{u.username} ({u.jabatan})" for u in User.query.order_by(User.id)))


if __name__ == "__main__":
    os.makedirs(UPLOADS, exist_ok=True)
    main()
