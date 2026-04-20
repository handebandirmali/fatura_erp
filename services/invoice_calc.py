import lxml.etree as ET


NS = {
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
}


def _qname(tag: str):
    prefix, local = tag.split(":")
    return f"{{{NS[prefix]}}}{local}"


def _find_or_create(root, path):
    parts = path.split("/")
    current = root

    for part in parts:
        found = current.find(part, NS)
        if found is None:
            found = ET.SubElement(current, _qname(part))
        current = found

    return current


def safe_float(value, default=0.0) -> float:
    try:
        if value is None:
            return float(default)
        text = str(value).strip().replace(",", ".")
        if text == "":
            return float(default)
        return float(text)
    except Exception:
        return float(default)


def calculate_line_totals(miktar, birim_fiyat, kdv_orani) -> dict:
    miktar = safe_float(miktar, 0)
    birim_fiyat = safe_float(birim_fiyat, 0)
    kdv_orani = safe_float(kdv_orani, 0)

    ara_toplam = round(miktar * birim_fiyat, 2)
    kdv_tutar = round(ara_toplam * kdv_orani / 100.0, 2)
    satir_toplam = round(ara_toplam + kdv_tutar, 2)

    return {
        "miktar": miktar,
        "birim_fiyat": birim_fiyat,
        "kdv_orani": kdv_orani,
        "ara_toplam": ara_toplam,
        "kdv_tutar": kdv_tutar,
        "satir_toplam": satir_toplam,
    }


def normalize_invoice_lines(kalemler: list) -> list:
    normalized = []

    for idx, kalem in enumerate(kalemler or [], start=1):
        hesap = calculate_line_totals(
            kalem.get("miktar", 0),
            kalem.get("birim_fiyat", 0),
            kalem.get("kdv_orani", 0),
        )

        normalized.append({
            "stok_kod": str(kalem.get("stok_kod", f"STK-{idx}") or f"STK-{idx}").strip(),
            "urun_adi": str(kalem.get("urun_adi", "") or "").strip(),
            "miktar": hesap["miktar"],
            "birim_fiyat": hesap["birim_fiyat"],
            "kdv_orani": hesap["kdv_orani"],
            "ara_toplam": hesap["ara_toplam"],
            "kdv_tutar": hesap["kdv_tutar"],
            "satir_toplam": hesap["satir_toplam"],
        })

    return normalized


def calculate_invoice_totals(kalemler: list) -> dict:
    normalized_lines = normalize_invoice_lines(kalemler)

    ara_toplam = round(sum(line["ara_toplam"] for line in normalized_lines), 2)
    kdv_toplam = round(sum(line["kdv_tutar"] for line in normalized_lines), 2)
    genel_toplam = round(ara_toplam + kdv_toplam, 2)

    return {
        "kalemler": normalized_lines,
        "ara_toplam": ara_toplam,
        "vergi_haric_toplam": ara_toplam,
        "kdv_toplam": kdv_toplam,
        "vergi_dahil_toplam": genel_toplam,
        "genel_toplam": genel_toplam,
    }


def update_invoice_xml(xml_string, updates):
    root = ET.fromstring(xml_string.encode("utf-8"))
    invoice_lines = root.findall(".//cac:InvoiceLine", namespaces=NS)

    if len(invoice_lines) != len(updates):
        raise ValueError("XML satır sayısı ile update satır sayısı uyuşmuyor.")

    cari_kod = updates[0][0]
    cari_ad = updates[0][1]
    tarih = updates[0][6]
    fatura_no = updates[0][7]

    _find_or_create(root, "cbc:ID").text = str(fatura_no)
    _find_or_create(root, "cbc:IssueDate").text = str(tarih)

    _find_or_create(
        root,
        "cac:AccountingCustomerParty/cac:Party/cac:PartyName/cbc:Name"
    ).text = str(cari_ad)

    _find_or_create(
        root,
        "cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID"
    ).text = str(cari_kod)

    toplam_net = 0.0
    toplam_kdv = 0.0

    for line, u in zip(invoice_lines, updates):
        urun_adi = u[2]
        stok_kod = u[8] if len(u) > 8 else ""

        hesap = calculate_line_totals(u[3], u[4], u[5])
        toplam_net += hesap["ara_toplam"]
        toplam_kdv += hesap["kdv_tutar"]

        _find_or_create(line, "cac:Item/cbc:Name").text = str(urun_adi)
        _find_or_create(line, "cbc:InvoicedQuantity").text = str(hesap["miktar"])
        _find_or_create(line, "cac:Price/cbc:PriceAmount").text = f"{hesap['birim_fiyat']:.2f}"
        _find_or_create(line, "cbc:LineExtensionAmount").text = f"{hesap['ara_toplam']:.2f}"
        _find_or_create(line, "cac:TaxTotal/cbc:TaxAmount").text = f"{hesap['kdv_tutar']:.2f}"
        _find_or_create(line, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount").text = f"{hesap['ara_toplam']:.2f}"
        _find_or_create(line, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount").text = f"{hesap['kdv_tutar']:.2f}"
        _find_or_create(line, "cac:TaxTotal/cac:TaxSubtotal/cbc:Percent").text = f"{hesap['kdv_orani']:.2f}"

        if stok_kod:
            _find_or_create(
                line,
                "cac:Item/cac:SellersItemIdentification/cbc:ID"
            ).text = str(stok_kod)

    genel_toplam = round(toplam_net + toplam_kdv, 2)

    _find_or_create(root, "cac:TaxTotal/cbc:TaxAmount").text = f"{toplam_kdv:.2f}"
    _find_or_create(root, "cac:LegalMonetaryTotal/cbc:LineExtensionAmount").text = f"{toplam_net:.2f}"
    _find_or_create(root, "cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount").text = f"{toplam_net:.2f}"
    _find_or_create(root, "cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount").text = f"{genel_toplam:.2f}"
    _find_or_create(root, "cac:LegalMonetaryTotal/cbc:PayableAmount").text = f"{genel_toplam:.2f}"

    return ET.tostring(root, encoding="utf-8").decode("utf-8")
