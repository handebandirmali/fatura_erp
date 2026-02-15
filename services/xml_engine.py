import lxml.etree as ET
import os
import webbrowser


def render_invoice_html(xml_string):

    tree = ET.fromstring(xml_string.encode("utf-8"))

    xslt_str = """<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:ubl="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">

<xsl:output method="html" indent="yes"/>

<xsl:template match="/">
<html>
<head>
<meta charset="UTF-8"/>
<style>
body { font-family:Segoe UI; background:#f4f4f4; padding:20px; }
.card { background:#fff; padding:30px; width:1100px; margin:auto; border:1px solid #000; }
.title { text-align:center; font-size:22px; font-weight:bold; border-bottom:2px solid #000; padding-bottom:10px; }
table { width:100%; border-collapse:collapse; margin-top:15px; }
th, td { border:1px solid #000; padding:8px; font-size:13px; }
th { background:#333; color:#fff; }
</style>
</head>
<body>
<div class="card">
<div class="title">E-FATURA GÖRÜNTÜLEME</div>

<table>
<tr><td><b>MÜŞTERİ</b><br/>
<xsl:value-of select="//cac:AccountingCustomerParty//cbc:Name"/>
</td></tr>
</table>

<table>
<tr>
<td>Fatura No</td><td><xsl:value-of select="//cbc:ID"/></td>
<td>Tarih</td><td><xsl:value-of select="//cbc:IssueDate"/></td>
</tr>
</table>

<table>
<tr>
<th>No</th><th>Ürün</th><th>Miktar</th><th>Birim Fiyat</th>
<th>KDV %</th><th>KDV</th><th>Toplam</th>
</tr>

<xsl:for-each select="//cac:InvoiceLine">
<tr>
<td><xsl:value-of select="cbc:ID"/></td>
<td><xsl:value-of select="cac:Item/cbc:Name"/></td>
<td><xsl:value-of select="cbc:InvoicedQuantity"/></td>
<td><xsl:value-of select="format-number(cac:Price/cbc:PriceAmount,'#.##0,00')"/></td>
<td><xsl:value-of select="cac:TaxTotal/cac:TaxSubtotal/cbc:Percent"/></td>
<td><xsl:value-of select="format-number(cac:TaxTotal/cbc:TaxAmount,'#.##0,00')"/></td>
<td><xsl:value-of select="format-number(cbc:LineExtensionAmount + cac:TaxTotal/cbc:TaxAmount,'#.##0,00')"/></td>
</tr>
</xsl:for-each>
</table>

</div>
</body>
</html>
</xsl:template>
</xsl:stylesheet>
"""

    transform = ET.XSLT(ET.XML(xslt_str.encode()))
    result = transform(tree)

    with open("fatura_onizleme.html", "wb") as f:
        f.write(ET.tostring(result, pretty_print=True, method="html"))

    webbrowser.open("file://" + os.path.abspath("fatura_onizleme.html"))
