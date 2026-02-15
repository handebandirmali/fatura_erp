import lxml.etree as ET

def update_invoice_xml(xml_string, updates):

    ns = {
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'
    }

    root = ET.fromstring(xml_string.encode("utf-8"))
    invoice_lines = root.findall(".//cac:InvoiceLine", namespaces=ns)

    total_without_tax = 0
    total_tax = 0

    for line, u in zip(invoice_lines, updates):

        cari_kod, cari_ad, urun_adi, miktar, birim_fiyat, kdv_orani, urun_tarihi, fatura_no, stok_kod = u

        miktar = float(miktar)
        birim_fiyat = float(birim_fiyat)
        kdv_orani = float(kdv_orani)

        ara_toplam = miktar * birim_fiyat
        kdv_tutari = ara_toplam * kdv_orani / 100

        total_without_tax += ara_toplam
        total_tax += kdv_tutari

        line.find("cbc:InvoicedQuantity", ns).text = f"{miktar:.2f}"
        line.find("cac:Price/cbc:PriceAmount", ns).text = f"{birim_fiyat:.2f}"
        line.find("cbc:LineExtensionAmount", ns).text = f"{ara_toplam:.2f}"

        line.find("cac:TaxTotal/cac:TaxSubtotal/cbc:Percent", ns).text = f"{kdv_orani:.2f}"
        line.find("cac:TaxTotal/cbc:TaxAmount", ns).text = f"{kdv_tutari:.2f}"

        item_name = line.find("cac:Item/cbc:Name", ns)
        if item_name is not None:
            item_name.text = urun_adi

    general_total = total_without_tax + total_tax

    root.find(".//cbc:TaxExclusiveAmount", ns).text = f"{total_without_tax:.2f}"
    root.find(".//cbc:TaxInclusiveAmount", ns).text = f"{general_total:.2f}"
    root.find(".//cbc:PayableAmount", ns).text = f"{general_total:.2f}"

    return ET.tostring(root, encoding="utf-8").decode("utf-8")
