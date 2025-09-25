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
        data = sheet.get_all_records(expected_headers=None)  # Evite problème duplicate headers
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Erreur lors du chargement de la feuille '{sheet_name}': {e}")
        return pd.DataFrame()

# -----------------------------
# 🔹 Données initiales
# -----------------------------
df_produits = load_sheet("Produits")
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
        # Marque
        marques_dispo = df_produits['Marque'].dropna().unique().tolist() if not df_produits.empty else []
        marque_sel = st.selectbox("Marque", [""] + marques_dispo)

        # Catégorie
        categories_dispo = df_produits[df_produits['Marque'] == marque_sel]['Catégorie'].dropna().unique().tolist() if marque_sel else []
        categorie_sel = st.selectbox("Catégorie", [""] + categories_dispo)

        # Famille
        familles_dispo = df_produits[
            (df_produits['Marque'] == marque_sel) & (df_produits['Catégorie'] == categorie_sel)
        ]['Famille'].dropna().unique().tolist() if marque_sel and categorie_sel else []
        famille_sel = st.selectbox("Famille", [""] + familles_dispo)

        # Produit
        produits_dispo_filtre = df_produits[
            (df_produits['Marque'] == marque_sel) &
            (df_produits['Catégorie'] == categorie_sel) &
            (df_produits['Famille'] == famille_sel)
        ]['Produit'].dropna().unique().tolist() if marque_sel and categorie_sel and famille_sel else []
        produit_stock = st.selectbox("Produit", [""] + produits_dispo_filtre)

        quantite_stock = st.number_input("Quantité achetée", min_value=1, step=1)
        prix_achat = st.number_input("Prix d'achat unitaire", min_value=0.0, step=1.0, disabled=True)

        if st.form_submit_button("Ajouter au stock"):
            if not produit_stock:
                st.error("⚠️ Veuillez sélectionner un produit.")
            else:
                row = [str(datetime.now()), marque_sel, categorie_sel, famille_sel, produit_stock, quantite_stock, prix_achat]
                spreadsheet.worksheet("Stock").append_row(row)
                st.success(f"{quantite_stock} x {produit_stock} ajouté(s) au stock.")

# -----------------------------
# Onglet 2 : Enregistrer Vente
# -----------------------------
elif tab_choice == "💰 Enregistrer Vente":
    st.header("Enregistrer une vente multi-produits")

    with st.form("form_vente_multi"):
        # Marque
        marques_dispo = df_produits['Marque'].dropna().unique().tolist() if not df_produits.empty else []
        marque_sel = st.selectbox("Marque", [""] + marques_dispo, key="marque_vente")

        # Catégorie
        categories_dispo = df_produits[df_produits['Marque'] == marque_sel]['Catégorie'].dropna().unique().tolist() if marque_sel else []
        categorie_sel = st.selectbox("Catégorie", [""] + categories_dispo, key="categorie_vente")

        # Famille
        familles_dispo = df_produits[
            (df_produits['Marque'] == marque_sel) & (df_produits['Catégorie'] == categorie_sel)
        ]['Famille'].dropna().unique().tolist() if marque_sel and categorie_sel else []
        famille_sel = st.selectbox("Famille", [""] + familles_dispo, key="famille_vente")

        # Produit
        produits_dispo_filtre = df_produits[
            (df_produits['Marque'] == marque_sel) &
            (df_produits['Catégorie'] == categorie_sel) &
            (df_produits['Famille'] == famille_sel)
        ]['Produit'].dropna().unique().tolist() if marque_sel and categorie_sel and famille_sel else []
        produit_vente = st.selectbox("Produit vendu *", [""] + produits_dispo_filtre, key="produit_vente")

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

        # Prix unitaire
        prix_unitaire = float(
            df_produits.loc[df_produits['Produit'] == produit_vente, 'Prix unitaire'].values[0]
        ) if not df_produits.empty and produit_vente else 0.0
        total_vente = prix_unitaire * quantite_vente

        st.write(
            f"Prix unitaire : {prix_unitaire} | "
            f"Total HT : {total_vente:.2f} | "
            f"Total TTC : {round(total_vente * 1.19, 2)}"
        )

        # Ajout au panier
        if st.form_submit_button("Ajouter au panier"):
            if not produit_vente or quantite_vente <= 0 or not client_nom.strip() or not client_tel.strip():
                st.error("⚠️ Veuillez remplir tous les champs obligatoires : Produit, Quantité, Nom et Téléphone.")
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

    # Affichage du panier
    if st.session_state.panier:
        st.subheader("Panier actuel (modifiable)")
        df_panier = pd.DataFrame(st.session_state.panier)
        st.dataframe(df_panier, use_container_width=True, hide_index=True)

        indices_a_supprimer = []
        for i, item in enumerate(st.session_state.panier):
            col1, col2, col3 = st.columns([4, 2, 1])
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

        # Enregistrer la vente
        if st.button("Enregistrer la vente", key="enregistrer_vente"):
            df_stock = load_sheet("Stock")
            df_ventes = load_sheet("Ventes")
            vente_valide = True

            # Vérification stock
            for item in st.session_state.panier:
                stock_dispo = df_stock[
                    (df_stock['Marque'] == item["Marque"]) &
                    (df_stock['Catégorie'] == item["Catégorie"]) &
                    (df_stock['Famille'] == item["Famille"]) &
                    (df_stock['Produit'] == item["Produit"])
                ]['Quantité'].sum() if not df_stock.empty else 0

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
                st.success("Vente enregistrée avec succès !")
                st.session_state.panier = []

# -----------------------------
# Onglet 3 : État Stock
# -----------------------------
elif tab_choice == "📦 État Stock":
    st.header("État du stock")
    df_stock = load_sheet("Stock")
    df_ventes = load_sheet("Ventes")
    if not df_stock.empty:
        stock_reel = df_stock.groupby(["Marque", "Catégorie", "Famille", "Produit"])["Quantité"].sum().reset_index()
        if not df_ventes.empty:
            ventes_group = df_ventes.groupby(["Marque", "Catégorie", "Famille", "Produit"])["Quantité"].sum().reset_index()
            stock_reel = stock_reel.merge(ventes_group, on=["Marque", "Catégorie", "Famille", "Produit"], how="left", suffixes=('', '_vendu'))
            stock_reel['Quantité_vendu'] = stock_reel['Quantité_vendu'].fillna(0)
            stock_reel['Stock restant'] = stock_reel['Quantité'] - stock_reel['Quantité_vendu']
        else:
            stock_reel['Stock restant'] = stock_reel['Quantité']
        st.dataframe(stock_reel[['Marque', 'Catégorie', 'Famille', 'Produit', 'Stock restant']], use_container_width=True)
    else:
        st.write("Aucun stock enregistré.")

# -----------------------------
# Onglet 4 : Historique Ventes
# -----------------------------
elif tab_choice == "📄 Historique Ventes":
    st.header("Historique des ventes")
    try:
        sheet_ventes = spreadsheet.worksheet("Ventes")
        data_ventes = sheet_ventes.get_all_records(expected_headers=None)
        df_ventes = pd.DataFrame(data_ventes)
    except Exception as e:
        st.error(f"Erreur lors du chargement des ventes : {e}")
        df_ventes = pd.DataFrame()
    if not df_ventes.empty:
        st.dataframe(df_ventes, use_container_width=True)
    else:
        st.write("Aucune vente enregistrée.")
