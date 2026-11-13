"""Aplikasi Checklist Ruangan OB - versi awal (MVP).

Jalankan:  python seed.py   (sekali, untuk mengisi data awal)
           python app.py    (buka http://localhost:5000)
"""
import os
import re
import secrets
import uuid

from datetime import datetime
from functools import wraps
from zoneinfo import ZoneInfo

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template, request,
                   send_from_directory, session, url_for)
from PIL import Image, ImageOps
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

from models import (Foto, Laporan, LaporanItem, Lokasi, Penugasan,
                    RequestPembersihan, Template, User, db)
from supabase_client import supabase

BASE = os.path.dirname(os.path.abspath(__file__))
if os.environ.get("VERCEL"):
    INSTANCE = "/tmp/instance"
else:
    INSTANCE = os.environ.get("OB_INSTANCE", os.path.join(BASE, "instance"))

UPLOADS = os.path.join(INSTANCE, "uploads")
os.makedirs(UPLOADS, exist_ok=True)

TZ = ZoneInfo("Asia/Jakarta")
JENIS_FOTO = [("before", "Sebelum"), ("process", "Proses"), ("after", "Sesudah")]
MAX_FOTO_PER_JENIS = 5          # batas per jenis, supaya penyimpanan dan WiFi tidak penuh
DEFAULT_PASSWORD = os.environ.get("SEED_PASSWORD", "KBM-2026-ITSB")
STATUS_LABEL = {"belum": "Belum", "proses": "Dikerjakan", "selesai": "Selesai", "dicek": "Sudah diperiksa"}
STATUS_REQUEST = {"menunggu": "Menunggu", "proses": "Diproses", "selesai": "Selesai"}


def _secret_key():
    """Kunci rahasia sesi: prioritas dari env OB_SECRET, fallback tetap di Vercel."""
    if os.environ.get("OB_SECRET"):
        return os.environ["OB_SECRET"]
    if os.environ.get("VERCEL"):
        return "kunci-rahasia-ob-app-itsb-2026-aman"
    path = os.path.join(INSTANCE, "secret.key")
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(secrets.token_hex(32))
    with open(path) as f:
        return f.read().strip()

db_url = os.environ.get("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app = Flask(__name__)
app.config.update(
    SECRET_KEY=_secret_key(),
    SQLALCHEMY_DATABASE_URI=db_url or ("sqlite:///" + os.path.join(INSTANCE, "ob.db")),
    SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
    MAX_CONTENT_LENGTH=40 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=bool(os.environ.get("VERCEL")),
)

if db_url:
    db.metadata.schema = "ob_app"
    for table in db.metadata.tables.values():
        table.schema = "ob_app"

db.init_app(app)
with app.app_context():
    db.create_all()


# ---------------------------------------------------------------- helper umum
def sekarang():
    return datetime.now(TZ).replace(tzinfo=None)


def hari_ini():
    return sekarang().date()


def jatuh_tempo(frekuensi, tgl):
    """Aturan sementara (usulan): harian tiap hari, mingguan tiap Senin, bulanan tiap tanggal 1."""
    if frekuensi == "mingguan":
        return tgl.weekday() == 0
    if frekuensi == "bulanan":
        return tgl.day == 1
    return True


def buat_laporan(tgl):
    """Buat laporan harian untuk semua ruangan yang sudah ada penanggung jawabnya. Aman dipanggil berulang."""
    dibuat = 0
    for p in Penugasan.query.all():
        if Laporan.query.filter_by(tanggal=tgl, lokasi_id=p.lokasi_id).first():
            continue
        tmpl = (Template.query.filter_by(jenis=p.lokasi.jenis, aktif=True)
                .order_by(Template.urutan, Template.id).all())
        tmpl = [t for t in tmpl if jatuh_tempo(t.frekuensi, tgl)]
        if not tmpl:
            continue
        lap = Laporan(tanggal=tgl, lokasi_id=p.lokasi_id, user_id=p.user_id)
        lap.items = [LaporanItem(template_id=t.id, urutan=i, nama_tugas=t.nama_tugas)
                     for i, t in enumerate(tmpl, 1)]
        db.session.add(lap)
        dibuat += 1
    db.session.commit()
    return dibuat


def simpan_foto(file_storage, laporan_id):
    """Kecilkan foto (maks 1280 px, JPEG) lalu simpan ke disk. Mengembalikan nama file."""
    img = Image.open(file_storage.stream)
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((1280, 1280))
    folder = os.path.join(UPLOADS, str(laporan_id))
    os.makedirs(folder, exist_ok=True)
    nama = uuid.uuid4().hex + ".jpg"
    img.save(os.path.join(folder, nama), "JPEG", quality=75, optimize=True)
    return nama


def kekurangan(lap):
    """Daftar alasan laporan belum boleh diselesaikan."""
    masalah = []
    sisa = [i for i in lap.items if not i.selesai]
    if sisa:
        masalah.append(f"{len(sisa)} butir checklist belum dicentang")
    for kode, label in JENIS_FOTO:
        if not any(f.jenis == kode for f in lap.fotos):
            masalah.append(f"foto {label.lower()} belum ada")
    return masalah


# ---------------------------------------------------------------- sesi, login, CSRF
@app.context_processor
def konteks():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return {
        "csrf_token": session["csrf"],
        "user": g.get("user"),
        "STATUS_LABEL": STATUS_LABEL,
        "STATUS_REQUEST": STATUS_REQUEST,
    }


@app.before_request
def muat_pengguna():
    g.user = None
    uid = session.get("uid")
    if uid:
        u = db.session.get(User, uid)
        if u and u.aktif:
            g.user = u
        else:
            session.pop("uid", None)
    if request.method == "POST":
        token = session.get("csrf")
        if not token or token != request.form.get("_csrf"):
            abort(400, "Sesi kedaluwarsa. Muat ulang halaman lalu coba lagi.")
    if g.user and g.user.must_change and request.endpoint not in ("ganti_password", "logout", "static"):
        return redirect(url_for("ganti_password"))


def login_wajib(f):
    @wraps(f)
    def dibungkus(*a, **kw):
        if not g.user:
            return redirect(url_for("login"))
        return f(*a, **kw)
    return dibungkus


def spv_wajib(f):
    @wraps(f)
    @login_wajib
    def dibungkus(*a, **kw):
        if g.user.peran != "supervisor":
            abort(403)
        return f(*a, **kw)
    return dibungkus


def client_wajib(f):
    @wraps(f)
    @login_wajib
    def dibungkus(*a, **kw):
        if g.user.peran != "client":
            abort(403)
        return f(*a, **kw)
    return dibungkus


@app.route("/")
def index():
    if not g.user:
        return redirect(url_for("login"))
    if g.user.peran == "supervisor":
        return redirect(url_for("dashboard"))
    elif g.user.peran == "client":
        return redirect(url_for("client_overview"))
    return redirect(url_for("hari_ini_ob"))

# ---------------------------------------------------------------- API SUPABASE

@app.route("/api/gedung", methods=["GET"])
def api_gedung():
    try:
        response = (
            supabase
            .table("gedung")
            .select("id_gedung, nama_gedung, keterangan")
            .order("id_gedung")
            .execute()
        )

        data = response.data

        return jsonify({
            "success": True,
            "jumlah": len(data),
            "data": data
        }), 200

    except Exception:
        app.logger.exception("Gagal mengambil data gedung dari Supabase")

        return jsonify({
            "success": False,
            "message": "Gagal mengambil data gedung."
        }), 500

@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("index"))
    if request.method == "POST":
        u = User.query.filter_by(username=request.form.get("username", "").strip().lower()).first()
        if u and u.aktif and check_password_hash(u.password_hash, request.form.get("password", "")):
            session.clear()
            session["uid"] = u.id
            return redirect(url_for("index"))
        flash("Username atau password salah.", "error")
    return render_template("login.html")


def buat_kode_pengguna():
    """Membuat kode unik pengguna otomatis berikutnya, misal U14, U15, dst."""
    semua_kode = [r[0] for r in db.session.query(User.kode).all() if r[0]]
    nomor_list = []
    for k in semua_kode:
        m = re.search(r"\d+", k)
        if m:
            nomor_list.append(int(m.group()))
    next_nomor = (max(nomor_list) + 1) if nomor_list else 1
    return f"U{next_nomor:02d}"


@app.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("index"))
    if request.method == "POST":
        nama = request.form.get("nama", "").strip()
        username = request.form.get("username", "").strip().lower()
        peran_pilihan = request.form.get("peran_pilihan", "ob_cleaning")
        pw = request.form.get("password", "")
        ulang = request.form.get("konfirmasi_password", "")

        if not nama or not username or not pw:
            flash("Nama, username, dan password wajib diisi.", "error")
        elif not re.match(r"^[a-z0-9_.-]+$", username):
            flash("Username hanya boleh berisi huruf, angka, titik, atau garis bawah.", "error")
        elif len(pw) < 6:
            flash("Password minimal 6 karakter.", "error")
        elif pw != ulang:
            flash("Password dan konfirmasi password tidak sama.", "error")
        elif User.query.filter_by(username=username).first():
            flash(f"Username '{username}' sudah digunakan. Silakan gunakan username lain.", "error")
        else:
            if peran_pilihan == "supervisor":
                peran = "supervisor"
                jabatan = "SPV"
                divisi = "cleaning"
            elif peran_pilihan == "client":
                peran = "client"
                jabatan = "Client"
                divisi = "umum"
            elif peran_pilihan == "ob_taman":
                peran = "ob"
                jabatan = "Gardener"
                divisi = "taman"
            else:
                peran = "ob"
                jabatan = "Crew"
                divisi = "cleaning"

            kode = buat_kode_pengguna()
            user_baru = User(
                kode=kode,
                nama=nama,
                jabatan=jabatan,
                peran=peran,
                divisi=divisi,
                username=username,
                password_hash=generate_password_hash(pw),
                aktif=True,
                must_change=False,
            )
            db.session.add(user_baru)
            db.session.commit()
            flash("Pendaftaran berhasil! Silakan masuk dengan akun baru Anda.", "ok")
            return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/ganti-password", methods=["GET", "POST"])
@login_wajib
def ganti_password():
    if request.method == "POST":
        lama, baru, ulang = (request.form.get(k, "") for k in ("lama", "baru", "ulang"))
        if not check_password_hash(g.user.password_hash, lama):
            flash("Password lama salah.", "error")
        elif baru == DEFAULT_PASSWORD:
            flash("Password baru tidak boleh sama dengan password awal.", "error")
        elif len(baru) < 8:
            flash("Password baru minimal 8 karakter.", "error")
        elif baru != ulang:
            flash("Pengulangan password tidak sama.", "error")
        else:
            g.user.password_hash = generate_password_hash(baru)
            g.user.must_change = False
            db.session.commit()
            flash("Password diganti.", "ok")
            return redirect(url_for("index"))
    return render_template("ganti_password.html")


# ---------------------------------------------------------------- halaman OB
@app.route("/hari-ini")
@login_wajib
def hari_ini_ob():
    tgl = hari_ini()
    buat_laporan(tgl)
    laporan = (Laporan.query.filter_by(tanggal=tgl, user_id=g.user.id).join(Lokasi)
               .order_by(Lokasi.gedung, Lokasi.lantai, Lokasi.nama).all())
    selesai = sum(1 for l in laporan if l.status in ("selesai", "dicek"))
    lokasi_ids = [l.lokasi_id for l in laporan]
    reqs = RequestPembersihan.query.filter(
        RequestPembersihan.lokasi_id.in_(lokasi_ids),
        RequestPembersihan.status.in_(("menunggu", "proses"))
    ).all() if lokasi_ids else []
    permintaan_per_lokasi = {r.lokasi_id: r for r in reqs}
    return render_template("hari_ini.html", laporan=laporan, tgl=tgl, selesai=selesai,
                           permintaan_per_lokasi=permintaan_per_lokasi)


def ambil_laporan(lap_id):
    """Ambil laporan; OB hanya boleh membuka miliknya sendiri, SPV dan Client boleh melihat."""
    lap = db.get_or_404(Laporan, lap_id)
    if g.user.peran not in ("supervisor", "client") and lap.user_id != g.user.id:
        abort(403)
    return lap


def bisa_edit(lap):
    return g.user.id == lap.user_id and lap.status in ("belum", "proses")


@app.route("/laporan/<int:lap_id>")
@login_wajib
def laporan(lap_id):
    lap = ambil_laporan(lap_id)
    foto = {k: [f for f in lap.fotos if f.jenis == k] for k, _ in JENIS_FOTO}
    return render_template("laporan.html", lap=lap, foto=foto, jenis_foto=JENIS_FOTO,
                           edit=bisa_edit(lap), maks=MAX_FOTO_PER_JENIS)


@app.route("/laporan/<int:lap_id>/checklist", methods=["POST"])
@login_wajib
def simpan_checklist(lap_id):
    lap = ambil_laporan(lap_id)
    if not bisa_edit(lap):
        abort(403)
    dicentang = set(request.form.getlist("item"))
    for it in lap.items:
        it.selesai = str(it.id) in dicentang
    if lap.waktu_mulai is None and (dicentang or lap.fotos):
        lap.waktu_mulai = sekarang()
    lap.status = "proses" if (dicentang or lap.fotos) else "belum"
    if request.form.get("aksi") == "selesai":
        masalah = kekurangan(lap)
        if masalah:
            db.session.commit()
            flash("Belum bisa diselesaikan: " + "; ".join(masalah) + ".", "error")
            return redirect(url_for("laporan", lap_id=lap.id))
        lap.status = "selesai"
        lap.waktu_selesai = sekarang()
        flash("Ruangan ditandai selesai.", "ok")
    else:
        flash("Checklist disimpan.", "ok")
    db.session.commit()
    return redirect(url_for("laporan", lap_id=lap.id) if lap.status != "selesai" else url_for("hari_ini_ob"))


@app.route("/laporan/<int:lap_id>/foto", methods=["POST"])
@login_wajib
def unggah_foto(lap_id):
    lap = ambil_laporan(lap_id)
    if not bisa_edit(lap):
        abort(403)
    jenis = request.form.get("jenis")
    if jenis not in dict(JENIS_FOTO):
        abort(400)
    ada = sum(1 for f in lap.fotos if f.jenis == jenis)
    berkas = [f for f in request.files.getlist("foto") if f and f.filename]
    ok, gagal = 0, 0
    for f in berkas:
        if ada + ok >= MAX_FOTO_PER_JENIS:
            flash(f"Maksimal {MAX_FOTO_PER_JENIS} foto per jenis.", "error")
            break
        try:
            nama = simpan_foto(f, lap.id)
        except Exception:
            gagal += 1
            continue
        db.session.add(Foto(laporan_id=lap.id, jenis=jenis, nama_file=nama, waktu_ambil=sekarang()))
        ok += 1
    if ok:
        if lap.waktu_mulai is None:
            lap.waktu_mulai = sekarang()
        lap.status = "proses"
        flash(f"{ok} foto tersimpan.", "ok")
    if gagal:
        flash(f"{gagal} berkas bukan gambar yang valid.", "error")
    db.session.commit()
    return redirect(url_for("laporan", lap_id=lap.id) + "#foto")


@app.route("/laporan/<int:lap_id>/foto/<int:foto_id>/hapus", methods=["POST"])
@login_wajib
def hapus_foto(lap_id, foto_id):
    lap = ambil_laporan(lap_id)
    if not bisa_edit(lap):
        abort(403)
    f = Foto.query.filter_by(id=foto_id, laporan_id=lap.id).first_or_404()
    try:
        os.remove(os.path.join(UPLOADS, str(lap.id), f.nama_file))
    except OSError:
        pass
    db.session.delete(f)
    db.session.commit()
    return redirect(url_for("laporan", lap_id=lap.id) + "#foto")


@app.route("/foto/<int:foto_id>")
@login_wajib
def tampil_foto(foto_id):
    f = db.get_or_404(Foto, foto_id)
    ambil_laporan(f.laporan_id)  # cek hak akses
    return send_from_directory(os.path.join(UPLOADS, str(f.laporan_id)), f.nama_file, max_age=3600)


# ---------------------------------------------------------------- halaman SPV
@app.route("/spv")
@spv_wajib
def dashboard():
    try:
        tgl = datetime.strptime(request.args.get("tgl", ""), "%Y-%m-%d").date()
    except ValueError:
        tgl = hari_ini()
    laporan = (Laporan.query.filter_by(tanggal=tgl).join(Lokasi)
               .order_by(Lokasi.gedung, Lokasi.lantai, Lokasi.nama).all())
    per_ob = {}
    for l in laporan:
        d = per_ob.setdefault(l.user.nama, {"total": 0, "selesai": 0})
        d["total"] += 1
        d["selesai"] += l.status in ("selesai", "dicek")
    total_lokasi = Lokasi.query.count()
    belum_ditugaskan = total_lokasi - Penugasan.query.count()
    pending_requests = RequestPembersihan.query.filter_by(status="menunggu").count()
    return render_template("dashboard.html", tgl=tgl, laporan=laporan, per_ob=per_ob,
                           belum_ditugaskan=belum_ditugaskan, pending_requests=pending_requests,
                           adalah_hari_ini=(tgl == hari_ini()))


@app.route("/spv/buat", methods=["POST"])
@spv_wajib
def buat_hari_ini():
    n = buat_laporan(hari_ini())
    flash(f"{n} laporan baru dibuat untuk hari ini." if n else "Tidak ada laporan baru (sudah dibuat, atau belum ada penugasan).", "ok")
    return redirect(url_for("dashboard"))


@app.route("/spv/laporan/<int:lap_id>/periksa", methods=["POST"])
@spv_wajib
def periksa(lap_id):
    lap = db.get_or_404(Laporan, lap_id)
    if lap.status not in ("selesai", "dicek"):
        abort(400, "Laporan belum diselesaikan OB.")
    lap.status = "dicek"
    lap.diperiksa_oleh_id = g.user.id
    lap.waktu_periksa = sekarang()
    lap.catatan_spv = request.form.get("catatan", "").strip()[:500] or None
    db.session.commit()
    flash("Laporan ditandai sudah diperiksa.", "ok")
    return redirect(url_for("laporan", lap_id=lap.id))


@app.route("/spv/laporan/<int:lap_id>/buka", methods=["POST"])
@spv_wajib
def buka_kembali(lap_id):
    lap = db.get_or_404(Laporan, lap_id)
    lap.status = "proses"
    lap.waktu_selesai = None
    lap.waktu_periksa = None
    lap.diperiksa_oleh_id = None
    lap.catatan_spv = (request.form.get("catatan", "").strip()[:500] or None)
    db.session.commit()
    flash("Laporan dikembalikan ke OB untuk diperbaiki.", "ok")
    return redirect(url_for("laporan", lap_id=lap.id))


@app.route("/spv/penugasan", methods=["GET", "POST"])
@spv_wajib
def penugasan():
    gedung = request.values.get("gedung", "")
    lantai = request.values.get("lantai", "")
    q = Lokasi.query
    if gedung:
        q = q.filter_by(gedung=gedung)
    if lantai:
        q = q.filter_by(lantai=lantai)
    lokasi = q.order_by(Lokasi.gedung, Lokasi.lantai, Lokasi.nama).all()
    ob = User.query.filter_by(peran="ob", aktif=True).order_by(User.nama).all()
    if request.method == "POST":
        valid = {u.id for u in ob}
        ada = {p.lokasi_id: p for p in Penugasan.query.filter(Penugasan.lokasi_id.in_([l.id for l in lokasi])).all()}
        for l in lokasi:
            pilih = request.form.get(f"p_{l.id}", "")
            uid = int(pilih) if pilih.isdigit() and int(pilih) in valid else None
            if uid and l.id in ada:
                ada[l.id].user_id = uid
            elif uid:
                db.session.add(Penugasan(lokasi_id=l.id, user_id=uid))
            elif l.id in ada:
                db.session.delete(ada[l.id])
        db.session.commit()
        flash("Penugasan disimpan. Perubahan berlaku untuk laporan yang dibuat berikutnya.", "ok")
        return redirect(url_for("penugasan", gedung=gedung, lantai=lantai))
    tugas = {p.lokasi_id: p.user_id for p in Penugasan.query.all()}
    daftar_gedung = [r[0] for r in db.session.query(Lokasi.gedung).distinct().order_by(Lokasi.gedung)]
    daftar_lantai = [r[0] for r in db.session.query(Lokasi.lantai).distinct().order_by(Lokasi.lantai)]
    return render_template("penugasan.html", lokasi=lokasi, ob=ob, tugas=tugas, gedung=gedung, lantai=lantai,
                           daftar_gedung=daftar_gedung, daftar_lantai=daftar_lantai)


@app.route("/spv/checklist", methods=["GET", "POST"])
@spv_wajib
def kelola_template():
    if request.method == "POST":
        aksi = request.form.get("aksi")
        if aksi == "tambah":
            jenis = request.form.get("jenis", "").strip()
            nama = request.form.get("nama_tugas", "").strip()
            frek = request.form.get("frekuensi", "harian")
            if jenis and nama and frek in ("harian", "mingguan", "bulanan"):
                urut = (db.session.query(func.max(Template.urutan)).filter_by(jenis=jenis).scalar() or 0) + 1
                db.session.add(Template(jenis=jenis, nama_tugas=nama[:150], frekuensi=frek, urutan=urut, sumber="spv"))
                db.session.commit()
                flash("Butir checklist ditambahkan.", "ok")
        elif aksi in ("aktif", "frekuensi"):
            t = db.get_or_404(Template, int(request.form.get("id", 0)))
            if aksi == "aktif":
                t.aktif = not t.aktif
            elif request.form.get("frekuensi") in ("harian", "mingguan", "bulanan"):
                t.frekuensi = request.form["frekuensi"]
            db.session.commit()
        return redirect(url_for("kelola_template") + "#j-" + request.form.get("jenis", ""))
    jenis_list = [r[0] for r in db.session.query(Lokasi.jenis).distinct().order_by(Lokasi.jenis)]
    jumlah = dict(db.session.query(Lokasi.jenis, func.count(Lokasi.id)).group_by(Lokasi.jenis).all())
    tmpl = {j: Template.query.filter_by(jenis=j).order_by(Template.urutan, Template.id).all() for j in jenis_list}
    return render_template("checklist.html", jenis_list=jenis_list, tmpl=tmpl, jumlah=jumlah)


@app.route("/spv/pengguna", methods=["GET", "POST"])
@spv_wajib
def kelola_pengguna():
    if request.method == "POST":
        u = db.get_or_404(User, int(request.form.get("id", 0)))
        if u.id == g.user.id:
            flash("Tidak bisa mengubah akun sendiri di sini.", "error")
        elif request.form.get("aksi") == "reset":
            u.password_hash = generate_password_hash(DEFAULT_PASSWORD)
            u.must_change = True
            flash(f"Password {u.nama} dikembalikan ke password awal.", "ok")
        elif request.form.get("aksi") == "aktif":
            u.aktif = not u.aktif
        db.session.commit()
        return redirect(url_for("kelola_pengguna"))
    semua = User.query.order_by(User.peran.desc(), User.nama).all()
    return render_template("pengguna.html", semua=semua)


# ---------------------------------------------------------------- halaman Client & Permintaan
@app.route("/client", methods=["GET", "POST"])
@client_wajib
def client_overview():
    lokasi_dipilih_id = request.args.get("lokasi_id", type=int)
    if request.method == "POST":
        lok_id = int(request.form.get("lokasi_id", 0))
        catatan = request.form.get("catatan", "").strip()
        lok = db.session.get(Lokasi, lok_id)
        if not lok:
            flash("Ruangan yang dipilih tidak valid.", "error")
        elif not catatan:
            flash("Catatan atau alasan permintaan pembersihan wajib diisi.", "error")
        else:
            req = RequestPembersihan(
                user_id=g.user.id,
                lokasi_id=lok.id,
                waktu_buat=sekarang(),
                catatan=catatan,
                status="menunggu",
            )
            db.session.add(req)
            db.session.commit()
            flash(f"Permintaan pembersihan untuk {lok.nama} berhasil dikirim!", "ok")
            return redirect(url_for("client_overview"))

    riwayat = (RequestPembersihan.query.filter_by(user_id=g.user.id)
               .order_by(RequestPembersihan.waktu_buat.desc()).all())
    stats = {
        "total": len(riwayat),
        "menunggu": sum(1 for r in riwayat if r.status == "menunggu"),
        "proses": sum(1 for r in riwayat if r.status == "proses"),
        "selesai": sum(1 for r in riwayat if r.status == "selesai"),
    }
    daftar_lokasi = Lokasi.query.order_by(Lokasi.gedung, Lokasi.lantai, Lokasi.nama).all()
    return render_template("client_overview.html", riwayat=riwayat, stats=stats,
                           daftar_lokasi=daftar_lokasi, lokasi_dipilih_id=lokasi_dipilih_id)


@app.route("/client/ruangan")
@client_wajib
def client_ruangan():
    tgl = hari_ini()
    gedung = request.args.get("gedung", "")
    lantai = request.args.get("lantai", "")

    q = Lokasi.query
    if gedung:
        q = q.filter_by(gedung=gedung)
    if lantai:
        q = q.filter_by(lantai=lantai)
    daftar_lokasi = q.order_by(Lokasi.gedung, Lokasi.lantai, Lokasi.nama).all()

    laporan_hari_ini = {l.lokasi_id: l for l in Laporan.query.filter_by(tanggal=tgl).all()}
    permintaan_aktif = {}
    for r in RequestPembersihan.query.filter(RequestPembersihan.status.in_(("menunggu", "proses"))).all():
        permintaan_aktif[r.lokasi_id] = r

    daftar_gedung = [r[0] for r in db.session.query(Lokasi.gedung).distinct().order_by(Lokasi.gedung)]
    daftar_lantai = [r[0] for r in db.session.query(Lokasi.lantai).distinct().order_by(Lokasi.lantai)]

    return render_template("client_ruangan.html", daftar_lokasi=daftar_lokasi,
                           laporan_hari_ini=laporan_hari_ini, permintaan_aktif=permintaan_aktif,
                           gedung=gedung, lantai=lantai, daftar_gedung=daftar_gedung,
                           daftar_lantai=daftar_lantai, tgl=tgl)


@app.route("/spv/request", methods=["GET", "POST"])
@spv_wajib
def daftar_request_spv():
    if request.method == "POST":
        req_id = int(request.form.get("id", 0))
        aksi = request.form.get("aksi")
        catatan_selesai = request.form.get("catatan_selesai", "").strip()
        req = db.get_or_404(RequestPembersihan, req_id)

        if aksi == "proses":
            req.status = "proses"
            flash(f"Permintaan #{req.id} untuk {req.lokasi.nama} ditandai 'Sedang Diproses'.", "ok")
        elif aksi == "selesai":
            req.status = "selesai"
            req.waktu_selesai = sekarang()
            if catatan_selesai:
                req.catatan_selesai = catatan_selesai
            flash(f"Permintaan #{req.id} untuk {req.lokasi.nama} ditandai 'Selesai'.", "ok")
        db.session.commit()
        return redirect(url_for("daftar_request_spv"))

    daftar_req = RequestPembersihan.query.order_by(RequestPembersihan.waktu_buat.desc()).all()
    return render_template("spv_request.html", daftar_req=daftar_req)


if __name__ == "__main__":
    # host 0.0.0.0 supaya bisa dibuka dari HP di WiFi yang sama; untuk produksi pakai gunicorn/waitress
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=bool(os.environ.get("OB_DEBUG")))
