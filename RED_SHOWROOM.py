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
# 🔹 Charger une feuille Google Sheet
# -----------------------------
@st.cache_data(ttl=10)
def load_sheet(sheet_name):
    try:
        sheet = spreadsheet.worksheet(sheet_name)
        expected_headers = ["Date", "Marque", "Catégorie", "Famille", "Produit", "Quantité", "Prix unitaire"]
        data = sheet.get_all_records(expected_headers=expected_headers)
        df = pd.DataFrame(data)
        df = df.loc[:, df.columns.str.strip() != '']  # Supprimer colonnes vides
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Erreur lors du chargement de la feuille '{sheet_name}': {e}")
        return pd.DataFrame()


# -----------------------------
# 🔹 Données initiales
# -----------------------------
df_produits = load_sheet("Produits")
marques_dispo = df_produits['Marque'].dropna().unique().tolist() if not df_produits.empty else []

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
    df_stock = load_sheet("Stock")

    with st.form("form_stock"):
        # Sélection dépendante : Marque → Catégorie → Famille → Produit
        marque_sel = st.selectbox("Marque", marques_dispo)
        categories_dispo = df_produits[df_produits['Marque'] == marque_sel]['Catégorie'].dropna().unique().tolist()
        categorie_sel = st.selectbox("Catégorie", categories_dispo)
        familles_dispo = df_produits[(df_produits['Marque'] == marque_sel) &
                                     (df_produits['Catégorie'] == categorie_sel)]['Famille'].dropna().unique().tolist()
        famille_sel = st.selectbox("Famille", familles_dispo)
        produits_dispo_filtre = df_produits[(df_produits['Marque'] == marque_sel) &
                                            (df_produits['Catégorie'] == categorie_sel) &
                                            (df_produits['Famille'] == famille_sel)]['Produit'].dropna().tolist()
        produit_sel = st.selectbox("Produit", produits_dispo_filtre)

        quantite_stock = st.number_input("Quantité achetée", min_value=1, step=1)
        prix_unitaire = st.number_input("Prix unitaire", min_value=0.0, step=1.0, disabled=True)

        if st.form_submit_button("Ajouter au stock"):
            row = [str(datetime.now()), marque_sel, categorie_sel, famille_sel, produit_sel, quantite_stock,
                   prix_unitaire]
            spreadsheet.worksheet("Stock").append_row(row)
            st.success(f"{quantite_stock} x {produit_sel} ajouté(s) au stock.")

# -----------------------------
# Onglet 2 : Enregistrer Vente
# -----------------------------
elif tab_choice == "💰 Enregistrer Vente":
    st.header("Enregistrer une vente multi-produits")

    with st.form("form_vente_multi"):
        # Sélection dépendante : Marque → Catégorie → Famille → Produit
        marque_sel = st.selectbox("Marque", marques_dispo)
        categories_dispo = df_produits[df_produits['Marque'] == marque_sel]['Catégorie'].dropna().unique().tolist()
        categorie_sel = st.selectbox("Catégorie", categories_dispo)
        familles_dispo = df_produits[(df_produits['Marque'] == marque_sel) &
                                     (df_produits['Catégorie'] == categorie_sel)]['Famille'].dropna().unique().tolist()
        famille_sel = st.selectbox("Famille", familles_dispo)
        produits_dispo_filtre = df_produits[(df_produits['Marque'] == marque_sel) &
                                            (df_produits['Catégorie'] == categorie_sel) &
                                            (df_produits['Famille'] == famille_sel)]['Produit'].dropna().tolist()
        produit_sel = st.selectbox("Produit vendu *", produits_dispo_filtre)

        quantite_vente = st.number_input("Quantité vendue *", min_value=1, step=1)

        # Infos client obligatoires
        client_nom = st.text_input("Nom du client *")
        client_tel = st.text_input("Téléphone du client *")
        client_email = st.text_input("Email du client")
        client_rc = st.text_input("RC du client")
        client_nif = st.text_input("NIF du client")
        client_art = st.text_input("ART du client")
        client_adresse = st.text_input("Adresse du client")

        generer_facture = st.checkbox("Générer une facture PDF")

        prix_unitaire = float(df_produits.loc[df_produits['Produit'] == produit_sel, 'Prix unitaire'].values[
                                  0]) if not df_produits.empty else 0.0
        total_vente = prix_unitaire * quantite_vente
        st.write(
            f"Prix unitaire : {prix_unitaire} | Total HT : {total_vente:.2f} | Total TTC : {round(total_vente * 1.19, 2)}")

        if st.form_submit_button("Ajouter au panier"):
            if not produit_sel or quantite_vente <= 0 or not client_nom.strip() or not client_tel.strip():
                st.error(
                    "⚠️ Merci de remplir tous les champs obligatoires : Produit, Quantité, Nom et Téléphone du client.")
            else:
                st.session_state.panier.append({
                    "Marque": marque_sel,
                    "Catégorie": categorie_sel,
                    "Famille": famille_sel,
                    "Produit": produit_sel,
                    "Quantité": quantite_vente,
                    "Prix unitaire": prix_unitaire,
                    "Total": total_vente
                })
                st.success(f"{quantite_vente} x {produit_sel} ajouté(s) au panier.")

    # Affichage panier
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
                nouvelle_quantite = st.number_input(f"Quantité {i}", min_value=1, value=item["Quantité"],
                                                    key=f"qty_{i}")
                st.session_state.panier[i]["Quantité"] = nouvelle_quantite
                st.session_state.panier[i]["Total"] = nouvelle_quantite * item["Prix unitaire"]
            with col3:
                if st.button("❌ Supprimer", key=f"del_{i}"):
                    indices_a_supprimer.append(i)
        for index in sorted(indices_a_supprimer, reverse=True):
            st.session_state.panier.pop(index)

        st.markdown("---")

        # Enregistrement de la vente
        if st.button("Enregistrer la vente", key="enregistrer_vente"):
            df_stock = load_sheet("Stock")
            df_ventes = load_sheet("Ventes")
            vente_valide = True

            # Vérification stock
            for item in st.session_state.panier:
                mask_stock = (
                        (df_stock['Marque'] == item["Marque"]) &
                        (df_stock['Catégorie'] == item["Catégorie"]) &
                        (df_stock['Famille'] == item["Famille"]) &
                        (df_stock['Produit'] == item["Produit"])
                )
                stock_dispo = df_stock.loc[mask_stock, 'Quantité'].sum() if not df_stock.empty else 0
                ventes_sum = df_ventes[df_ventes['Produit'] == item["Produit"]][
                    'Quantité'].sum() if not df_ventes.empty else 0
                stock_reel = stock_dispo - ventes_sum
                if item["Quantité"] > stock_reel:
                    st.error(f"Stock insuffisant pour {item['Produit']} ! Disponible : {stock_reel}")
                    vente_valide = False

            if vente_valide:
                # Numéro de facture
                prochain_num = ""
                if generer_facture:
                    factures_existantes = df_ventes[
                        df_ventes["Numéro de facture"].notnull()] if not df_ventes.empty else pd.DataFrame()
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

                # Enregistrer dans Google Sheet
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
