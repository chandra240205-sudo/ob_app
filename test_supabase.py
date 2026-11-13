
from supabase_client import supabase

try:
    response = (
        supabase
        .table("gedung")
        .select("*")
        .limit(5)
        .execute()
    )

    print("Koneksi dan query berhasil!")
    print("Jumlah data:", len(response.data))
    print("Data gedung:", response.data)

except Exception as e:
    print("Terjadi kesalahan:", e)
