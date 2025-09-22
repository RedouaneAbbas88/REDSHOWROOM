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
@st.cache_data(ttl=10)
def load_sheet(sheet_name):
    try:
        sheet = spreadsheet.worksheet(sheet_name)
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Erreur lors du chargement de la feuille '{sheet_name}': {e}")
        return pd.DataFrame()

# ---------------------------------------------------
# 🔹 Données initiales
# ---------------------------------------------------
df_produits = load_sheet("Produits")
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

# -------------------- Onglet 2 : Enregistrer Vente Multi-produits --------------------
with tabs[1]:
    st.header("Enregistrer une vente multi-produits")

    # Initialiser le panier
    if "panier" not in st.session_state:
        st.session_state.panier = []

    with st.form("form_vente_multi"):
        produit_vente = st.selectbox("Produit vendu", produits_dispo)
        quantite_vente = st.number_input("Quantité vendue", min_value=1, step=1)
        client_nom = st.text_input("Nom du client")
        client_email = st.text_input("Email du client")
        client_tel = st.text_input("Téléphone du client")

        prix_unitaire = float(df_produits.loc[df_produits['Produit'] == produit_vente, 'Prix unitaire'].values[0]) if not df_produits.empty else 0.0
        total_vente = prix_unitaire * quantite_vente
        st.write(f"Prix unitaire : {prix_unitaire} | Total : {total_vente}")

        if st.form_submit_button("Ajouter au panier"):
            st.session_state.panier.append({
                "Produit": produit_vente,
                "Quantité": quantite_vente,
                "Prix unitaire": prix_unitaire,
                "Total": total_vente
            })

    # Afficher le panier
    if st.session_state.panier:
        st.subheader("Panier actuel")
        df_panier = pd.DataFrame(st.session_state.panier)
        st.dataframe(df_panier, use_container_width=True)

        if st.button("Enregistrer la vente"):
            # Vérification stock pour chaque produit
            df_stock = load_sheet("Stock")
            df_ventes = load_sheet("Ventes")
            vente_valide = True

            for item in st.session_state.panier:
                stock_dispo = df_stock[df_stock['Produit'] == item["Produit"]]['Quantité'].sum()
                ventes_sum = df_ventes[df_ventes['Produit'] == item["Produit"]]['Quantité'].sum() if not df_ventes.empty else 0
                stock_reel = stock_dispo - ventes_sum
                if item["Quantité"] > stock_reel:
                    st.error(f"Stock insuffisant pour {item['Produit']} ! Disponible : {stock_reel}")
                    vente_valide = False

            if vente_valide:
                # Ajouter les ventes
                for item in st.session_state.panier:
                    row_vente = [str(datetime.now()), client_nom, client_email, client_tel,
                                 item["Produit"], item["Quantité"], item["Prix unitaire"], item["Total"]]
                    spreadsheet.worksheet("Ventes").append_row(row_vente)

                st.success(f"Vente enregistrée pour {client_nom} avec {len(st.session_state.panier)} produits.")

                # Génération PDF simple
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", 'B', 14)
                pdf.cell(200, 10, txt="FACTURE SHOWROOM", ln=True, align="C")
                pdf.ln(5)

                # Coordonnées fixes de l'entreprise
                entreprise_nom = "NORTH AFRICA"
                entreprise_adresse = "123 Rue Principale, Alger"
                entreprise_rc = "RC: 123456"
                entreprise_nif = "NIF: 654321"
                entreprise_art = "ART: 987654"

                # Coordonnées client
                pdf.set_font("Arial", size=12)
                pdf.cell(200, 5, txt=f"Client: {client_nom}", ln=True)
                pdf.cell(200, 5, txt=f"Email: {client_email} | Tel: {client_tel}", ln=True)
                pdf.ln(5)

                # Tableau produits
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", 'B', 14)
                pdf.cell(200, 10, txt="FACTURE SHOWROOM", ln=True, align="C")
                pdf.ln(5)

                # Coordonnées entreprise
                pdf.set_font("Arial", size=12)
                pdf.cell(200, 5, txt=f"{entreprise_nom}", ln=True)
                pdf.cell(200, 5, txt=f"{entreprise_adresse}", ln=True)
                pdf.cell(200, 5, txt=f"{entreprise_rc} | {entreprise_nif} | {entreprise_art}", ln=True)
                pdf.ln(5)

                # Coordonnées client
                pdf.cell(200, 5, txt=f"Client: {client_nom}", ln=True)
                pdf.cell(200, 5, txt=f"Email: {client_email} | Tel: {client_tel}", ln=True)
                pdf.cell(200, 5,
                         txt=f"RC: {client_rc} | NIF: {client_nif} | ART: {client_art} | Adresse: {client_adresse}",
                         ln=True)
                pdf.ln(5)

                # Tableau produits
                pdf.cell(50, 10, "Produit", 1)
                pdf.cell(30, 10, "Quantité", 1)
                pdf.cell(40, 10, "Prix HT", 1)
                pdf.cell(40, 10, "Total HT", 1)
                pdf.cell(30, 10, "Total TTC", 1, ln=True)

                for item in st.session_state.panier:
                    total_ttc = round(item["Total"] * 1.19, 2)  # Calcul TTC
                    pdf.cell(50, 10, str(item["Produit"]), 1)
                    pdf.cell(30, 10, str(item["Quantité"]), 1)
                    pdf.cell(40, 10, str(item["Prix unitaire"]), 1)
                    pdf.cell(40, 10, str(item["Total"]), 1)
                    pdf.cell(30, 10, str(total_ttc), 1, ln=True)

# -------------------- Onglet 3 : État Stock --------------------
with tabs[2]:
    st.header("État du stock")
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
