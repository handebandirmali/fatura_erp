import random
from datetime import datetime

# ====== CARİ VE ÜRÜN LİSTELERİ ======
cari_list = [
    ("C001", "A TEMİZLİK"), ("C002", "B GIDA"), ("C003", "D OFİS SİSTEMLERİ"),
    ("C004", "E TEKNOLOJİ"), ("C005", "G GIDA PAZARLAMA"), ("C006", "H TEMİZLİK ÜRÜNLERİ"),
    ("C007", "J KIRTASİYE VE OFİS"), ("C008", "C TİCARET"), ("C009", "F KIRTASİYE"),
    ("C010", "I OFİS MALZ."), ("C011", "KL KIRTASİYE"), ("C012", "MO OFİS"),
    ("C013", "P TEMİZLİK"), ("C014", "U GIDA")
]

urun_gruplari = {
    "TEMİZLİK": ["Çamaşır Deterjanı", "Bulaşık Deterjanı", "Yüzey Temizleyici", "Sıvı Sabun", "Tuvalet Temizleyici"],
    "GIDA": ["Makarna", "Pirinç", "Zeytinyağı", "Çay", "Kahve", "Un", "Şeker"],
    "OFIS": ["Laptop", "Mouse", "Keyboard", "Monitor", "USB Flash", "Yazıcı"]
}

# ====== SİSTEM HAFIZALARI ======
stok_eslesme_tablosu = {}
sabit_miktar_hafizasi = {}
stok_sayaci = 1
fatura_set = set()

kdv_hafizasi = {}
fiyat_hafizasi = {}
yillik_fiyat_hafizasi = {}

cari_anlasma_hafizasi = {}
alis_tarih_hafizasi = {}

# ====== AYARLAR ======
hedef_kayit_sayisi = 6128
output_file = "fatura_veritabani.txt"

# ====== STOK KODU ======
def get_unique_stok_kod(cari_kod, urun_adi):
    global stok_sayaci

    key = (cari_kod, urun_adi)

    if key not in stok_eslesme_tablosu:
        stok_eslesme_tablosu[key] = f"STK-{stok_sayaci:03}"
        stok_sayaci += 1

    return stok_eslesme_tablosu[key]


# ====== FATURA NO ======
def get_unique_fatura_no():
    while True:
        fno = f"FT-{random.randint(100000, 999999)}"

        if fno not in fatura_set:
            fatura_set.add(fno)
            return fno


# ====== CARİ ANLAŞMA MODELİ ======
def get_cari_contract(cari_kod):

    if cari_kod not in cari_anlasma_hafizasi:

        simdi = datetime.now()

        baslangic_yil = random.randint(2017, simdi.year)
        baslangic_ay = random.randint(1, 12)
        alis_gunu = random.randint(1, 28)

        cari_anlasma_hafizasi[cari_kod] = {
            "baslangic_yil": baslangic_yil,
            "baslangic_ay": baslangic_ay,
            "alis_gunu": alis_gunu
        }

    return cari_anlasma_hafizasi[cari_kod]


# ====== CARİDEN SEKTÖR BUL ======
def get_sektor_from_cari(cari_tam_ad):
    sektor = "OFIS"

    for anahtar in urun_gruplari.keys():
        if anahtar in cari_tam_ad.upper():
            sektor = anahtar
            break

    return sektor


# ====== AY EKLE ======
def ay_ekle(tarih_obj):
    yeni_ay = tarih_obj.month + 1
    yeni_yil = tarih_obj.year

    if yeni_ay > 12:
        yeni_ay = 1
        yeni_yil += 1

    yeni_gun = min(tarih_obj.day, 28)

    return datetime(yeni_yil, yeni_ay, yeni_gun)


# ====== YILLIK FİYAT ======
def get_yearly_price(key, tarih_obj):
    yil = tarih_obj.year

    if yil < 2017:
        yil = 2017

    yil_key = (key, yil)

    # baz fiyat: 2017 referans fiyatı
    if key not in fiyat_hafizasi:
        fiyat_hafizasi[key] = round(random.uniform(50, 1000), 2)

    base_fiyat = fiyat_hafizasi[key]

    if yil_key not in yillik_fiyat_hafizasi:
        yil_farki = yil - 2017
        enflasyon_katsayi = 1.12 ** yil_farki
        fiyat = round(base_fiyat * enflasyon_katsayi, 2)
        yillik_fiyat_hafizasi[yil_key] = fiyat

    return yillik_fiyat_hafizasi[yil_key]


# ====== BAŞLANGIÇ TARİHLERİNİ HAZIRLA ======
cari_ad_hafizasi = {}
tum_kombinasyonlar = []

for cari_k, cari_tam_ad in cari_list:
    cari_ad_hafizasi[cari_k] = cari_tam_ad

    sektor = get_sektor_from_cari(cari_tam_ad)

    for urun in urun_gruplari[sektor]:
        key = (cari_k, urun)
        tum_kombinasyonlar.append(key)

        contract = get_cari_contract(cari_k)

        ilk_tarih = datetime(
            contract["baslangic_yil"],
            contract["baslangic_ay"],
            contract["alis_gunu"]
        )

        alis_tarih_hafizasi[key] = ilk_tarih


# ====== VERİ ÜRETİMİ ======
kayitlar = []
bugun = datetime.now()

while len(kayitlar) < hedef_kayit_sayisi:
    aktif_key_list = []

    for key, tarih_obj in alis_tarih_hafizasi.items():
        if tarih_obj <= bugun:
            aktif_key_list.append(key)

    if not aktif_key_list:
        break

    key = random.choice(aktif_key_list)

    cari_k, urun = key
    cari_tam_ad = cari_ad_hafizasi[cari_k]
    stok_k = get_unique_stok_kod(cari_k, urun)

    tarih_obj = alis_tarih_hafizasi[key]
    tarih = tarih_obj.strftime("%Y-%m-%d")

    # miktar aynı cari + ürün için sabit
    if key not in sabit_miktar_hafizasi:
        sabit_miktar_hafizasi[key] = random.randint(1, 30)

    miktar = sabit_miktar_hafizasi[key]

    # kdv aynı cari + ürün için sabit
    if key not in kdv_hafizasi:
        kdv_hafizasi[key] = random.choice([8, 10, 18, 20])

    kdv = kdv_hafizasi[key]

    # aynı yıl içinde aynı fiyat
    fiyat = get_yearly_price(key, tarih_obj)

    fatura_n = get_unique_fatura_no()

    kayitlar.append(
        (fatura_n, cari_k, cari_tam_ad, stok_k, urun, tarih, miktar, fiyat, kdv)
    )

    # bir sonraki ayın aynı günü
    alis_tarih_hafizasi[key] = ay_ekle(tarih_obj)


# ====== KARIŞTIR ======
random.shuffle(kayitlar)


# ====== SQL YAZ ======
with open(output_file, "w", encoding="utf-8") as f:
    for r in kayitlar:
        sql = (
            f"INSERT INTO dbo.FaturaDetay "
            f"(fatura_no, cari_kod, cari_ad, stok_kod, urun_adi, urun_tarihi, "
            f"fiili_tarih, miktar, birim_fiyat, kdv_orani) VALUES "
            f"('{r[0]}', '{r[1]}', '{r[2]}', '{r[3]}', '{r[4]}', '{r[5]}', "
            f"'{r[5]}', {r[6]}, {r[7]}, {r[8]});\n"
        )
        f.write(sql)

print(f"işlem tamam, toplam {len(kayitlar)} kayıt üretildi.")