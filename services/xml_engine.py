import lxml.etree as ET
import os
import webbrowser

def render_invoice_html(xml_string):
    tree = ET.fromstring(xml_string.encode("utf-8"))

    # Logoların bilgisayarındaki yolları
    gedik_logo_path = r"C:\Users\Hande\Pictures\Screenshots\Ekran görüntüsü 2026-02-16 161247.png"
    gib_logo_path = r"C:\Users\Hande\Pictures\Screenshots\Ekran görüntüsü 2026-02-16 155657.png"
    
    # URL formatına dönüştürme (Boşluklar ve Türkçe karakterler için)
    gedik_url = "file:///" + gedik_logo_path.replace("\\", "/")
    gib_url = "file:///" + gib_logo_path.replace("\\", "/")

    xslt_str = f"""<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">

<xsl:output method="html" indent="yes"/>

<xsl:template match="/">
<html>
<head>
<meta charset="UTF-8"/>
<style>
    body {{ font-family: 'Arial', sans-serif; background:#fff; padding:10px; color: #333; }}
    .container {{ width:1000px; margin:auto; border:1px solid #ccc; padding:25px; min-height: 1200px; }}
    
    /* Header Yapısı */
    .header-table {{ width: 100%; border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 15px; }}
    .logo-left {{ width: 40%; text-align: left; vertical-align: middle; }}
    .title-center {{ width: 20%; text-align: center; vertical-align: middle; font-weight: bold; font-size: 20px; }}
    .logo-right {{ width: 40%; text-align: right; vertical-align: middle; }}
    
    .main-logo {{ max-width: 220px; height: auto; }}
    .gib-logo {{ max-width: 120px; height: auto; }}
    
    /* Müşteri ve Bilgi Alanı */
    .info-row {{ width: 100%; margin-top: 15px; }}
    .customer-area {{ width: 55%; vertical-align: top; text-align: left; }}
    .meta-area {{ width: 45%; vertical-align: top; }}
    
    .sayin-label {{ font-weight: bold; font-size: 16px; display: block; text-align: left; }}
    .customer-name {{ font-weight: bold; font-size: 14px; margin: 5px 0; text-align: left; }}
    
    .meta-table {{ width: 100%; border-collapse: collapse; }}
    .meta-table td {{ border: 1px solid #000; padding: 5px; font-size: 11px; }}
    .meta-head {{ background: #f2f2f2; font-weight: bold; width: 40%; }}

    /* Kalemler Tablosu */
    .line-table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
    .line-table th {{ border: 1px solid #000; padding: 8px; font-size: 11px; background: #eee; }}
    .line-table td {{ border: 1px solid #000; padding: 8px; font-size: 11px; text-align: center; }}
    
    /* Toplamlar */
    .totals-table {{ width: 35%; margin-left: auto; border-collapse: collapse; margin-top: 20px; }}
    .totals-table td {{ border: 1px solid #000; padding: 6px; font-size: 13px; }}
    .total-lbl {{ font-weight: bold; text-align: right; background: #f9f9f9; }}

    .footer {{ margin-top: 40px; font-size: 11px; border-top: 1px solid #eee; padding-top: 10px; }}
</style>
</head>
<body>
<div class="container">
    <table class="header-table">
        <tr>
            <td class="logo-left">
                <img src="{gedik_url}" class="main-logo" alt="Gedik Piliç"/>
            </td>
            <td class="title-center">e-Arşiv Fatura</td>
            <td class="logo-right">
                <img src="{gib_url}" class="gib-logo" alt="GİB Logo"/>
            </td>
        </tr>
    </table>

    <table class="info-row">
        <tr>
            <td class="customer-area">
                <div class="sayin-label">SAYIN</div>
                <div class="customer-name">
                    <xsl:value-of select="//cac:AccountingCustomerParty//cbc:Name"/>
                </div>
                <div style="font-size:11px; margin-top:10px;">
                    <strong>ETTN:</strong> <xsl:value-of select="//cbc:UUID"/>
                </div>
            </td>
            <td class="meta-area">
                <table class="meta-table">
                    <tr><td class="meta-head">Fatura No:</td><td><xsl:value-of select="//cbc:ID"/></td></tr>
                    <tr><td class="meta-head">Fatura Tarihi:</td><td><xsl:value-of select="//cbc:IssueDate"/></td></tr>
                    <tr><td class="meta-head">Fatura Tipi:</td><td><xsl:value-of select="//cbc:InvoiceTypeCode"/></td></tr>
                    <tr><td class="meta-head">Senaryo:</td><td>EARSIVFATURA</td></tr>
                </table>
            </td>
        </tr>
    </table>

    <table class="line-table">
        <thead>
            <tr>
                <th>No</th>
                <th>Ürün / Hizmet Açıklaması</th>
                <th>Miktar</th>
                <th>Birim Fiyat</th>
                <th>KDV %</th>
                <th>KDV Tutarı</th>
                <th>Toplam</th>
            </tr>
        </thead>
        <tbody>
            <xsl:for-each select="//cac:InvoiceLine">
                <tr>
                    <td><xsl:value-of select="cbc:ID"/></td>
                    <td style="text-align:left;"><xsl:value-of select="cac:Item/cbc:Name"/></td>
                    <td><xsl:value-of select="cbc:InvoicedQuantity"/></td>
                    <td><xsl:value-of select="format-number(cac:Price/cbc:PriceAmount,'#.##0,00')"/> TL</td>
                    <td>%<xsl:value-of select="cac:TaxTotal/cac:TaxSubtotal/cbc:Percent"/></td>
                    <td><xsl:value-of select="format-number(cac:TaxTotal/cbc:TaxAmount,'#.##0,00')"/> TL</td>
                    <td><xsl:value-of select="format-number(cbc:LineExtensionAmount + cac:TaxTotal/cbc:TaxAmount,'#.##0,00')"/> TL</td>
                </tr>
            </xsl:for-each>
        </tbody>
    </table>

    <table class="totals-table">
        <tr>
            <td class="total-lbl">Ara Toplam</td>
            <td style="text-align:right;"><xsl:value-of select="format-number(//cac:LegalMonetaryTotal/cbc:LineExtensionAmount,'#.##0,00')"/> TL</td>
        </tr>
        <tr>
            <td class="total-lbl">KDV Toplamı</td>
            <td style="text-align:right;"><xsl:value-of select="format-number(//cac:TaxTotal/cbc:TaxAmount,'#.##0,00')"/> TL</td>
        </tr>
        <tr style="font-weight:bold;">
            <td class="total-lbl">Ödenecek Tutar</td>
            <td style="text-align:right;"><xsl:value-of select="format-number(//cac:LegalMonetaryTotal/cbc:PayableAmount,'#.##0,00')"/> TL</td>
        </tr>
    </table>

    <div class="footer">
        İrsaliye yerine geçer. Nakit ödenmiştir.<br/>
        Bu fatura elektronik ortamda oluşturulmuştur.
    </div>
</div>
</body>
</html>
</xsl:template>
</xsl:stylesheet>
"""

    transform = ET.XSLT(ET.XML(xslt_str.encode()))
    result = transform(tree)
    
    output_file = os.path.abspath("fatura_onizleme.html")
    with open(output_file, "wb") as f:
        f.write(ET.tostring(result, pretty_print=True, method="html"))

    webbrowser.open("file://" + output_file)