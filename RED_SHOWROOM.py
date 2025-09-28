import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from fpdf import FPDF
import io
from num2words import num2words

# -----------------------------
# ⚙️ Configuration Streamlit
# -----------------------------
st.set_page_config(page_title="Showroom Stock & Vente", layout="wide")
st.title("📊 Gestion Showroom")

# -----------------------------
# 🔹 Connexion Google Sheets
# -----------------------------
SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]

creds_dict = st.secrets["google"]
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
client = gspread.authorize(creds)

SPREADSHEET_ID = "1r4xnyKDaY6jzYGLUORKHlPeGKMCCLkkIx_XvSkIobhc"
spreadsheet = client.open_by_key(SPREADSHEET_ID)

# -----------------------------
# 🔹 Charger une feuille
# -----------------------------
@st.cache_data(ttl=10)
def load_sheet(sheet_name):
    try:
        sheet = spreadsheet.worksheet(sheet_name)
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Erreur lors du chargement de '{sheet_name}': {e}")
        return pd.DataFrame()

# -----------------------------
# 🔹 Données initiales
# -----------------------------
df_produits = load_sheet("Produits")
produits_dispo = df_produits['Produit'].tolist() if not df_produits.empty else []

# -----------------------------
# 🔹 Gestion des onglets
# -----------------------------
tabs_labels = ["🛒 Ajouter Stock", "💰 Enregistrer Vente", "📦 État Stock", "📄 Historique Ventes"]
if "active_tab" not in st.session_state:
    st.session_state.active_tab = 0
if "panier" not in st.session_state:
    st.session_state.panier = []

tab_choice = st.radio("Choisir l'onglet", tabs_labels, index=st.session_state.active_tab)
st.session_state.active_tab = tabs_labels.index(tab_choice)

# -----------------------------
# Onglet 1 : Ajouter Stock
# -----------------------------
if tab_choice == "🛒 Ajouter Stock":
    st.header("Ajouter du stock")
    with st.form("form_stock"):
        produit_stock = st.selectbox("Produit", produits_dispo)
        quantite_stock = st.number_input("Quantité achetée", min_value=1, step=1)
        prix_achat = st.number_input("Prix d'achat unitaire", min_value=0.0, step=1.0, disabled=True)
        if st.form_submit_button("Ajouter au stock"):
            row = [str(datetime.now()), produit_stock, quantite_stock, prix_achat]
            spreadsheet.worksheet("Stock").append_row(row)
            st.success(f"{quantite_stock} {produit_stock} ajouté(s) au stock.")

# -----------------------------
# Onglet 2 : Enregistrer Vente
# -----------------------------
elif tab_choice == "💰 Enregistrer Vente":
    st.header("Enregistrer une vente")

    with st.form("form_vente"):
        produit_vente = st.selectbox("Produit vendu *", produits_dispo)
        quantite_vente = st.number_input("Quantité vendue *", min_value=1, step=1)

        client_nom = st.text_input("Nom du client *")
        client_tel = st.text_input("Téléphone du client *")

        generer_facture = st.checkbox("Générer une facture PDF")

        prix_unitaire = float(
            df_produits.loc[df_produits['Produit'] == produit_vente, 'Prix unitaire'].values[0]
        ) if not df_produits.empty else 0.0
        total_ht = prix_unitaire * quantite_vente
        total_ttc = round(total_ht * 1.19, 2)

        st.write(f"💵 Montant TTC : {total_ttc:.2f} DA")

        if st.form_submit_button("Ajouter au panier"):
            if not produit_vente or quantite_vente <= 0 or not client_nom.strip() or not client_tel.strip():
                st.error("⚠️ Merci de remplir les champs obligatoires.")
            else:
                st.session_state.panier.append({
                    "Produit": produit_vente,
                    "Quantité": quantite_vente,
                    "Prix TTC": round(prix_unitaire * 1.19, 2),
                    "Total TTC": total_ttc
                })
                st.success(f"{quantite_vente} x {produit_vente} ajouté(s) au panier.")

    if st.session_state.panier:
        st.subheader("Panier actuel")
        df_panier = pd.DataFrame(st.session_state.panier)
        st.dataframe(df_panier, use_container_width=True, hide_index=True)

        if st.button("Enregistrer la vente", key="enregistrer_vente"):
            df_ventes = load_sheet("Ventes")

            # Numéro de facture incrémenté
            prochain_num = ""
            if generer_facture:
                factures_existantes = df_ventes[df_ventes["Numéro de facture"].notnull()] if not df_ventes.empty else pd.DataFrame()
                if not factures_existantes.empty:
                    nums = factures_existantes["Numéro de facture"].str.split("/").str[0]
                    nums = nums[nums.str.isnumeric()].astype(int)
                    dernier_num = nums.max() if not nums.empty else 0
                else:
                    dernier_num = 0
                prochain_num = f"{dernier_num + 1:03d}/2025"

            # Enregistrer chaque produit
            for item in st.session_state.panier:
                row_vente = [
                    str(datetime.now()), client_nom, client_tel,
                    item["Produit"], item["Quantité"], item["Prix TTC"], item["Total TTC"],
                    prochain_num
                ]
                spreadsheet.worksheet("Ventes").append_row(row_vente)

            st.success(f"✅ Vente enregistrée pour {client_nom}.")

            # Génération facture PDF
            if generer_facture:
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", 'B', 14)
                pdf.cell(200, 10, txt=f"Facture N° {prochain_num}", ln=True, align="C")
                pdf.ln(10)

                pdf.set_font("Arial", size=12)
                pdf.cell(200, 8, txt=f"Client : {client_nom} | Tel : {client_tel}", ln=True)
                pdf.ln(5)

                pdf.set_font("Arial", 'B', 11)
                pdf.cell(70, 10, "Produit", 1)
                pdf.cell(30, 10, "Qté", 1)
                pdf.cell(40, 10, "Prix TTC", 1)
                pdf.cell(40, 10, "Total TTC", 1, ln=True)

                total_general = 0
                for item in st.session_state.panier:
                    total_general += item["Total TTC"]
                    pdf.set_font("Arial", size=11)
                    pdf.cell(70, 10, str(item["Produit"]), 1)
                    pdf.cell(30, 10, str(item["Quantité"]), 1)
                    pdf.cell(40, 10, f"{item['Prix TTC']:.2f}", 1)
                    pdf.cell(40, 10, f"{item['Total TTC']:.2f}", 1, ln=True)

                pdf.set_font("Arial", 'B', 12)
                pdf.cell(140, 10, "TOTAL TTC", 1)
                pdf.cell(40, 10, f"{total_general:.2f}", 1, ln=True)

                montant_lettres = num2words(int(total_general), lang='fr') + " dinars algériens"
                pdf.ln(10)
                pdf.set_font("Arial", 'I', 11)
                pdf.multi_cell(0, 10, f"Arrêté la présente facture à : {montant_lettres}")

                pdf_bytes = pdf.output(dest='S').encode('latin1')
                pdf_io = io.BytesIO(pdf_bytes)

                st.download_button("📥 Télécharger la facture", data=pdf_io,
                                   file_name=f"facture_{client_nom}_{prochain_num}.pdf",
                                   mime="application/pdf")

            st.session_state.panier = []

# -----------------------------
# Onglet 3 : État Stock
# -----------------------------
elif tab_choice == "📦 État Stock":
    st.header("État du stock")
    df_stock = load_sheet("Stock")
    df_ventes = load_sheet("Ventes")
    if not df_stock.empty:
        stock_reel = df_stock.groupby("Produit")["Quantité"].sum().reset_index()
        if not df_ventes.empty:
            ventes_group = df_ventes.groupby("Produit")["Quantité"].sum().reset_index()
            stock_reel = stock_reel.merge(ventes_group, on="Produit", how="left", suffixes=('', '_vendu'))
            stock_reel['Quantité_vendu'] = stock_reel['Quantité_vendu'].fillna(0)
            stock_reel['Stock restant'] = stock_reel['Quantité'] - stock_reel['Quantité_vendu']
        else:
            stock_reel['Stock restant'] = stock_reel['Quantité']
        st.dataframe(stock_reel[['Produit','Stock restant']], use_container_width=True)
    else:
        st.write("Aucun stock enregistré.")

# -----------------------------
# Onglet 4 : Historique Ventes
# -----------------------------
elif tab_choice == "📄 Historique Ventes":
    st.header("Historique des ventes")
    df_ventes = load_sheet("Ventes")
    if not df_ventes.empty:
        st.dataframe(df_ventes, use_container_width=True)
    else:
        st.write("Aucune vente enregistrée.")
