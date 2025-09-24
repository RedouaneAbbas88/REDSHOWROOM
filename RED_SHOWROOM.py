import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from fpdf import FPDF
import io

# ------------------ Connexion Google Sheets ------------------
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

sheet = client.open("VentesDB").worksheet("Ventes")

# ------------------ Initialisation session ------------------
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "Ajouter Stock"

if "panier" not in st.session_state:
    st.session_state.panier = []

# ------------------ Navigation par onglets ------------------
tabs = ["Ajouter Stock", "Enregistrer Vente", "Rapports"]
selected_tab = st.radio("Navigation :", tabs, index=tabs.index(st.session_state.active_tab), horizontal=True)
st.session_state.active_tab = selected_tab

# ------------------ Ajouter Stock ------------------
if st.session_state.active_tab == "Ajouter Stock":
    st.header("➕ Ajouter du stock")

    produit = st.text_input("Nom du produit")
    quantite = st.number_input("Quantité", min_value=1, step=1)
    prix = st.number_input("Prix unitaire", min_value=0.0, step=0.01)

    if st.button("Ajouter au stock"):
        sheet.append_row([produit, quantite, prix])
        st.success(f"✅ {produit} ajouté avec {quantite} unités à {prix} DA")

# ------------------ Enregistrer Vente ------------------
elif st.session_state.active_tab == "Enregistrer Vente":
    st.header("🛒 Enregistrer une vente")

    # Infos client
    client_nom = st.text_input("Nom du client")
    client_email = st.text_input("Email")
    client_tel = st.text_input("Téléphone")
    rc_client = st.text_input("RC Client")
    nif_client = st.text_input("NIF Client")
    art_client = st.text_input("ART Client")
    adresse_client = st.text_area("Adresse Client")

    # Coordonnées entreprise fixes
    rc_entreprise = "123456"
    nif_entreprise = "654321"
    art_entreprise = "111222"
    adresse_entreprise = "Zone Industrielle Alger"

    # Produit à ajouter au panier
    produit = st.text_input("Produit")
    quantite = st.number_input("Quantité", min_value=1, step=1, key="qte")
    prix = st.number_input("Prix unitaire", min_value=0.0, step=0.01, key="prix")

    if st.button("Ajouter au panier"):
        st.session_state.panier.append({
            "Produit": produit,
            "Quantité": quantite,
            "Prix unitaire": prix,
            "Total": quantite * prix
        })
        st.success(f"✅ {produit} ajouté au panier")

    # Affichage du panier
    if st.session_state.panier:
        st.subheader("🛍️ Panier en cours")
        df_panier = pd.DataFrame(st.session_state.panier)
        df_panier["Total TTC"] = df_panier["Total"] * 1.19

        st.dataframe(df_panier, use_container_width=True, hide_index=True)

        total_ht = df_panier["Total"].sum()
        total_ttc = df_panier["Total TTC"].sum()
        st.write(f"**Total HT :** {total_ht} DA")
        st.write(f"**Total TTC :** {total_ttc} DA")

        # Boutons par ligne
        for i, item in enumerate(st.session_state.panier):
            col1, col2 = st.columns(2)
            with col1:
                if st.button(f"📝 Modifier {item['Produit']}", key=f"modif_{i}"):
                    st.session_state.panier[i]["Quantité"] += 1
                    st.session_state.panier[i]["Total"] = (
                        st.session_state.panier[i]["Quantité"] * st.session_state.panier[i]["Prix unitaire"]
                    )
            with col2:
                if st.button(f"❌ Supprimer {item['Produit']}", key=f"suppr_{i}"):
                    st.session_state.panier.pop(i)
                    st.rerun()

        # Numéro de facture
        ventes_data = sheet.get_all_records()
        prochain_num = len(ventes_data) + 1
        facture_num = f"{prochain_num:03d}/2025"

        generer_facture = st.checkbox("🧾 Générer une facture")

        if st.button("✅ Enregistrer la vente"):
            for item in st.session_state.panier:
                sheet.append_row([
                    str(pd.Timestamp.now().date()), client_nom, client_email, client_tel,
                    rc_client, nif_client, art_client, adresse_client,
                    item["Produit"], item["Quantité"], item["Prix unitaire"], item["Total"],
                    item["Total"] * 1.19, rc_entreprise, nif_entreprise, art_entreprise,
                    adresse_entreprise, facture_num
                ])
            st.success("💾 Vente enregistrée avec succès")
            st.session_state.panier = []

            # Génération facture PDF
            if generer_facture:
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", "B", 16)
                pdf.cell(200, 10, f"FACTURE N° {facture_num}", ln=True, align="C")

                pdf.set_font("Arial", "", 12)
                pdf.ln(10)
                pdf.cell(100, 10, f"Client: {client_nom}")
                pdf.ln(5)
                pdf.cell(100, 10, f"Téléphone: {client_tel}")
                pdf.ln(5)
                pdf.multi_cell(0, 10, f"Adresse: {adresse_client}")
                pdf.ln(10)

                pdf.cell(100, 10, f"RC: {rc_entreprise} | NIF: {nif_entreprise}")
                pdf.ln(5)
                pdf.cell(100, 10, f"ART: {art_entreprise}")
                pdf.ln(5)
                pdf.multi_cell(0, 10, f"Adresse Entreprise: {adresse_entreprise}")
                pdf.ln(10)

                # Tableau produits
                pdf.set_font("Arial", "B", 12)
                pdf.cell(50, 10, "Produit", 1)
                pdf.cell(30, 10, "Quantité", 1)
                pdf.cell(40, 10, "Prix unitaire", 1)
                pdf.cell(40, 10, "Total", 1, ln=True)

                pdf.set_font("Arial", "", 12)
                for item in df_panier.to_dict("records"):
                    pdf.cell(50, 10, str(item["Produit"]), 1)
                    pdf.cell(30, 10, str(item["Quantité"]), 1)
                    pdf.cell(40, 10, str(item["Prix unitaire"]), 1)
                    pdf.cell(40, 10, str(item["Total"]), 1, ln=True)

                pdf.ln(5)
                pdf.cell(160, 10, "Total TTC", 1)
                pdf.cell(40, 10, str(total_ttc), 1, ln=True)

                # ✅ Export correct du PDF
                pdf_bytes = pdf.output(dest="S").encode("latin1")
                pdf_io = io.BytesIO(pdf_bytes)

                st.download_button(
                    label="📥 Télécharger la facture",
                    data=pdf_io.getvalue(),
                    file_name=f"facture_{facture_num}.pdf",
                    mime="application/pdf"
                )

# ------------------ Rapports ------------------
elif st.session_state.active_tab == "Rapports":
    st.header("📊 Rapports des ventes")

    data = sheet.get_all_records()
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Aucune vente enregistrée pour l’instant.")
