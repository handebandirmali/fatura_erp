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


def update_invoice_xml(xml_string, updates):
    root = ET.fromstring(xml_string.encode("utf-8"))
    invoice_lines = root.findall(".//cac:InvoiceLine", namespaces=NS)

    if len(invoice_lines) != len(updates):
        raise ValueError("XML satır sayısı ile update satır sayısı uyuşmuyor.")

    cari_kod = updates[0][0]
    cari_ad = updates[0][1]
    fatura_no = updates[0][7]
    tarih = updates[0][6]

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
        miktar = float(u[3])
        birim_fiyat = float(u[4])
        kdv_orani = float(u[5])

        stok_kod = ""
        if len(u) > 8:
            stok_kod = u[8]

        ara_toplam = miktar * birim_fiyat
        kdv_tutar = ara_toplam * kdv_orani / 100

        toplam_net += ara_toplam
        toplam_kdv += kdv_tutar

        _find_or_create(line, "cac:Item/cbc:Name").text = str(urun_adi)
        _find_or_create(line, "cbc:InvoicedQuantity").text = str(miktar)
        _find_or_create(line, "cac:Price/cbc:PriceAmount").text = str(round(birim_fiyat, 2))
        _find_or_create(line, "cbc:LineExtensionAmount").text = str(round(ara_toplam, 2))
        _find_or_create(line, "cac:TaxTotal/cbc:TaxAmount").text = str(round(kdv_tutar, 2))
        _find_or_create(line, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxableAmount").text = str(round(ara_toplam, 2))
        _find_or_create(line, "cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount").text = str(round(kdv_tutar, 2))
        _find_or_create(line, "cac:TaxTotal/cac:TaxSubtotal/cbc:Percent").text = str(round(kdv_orani, 2))

        if stok_kod:
            _find_or_create(
                line,
                "cac:Item/cac:SellersItemIdentification/cbc:ID"
            ).text = str(stok_kod)

    _find_or_create(root, "cac:TaxTotal/cbc:TaxAmount").text = str(round(toplam_kdv, 2))
    _find_or_create(root, "cac:LegalMonetaryTotal/cbc:LineExtensionAmount").text = str(round(toplam_net, 2))
    _find_or_create(root, "cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount").text = str(round(toplam_net, 2))
    _find_or_create(root, "cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount").text = str(round(toplam_net + toplam_kdv, 2))
    _find_or_create(root, "cac:LegalMonetaryTotal/cbc:PayableAmount").text = str(round(toplam_net + toplam_kdv, 2))

    return ET.tostring(root, encoding="utf-8").decode("utf-8")