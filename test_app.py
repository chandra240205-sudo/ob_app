"""Tes otomatis alur utama. Jalankan: python test_app.py"""
import io, os, re, sys, tempfile
os.environ["OB_INSTANCE"] = tempfile.mkdtemp()
sys.argv = ["seed.py", "--demo"]
import seed
seed.main()
from app import app, DEFAULT_PASSWORD
from models import db, User, Laporan, Penugasan
from PIL import Image

def csrf(c, url="/login"):
    html = c.get(url).get_data(as_text=True)
    return re.search(r'name="_csrf" value="([^"]+)"', html).group(1)

def masuk(c, u, pw):
    t = csrf(c)
    return c.post("/login", data={"username": u, "password": pw, "_csrf": t}, follow_redirects=True)

def jpg(w=3000, h=2000):
    b = io.BytesIO(); Image.new("RGB", (w, h), (120, 160, 90)).save(b, "JPEG"); b.seek(0); return b

def post(c, url, data=None, **kw):
    data = dict(data or {}); data["_csrf"] = tok(c)
    return c.post(url, data=data, **kw)

def tok(c):
    with c.session_transaction() as s:
        return s.get("csrf") or ""

def ok(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: sys.exit(1)

ob = app.test_client(); spv = app.test_client()

# login salah
r = masuk(app.test_client(), "indri", "salah"); ok("salah" in r.get_data(as_text=True), "login salah ditolak")
# akses tanpa login
ok(app.test_client().get("/spv").status_code == 302, "halaman SPV butuh login")
# OB login pertama -> wajib ganti password
r = masuk(ob, "indri", DEFAULT_PASSWORD); ok("Ganti password" in r.get_data(as_text=True), "OB dipaksa ganti password")
r = post(ob, "/ganti-password", {"lama": DEFAULT_PASSWORD, "baru": DEFAULT_PASSWORD, "ulang": DEFAULT_PASSWORD}, follow_redirects=True)
ok("tidak boleh sama" in r.get_data(as_text=True), "password baru = password awal ditolak")
r = post(ob, "/ganti-password", {"lama": DEFAULT_PASSWORD, "baru": "rahasia123", "ulang": "rahasia123"}, follow_redirects=True)
ok("Tugas hari ini" in r.get_data(as_text=True), "ganti password lalu masuk halaman OB")
ok("Ruangan 301" in r.get_data(as_text=True), "OB melihat ruangannya (lt 3)")
ok("Ruangan 401" not in r.get_data(as_text=True), "OB tidak melihat ruangan OB lain")
# OB tidak boleh buka halaman SPV
ok(ob.get("/spv").status_code == 403, "OB ditolak di halaman SPV")
# POST tanpa CSRF
ok(ob.post("/logout", data={}).status_code == 400, "POST tanpa CSRF ditolak")

with app.app_context():
    lap = Laporan.query.join(User, Laporan.user_id == User.id).filter(User.username == "indri").first()
    lid = lap.id; n_item = len(lap.items); lap_dewi = Laporan.query.join(User, Laporan.user_id == User.id).filter(User.username == "dewi").first().id
ok(ob.get(f"/laporan/{lap_dewi}").status_code == 403, "OB tidak bisa buka laporan OB lain")

# coba selesaikan tanpa apa-apa
r = post(ob, f"/laporan/{lid}/checklist", {"aksi": "selesai"}, follow_redirects=True)
ok("Belum bisa diselesaikan" in r.get_data(as_text=True), "selesai ditolak bila checklist/foto kosong")
# unggah foto 3 jenis (satu file besar -> harus dikecilkan)
for j in ("before", "process", "after"):
    r = post(ob, f"/laporan/{lid}/foto", {"jenis": j, "foto": (jpg(), "x.jpg")}, content_type="multipart/form-data", follow_redirects=True)
    ok("1 foto tersimpan" in r.get_data(as_text=True), f"foto {j} tersimpan")
# berkas bukan gambar
r = post(ob, f"/laporan/{lid}/foto", {"jenis": "before", "foto": (io.BytesIO(b"bukan gambar"), "x.jpg")}, content_type="multipart/form-data", follow_redirects=True)
ok("bukan gambar" in r.get_data(as_text=True), "berkas bukan gambar ditolak")
with app.app_context():
    from models import Foto
    f = Foto.query.filter_by(laporan_id=lid).first()
    im = Image.open(os.path.join(os.environ["OB_INSTANCE"], "uploads", str(lid), f.nama_file))
    ok(max(im.size) <= 1280, f"foto dikecilkan ke {im.size}")
    ids = [i.id for i in Laporan.query.get(lid).items]
# centang semua + selesai
r = post(ob, f"/laporan/{lid}/checklist", {"aksi": "selesai", "item": [str(i) for i in ids]}, follow_redirects=True)
ok("Selesai" in r.get_data(as_text=True) and "1 dari" in r.get_data(as_text=True), "ruangan selesai dan progres terhitung")
ok(post(ob, f"/laporan/{lid}/checklist", {"aksi": "simpan"}).status_code == 403, "laporan selesai terkunci untuk OB")

# SPV
r = masuk(spv, "aditiya", DEFAULT_PASSWORD); ok("Ganti password" in r.get_data(as_text=True), "SPV dipaksa ganti password")
post(spv, "/ganti-password", {"lama": DEFAULT_PASSWORD, "baru": "spvrahasia1", "ulang": "spvrahasia1"})
r = spv.get("/spv"); ok("Indri Andriyani" in r.get_data(as_text=True) and "1/" in r.get_data(as_text=True), "dashboard SPV menampilkan progres OB")
r = spv.get(f"/laporan/{lid}"); ok("Pemeriksaan supervisor" in r.get_data(as_text=True), "SPV bisa lihat foto dan laporan")
fid = f.id; ok(spv.get(f"/foto/{fid}").status_code == 200, "SPV bisa lihat foto")
ok(ob.get(f"/foto/{fid}").status_code == 200, "OB pemilik bisa lihat fotonya")
r = post(spv, f"/spv/laporan/{lid}/buka", {"catatan": "Foto after kurang jelas"}, follow_redirects=True)
ok("Foto after kurang jelas" in r.get_data(as_text=True), "SPV mengembalikan laporan dengan catatan")
r = ob.get(f"/laporan/{lid}"); ok("Foto after kurang jelas" in r.get_data(as_text=True), "OB melihat catatan SPV")
post(ob, f"/laporan/{lid}/checklist", {"aksi": "selesai", "item": [str(i) for i in ids]})
r = post(spv, f"/spv/laporan/{lid}/periksa", {"catatan": "OK"}, follow_redirects=True)
ok("Sudah diperiksa" in r.get_data(as_text=True), "SPV menandai sudah diperiksa")

# penugasan oleh SPV
with app.app_context():
    from models import Lokasi
    lok = Lokasi.query.filter_by(nama="Toilet Perempuan", gedung="Gedung Utama", lantai="1").first(); lokid = lok.id
    neni = User.query.filter_by(username="neni").first().id
r = post(spv, "/spv/penugasan", {"gedung": "Gedung Utama", "lantai": "1", f"p_{lokid}": str(neni)}, follow_redirects=True)
ok("Penugasan disimpan" in r.get_data(as_text=True), "SPV menyimpan penugasan")
with app.app_context():
    ok(Penugasan.query.filter_by(lokasi_id=lokid, user_id=neni).count() == 1, "penugasan tercatat di database")
r = post(spv, "/spv/buat"); ok(r.status_code == 302, "SPV membuat laporan harian")
with app.app_context():
    l2 = Laporan.query.filter_by(lokasi_id=lokid).first()
    ok(l2 is not None and len(l2.items) >= 4, f"laporan toilet dibuat dengan {len(l2.items)} butir")
# template editor & reset password
r = post(spv, "/spv/checklist", {"aksi": "tambah", "jenis": "toilet", "nama_tugas": "Cek pewangi", "frekuensi": "harian"}, follow_redirects=True)
ok("Cek pewangi" in r.get_data(as_text=True), "SPV menambah butir checklist")
for url in ("/spv", "/spv/penugasan", "/spv/checklist", "/spv/pengguna"):
    ok(spv.get(url).status_code == 200, f"halaman {url} terbuka")
print("\nSEMUA TES LULUS")
