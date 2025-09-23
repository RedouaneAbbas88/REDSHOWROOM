import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from fpdf import FPDF
import datetime
import io

# Connexion Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

# Charger les feuilles Google Sheets
sheet_ventes = client.open("GestionStock").worksheet("ventes")
sheet_stock = client.open("GestionStock").worksheet("stock")

# Initialiser le panier en session
if "panier" not in st.session_state:
    st.session_state.panier = []

if "active_tab" not in st.session_state:
    st.session_state.active_tab = "Enregistrer une vente"

# --- Définition des onglets ---
tabs = st.tabs(["Ajouter au stock", "Consulter le stock", "Enregistrer une vente"])
tab_labels = ["Ajouter au stock", "Consulter le stock", "Enregistrer une vente"]

# Associer index -> nom onglet
tab_index = tab_labels.index(st.session_state.active_tab)

# Onglet 1 : Ajouter au stock
with tabs[0]:
    if tab_index == 0:
        st.header("➕ Ajouter au stock")
        produit = st.text_input("Nom du produit")
        quantite = st.number_input("Quantité", min_value=1, step=1)
        prix = st.number_input("Prix unitaire", min_value=0.0, step=0.01)
        if st.button("Ajouter au stock"):
            sheet_stock.append_row([produit, quantite, prix])
            st.success(f"{produit} ajouté au stock ✅")
            st.session_state.active_tab = "Ajouter au stock"

# Onglet 2 : Consulter le stock
with tabs[1]:
    if tab_index == 1:
        st.header("📦 Consulter le stock")
        data = sheet_stock.get_all_records()
        df_stock = pd.DataFrame(data)
        st.dataframe(df_stock)
        st.session_state.active_tab = "Consulter le stock"

# Onglet 3 : Enregistrer une vente
with tabs[2]:
    if tab_index == 2:
        st.header("🛒 Enregistrer une vente")

        # Formulaire client
        nom = st.text_input("Nom du client")
        produit = st.text_input("Produit")
        quantite = st.number_input("Quantité vendue", min_value=1, step=1)
        prix = st.number_input("Prix unitaire", min_value=0.0, step=0.01)

        if st.button("Ajouter au panier"):
            total = quantite * prix
            st.session_state.panier.append({"produit": produit, "quantite": quantite, "prix": prix, "total": total})
            st.success(f"{produit} ajouté au panier ✅")
            st.session_state.active_tab = "Enregistrer une vente"

        # Afficher le panier
        if st.session_state.panier:
            st.subheader("🛍️ Panier en cours")
            df_panier = pd.DataFrame(st.session_state.panier)
            st.table(df_panier)

            total_general = sum(item["total"] for item in st.session_state.panier)
            st.write(f"💰 **Total TTC : {total_general} DA**")

            if st.button("Enregistrer la vente"):
                numero_facture = f"FAC-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
                for item in st.session_state.panier:
                    sheet_ventes.append_row([
                        datetime.datetime.now().strftime("%Y-%m-%d"),
                        nom, "", "", "", "", "", "",  # Infos client
                        item["produit"], item["quantite"], item["prix"], item["total"], total_general,
                        "RC_ENTREPRISE", "NIF_ENTREPRISE", "ART_ENTREPRISE", "ADRESSE_ENTREPRISE",
                        numero_facture
                    ])

                # Génération du PDF
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", size=12)
                pdf.cell(200, 10, txt=f"Facture {numero_facture}", ln=True, align="C")
                pdf.cell(200, 10, txt=f"Client : {nom}", ln=True, align="L")
                pdf.ln(10)
                for item in st.session_state.panier:
                    pdf.cell(200, 10, txt=f"{item['produit']} x {item['quantite']} - {item['total']} DA", ln=True)
                pdf.ln(10)
                pdf.cell(200, 10, txt=f"Total TTC : {total_general} DA", ln=True)

                # Export
                buffer = io.BytesIO()
                pdf.output(buffer)
                st.download_button("📥 Télécharger la facture", buffer, file_name=f"{numero_facture}.pdf")

                st.success("Vente enregistrée ✅")
                st.session_state.panier = []
                st.session_state.active_tab = "Enregistrer une vente"

            if st.button("🗑️ Vider le panier"):
                st.session_state.panier = []
                st.session_state.active_tab = "Enregistrer une vente"
