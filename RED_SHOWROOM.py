import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from fpdf import FPDF
import io

# ---------------------------------------------------
# ⚙️ Configuration Streamlit
# ---------------------------------------------------
st.set_page_config(
    page_title="Showroom Stock & Vente",
    layout="wide"
)
st.title("📊 Gestion Showroom")

# ---------------------------------------------------
# 🔹 Connexion Google Sheets
# ---------------------------------------------------
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds_dict = st.secrets["google"]
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
client = gspread.authorize(creds)

SPREADSHEET_ID = "1r4xnyKDaY6jzYGLUORKHlPeGKMCCLkkIx_XvSkIobhc"
spreadsheet = client.open_by_key(SPREADSHEET_ID)

# ---------------------------------------------------
# 🔹 Fonction pour charger une feuille
# ---------------------------------------------------
@st.cache_data(ttl=10)  # Rafraîchit les données toutes les 10 secondes
def load_sheet(sheet_name):
    try:
        sheet = spreadsheet.worksheet(sheet_name)
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Erreur lors du chargement de la feuille '{sheet_name}': {e}")
        return pd.DataFrame()

# ---------------------------------------------------
# 🔹 Charger les données initiales
# ---------------------------------------------------
df_produits = load_sheet("Produits")
df_clients = load_sheet("Clients")
produits_dispo = df_produits['Produit'].tolist() if not df_produits.empty else []

# ---------------------------------------------------
# 🔹 Onglets
# ---------------------------------------------------
tabs = st.tabs(["🛒 Ajouter Stock", "💰 Enregistrer Vente", "📦 État Stock", "📄 Historique Ventes"])

# -------------------- Onglet 1 : Ajouter Stock --------------------
with tabs[0]:
    st.header("Ajouter du stock")
    with st.form("form_stock"):
        produit_stock = st.selectbox("Produit", produits_dispo)
        quantite_stock = st.number_input("Quantité achetée", min_value=1, step=1)
        prix_achat = st.number_input("Prix d'achat unitaire", min_value=0.0, step=1.0)
        submit_stock = st.form_submit_button("Ajouter au stock")

        if submit_stock:
            row = [str(datetime.now()), produit_stock, quantite_stock, prix_achat]
            spreadsheet.worksheet("Stock").append_row(row)
            st.success(f"{quantite_stock} {produit_stock} ajouté(s) au stock.")

# -------------------- Onglet 2 : Enregistrer Vente --------------------
with tabs[1]:
    st.header("Enregistrer une vente")
    vente_enregistree = False

    with st.form("form_vente"):
        produit_vente = st.selectbox("Produit vendu", produits_dispo)
        quantite_vente = st.number_input("Quantité vendue", min_value=1, step=1)
        client_nom = st.text_input("Nom du client")
        client_email = st.text_input("Email du client")
        client_tel = st.text_input("Téléphone du client")

        prix_unitaire = float(df_produits.loc[df_produits['Produit'] == produit_vente, 'Prix unitaire'].values[0]) if not df_produits.empty else 0.0
        total_vente = prix_unitaire * quantite_vente
        st.write(f"Prix unitaire : {prix_unitaire} | Total : {total_vente}")

        submit_vente = st.form_submit_button("Enregistrer la vente")

        if submit_vente:
            df_stock = load_sheet("Stock")
            df_ventes = load_sheet("Ventes")

            stock_dispo = df_stock[df_stock['Produit'] == produit_vente]['Quantité'].sum()
            ventes_sum = df_ventes[df_ventes['Produit'] == produit_vente]['Quantité'].sum() if not df_ventes.empty else 0
            stock_reel = stock_dispo - ventes_sum

            if quantite_vente > stock_reel:
                st.error(f"Stock insuffisant ! Stock disponible : {stock_reel}")
            else:
                # Ajouter la vente
                row_vente = [str(datetime.now()), client_nom, produit_vente, quantite_vente, prix_unitaire, total_vente]
                spreadsheet.worksheet("Ventes").append_row(row_vente)

                # Ajouter client si nouveau
                df_clients = load_sheet("Clients")
                if client_nom not in df_clients['Nom'].tolist():
                    row_client = [client_nom, client_email, client_tel]
                    spreadsheet.worksheet("Clients").append_row(row_client)

                st.success(f"Vente enregistrée pour {client_nom} : {quantite_vente} {produit_vente} ({total_vente})")
                vente_enregistree = True

    # Génération PDF
    if vente_enregistree:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt="FACTURE SHOWROOM", ln=True, align="C")
        pdf.ln(10)
        pdf.cell(200, 10, txt=f"Client: {client_nom}", ln=True)
        pdf.cell(200, 10, txt=f"Produit: {produit_vente}", ln=True)
        pdf.cell(200, 10, txt=f"Quantité: {quantite_vente}", ln=True)
        pdf.cell(200, 10, txt=f"Prix unitaire: {prix_unitaire}", ln=True)
        pdf.cell(200, 10, txt=f"Total: {total_vente}", ln=True)

        pdf_bytes = pdf.output(dest='S').encode('latin1')
        pdf_io = io.BytesIO(pdf_bytes)

        st.download_button(
            label="📥 Télécharger la facture",
            data=pdf_io,
            file_name=f"facture_{client_nom}.pdf",
            mime="application/pdf"
        )

# -------------------- Onglet 3 : État Stock --------------------
with tabs[2]:
    st.header("État du stock")
    if st.button("🔄 Actualiser stock"):
        df_stock = load_sheet("Stock")
        df_ventes = load_sheet("Ventes")

    df_stock = load_sheet("Stock")
    df_ventes = load_sheet("Ventes")

    if not df_stock.empty:
        stock_reel = df_stock.groupby("Produit")['Quantité'].sum().reset_index()
        if not df_ventes.empty:
            ventes_group = df_ventes.groupby("Produit")['Quantité'].sum().reset_index()
            stock_reel = stock_reel.merge(ventes_group, on="Produit", how="left", suffixes=('', '_vendu'))
            stock_reel['Quantité_vendu'] = stock_reel['Quantité_vendu'].fillna(0)
            stock_reel['Stock restant'] = stock_reel['Quantité'] - stock_reel['Quantité_vendu']
        else:
            stock_reel['Stock restant'] = stock_reel['Quantité']

        st.dataframe(stock_reel[['Produit', 'Stock restant']], use_container_width=True)
    else:
        st.write("Aucun stock enregistré.")

# -------------------- Onglet 4 : Historique Ventes --------------------
with tabs[3]:
    st.header("Historique des ventes")

    # Charger les ventes sans cache pour voir les mises à jour immédiates
    try:
        sheet_ventes = spreadsheet.worksheet("Ventes")
        data_ventes = sheet_ventes.get_all_records()
        df_ventes = pd.DataFrame(data_ventes)
    except Exception as e:
        st.error(f"Erreur lors du chargement des ventes : {e}")
        df_ventes = pd.DataFrame()

    if not df_ventes.empty:
        st.dataframe(df_ventes, use_container_width=True)
    else:
        st.write("Aucune vente enregistrée.")