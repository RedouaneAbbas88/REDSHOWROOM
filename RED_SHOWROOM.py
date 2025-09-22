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
# 🔹 Fonction pour charger une feuille (sans cache pour les feuilles dynamiques)
# ---------------------------------------------------
def load_sheet(sheet_name):
    try:
        sheet = spreadsheet.worksheet(sheet_name)
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Erreur lors du chargement de la feuille '{sheet_name}': {e}")
        return pd.DataFrame()

# Pour les produits (rarement modifiés), on peut garder le cache
@st.cache_data(ttl=600)
def load_products():
    return load_sheet("Produits")

# ---------------------------------------------------
# 🔹 Charger les données initiales
# ---------------------------------------------------
df_produits = load_products()
produits_dispo = df_produits['Produit'].tolist() if not df_produits.empty else []

# ---------------------------------------------------
# 🔹 Formulaire Ajout Stock
# ---------------------------------------------------
st.header("🛒 Gestion du Stock")
with st.form("form_stock"):
    st.subheader("Ajouter du stock")
    produit_stock = st.selectbox("Produit", produits_dispo)
    quantite_stock = st.number_input("Quantité achetée", min_value=1, step=1)
    prix_achat = st.number_input("Prix d'achat unitaire", min_value=0.0, step=1.0)
    submit_stock = st.form_submit_button("Ajouter au stock")

    if submit_stock:
        row = [str(datetime.now()), produit_stock, quantite_stock, prix_achat]
        spreadsheet.worksheet("Stock").append_row(row)
        st.success(f"{quantite_stock} {produit_stock} ajouté(s) au stock.")

# ---------------------------------------------------
# 🔹 Formulaire Vente
# ---------------------------------------------------
st.header("💰 Ventes")
vente_enregistree = False

with st.form("form_vente"):
    st.subheader("Enregistrer une vente")
    produit_vente = st.selectbox("Produit vendu", produits_dispo)
    quantite_vente = st.number_input("Quantité vendue", min_value=1, step=1)
    client_nom = st.text_input("Nom du client")
    client_email = st.text_input("Email du client")
    client_tel = st.text_input("Téléphone du client")

    prix_unitaire = float(df_produits.loc[df_produits['Produit'] == produit_vente, 'Prix unitaire'].values[0]) \
        if not df_produits.empty else 0.0
    total_vente = prix_unitaire * quantite_vente
    st.write(f"Prix unitaire : {prix_unitaire} | Total : {total_vente}")

    submit_vente = st.form_submit_button("Enregistrer la vente")

    if submit_vente:
        # Recharger stock et ventes dynamiques
        df_stock = load_sheet("Stock")
        df_ventes = load_sheet("Ventes")
        df_clients = load_sheet("Clients")

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
            if client_nom not in df_clients['Nom'].tolist():
                row_client = [client_nom, client_email, client_tel]
                spreadsheet.worksheet("Clients").append_row(row_client)

            st.success(f"Vente enregistrée pour {client_nom} : {quantite_vente} {produit_vente} ({total_vente})")
            vente_enregistree = True

# ---------------------------------------------------
# 🔹 Génération facture PDF
# ---------------------------------------------------
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

# ---------------------------------------------------
# 🔹 État du stock
# ---------------------------------------------------
st.header("📦 État du Stock")
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

# ---------------------------------------------------
# 🔹 Historique des ventes
# ---------------------------------------------------
st.header("📄 Historique des Ventes")
df_ventes = load_sheet("Ventes")
if not df_ventes.empty:
    st.dataframe(df_ventes, use_container_width=True)
else:
    st.write("Aucune vente enregistrée.")
