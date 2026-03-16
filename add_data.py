import random
from datetime import datetime, timedelta

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
alis_tarih_hafizasi = {}
cari_ad_hafizasi = {}

# ====== AYARLAR ======
hedef_kayit_sayisi = 6128
output_file = "fatura_veritabani.txt"

# ====== YARDIMCI FONKSİYONLAR ======
def get_unique_stok_kod(cari_kod, urun_adi):
    global stok_sayaci
    key = (cari_kod, urun_adi)
    if key not in stok_eslesme_tablosu:
        stok_eslesme_tablosu[key] = f"STK-{stok_sayaci:03}"
        stok_sayaci += 1
    return stok_eslesme_tablosu[key]

def get_unique_fatura_no():
    while True:
        fno = f"FT-{random.randint(100000, 999999)}"
        if fno not in fatura_set:
            fatura_set.add(fno)
            return fno

def get_sektor_from_cari(cari_tam_ad):
    sektor = "OFIS"
    for anahtar in urun_gruplari.keys():
        if anahtar in cari_tam_ad.upper():
            sektor = anahtar
            break
    return sektor

def get_yearly_price(key, tarih_obj):
    yil = tarih_obj.year
    yil_key = (key, yil)
    if key not in fiyat_hafizasi:
        fiyat_hafizasi[key] = round(random.uniform(50, 1000), 2)
    
    base_fiyat = fiyat_hafizasi[key]
    if yil_key not in yillik_fiyat_hafizasi:
        yil_farki = yil - 2017
        enflasyon_katsayi = 1.18 ** yil_farki 
        fiyat = round(base_fiyat * enflasyon_katsayi, 2)
        yillik_fiyat_hafizasi[yil_key] = fiyat
    return yillik_fiyat_hafizasi[yil_key]

# ====== BAŞLANGIÇ TARİHLERİ VE KOMBİNASYONLAR ======
kombinasyon_listesi = []
for cari_k, cari_tam_ad in cari_list:
    cari_ad_hafizasi[cari_k] = cari_tam_ad
    sektor = get_sektor_from_cari(cari_tam_ad)
    for urun in urun_gruplari[sektor]:
        key = (cari_k, urun)
        kombinasyon_listesi.append(key)
        # Başlangıç tarihini geçmişe yayıyoruz (2017-2022 arası başlasınlar)
        alis_tarih_hafizasi[key] = datetime(random.randint(2017, 2022), random.randint(1, 12), random.randint(1, 28))

# ====== VERİ ÜRETİMİ (TAM 6128 KAYIT) ======
kayitlar = []

while len(kayitlar) < hedef_kayit_sayisi:
    # Rastgele bir cari-ürün çifti seç
    key = random.choice(kombinasyon_listesi)
    cari_k, urun = key
    tarih_obj = alis_tarih_hafizasi[key]
    
    stok_k = get_unique_stok_kod(cari_k, urun)
    fatura_n = get_unique_fatura_no()
    
    if key not in sabit_miktar_hafizasi:
        sabit_miktar_hafizasi[key] = random.randint(1, 50)
    
    if key not in kdv_hafizasi:
        kdv_hafizasi[key] = random.choice([1, 8, 10, 18, 20])

    miktar = sabit_miktar_hafizasi[key]
    kdv = kdv_hafizasi[key]
    fiyat = get_yearly_price(key, tarih_obj)
    tarih_str = tarih_obj.strftime("%Y-%m-%d")

    kayitlar.append((fatura_n, cari_k, cari_ad_hafizasi[cari_k], stok_k, urun, tarih_str, miktar, fiyat, kdv))

    # --- AYNI GÜNÜ BOZAN VE SÜREKLİ İLERLEYEN TARİH ---
    # Her işlemden sonra bu ürünün bir sonraki alış tarihini 15-40 gün sonraya atıyoruz
    alis_tarih_hafizasi[key] = tarih_obj + timedelta(days=random.randint(15, 40))

# Verileri karıştır (tarih sırasını bozmak için)
random.shuffle(kayitlar)

# ====== SQL YAZ ======
with open(output_file, "w", encoding="utf-8") as f:
    for r in kayitlar:
        sql = (
            f"INSERT INTO dbo.FaturaDetay (fatura_no, cari_kod, cari_ad, stok_kod, urun_adi, urun_tarihi, "
            f"fiili_tarih, miktar, birim_fiyat, kdv_orani) VALUES "
            f"('{r[0]}', '{r[1]}', '{r[2]}', '{r[3]}', '{r[4]}', '{r[5]}', '{r[5]}', {r[6]}, {r[7]}, {r[8]});\n"
        )
        f.write(sql)

print(f"İşlem tamam, tam olarak {len(kayitlar)} kayıt üretildi.")