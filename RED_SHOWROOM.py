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
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds_dict = st.secrets["google"]
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
client = gspread.authorize(creds)

SPREADSHEET_ID = "1r4xnyKDaY6jzYGLUORKHlPeGKMCCLkkIx_XvSkIobhc"
spreadsheet = client.open_by_key(SPREADSHEET_ID)


# -----------------------------
# 🔹 Charger une feuille Google
# -----------------------------
@st.cache_data(ttl=10)
def load_sheet(sheet_name):
    try:
        sheet = spreadsheet.worksheet(sheet_name)
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        df = df.loc[:, df.columns.str.strip() != '']
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Erreur lors du chargement de la feuille '{sheet_name}': {e}")
        return pd.DataFrame()


# -----------------------------
# 🔹 Données initiales
# -----------------------------
df_produits = load_sheet("Produits")
if not df_produits.empty:
    df_produits.columns = df_produits.columns.str.strip()
produits_dispo = df_produits['Produit'].dropna().unique().tolist() if not df_produits.empty else []

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
        marques_dispo = df_produits['Marque'].dropna().unique().tolist() if not df_produits.empty else []
        marque_sel = st.selectbox("Marque", [""] + marques_dispo)

        categories_dispo = df_produits[df_produits['Marque'] == marque_sel][
            'Catégorie'].dropna().unique().tolist() if marque_sel else []
        categorie_sel = st.selectbox("Catégorie", [""] + categories_dispo)

        familles_dispo = df_produits[(df_produits['Marque'] == marque_sel) &
                                     (df_produits['Catégorie'] == categorie_sel)][
            'Famille'].dropna().unique().tolist() if categorie_sel else []
        famille_sel = st.selectbox("Famille", [""] + familles_dispo)

        produits_dispo_filtre = df_produits[
            (df_produits['Marque'] == marque_sel) &
            (df_produits['Catégorie'] == categorie_sel) &
            (df_produits['Famille'] == famille_sel)
            ]['Produit'].dropna().unique().tolist() if famille_sel else []

        produit_stock = st.selectbox("Produit", [""] + produits_dispo_filtre)
        quantite_stock = st.number_input("Quantité achetée", min_value=1, step=1)
        prix_achat = st.number_input("Prix d'achat unitaire", min_value=0.0, step=1.0, disabled=True)

        if st.form_submit_button("Ajouter au stock"):
            if not produit_stock:
                st.error("⚠️ Veuillez sélectionner un produit.")
            else:
                row = [str(datetime.now()), marque_sel, categorie_sel, famille_sel, produit_stock, quantite_stock,
                       prix_achat]
                spreadsheet.worksheet("Stock").append_row(row)
                st.success(f"{quantite_stock} x {produit_stock} ajouté(s) au stock.")

# -----------------------------
# Onglet 2 : Enregistrer Vente
# -----------------------------
elif tab_choice == "💰 Enregistrer Vente":
    st.header("Enregistrer une vente multi-produits")
    with st.form("form_vente_multi"):
        marques_dispo = df_produits['Marque'].dropna().unique().tolist() if not df_produits.empty else []
        marque_sel = st.selectbox("Marque", [""] + marques_dispo)

        categories_dispo = df_produits[df_produits['Marque'] == marque_sel][
            'Catégorie'].dropna().unique().tolist() if marque_sel else []
        categorie_sel = st.selectbox("Catégorie", [""] + categories_dispo)

        familles_dispo = df_produits[(df_produits['Marque'] == marque_sel) &
                                     (df_produits['Catégorie'] == categorie_sel)][
            'Famille'].dropna().unique().tolist() if categorie_sel else []
        famille_sel = st.selectbox("Famille", [""] + familles_dispo)

        produits_dispo_filtre = df_produits[
            (df_produits['Marque'] == marque_sel) &
            (df_produits['Catégorie'] == categorie_sel) &
            (df_produits['Famille'] == famille_sel)
            ]['Produit'].dropna().unique().tolist() if famille_sel else []

        produit_vente = st.selectbox("Produit vendu *", [""] + produits_dispo_filtre)
        quantite_vente = st.number_input("Quantité vendue *", min_value=1, step=1)

        client_nom = st.text_input("Nom du client *")
        client_email = st.text_input("Email du client")
        client_tel = st.text_input("Téléphone du client *")
        client_rc = st.text_input("RC du client")
        client_nif = st.text_input("NIF du client")
        client_art = st.text_input("ART du client")
        client_adresse = st.text_input("Adresse du client")

        generer_facture = st.checkbox("Générer une facture PDF")

        prix_unitaire = float(df_produits.loc[df_produits['Produit'] == produit_vente, 'Prix unitaire'].values[
                                  0]) if not df_produits.empty and produit_vente else 0.0
        total_vente = prix_unitaire * quantite_vente if produit_vente else 0.0

        st.write(
            f"Prix unitaire : {prix_unitaire} | Total HT : {total_vente:.2f} | Total TTC : {round(total_vente * 1.19, 2)}")

        if st.form_submit_button("Ajouter au panier"):
            if not produit_vente or quantite_vente <= 0 or not client_nom.strip() or not client_tel.strip():
                st.error(
                    "⚠️ Merci de remplir tous les champs obligatoires : Produit, Quantité, Nom du client et Téléphone.")
            else:
                st.session_state.panier.append({
                    "Marque": marque_sel,
                    "Catégorie": categorie_sel,
                    "Famille": famille_sel,
                    "Produit": produit_vente,
                    "Quantité": quantite_vente,
                    "Prix unitaire": prix_unitaire,
                    "Total": total_vente
                })
                st.success(f"{quantite_vente} x {produit_vente} ajouté(s) au panier.")

# -----------------------------
# Onglet 3 : État Stock
# -----------------------------
elif tab_choice == "📦 État Stock":
    st.header("État du stock")
    df_stock = load_sheet("Stock")
    df_ventes = load_sheet("Ventes")
    if not df_stock.empty:
        df_stock.columns = df_stock.columns.str.strip()
        stock_reel = df_stock.groupby("Produit")["Quantité"].sum().reset_index()
        if not df_ventes.empty:
            df_ventes.columns = df_ventes.columns.str.strip()
            ventes_group = df_ventes.groupby("Produit")["Quantité"].sum().reset_index()
            stock_reel = stock_reel.merge(ventes_group, on="Produit", how="left", suffixes=('', '_vendu'))
            stock_reel['Quantité_vendu'] = stock_reel['Quantité_vendu'].fillna(0)
            stock_reel['Stock restant'] = stock_reel['Quantité'] - stock_reel['Quantité_vendu']
        else:
            stock_reel['Stock restant'] = stock_reel['Quantité']
        st.dataframe(stock_reel[['Produit', 'Stock restant']], use_container_width=True)
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
