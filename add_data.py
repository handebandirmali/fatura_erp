import random
from datetime import datetime, timedelta
import os

# ====== CARİ LİST ======
cari_list = [
    ("C008", "C TİCARET"),
    ("C009", "F KIRTASİYE"),
    ("C010", "I OFİS MALZ."),
    ("C011", "KL KIRTASİYE"),
    ("C012", "MO OFİS"),
    ("C013", "P TEMİZLİK"),
    ("C014", "U GIDA")
]

# ====== ÜRÜN GRUPLARI ======
temizlik_urunleri = [
    "Çamaşır Deterjanı", "Bulaşık Deterjanı", "Yüzey Temizleyici", 
    "Mikrofiber Bez", "Sıvı Sabun", "Banyo Köpüğü", "Tuvalet Temizleyici", 
    "Cam Sileceği", "Halı Şampuanı", "Dezenfektan Sprey", "Bulaşık Süngeri", 
    "Çöp Torbası", "Klozet Fırçası", "Toz Bezi", "Oda Kokusu"
]

yemek_urunleri = [
    "Makarna", "Pirinç", "Zeytinyağı", "Konserve Ton Balığı", "Çay", "Kahve",
    "Un", "Şeker", "Tuz", "Sıvı Yağ", "Biber Salçası", "Domates Konservesi", 
    "Mısır Konservesi", "Süt", "Yoğurt", "Peynir", "Yumurta", "Reçel", 
    "Bisküvi", "Kraker"
]

ofis_urunleri = [
    "Laptop", "Mouse", "Keyboard", "Monitor", "USB Flash", "Harici HDD", 
    "Yazıcı", "Tarayıcı", "Webcam", "Ofis Telefonu", "Projector", "Kırtasiye Seti",
    "Defter", "Kalem", "Marker", "Zımba", "Delgeç", "Dosya Klasörü", "Ajanda", "Mouse Pad"
]

# ====== RANDOM TARİH ======
def random_date(start_year=2025, end_year=2026):
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    delta = end - start
    random_days = random.randint(0, delta.days)
    return (start + timedelta(days=random_days)).strftime("%Y-%m-%d")

# ====== SQL OLUŞTUR VE KAYDET ======
temizlik_count = 1
yemek_count = 1
ofis_count = 1

output_file = "fatura_insert_queries.txt"
fatura_set = set()  # benzersiz fatura no kontrolü

with open(output_file, "w", encoding="utf-8") as f:
    for i in range(5000):  # 5000 satır
        # ====== RANDOM FATURA NO ======
        while True:
            fatura_no = f"FT-{random.randint(100000, 999999)}"
            if fatura_no not in fatura_set:
                fatura_set.add(fatura_no)
                break

        cari = random.choice(cari_list)
        cari_ad = cari[1]

        # Cari türüne göre ürün seçimi ve stok kodu
        if "TEMİZLİK" in cari_ad.upper():
            urun_adi = random.choice(temizlik_urunleri)
            stok_kod = f"TMP-{temizlik_count:03}"
            temizlik_count += 1
        elif "GIDA" in cari_ad.upper() or "YEMEK" in cari_ad.upper():
            urun_adi = random.choice(yemek_urunleri)
            stok_kod = f"YEM-{yemek_count:03}"
            yemek_count += 1
        else:
            urun_adi = random.choice(ofis_urunleri)
            stok_kod = f"OFIS-{ofis_count:03}"
            ofis_count += 1

        urun_tarihi = random_date()
        fiili_tarih = random_date()
        miktar = random.randint(1, 100)
        birim_fiyat = round(random.uniform(10, 2000), 2)
        kdv = random.choice([8, 18, 20])

        sql = f"""INSERT INTO dbo.FaturaDetay 
(fatura_no, cari_kod, cari_ad, stok_kod, urun_adi, urun_tarihi, fiili_tarih, miktar, birim_fiyat, kdv_orani) 
VALUES 
('{fatura_no}', '{cari[0]}', '{cari_ad}', '{stok_kod}', '{urun_adi}', '{urun_tarihi}', '{fiili_tarih}', {miktar}, {birim_fiyat}, {kdv});\n"""
        
        f.write(sql)

print(f"✅ 5000 SQL insert sorgusu '{os.path.abspath(output_file)}' dosyasına kaydedildi.")
