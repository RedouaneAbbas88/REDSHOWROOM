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
        df = pd.DataFrame(data)
        # Nettoyage des noms de colonnes
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
    marques_dispo = df_produits['Marque'].unique().tolist()
    categories_dispo = df_produits['Catégorie'].unique().tolist()
    familles_dispo = df_produits['Famille'].unique().tolist()
    produits_dispo = df_produits['Produit'].tolist()
else:
    marques_dispo = []
    categories_dispo = []
    familles_dispo = []
    produits_dispo = []

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
        marque_stock = st.selectbox("Marque", marques_dispo)
        categorie_stock = st.selectbox(
            "Catégorie",
            df_produits[df_produits['Marque'] == marque_stock]['Catégorie'].unique() if marque_stock else []
        )
        famille_stock = st.selectbox(
            "Famille",
            df_produits[(df_produits['Marque'] == marque_stock) &
                        (df_produits['Catégorie'] == categorie_stock)]['Famille'].unique() if categorie_stock else []
        )
        produit_stock = st.selectbox(
            "Produit",
            df_produits[(df_produits['Marque'] == marque_stock) &
                        (df_produits['Catégorie'] == categorie_stock) &
                        (df_produits['Famille'] == famille_stock)]['Produit'].tolist() if famille_stock else []
        )
        quantite_stock = st.number_input("Quantité achetée", min_value=1, step=1)
        prix_achat = st.number_input("Prix d'achat unitaire", min_value=0.0, step=1.0, disabled=True)

        if st.form_submit_button("Ajouter au stock"):
            row = [str(datetime.now()), marque_stock, categorie_stock, famille_stock, produit_stock, quantite_stock, prix_achat]
            spreadsheet.worksheet("Stock").append_row(row)
            st.success(f"{quantite_stock} x {produit_stock} ajouté(s) au stock.")

# -----------------------------
# Onglet 2 : Enregistrer Vente
# -----------------------------
elif tab_choice == "💰 Enregistrer Vente":
    st.header("Enregistrer une vente multi-produits")
    df_stock = load_sheet("Stock")
    df_ventes = load_sheet("Ventes")
    for col in ["Marque", "Catégorie", "Famille", "Produit", "Quantité"]:
        if col not in df_stock.columns:
            df_stock[col] = ""
        if col not in df_ventes.columns:
            df_ventes[col] = 0

    with st.form("form_vente_multi"):
        marque_vente = st.selectbox("Marque", marques_dispo)
        categorie_vente = st.selectbox(
            "Catégorie",
            df_produits[df_produits['Marque'] == marque_vente]['Catégorie'].unique() if marque_vente else []
        )
        famille_vente = st.selectbox(
            "Famille",
            df_produits[(df_produits['Marque'] == marque_vente) &
                        (df_produits['Catégorie'] == categorie_vente)]['Famille'].unique() if categorie_vente else []
        )
        produit_vente = st.selectbox(
            "Produit vendu *",
            df_produits[(df_produits['Marque'] == marque_vente) &
                        (df_produits['Catégorie'] == categorie_vente) &
                        (df_produits['Famille'] == famille_vente)]['Produit'].tolist() if famille_vente else []
        )
        quantite_vente = st.number_input("Quantité vendue *", min_value=1, step=1)

        # Infos client
        client_nom = st.text_input("Nom du client *")
        client_email = st.text_input("Email du client")
        client_tel = st.text_input("Téléphone du client *")
        client_rc = st.text_input("RC du client")
        client_nif = st.text_input("NIF du client")
        client_art = st.text_input("ART du client")
        client_adresse = st.text_input("Adresse du client")

        generer_facture = st.checkbox("Générer une facture PDF")

        prix_unitaire = float(df_produits.loc[df_produits['Produit'] == produit_vente, 'Prix unitaire'].values[0]) if not df_produits.empty else 0.0
        total_vente = prix_unitaire * quantite_vente
        st.write(f"Prix unitaire : {prix_unitaire} | Total HT : {total_vente:.2f} | Total TTC : {round(total_vente*1.19,2)}")

        if st.form_submit_button("Ajouter au panier"):
            if not produit_vente or quantite_vente <= 0 or not client_nom.strip() or not client_tel.strip():
                st.error("⚠️ Merci de remplir tous les champs obligatoires : Produit, Quantité, Nom du client et Téléphone.")
            else:
                st.session_state.panier.append({
                    "Marque": marque_vente,
                    "Catégorie": categorie_vente,
                    "Famille": famille_vente,
                    "Produit": produit_vente,
                    "Quantité": quantite_vente,
                    "Prix unitaire": prix_unitaire,
                    "Total": total_vente
                })
                st.success(f"{quantite_vente} x {produit_vente} ajouté(s) au panier.")

    # Affichage et modification du panier
    if st.session_state.panier:
        st.subheader("Panier actuel (modifiable)")
        df_panier = pd.DataFrame(st.session_state.panier)
        st.dataframe(df_panier, use_container_width=True, hide_index=True)

        indices_a_supprimer = []
        for i, item in enumerate(st.session_state.panier):
            col1, col2, col3 = st.columns([4,2,1])
            with col1:
                st.write(item["Produit"])
            with col2:
                nouvelle_quantite = st.number_input(f"Quantité {i}", min_value=1, value=item["Quantité"], key=f"qty_{i}")
                st.session_state.panier[i]["Quantité"] = nouvelle_quantite
                st.session_state.panier[i]["Total"] = nouvelle_quantite * item["Prix unitaire"]
            with col3:
                if st.button("❌ Supprimer", key=f"del_{i}"):
                    indices_a_supprimer.append(i)
        for index in sorted(indices_a_supprimer, reverse=True):
            st.session_state.panier.pop(index)

        st.markdown("---")

        # Enregistrement des ventes
        if st.button("Enregistrer la vente", key="enregistrer_vente"):
            vente_valide = True
            for item in st.session_state.panier:
                stock_dispo = df_stock[
                    (df_stock['Marque'] == item["Marque"]) &
                    (df_stock['Catégorie'] == item["Catégorie"]) &
                    (df_stock['Famille'] == item["Famille"]) &
                    (df_stock['Produit'] == item["Produit"])
                ]['Quantité'].sum()
                ventes_sum = df_ventes[
                    (df_ventes['Marque'] == item["Marque"]) &
                    (df_ventes['Catégorie'] == item["Catégorie"]) &
                    (df_ventes['Famille'] == item["Famille"]) &
                    (df_ventes['Produit'] == item["Produit"])
                ]['Quantité'].sum() if not df_ventes.empty else 0
                stock_reel = stock_dispo - ventes_sum
                if item["Quantité"] > stock_reel:
                    st.error(f"Stock insuffisant pour {item['Produit']} ! Disponible : {stock_reel}")
                    vente_valide = False

            if vente_valide:
                prochain_num = ""
                if generer_facture:
                    factures_existantes = df_ventes[df_ventes["Numéro de facture"].notnull()] if not df_ventes.empty else pd.DataFrame()
                    if not factures_existantes.empty:
                        numeros_valides = factures_existantes["Numéro de facture"].str.split("/").str[0]
                        numeros_valides = numeros_valides[numeros_valides.str.isnumeric()].astype(int)
                        dernier_num = numeros_valides.max() if not numeros_valides.empty else 0
                    else:
                        dernier_num = 0
                    prochain_num = f"{dernier_num + 1:03d}/2025"

                entreprise_nom = "NORTH AFRICA ELECTRONICS"
                entreprise_adresse = "123 Rue Principale, Alger"
                entreprise_rc = "RC: 16/00-1052043 B23"
                entreprise_nif = "NIF: 002316105204354"
                entreprise_art = "ART: 002316300298344"

                # Ajout ventes Google Sheet
                for item in st.session_state.panier:
                    row_vente = [
                        str(datetime.now()), client_nom, client_email, client_tel,
                        client_rc, client_nif, client_art, client_adresse,
                        item["Marque"], item["Catégorie"], item["Famille"], item["Produit"],
                        item["Quantité"], item["Prix unitaire"], item["Total"],
                        round(item["Total"] * 1.19, 2),
                        entreprise_rc, entreprise_nif, entreprise_art, entreprise_adresse,
                        prochain_num
                    ]
                    spreadsheet.worksheet("Ventes").append_row(row_vente)

                st.success(f"Vente enregistrée pour {client_nom} avec {len(st.session_state.panier)} produits.")
                st.session_state.panier = []

# -----------------------------
# Onglet 3 : État Stock
# -----------------------------
elif tab_choice == "📦 État Stock":
    st.header("État du stock")
    df_stock = load_sheet("Stock")
    if not df_stock.empty:
        df_stock.columns = df_stock.columns.str.strip()
        stock_reel = df_stock.groupby("Produit")["Quantité"].sum().reset_index()
        st.dataframe(stock_reel[['Produit','Quantité']], use_container_width=True)
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
