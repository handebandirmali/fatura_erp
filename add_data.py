import random
from datetime import datetime, timedelta
from collections import defaultdict

random.seed(42)

# =========================================================
# CARİ VE ÜRÜN LİSTELERİ
# =========================================================
cari_list = [
    ("C001", "A TEMİZLİK"),
    ("C002", "B GIDA"),
    ("C003", "D OFİS SİSTEMLERİ"),
    ("C004", "E TEKNOLOJİ"),
    ("C005", "G GIDA PAZARLAMA"),
    ("C006", "H TEMİZLİK ÜRÜNLERİ"),
    ("C007", "J KIRTASİYE VE OFİS"),
    ("C008", "C TİCARET"),
    ("C009", "F KIRTASİYE"),
    ("C010", "I OFİS MALZ."),
    ("C011", "KL KIRTASİYE"),
    ("C012", "MO OFİS"),
    ("C013", "P TEMİZLİK"),
    ("C014", "U GIDA"),
]

urun_gruplari = {
    "TEMIZLIK": [
        "Çamaşır Deterjanı",
        "Bulaşık Deterjanı",
        "Yüzey Temizleyici",
        "Sıvı Sabun",
        "Tuvalet Temizleyici",
    ],
    "GIDA": [
        "Makarna",
        "Pirinç",
        "Zeytinyağı",
        "Çay",
        "Kahve",
        "Un",
        "Şeker",
    ],
    "OFIS": [
        "Laptop",
        "Mouse",
        "Keyboard",
        "Monitor",
        "USB Flash",
        "Yazıcı",
    ],
}

# =========================================================
# AYARLAR
# =========================================================
output_file = "fatura_veritabani.txt"
min_gecmis_kayit = 4
max_gecmis_kayit = 7
min_baslangic_tarihi = datetime(2022, 1, 1).date()

# YARIN AĞIRLIKLI DAĞILIM
# hedef_gun -> profil sayısı
gunluk_profil_hedefleri = {
    1: 220,   # yarın çok yoğun
    2: 110,
    3: 90,
    4: 70,
    5: 60,
    6: 50,
    7: 40,
    8: 30,
    9: 25,
    10: 20,
}

# =========================================================
# HAFIZA
# =========================================================
stok_eslesme_tablosu = {}
stok_sayaci = 1
fatura_set = set()
baz_fiyat_hafizasi = {}
yillik_fiyat_hafizasi = {}
cari_ad_hafizasi = {}

# =========================================================
# YARDIMCILAR
# =========================================================
def sql_escape(value):
    if value is None:
        return ""
    return str(value).replace("'", "''")


def get_unique_stok_kod(unique_key):
    global stok_sayaci
    if unique_key not in stok_eslesme_tablosu:
        stok_eslesme_tablosu[unique_key] = f"STK-{stok_sayaci:04d}"
        stok_sayaci += 1
    return stok_eslesme_tablosu[unique_key]


def get_unique_fatura_no():
    while True:
        fno = f"FT-{random.randint(100000, 999999)}"
        if fno not in fatura_set:
            fatura_set.add(fno)
            return fno


def get_sektor_from_cari(cari_tam_ad):
    ad = cari_tam_ad.upper()

    if "GIDA" in ad:
        return "GIDA"

    if "TEMİZLİK" in ad or "TEMIZLIK" in ad:
        return "TEMIZLIK"

    if (
        "OFİS" in ad
        or "OFIS" in ad
        or "KIRTASİYE" in ad
        or "TEKNOLOJİ" in ad
        or "TEKNOLOJI" in ad
    ):
        return "OFIS"

    return "OFIS"


def get_dynamic_quantity(base_miktar):
    oran = random.uniform(0.92, 1.08)
    return max(1, round(base_miktar * oran))


def get_yearly_price(key, tarih_obj):
    yil = tarih_obj.year
    yil_key = (key, yil)

    if key not in baz_fiyat_hafizasi:
        baz_fiyat_hafizasi[key] = round(random.uniform(90, 3000), 2)

    baz_fiyat = baz_fiyat_hafizasi[key]

    if yil_key not in yillik_fiyat_hafizasi:
        yil_farki = yil - 2022
        enflasyon_katsayi = 1.18 ** max(0, yil_farki)
        yillik_fiyat_hafizasi[yil_key] = round(baz_fiyat * enflasyon_katsayi, 2)

    return yillik_fiyat_hafizasi[yil_key]


# =========================================================
# TÜM KOMBİNASYONLAR
# =========================================================
tum_kombinasyonlar = []

for cari_kod, cari_ad in cari_list:
    cari_ad_hafizasi[cari_kod] = cari_ad
    sektor = get_sektor_from_cari(cari_ad)

    for urun_adi in urun_gruplari[sektor]:
        tum_kombinasyonlar.append((cari_kod, cari_ad, urun_adi))

# =========================================================
# PROFİL OLUŞTUR
# =========================================================
bugun = datetime.today().date()
profiller = []
profil_index = 1

for hedef_gun, adet in gunluk_profil_hedefleri.items():
    for _ in range(adet):
        cari_kod, cari_ad, urun_adi = random.choice(tum_kombinasyonlar)

        # Aynı cari+ürün çok tekrar etsin istemediğimiz için profile özel key
        unique_profile_key = f"{cari_kod}|{urun_adi}|P{profil_index:04d}"
        stok_kod = get_unique_stok_kod(unique_profile_key)

        # periyotlar kısa/orta olsun ki yarın filtresinde daha çok kayıt geçsin
        interval = random.choice([7, 10, 14, 15, 21, 30])
        base_miktar = random.randint(5, 60)
        kdv = random.choice([1, 8, 10, 18, 20])

        # beklenecek tarih
        beklenen_tarih = bugun + timedelta(days=hedef_gun)

        # son gerçek alış tarihi
        son_alis_tarihi = beklenen_tarih - timedelta(days=interval)

        profiller.append({
            "profil_no": profil_index,
            "cari_kod": cari_kod,
            "cari_ad": cari_ad,
            "stok_kod": stok_kod,
            "urun_adi": urun_adi,
            "interval": interval,
            "base_miktar": base_miktar,
            "kdv": kdv,
            "hedef_gun": hedef_gun,
            "beklenen_tarih": beklenen_tarih,
            "son_alis_tarihi": son_alis_tarihi,
        })
        profil_index += 1

# =========================================================
# GEÇMİŞ KAYITLARI ÜRET
# =========================================================
kayitlar = []

for profil in profiller:
    kayit_sayisi = random.randint(min_gecmis_kayit, max_gecmis_kayit)
    interval = profil["interval"]

    # Hafif oynama var ama çok bozmuyor
    jitter_options = [-1, 0, 1]

    tarihler = [profil["son_alis_tarihi"]]

    while len(tarihler) < kayit_sayisi:
        onceki = tarihler[0]
        step = max(1, interval + random.choice(jitter_options))
        yeni_tarih = onceki - timedelta(days=step)

        if yeni_tarih < min_baslangic_tarihi:
            break

        tarihler.insert(0, yeni_tarih)

    # En az 3 kayıt kalsın
    while len(tarihler) < 3:
        ilk = tarihler[0]
        yeni_tarih = ilk - timedelta(days=interval)
        if yeni_tarih < min_baslangic_tarihi:
            break
        tarihler.insert(0, yeni_tarih)

    for tarih in tarihler:
        fatura_no = get_unique_fatura_no()
        miktar = get_dynamic_quantity(profil["base_miktar"])
        birim_fiyat = get_yearly_price(
            (profil["cari_kod"], profil["stok_kod"], profil["urun_adi"]),
            datetime.combine(tarih, datetime.min.time())
        )

        kayitlar.append({
            "fatura_no": fatura_no,
            "cari_kod": profil["cari_kod"],
            "cari_ad": profil["cari_ad"],
            "stok_kod": profil["stok_kod"],
            "urun_adi": profil["urun_adi"],
            "urun_tarihi": tarih,
            "fiili_tarih": tarih,
            "miktar": miktar,
            "birim_fiyat": birim_fiyat,
            "kdv_orani": profil["kdv"],
        })

random.shuffle(kayitlar)

# =========================================================
# SQL DOSYASI YAZ
# =========================================================
with open(output_file, "w", encoding="utf-8") as f:
    for r in kayitlar:
        sql = (
            "INSERT INTO dbo.FaturaDetay "
            "(fatura_no, cari_kod, cari_ad, stok_kod, urun_adi, urun_tarihi, fiili_tarih, miktar, birim_fiyat, kdv_orani) "
            "VALUES "
            f"('{sql_escape(r['fatura_no'])}', "
            f"'{sql_escape(r['cari_kod'])}', "
            f"'{sql_escape(r['cari_ad'])}', "
            f"'{sql_escape(r['stok_kod'])}', "
            f"'{sql_escape(r['urun_adi'])}', "
            f"'{r['urun_tarihi'].strftime('%Y-%m-%d')}', "
            f"'{r['fiili_tarih'].strftime('%Y-%m-%d')}', "
            f"{float(r['miktar'])}, "
            f"{float(r['birim_fiyat'])}, "
            f"{float(r['kdv_orani'])});\n"
        )
        f.write(sql)

# =========================================================
# RAPOR
# =========================================================
ozet = defaultdict(int)
for p in profiller:
    ozet[p["hedef_gun"]] += 1

print("=" * 60)
print(f"Toplam profil sayısı              : {len(profiller)}")
print(f"Toplam geçmiş kayıt sayısı        : {len(kayitlar)}")
print(f"Oluşturulan SQL dosyası           : {output_file}")
print("-" * 60)
print("Beklenen gün dağılımı:")
for gun in range(1, 11):
    print(f"Gün +{gun}: {ozet[gun]} profil")
print("=" * 60)