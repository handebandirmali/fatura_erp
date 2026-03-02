import streamlit as st
import pandas as pd
import time
import random
import string
from ai.tools.ocr_engine import faturadan_metin_cikar
from ai.tools.brain_engine import faturayi_anlamlandir
from ai.tools.db_tool import save_invoice_to_db

def generate_random_code(prefix, length=4):
    """Rastgele benzersiz kod üretir (Örn: FAT-171234-A1B2)"""
    timestamp = int(time.time())
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
    return f"{prefix}-{timestamp}-{suffix}"

def render_fatura_yukleme_page():
    st.header("📤 Akıllı Fatura Yükleme")
    
    if 'analiz_verisi' not in st.session_state:
        st.session_state.analiz_verisi = None

    yuklenen_dosya = st.file_uploader("Fatura Görseli veya PDF Seçin", type=['png', 'jpg', 'jpeg', 'pdf'])
    
    if yuklenen_dosya:
        st.image(yuklenen_dosya, caption="Yüklenen Fatura", width=300)
        
        if st.button("🔍 ANALİZİ BAŞLAT", type="secondary"):
            with st.status("Fatura işleniyor...", expanded=True) as status:
                st.write("🔍 Metinler okunuyor (OCR)...")
                ham_metin = faturadan_metin_cikar(yuklenen_dosya)
                
                st.write("🧠 AI verileri ayıklıyor...")
                res = faturayi_anlamlandir(ham_metin)

                if not res.get("fatura_no") or res.get("fatura_no") == "AI-TEMP-001":
                    res["fatura_no"] = generate_random_code("FAT")
                
                if not res.get("cari_kod"):
                    res["cari_kod"] = generate_random_code("CARI")
                
                for kalem in res.get("kalemler", []):
                    if not kalem.get("stok_kod") or kalem.get("stok_kod") == "STOK-001":
                        kalem["stok_kod"] = generate_random_code("STK")

                st.session_state.analiz_verisi = res
                status.update(label="Analiz Tamamlandı!", state="complete", expanded=False)

        if st.session_state.analiz_verisi:
            res = st.session_state.analiz_verisi
            
            st.subheader("📝 Fatura Bilgileri")
            col1, col2, col3, col4 = st.columns(4)
            
            onayli_fatura_no = col1.text_input("Fatura Numarası", value=res.get("fatura_no"))
            onayli_cari_kod = col2.text_input("Cari Kod", value=res.get("cari_kod"))
            onayli_firma = col3.text_input("Firma Adı", value=res.get("firma_adi", "Bilinmeyen"))
            onayli_tarih = col4.text_input("Tarih (GG.AA.YYYY)", value=res.get("tarih", ""))

            df_kalemler = pd.DataFrame(res.get("kalemler", []))
            
            if "stok_kod" not in df_kalemler.columns:
                df_kalemler["stok_kod"] = [generate_random_code("STK") for _ in range(len(df_kalemler))]

            st.subheader("📦 Kalem Detayları")
            onayli_df = st.data_editor(
                df_kalemler[["stok_kod", "urun_adi", "miktar", "birim_fiyat", "kdv_orani"]], 
                num_rows="dynamic", 
                use_container_width=True
            )

            try:
                # --- VİRGÜL VE SAYI DÜZELTME KATMANI ---
                for col in ["miktar", "birim_fiyat", "kdv_orani"]:
                    # Eğer veri tipi metin (object) ise virgülleri noktaya çevir
                    if onayli_df[col].dtype == 'object':
                        onayli_df[col] = onayli_df[col].astype(str).str.replace(',', '.')
                
                # Sayısal dönüşüm
                onayli_df["miktar"] = pd.to_numeric(onayli_df["miktar"], errors='coerce').fillna(0)
                onayli_df["birim_fiyat"] = pd.to_numeric(onayli_df["birim_fiyat"], errors='coerce').fillna(0)
                onayli_df["kdv_orani"] = pd.to_numeric(onayli_df["kdv_orani"], errors='coerce').fillna(20)
                
                onayli_df["satir_toplam"] = onayli_df["miktar"] * onayli_df["birim_fiyat"]
                ara_toplam = onayli_df["satir_toplam"].sum()
                kdv_toplam = (onayli_df["satir_toplam"] * (onayli_df["kdv_orani"] / 100)).sum()
                genel_toplam = ara_toplam + kdv_toplam

                c1, c2, c3 = st.columns(3)
                c1.metric("Ara Toplam", f"{ara_toplam:,.2f} TL")
                c2.metric("KDV Toplam", f"{kdv_toplam:,.2f} TL")
                c3.metric("Genel Toplam", f"{genel_toplam:,.2f} TL")

                if st.button("💾 VERİLERİ SİSTEME KAYDET", type="primary"):
                    save_data = {
                        "fatura_no": onayli_fatura_no,
                        "cari_kod": onayli_cari_kod,
                        "firma_adi": onayli_firma,
                        "tarih": onayli_tarih,
                        "kalemler": onayli_df.to_dict('records'),
                        "ara_toplam": ara_toplam,
                        "genel_toplam": genel_toplam
                    }
                    
                    result = save_invoice_to_db(save_data)
                    
                    if result.success:
                        st.balloons()
                        st.success("✅ Fatura başarıyla kaydedildi!")
                        
                        # ÖNEMLİ: analiz_verisi'ni burada temizlemiyoruz ki form açık kalsın 
                        # ve aşağıdaki buton görünsün. Temizliği 'Yeni Fatura' butonuna bırakıyoruz.
                        if st.button("🔄 Yeni Fatura Yüklemek İçin Formu Temizle"):
                            st.session_state.analiz_verisi = None
                            st.rerun()
                            
                    else:
                        st.error(f"Hata: {result.error}")
                    
            except Exception as e:
                st.error(f"Hesaplama hatası: {e}")