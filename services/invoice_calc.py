import lxml.etree as ET

def update_invoice_xml(xml_string, updates):

    ns = {
        "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    }

    root = ET.fromstring(xml_string.encode("utf-8"))
    invoice_lines = root.findall(".//cac:InvoiceLine", namespaces=ns)

    if len(invoice_lines) != len(updates):
        raise ValueError("XML satır sayısı ile update satır sayısı uyuşmuyor.")

    # ============ HEADER UPDATE ============
    cari_kod = updates[0][0]
    cari_ad = updates[0][1]
    fatura_no = updates[0][7]
    tarih = updates[0][6]

    node = root.find(".//cbc:ID", ns)
    if node is not None:
        node.text = str(fatura_no)

    node = root.find(".//cbc:IssueDate", ns)
    if node is not None:
        node.text = str(tarih)

    node = root.find(".//cac:AccountingCustomerParty/cac:Party/cac:PartyName/cbc:Name", ns)
    if node is not None:
        node.text = str(cari_ad)

    node = root.find(".//cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID", ns)
    if node is not None:
        node.text = str(cari_kod)

    # ============ LINE UPDATE ============
    toplam_net = 0
    toplam_kdv = 0

    for line, u in zip(invoice_lines, updates):

        urun_adi = u[2]
        miktar = float(u[3])
        birim_fiyat = float(u[4])
        kdv_orani = float(u[5])

        ara_toplam = miktar * birim_fiyat
        kdv_tutar = ara_toplam * kdv_orani / 100

        toplam_net += ara_toplam
        toplam_kdv += kdv_tutar

        line.find("cac:Item/cbc:Name", ns).text = str(urun_adi)
        line.find("cbc:InvoicedQuantity", ns).text = str(miktar)
        line.find("cac:Price/cbc:PriceAmount", ns).text = str(round(birim_fiyat, 2))
        line.find("cbc:LineExtensionAmount", ns).text = str(round(ara_toplam, 2))
        line.find("cac:TaxTotal/cac:TaxSubtotal/cbc:Percent", ns).text = str(round(kdv_orani, 2))
        line.find("cac:TaxTotal/cbc:TaxAmount", ns).text = str(round(kdv_tutar, 2))
        line.find("cac:TaxTotal/cac:TaxSubtotal/cbc:TaxAmount", ns).text = str(round(kdv_tutar, 2))

    # ============ HEADER TOTAL UPDATE ============
    root.find(".//cac:TaxTotal/cbc:TaxAmount", ns).text = str(round(toplam_kdv, 2))
    root.find(".//cac:LegalMonetaryTotal/cbc:LineExtensionAmount", ns).text = str(round(toplam_net, 2))
    root.find(".//cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount", ns).text = str(round(toplam_net + toplam_kdv, 2))
    root.find(".//cac:LegalMonetaryTotal/cbc:PayableAmount", ns).text = str(round(toplam_net + toplam_kdv, 2))

    return ET.tostring(root, encoding="utf-8").decode("utf-8")