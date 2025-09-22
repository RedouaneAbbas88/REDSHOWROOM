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
SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]

creds_dict = st.secrets["google"]
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
client = gspread.authorize(creds)

SPREADSHEET_ID = "1r4xnyKDaY6jzYGLUORKHlPeGKMCCLkkIx_XvSkIobhc"
spreadsheet = client.open_by_key(SPREADSHEET_ID)

# Feuilles
sheet_produits = spreadsheet.worksheet("Produits")
sheet_stock = spreadsheet.worksheet("Stock")
sheet_ventes = spreadsheet.worksheet("Ventes")
sheet_clients = spreadsheet.worksheet("Clients")  # Nouvelle feuille clients

# ---------------------------------------------------
# 🔹 Charger les données
# ---------------------------------------------------
df_produits = pd.DataFrame(sheet_produits.get_all_records())
df_stock = pd.DataFrame(sheet_stock.get_all_records())
df_ventes = pd.DataFrame(sheet_ventes.get_all_records())
df_clients = pd.DataFrame(sheet_clients.get_all_records())

produits_dispo = df_produits['Produit'].tolist()

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
        sheet_stock.append_row(row)
        st.success(f"{quantite_stock} {produit_stock} ajouté(s) au stock.")

# ---------------------------------------------------
# 🔹 Formulaire Vente
# ---------------------------------------------------
st.header("💰 Ventes")
vente_enregistree = False  # flag pour bouton téléchargement

with st.form("form_vente"):
    st.subheader("Enregistrer une vente")
    produit_vente = st.selectbox("Produit vendu", produits_dispo)
    quantite_vente = st.number_input("Quantité vendue", min_value=1, step=1)
    client_nom = st.text_input("Nom du client")
    client_email = st.text_input("Email du client")
    client_tel = st.text_input("Téléphone du client")

    prix_unitaire = float(df_produits.loc[df_produits['Produit'] == produit_vente, 'Prix unitaire'].values[0])
    total_vente = prix_unitaire * quantite_vente
    st.write(f"Prix unitaire : {prix_unitaire} | Total : {total_vente}")

    submit_vente = st.form_submit_button("Enregistrer la vente")

    if submit_vente:
        # Vérifier stock disponible
        df_stock = pd.DataFrame(sheet_stock.get_all_records())
        df_ventes = pd.DataFrame(sheet_ventes.get_all_records())
        stock_dispo = df_stock[df_stock['Produit'] == produit_vente]['Quantité'].sum() - \
                      df_ventes[df_ventes['Produit'] == produit_vente]['Quantité'].sum() if not df_ventes.empty else \
                      df_stock[df_stock['Produit'] == produit_vente]['Quantité'].sum()

        if quantite_vente > stock_dispo:
            st.error(f"Stock insuffisant ! Stock disponible : {stock_dispo}")
        else:
            # Ajouter la vente
            row_vente = [str(datetime.now()), client_nom, produit_vente, quantite_vente, prix_unitaire, total_vente]
            sheet_ventes.append_row(row_vente)

            # Ajouter client dans la feuille Clients si nouveau
            if client_nom not in df_clients['Nom'].tolist():
                row_client = [client_nom, client_email, client_tel]
                sheet_clients.append_row(row_client)

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

    pdf_output = io.BytesIO()
    pdf.output(pdf_output)
    pdf_output.seek(0)

    # Bouton téléchargement en dehors du formulaire
    st.download_button("📥 Télécharger la facture", pdf_output, file_name=f"facture_{client_nom}.pdf")

# ---------------------------------------------------
# 🔹 État du stock
# ---------------------------------------------------
st.header("📦 État du Stock")
df_stock = pd.DataFrame(sheet_stock.get_all_records())
df_ventes = pd.DataFrame(sheet_ventes.get_all_records())

stock_reel = df_stock.groupby("Produit")['Quantité'].sum().reset_index()
if not df_ventes.empty:
    ventes_group = df_ventes.groupby("Produit")['Quantité'].sum().reset_index()
    stock_reel = stock_reel.merge(ventes_group, on="Produit", how="left")
    stock_reel['Quantité_y'] = stock_reel['Quantité_y'].fillna(0)
    stock_reel['Stock restant'] = stock_reel['Quantité'] - stock_reel['Quantité_y']
else:
    stock_reel['Stock restant'] = stock_reel['Quantité']

st.dataframe(stock_reel[['Produit', 'Stock restant']], use_container_width=True)

# ---------------------------------------------------
# 🔹 Historique des ventes
# ---------------------------------------------------
st.header("📄 Historique des Ventes")
if not df_ventes.empty:
    st.dataframe(df_ventes, use_container_width=True)
else:
    st.write("Aucune vente enregistrée.")
