import re
import xml.etree.ElementTree as ET


NS = {
    "inv": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
    "ds": "http://www.w3.org/2000/09/xmldsig#",
    "xades": "http://uri.etsi.org/01903/v1.3.2#",
}


def _safe_text(node, default=""):
    if node is not None and node.text is not None:
        return node.text.strip()
    return default


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        value = str(value).strip().replace(",", ".")
        if value == "":
            return default
        return float(value)
    except Exception:
        return default


def _extract_cari_kod_from_notes(root):
    note_nodes = root.findall("cbc:Note", NS)

    for note in note_nodes:
        text = _safe_text(note)
        if not text:
            continue

        match = re.search(r"CAR[İI]\s*KODU\s*:\s*([^\n\r#]+)", text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return ""


def _extract_customer_identifiers(root):
    ids = []

    nodes = root.findall(
        "cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID",
        NS
    )

    for node in nodes:
        value = _safe_text(node)
        scheme = node.attrib.get("schemeID", "").strip() if node is not None else ""
        if value:
            ids.append({
                "schemeID": scheme,
                "value": value
            })

    return ids


def parse_invoice_xml(xml_text: str) -> dict:
    if not xml_text or not str(xml_text).strip():
        return {
            "fatura_no": "",
            "uuid": "",
            "tarih": "",
            "fatura_tipi": "",
            "para_birimi": "TRY",
            "cari_kod": "",
            "firma_adi": "",
            "ara_toplam": 0.0,
            "vergi_haric_toplam": 0.0,
            "vergi_dahil_toplam": 0.0,
            "kdv_toplam": 0.0,
            "genel_toplam": 0.0,
            "customer_identifiers": [],
            "kalemler": []
        }

    root = ET.fromstring(str(xml_text).strip())

    fatura_no = _safe_text(root.find("cbc:ID", NS))
    uuid = _safe_text(root.find("cbc:UUID", NS))
    tarih = _safe_text(root.find("cbc:IssueDate", NS))
    fatura_tipi = _safe_text(root.find("cbc:InvoiceTypeCode", NS))
    para_birimi = _safe_text(root.find("cbc:DocumentCurrencyCode", NS), "TRY")

    firma_adi = _safe_text(
        root.find(
            "cac:AccountingCustomerParty/cac:Party/cac:PartyName/cbc:Name",
            NS
        )
    )

    customer_identifiers = _extract_customer_identifiers(root)

    cari_kod = ""
    if customer_identifiers:
        cari_kod = customer_identifiers[0]["value"]

    note_cari_kod = _extract_cari_kod_from_notes(root)
    if note_cari_kod:
        cari_kod = note_cari_kod

    ara_toplam = _safe_float(
        _safe_text(root.find("cac:LegalMonetaryTotal/cbc:LineExtensionAmount", NS), "0")
    )

    vergi_haric_toplam = _safe_float(
        _safe_text(root.find("cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount", NS), "0")
    )

    vergi_dahil_toplam = _safe_float(
        _safe_text(root.find("cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount", NS), "0")
    )

    genel_toplam = _safe_float(
        _safe_text(root.find("cac:LegalMonetaryTotal/cbc:PayableAmount", NS), "0")
    )

    kdv_toplam = _safe_float(
        _safe_text(root.find("cac:TaxTotal/cbc:TaxAmount", NS), "0")
    )

    kalemler = []

    for line in root.findall("cac:InvoiceLine", NS):
        urun_adi = _safe_text(line.find("cac:Item/cbc:Name", NS))

        stok_kod = _safe_text(
            line.find("cac:Item/cac:SellersItemIdentification/cbc:ID", NS)
        )

        miktar = _safe_float(
            _safe_text(line.find("cbc:InvoicedQuantity", NS), "0")
        )

        birim_fiyat = _safe_float(
            _safe_text(line.find("cac:Price/cbc:PriceAmount", NS), "0")
        )

        kdv_orani = _safe_float(
            _safe_text(line.find("cac:TaxTotal/cac:TaxSubtotal/cbc:Percent", NS), "0")
        )

        satir_toplam = _safe_float(
            _safe_text(line.find("cbc:LineExtensionAmount", NS), "0")
        )

        if satir_toplam == 0 and miktar and birim_fiyat:
            satir_toplam = round(miktar * birim_fiyat, 2)

        kalemler.append({
            "stok_kod": stok_kod,
            "urun_adi": urun_adi,
            "miktar": miktar,
            "birim_fiyat": birim_fiyat,
            "kdv_orani": kdv_orani,
            "satir_toplam": satir_toplam
        })

    if genel_toplam == 0:
        if vergi_dahil_toplam > 0:
            genel_toplam = vergi_dahil_toplam
        else:
            genel_toplam = round(ara_toplam + kdv_toplam, 2)

    return {
        "fatura_no": fatura_no,
        "uuid": uuid,
        "tarih": tarih,
        "fatura_tipi": fatura_tipi,
        "para_birimi": para_birimi,
        "cari_kod": cari_kod,
        "firma_adi": firma_adi,
        "ara_toplam": ara_toplam,
        "vergi_haric_toplam": vergi_haric_toplam,
        "vergi_dahil_toplam": vergi_dahil_toplam,
        "kdv_toplam": kdv_toplam,
        "genel_toplam": genel_toplam,
        "customer_identifiers": customer_identifiers,
        "kalemler": kalemler
    }