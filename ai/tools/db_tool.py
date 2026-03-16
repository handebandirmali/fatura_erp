import pyodbc
import time
import random
import string
from datetime import datetime
from xml.sax.saxutils import escape


def generate_random_code(prefix, length=4):
    timestamp = int(time.time())
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
    return f"{prefix}-{timestamp}-{suffix}"


def get_connection():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=.;"
        "DATABASE=FaturaDB;"
        "Trusted_Connection=yes;"
    )


def generate_ubl_xml_content(analysis_data, duzgun_tarih):
    f_no = analysis_data.get("fatura_no") or "AI-TEMP-001"
    cari_kod = analysis_data.get("cari_kod") or "CARI-001"
    firma = analysis_data.get("firma_adi", "Bilinmeyen Firma")
    kalemler = analysis_data.get("kalemler", [])

    ara_toplam = 0.0
    toplam_kdv = 0.0

    xml_lines = [
        '<?xml version="1.0"?>',
        '<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"',
        '         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"',
        '         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">',
        f'    <cbc:ID>{escape(str(f_no))}</cbc:ID>',
        f'    <cbc:UUID>{escape(generate_random_code("UUID", 8))}</cbc:UUID>',
        f'    <cbc:IssueDate>{escape(str(duzgun_tarih))}</cbc:IssueDate>',
        '    <cbc:InvoiceTypeCode>SATIS</cbc:InvoiceTypeCode>',
        '    <cbc:DocumentCurrencyCode>TRY</cbc:DocumentCurrencyCode>',

        '    <cac:AccountingSupplierParty><cac:Party>',
        f'        <cac:PartyName><cbc:Name>{escape(str(firma))}</cbc:Name></cac:PartyName>',
        '    </cac:Party></cac:AccountingSupplierParty>',

        '    <cac:AccountingCustomerParty><cac:Party>',
        f'        <cac:PartyIdentification><cbc:ID>{escape(str(cari_kod))}</cbc:ID></cac:PartyIdentification>',
        '        <cac:PartyName>',
        f'            <cbc:Name>{escape(str(firma))}</cbc:Name>',
        '        </cac:PartyName>',
        f'        <cac:Contact><cbc:Name>{escape(str(cari_kod))}</cbc:Name></cac:Contact>',
        '    </cac:Party></cac:AccountingCustomerParty>'
    ]

    for i, kalem in enumerate(kalemler):
        urun = kalem.get("urun_adi", "İsimsiz Ürün")
        stok_kod = kalem.get("stok_kod", f"STK-{i+1}")

        try:
            miktar = float(str(kalem.get("miktar", 0)).replace(",", "."))
            fiyat = float(str(kalem.get("birim_fiyat", 0)).replace(",", "."))
            kdv_orani = float(str(kalem.get("kdv_orani", 20)).replace(",", "."))
        except Exception:
            miktar, fiyat, kdv_orani = 0.0, 0.0, 20.0

        satir_ara_toplam = miktar * fiyat
        satir_kdv_tutari = satir_ara_toplam * (kdv_orani / 100)

        ara_toplam += satir_ara_toplam
        toplam_kdv += satir_kdv_tutari

        xml_lines.append('    <cac:InvoiceLine>')
        xml_lines.append(f'        <cbc:ID>{i+1}</cbc:ID>')
        xml_lines.append(f'        <cbc:InvoicedQuantity unitCode="C62">{miktar}</cbc:InvoicedQuantity>')
        xml_lines.append(f'        <cbc:LineExtensionAmount currencyID="TRY">{satir_ara_toplam:.2f}</cbc:LineExtensionAmount>')

        xml_lines.append('        <cac:TaxTotal>')
        xml_lines.append(f'            <cbc:TaxAmount currencyID="TRY">{satir_kdv_tutari:.2f}</cbc:TaxAmount>')
        xml_lines.append('            <cac:TaxSubtotal>')
        xml_lines.append(f'                <cbc:TaxableAmount currencyID="TRY">{satir_ara_toplam:.2f}</cbc:TaxableAmount>')
        xml_lines.append(f'                <cbc:TaxAmount currencyID="TRY">{satir_kdv_tutari:.2f}</cbc:TaxAmount>')
        xml_lines.append(f'                <cbc:Percent>{kdv_orani}</cbc:Percent>')
        xml_lines.append('                <cac:TaxCategory><cac:TaxScheme><cbc:Name>KDV</cbc:Name></cac:TaxScheme></cac:TaxCategory>')
        xml_lines.append('            </cac:TaxSubtotal>')
        xml_lines.append('        </cac:TaxTotal>')

        xml_lines.append('        <cac:Item>')
        xml_lines.append(f'            <cbc:Name>{escape(str(urun))}</cbc:Name>')
        xml_lines.append(f'            <cac:SellersItemIdentification><cbc:ID>{escape(str(stok_kod))}</cbc:ID></cac:SellersItemIdentification>')
        xml_lines.append('        </cac:Item>')
        xml_lines.append(f'        <cac:Price><cbc:PriceAmount currencyID="TRY">{fiyat:.2f}</cbc:PriceAmount></cac:Price>')
        xml_lines.append('    </cac:InvoiceLine>')

    genel_toplam = ara_toplam + toplam_kdv

    xml_lines.append('    <cac:TaxTotal>')
    xml_lines.append(f'        <cbc:TaxAmount currencyID="TRY">{toplam_kdv:.2f}</cbc:TaxAmount>')
    xml_lines.append('    </cac:TaxTotal>')

    xml_lines.append('    <cac:LegalMonetaryTotal>')
    xml_lines.append(f'        <cbc:LineExtensionAmount currencyID="TRY">{ara_toplam:.2f}</cbc:LineExtensionAmount>')
    xml_lines.append(f'        <cbc:TaxExclusiveAmount currencyID="TRY">{ara_toplam:.2f}</cbc:TaxExclusiveAmount>')
    xml_lines.append(f'        <cbc:TaxInclusiveAmount currencyID="TRY">{genel_toplam:.2f}</cbc:TaxInclusiveAmount>')
    xml_lines.append(f'        <cbc:PayableAmount currencyID="TRY">{genel_toplam:.2f}</cbc:PayableAmount>')
    xml_lines.append('    </cac:LegalMonetaryTotal>')

    xml_lines.append('</Invoice>')
    return "\n".join(xml_lines)


def save_invoice_to_db(analysis_data):
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        kalemler = analysis_data.get("kalemler", [])
        if not kalemler:
            class Result:
                success = False
                error = "Kalem listesi boş."
            return Result()

        f_no = analysis_data.get("fatura_no") or "AI-TEMP-001"
        c_kod = analysis_data.get("cari_kod") or "CARI-001"
        firma = str(analysis_data.get("firma_adi", "Bilinmeyen"))
        ham_tarih = str(analysis_data.get("tarih", "2026-01-01")).strip()

        try:
            temiz_tarih = ham_tarih.replace("-", ".").replace("/", ".")
            tarih_objesi = datetime.strptime(temiz_tarih, "%d.%m.%Y")
            duzgun_tarih = tarih_objesi.strftime("%Y-%m-%d")
        except Exception:
            try:
                tarih_objesi = datetime.strptime(ham_tarih, "%Y-%m-%d")
                duzgun_tarih = tarih_objesi.strftime("%Y-%m-%d")
            except Exception:
                duzgun_tarih = datetime.now().strftime("%Y-%m-%d")

        generated_xml_ubl = generate_ubl_xml_content(analysis_data, duzgun_tarih)

        for kalem in kalemler:
            miktar = float(str(kalem.get("miktar", 0)).replace(",", "."))
            fiyat = float(str(kalem.get("birim_fiyat", 0)).replace(",", "."))
            kdv = float(str(kalem.get("kdv_orani", 20)).replace(",", "."))
            stok_kod = kalem.get("stok_kod", "STOK-001")
            urun_adi = str(kalem.get("urun_adi", "İsimsiz Ürün"))
            satir_toplam = miktar * fiyat

            params = (
                f_no[:20],
                c_kod[:20],
                firma[:100],
                stok_kod[:20],
                urun_adi[:150],
                duzgun_tarih,
                miktar,
                fiyat,
                kdv,
                satir_toplam,
                generated_xml_ubl
            )

            cursor.execute("""
                INSERT INTO FaturaDetay (
                    fatura_no, cari_kod, cari_ad, stok_kod, urun_adi,
                    urun_tarihi, miktar, birim_fiyat, kdv_orani, Toplam, xml_ubl
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, params)

        conn.commit()

        class Result:
            success = True

        return Result()

    except Exception as e:
        if conn:
            conn.rollback()

        class Result:
            success = False
            error = str(e)

        return Result()

    finally:
        if conn:
            conn.close()