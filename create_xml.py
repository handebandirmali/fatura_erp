import pyodbc
import lxml.etree as ET
import uuid
from datetime import datetime
from decimal import Decimal

# 1. Veritabanı Bağlantı Bilgileri
conn = pyodbc.connect(
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=.;"
    "DATABASE=FaturaDB;",
    "Trusted_Connection=yes;"
)
cursor = conn.cursor()


def _to_float(v, default=0.0):
    """
    pyodbc bazen Decimal döndürür, bazen None döndürür.
    Güvenli float çevirme.
    """
    if v is None:
        return float(default)
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(v)
    except Exception:
        return float(default)


def database_xml_guncelle():
    try:
        # 2. Verileri Çek
        query = """
        SELECT
            fatura_no,
            stok_kod,
            cari_ad,
            urun_adi,
            urun_tarihi,
            miktar,
            birim_fiyat,
            kdv_orani,
            Toplam
        FROM [FaturaDB].[dbo].[FaturaDetay]
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        # UBL-TR Standart Namespaces
        ns = {
            None: "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
            "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
            "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        }

        CBC = ns["cbc"]
        CAC = ns["cac"]

        print(f"{len(rows)} adet satır işleniyor...")

        for row in rows:
            # --- 🧮 MALİ HESAPLAMALAR ---
            f_no = row.fatura_no
            s_kod = row.stok_kod

            miktar = _to_float(row.miktar, 0)
            fiyat = _to_float(row.birim_fiyat, 0)
            kdv_oran = _to_float(row.kdv_orani, 20)

            # Hesaplamalar
            kdv_haric_toplam = round(miktar * fiyat, 2)
            kdv_tutari = round(kdv_haric_toplam * kdv_oran / 100, 2)
            kdv_dahil_toplam = round(kdv_haric_toplam + kdv_tutari, 2)

            urun_tarihi = row.urun_tarihi
            tarih_str = (
                urun_tarihi.strftime("%Y-%m-%d")
                if urun_tarihi
                else datetime.now().strftime("%Y-%m-%d")
            )

            cari_ad = row.cari_ad if row.cari_ad is not None else ""
            urun_adi = row.urun_adi if row.urun_adi is not None else ""

            # --- 🧾 XML OLUŞTURMA ---
            invoice = ET.Element("Invoice", nsmap=ns)

            ET.SubElement(invoice, f"{{{CBC}}}ID").text = str(f_no)
            ET.SubElement(invoice, f"{{{CBC}}}UUID").text = str(uuid.uuid4())
            ET.SubElement(invoice, f"{{{CBC}}}IssueDate").text = tarih_str

            ET.SubElement(invoice, f"{{{CBC}}}InvoiceTypeCode").text = "SATIS"
            ET.SubElement(invoice, f"{{{CBC}}}DocumentCurrencyCode").text = "TRY"

            cust_party = ET.SubElement(invoice, f"{{{CAC}}}AccountingCustomerParty")
            party = ET.SubElement(cust_party, f"{{{CAC}}}Party")
            p_name = ET.SubElement(party, f"{{{CAC}}}PartyName")
            ET.SubElement(p_name, f"{{{CBC}}}Name").text = str(cari_ad)

            tax_total = ET.SubElement(invoice, f"{{{CAC}}}TaxTotal")
            ET.SubElement(tax_total, f"{{{CBC}}}TaxAmount", currencyID="TRY").text = str(kdv_tutari)

            tax_subtotal = ET.SubElement(tax_total, f"{{{CAC}}}TaxSubtotal")
            ET.SubElement(tax_subtotal, f"{{{CBC}}}TaxableAmount", currencyID="TRY").text = str(kdv_haric_toplam)
            ET.SubElement(tax_subtotal, f"{{{CBC}}}TaxAmount", currencyID="TRY").text = str(kdv_tutari)
            ET.SubElement(tax_subtotal, f"{{{CBC}}}Percent").text = str(kdv_oran)

            tax_category = ET.SubElement(tax_subtotal, f"{{{CAC}}}TaxCategory")
            tax_scheme = ET.SubElement(tax_category, f"{{{CAC}}}TaxScheme")
            ET.SubElement(tax_scheme, f"{{{CBC}}}Name").text = "KDV"

            legal_total = ET.SubElement(invoice, f"{{{CAC}}}LegalMonetaryTotal")
            ET.SubElement(legal_total, f"{{{CBC}}}LineExtensionAmount", currencyID="TRY").text = str(kdv_haric_toplam)
            ET.SubElement(legal_total, f"{{{CBC}}}TaxExclusiveAmount", currencyID="TRY").text = str(kdv_haric_toplam)
            ET.SubElement(legal_total, f"{{{CBC}}}TaxInclusiveAmount", currencyID="TRY").text = str(kdv_dahil_toplam)
            ET.SubElement(legal_total, f"{{{CBC}}}PayableAmount", currencyID="TRY").text = str(kdv_dahil_toplam)

            line = ET.SubElement(invoice, f"{{{CAC}}}InvoiceLine")
            ET.SubElement(line, f"{{{CBC}}}ID").text = "1"

            qty = ET.SubElement(line, f"{{{CBC}}}InvoicedQuantity", unitCode="C62")
            qty.text = str(miktar)

            ET.SubElement(line, f"{{{CBC}}}LineExtensionAmount", currencyID="TRY").text = str(kdv_haric_toplam)

            tax_total_line = ET.SubElement(line, f"{{{CAC}}}TaxTotal")
            ET.SubElement(tax_total_line, f"{{{CBC}}}TaxAmount", currencyID="TRY").text = str(kdv_tutari)

            tax_sub = ET.SubElement(tax_total_line, f"{{{CAC}}}TaxSubtotal")
            ET.SubElement(tax_sub, f"{{{CBC}}}TaxableAmount", currencyID="TRY").text = str(kdv_haric_toplam)
            ET.SubElement(tax_sub, f"{{{CBC}}}TaxAmount", currencyID="TRY").text = str(kdv_tutari)
            ET.SubElement(tax_sub, f"{{{CBC}}}Percent").text = str(kdv_oran)

            tax_category_line = ET.SubElement(tax_sub, f"{{{CAC}}}TaxCategory")
            tax_scheme_line = ET.SubElement(tax_category_line, f"{{{CAC}}}TaxScheme")
            ET.SubElement(tax_scheme_line, f"{{{CBC}}}Name").text = "KDV"

            item = ET.SubElement(line, f"{{{CAC}}}Item")
            ET.SubElement(item, f"{{{CBC}}}Name").text = str(urun_adi)

            price = ET.SubElement(line, f"{{{CAC}}}Price")
            ET.SubElement(price, f"{{{CBC}}}PriceAmount", currencyID="TRY").text = str(fiyat)

            xml_string = ET.tostring(invoice, pretty_print=True, encoding="unicode")

            # 4. DB Güncelleme (Toplam da eklendi)
            update_query = """
            UPDATE [FaturaDB].[dbo].[FaturaDetay]
            SET [xml_ubl] = ?, [Toplam] = ?
            WHERE [fatura_no] = ? AND [stok_kod] = ?
            """
            cursor.execute(update_query, (xml_string, kdv_dahil_toplam, f_no, s_kod))

        conn.commit()
        print("İşlem tamamlandı. KDV ve Toplamlar eklendi.")

    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print(f"Hata oluştu: {e}")

    finally:
        try:
            cursor.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


database_xml_guncelle()
