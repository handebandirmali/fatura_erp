import streamlit as st
import pandas as pd
from db.connection import get_connection
from ui.sidebar import render_sidebar
from ui.forms import render_edit_form
from services.filters import apply_filters
from services.invoice_calc import update_invoice_xml
from services.xml_engine import render_invoice_html
from ui.ai_widget import render_ai_widget

def render_fatura_page():
    """
    E-Fatura modülünün ana render fonksiyonu.
    """
    st.title("🧾 Fatura Yönetim Sistemi")

    # 1. VERİ ÇEKME (Data Fetching)
    # Bu kısmı aslında bir 'service' fonksiyonuna taşımak daha clean olur ama şimdilik burada kalsın.
    conn = get_connection()
    # XML kolonu ağır olduğu için sadece ihtiyaç anında veya optimize çekilebilir.
    # Şimdilik mevcut yapıyı koruyoruz.
    query = """
    SELECT [fatura_no],[cari_kod],[cari_ad],[stok_kod],[urun_adi],
           [urun_tarihi],[miktar],[birim_fiyat],[kdv_orani],[Toplam],[xml_ubl]
    FROM [FaturaDB].[dbo].[FaturaDetay]
    """
    df = pd.read_sql(query, conn)

    # 2. FİLTRELEME (Filtering)
    filters = render_sidebar() 
    subset = apply_filters(df, filters)
    
    st.divider()

    # 3. TABLO GÖSTERİMİ (Data Grid)
    # Tabloyu gösterme işini ui katmanına taşıyabiliriz veya burada tutabiliriz.
    # Okunabilirlik için burada basit tutuyoruz.
    event = st.dataframe(
        subset.drop(columns=['xml_ubl'], errors='ignore'),
        use_container_width=True,
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun",
        height=400,
        column_config={
            "urun_tarihi": st.column_config.DateColumn("Tarih", format="DD/MM/YYYY"),
            "birim_fiyat": st.column_config.NumberColumn("Birim Fiyat", format="%.2f ₺"),
            "Toplam": st.column_config.NumberColumn("Toplam", format="%.2f ₺"),
            "kdv_orani": st.column_config.NumberColumn("KDV", format="%d%%")
        }
    )

    # 4. SEÇİM YÖNETİMİ (State Management)
    # Tablodan tıklanan satırı yakalama
    if event and event.selection and event.selection["rows"]:
        idx = event.selection["rows"][0]
        # Subset üzerinden iloc ile doğru satırı buluyoruz
        selected_row = subset.iloc[idx]
        st.session_state.fatura_select = selected_row["fatura_no"]

    # Fatura Listesi ve Selectbox
    fatura_list = subset['fatura_no'].unique().tolist()
    
    # Seçili fatura yoksa ilkini seç
    if "fatura_select" not in st.session_state:
        st.session_state.fatura_select = fatura_list[0] if fatura_list else None
    
    # Selectbox UI
    selected_fatura_no = st.selectbox(
        "📄 İşlem Yapılacak Fatura", 
        fatura_list, 
        key="fatura_select_box",
        # Session state ile senkronize çalışması için index bulma mantığı eklenebilir
        # ancak basitlik adına burada key ile bırakıyoruz.
        index=fatura_list.index(st.session_state.fatura_select) if st.session_state.fatura_select in fatura_list else 0
    )

    # Seçimi güncelle (Selectbox değişirse state de değişsin)
    st.session_state.fatura_select = selected_fatura_no

    # 5. AKSİYON BUTONLARI (Action Bar)
    _render_action_buttons(subset, selected_fatura_no, conn)

    # 6. AI WIDGET
    render_ai_widget(subset)

def _render_action_buttons(df, fatura_no, conn):
    """
    Aksiyon butonlarını ve edit modunu yöneten yardımcı fonksiyon.
    Private (_) olarak işaretlendi.
    """
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📄 FATURAYI GÖSTER", use_container_width=True):
            # XML verisini çek
            xml_data = df[df["fatura_no"] == fatura_no]["xml_ubl"].iloc[0] if not df[df["fatura_no"] == fatura_no].empty else None
            
            if xml_data:
                render_invoice_html(xml_data)
            else:
                st.warning("Bu faturaya ait XML verisi bulunamadı.")

    with col2:
        if st.button("✏️ FATURA DÜZENLE", use_container_width=True):
            st.session_state.edit_mode = True

    # Edit Modu Kontrolü
    if st.session_state.get("edit_mode", False):
        _render_edit_mode(df, fatura_no, conn)

def _render_edit_mode(df, fatura_no, conn):
    """
    Düzenleme formunu ve kayıt işlemini yönetir.
    """
    st.divider()
    st.subheader(f"✏️ Düzenleniyor: {fatura_no}")
    
    edit_df = df[df["fatura_no"] == fatura_no]

    with st.form("edit_form"):
        updates = render_edit_form(edit_df)
        
        col_cancel, col_save = st.columns([1, 4])
        
        with col_cancel:
            if st.form_submit_button("❌ İptal", type="secondary"):
                st.session_state.edit_mode = False
                st.rerun()
                
        with col_save:
            if st.form_submit_button("💾 DEĞİŞİKLİKLERİ KAYDET", type="primary"):
                _save_invoice_updates(conn, updates, edit_df, fatura_no)

def _save_invoice_updates(conn, updates, original_df, fatura_no):
    """
    Veritabanı güncelleme işlemlerini yapar.
    Service katmanına taşınabilir ama şimdilik burada.
    """
    try:
        cur = conn.cursor()
        
        # 1. DB Update
        for u in updates:
            # u -> (cari_kod, cari_ad, urun_adi, miktar, birim_fiyat, kdv, tarih, fatura_no, stok_kod)
            cur.execute("""
            UPDATE FaturaDetay SET 
                cari_kod=?, cari_ad=?, urun_adi=?, miktar=?, 
                birim_fiyat=?, kdv_orani=?, urun_tarihi=?
            WHERE fatura_no=? AND stok_kod=?
            """, u)
            
        # 2. XML Update
        old_xml = original_df.iloc[0]["xml_ubl"]
        if old_xml:
            new_xml = update_invoice_xml(old_xml, updates)
            cur.execute("UPDATE FaturaDetay SET xml_ubl=? WHERE fatura_no=?", (new_xml, fatura_no))
        
        conn.commit()
        
        st.success("✅ Fatura başarıyla güncellendi!")
        st.session_state.edit_mode = False
        import time
        time.sleep(1) # Kullanıcı success mesajını görsün diye
        st.rerun()
        
    except Exception as e:
        st.error(f"Hata oluştu: {str(e)}")

def render_irsaliye_page():
    """
    E-İrsaliye modülünün ana render fonksiyonu.
    """
    st.title("🚚 E-İrsaliye Yönetimi")
    
    st.info("🚧 Bu modül şu anda geliştirme aşamasındadır.")
    
    st.markdown("""
    ### Planlanan Özellikler:
    - İrsaliye listeleme
    - Depo stok kontrolü
    - İrsaliye -> Fatura dönüşümü
    """)