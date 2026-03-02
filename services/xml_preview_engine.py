import lxml.etree as ET

def get_preview_html(xml_string):
    try:
        # XML string'ini temizleyip byte'a çeviriyoruz
        xml_data = xml_string.strip()
        xml_data = xml_string.strip().encode("utf-8")
        tree = ET.fromstring(xml_data)
        
        # XSLT Tasarımı (Değişmedi)
        xslt_str = """<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
<xsl:template match="/">
<html>
<body style="font-family: Arial; padding: 20px;">
    <div style="border: 2px solid #333; padding: 20px; background: #fff;">
        <h2 style="text-align:center;">E-FATURA ÖNİZLEME</h2>
        <hr/>
        <p><strong>Alıcı:</strong> <xsl:value-of select="//cac:AccountingCustomerParty//cbc:Name"/></p>
        <p><strong>Tarih:</strong> <xsl:value-of select="//cbc:IssueDate"/></p>
        <table border="1" style="width:100%; border-collapse: collapse; margin-top:10px;">
            <tr style="background: #eee;"><th>Ürün</th><th>Miktar</th><th>Fiyat</th></tr>
            <xsl:for-each select="//cac:InvoiceLine">
            <tr>
                <td><xsl:value-of select="cac:Item/cbc:Name"/></td>
                <td align="center"><xsl:value-of select="cbc:InvoicedQuantity"/></td>
                <td align="right"><xsl:value-of select="cac:Price/cbc:PriceAmount"/> TL</td>
            </tr>
            </xsl:for-each>
        </table>
        <div style="text-align:right; margin-top:20px;">
            <p><strong>Toplam:</strong> <xsl:value-of select="//cac:LegalMonetaryTotal/cbc:PayableAmount"/> TL</p>
        </div>
    </div>
</body>
</html>
</xsl:template>
</xsl:stylesheet>
"""
        xslt_root = ET.fromstring(xslt_str.encode("utf-8"))
        transform = ET.XSLT(xslt_root)
        result_tree = transform(tree)
        return str(result_tree)
    except Exception as e:
        return f"<html><body><p style='color:red;'>XML Okuma Hatası: {str(e)}</p></body></html>"