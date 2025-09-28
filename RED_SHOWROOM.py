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
        st.error(f"Erreur lors du chargement de la feuille '{sheet_name}': {e}")
        return pd.DataFrame()

# -----------------------------
# 🔹 Fonction pour convertir en float proprement
# -----------------------------
def safe_float(valeur):
    try:
        return float(str(valeur).replace(",", ".").strip())
    except:
        return 0.0

# -----------------------------
# 🔹 Données initiales
# -----------------------------
df_produits = load_sheet("Produits")
produits_dispo = df_produits['Produit'].dropna().tolist() if not df_produits.empty else []

# -----------------------------
# 🔹 Gestion des onglets
# -----------------------------
tabs_labels = ["🛒 Ajouter Stock", "💰 Enregistrer Vente", "📦 État Stock", "📄 Historique Ventes", "💳 Paiements partiels"]
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
        produit_stock = st.selectbox("Produit *", produits_dispo)
        prix_achat = 0.0
        if produit_stock and not df_produits.empty:
            valeur = df_produits.loc[df_produits['Produit'] == produit_stock, 'Prix unitaire'].values[0]
            prix_achat = safe_float(valeur)

        quantite_stock = st.number_input("Quantité achetée", min_value=1, step=1)

        if st.form_submit_button("Ajouter au stock"):
            row = [str(datetime.now()), produit_stock, quantite_stock, prix_achat]
            spreadsheet.worksheet("Stock").append_row(row)
            st.success(f"{quantite_stock} {produit_stock} ajouté(s) au stock.")

# -----------------------------
# Onglet 2 : Enregistrer Vente
# -----------------------------
elif tab_choice == "💰 Enregistrer Vente":
    st.header("Enregistrer une vente multi-produits")

    produit_vente = st.selectbox("Produit vendu *", produits_dispo, key="produit_vente")
    prix_unitaire = 0.0
    if produit_vente and not df_produits.empty:
        valeur = df_produits.loc[df_produits['Produit'] == produit_vente, 'Prix unitaire'].values[0]
        prix_unitaire = safe_float(valeur)

    quantite_vente = st.number_input("Quantité vendue *", min_value=1, step=1, key="quantite_vente")

    # Infos client
    client_nom = st.text_input("Nom du client *", key="client_nom")
    client_email = st.text_input("Email du client", key="client_email")
    client_tel = st.text_input("Téléphone du client *", key="client_tel")
    client_rc = st.text_input("RC du client", key="client_rc")
    client_nif = st.text_input("NIF du client", key="client_nif")
    client_art = st.text_input("ART du client", key="client_art")
    client_adresse = st.text_input("Adresse du client", key="client_adresse")

    # 🔹 Calculs automatiques (TTC seulement à l’écran)
    total_ht = prix_unitaire * quantite_vente
    total_ttc = round(total_ht * 1.19, 2)

    st.write(f"🧾 Total TTC : **{total_ttc:,.2f} DA**")

    montant_paye = st.number_input("Montant payé par le client", min_value=0.0, max_value=total_ttc, step=1.0, key="montant_paye")
    reste_a_payer = round(total_ttc - montant_paye, 2)
    st.write(f"💳 Reste à payer : **{reste_a_payer:,.2f} DA**")

    generer_facture = st.checkbox("Générer une facture PDF", key="generer_facture")

    # Ajouter au panier
    if st.button("➕ Ajouter au panier"):
        if not produit_vente or quantite_vente <= 0 or not client_nom.strip() or not client_tel.strip():
            st.error("⚠️ Merci de remplir tous les champs obligatoires.")
        else:
            st.session_state.panier.append({
                "Produit": produit_vente,
                "Quantité": quantite_vente,
                "Prix unitaire": prix_unitaire,
                "Total HT": total_ht,
                "Total TTC": total_ttc,
                "Montant payé": montant_paye,
                "Reste à payer": reste_a_payer
            })
            st.success(f"{quantite_vente} x {produit_vente} ajouté(s) au panier.")

    # Affichage du panier
    if st.session_state.panier:
        st.subheader("Panier actuel")
        df_panier = pd.DataFrame(st.session_state.panier)
        st.dataframe(df_panier, use_container_width=True, hide_index=True)

        # Enregistrer la vente
        if st.button("💾 Enregistrer la vente"):
            df_stock = load_sheet("Stock")
            df_ventes = load_sheet("Ventes")
            vente_valide = True

            # Vérification stock
            for item in st.session_state.panier:
                stock_dispo = df_stock[df_stock['Produit'] == item["Produit"]]['Quantité'].sum()
                ventes_sum = df_ventes[df_ventes['Produit'] == item["Produit"]]['Quantité'].sum() if not df_ventes.empty else 0
                stock_reel = stock_dispo - ventes_sum
                if item["Quantité"] > stock_reel:
                    st.error(f"Stock insuffisant pour {item['Produit']} ! Disponible : {stock_reel}")
                    vente_valide = False

            if vente_valide:
                # Numéro facture incrémenté
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

                # Infos entreprise
                entreprise_nom = "NORTH AFRICA ELECTRONICS"
                entreprise_adresse = "123 Rue Principale, Alger"
                entreprise_rc = "RC: 16/00-1052043 B23"
                entreprise_nif = "NIF: 002316105204354"
                entreprise_art = "ART: 002316300298344"

                # Enregistrement Google Sheet
                for item in st.session_state.panier:
                    row_vente = [
                        str(datetime.now()), client_nom, client_email, client_tel,
                        client_rc, client_nif, client_art, client_adresse,
                        item["Produit"], item["Quantité"], item["Prix unitaire"], item["Total HT"],
                        item["Total TTC"], item["Montant payé"], item["Reste à payer"],
                        entreprise_rc, entreprise_nif, entreprise_art, entreprise_adresse,
                        prochain_num
                    ]
                    spreadsheet.worksheet("Ventes").append_row(row_vente)

                # Génération PDF
                if generer_facture:
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", 'B', 14)
                    pdf.cell(200, 10, txt=f"Facture Num : {prochain_num}", ln=True, align="C")
                    pdf.ln(5)
                    pdf.set_font("Arial", size=12)
                    pdf.cell(200, 5, txt=f"{entreprise_nom}", ln=True)
                    pdf.cell(200, 5, txt=f"{entreprise_adresse}", ln=True)
                    pdf.cell(200, 5, txt=f"{entreprise_rc} | {entreprise_nif} | {entreprise_art}", ln=True)
                    pdf.ln(5)
                    pdf.cell(200, 5, txt=f"Client: {client_nom}", ln=True)
                    pdf.cell(200, 5, txt=f"Email: {client_email} | Tel: {client_tel}", ln=True)
                    pdf.ln(5)

                    # Table
                    pdf.cell(60, 10, "Produit", 1)
                    pdf.cell(20, 10, "Qté", 1)
                    pdf.cell(30, 10, "Prix HT", 1)
                    pdf.cell(30, 10, "Total TTC", 1, ln=True)

                    total_ttc_facture, total_paye = 0, 0
                    for item in st.session_state.panier:
                        total_ttc_facture += item["Total TTC"]
                        total_paye += item["Montant payé"]
                        pdf.cell(60, 10, item["Produit"], 1)
                        pdf.cell(20, 10, str(item["Quantité"]), 1)
                        pdf.cell(30, 10, f"{item['Prix unitaire']:,.2f}", 1)
                        pdf.cell(30, 10, f"{item['Total TTC']:,.2f}", 1, ln=True)

                    # Totaux
                    total_reste = total_ttc_facture - total_paye
                    pdf.cell(110, 10, "Total TTC:", 0, align="R")
                    pdf.cell(30, 10, f"{total_ttc_facture:,.2f}", 1, ln=True)
                    pdf.cell(110, 10, "Montant payé:", 0, align="R")
                    pdf.cell(30, 10, f"{total_paye:,.2f}", 1, ln=True)
                    pdf.cell(110, 10, "Reste à payer:", 0, align="R")
                    pdf.cell(30, 10, f"{total_reste:,.2f}", 1, ln=True)

                    # Montant en lettres
                    montant_lettres = num2words(int(total_ttc_facture), lang='fr') + " dinars algériens"
                    pdf.ln(10)
                    pdf.set_font("Arial", 'I', 11)
                    pdf.multi_cell(0, 10, f"Arrêté la présente facture à la somme de : {montant_lettres}")

                    pdf_bytes = pdf.output(dest='S').encode('latin1')
                    pdf_io = io.BytesIO(pdf_bytes)
                    st.download_button(label="📥 Télécharger la facture", data=pdf_io,
                                       file_name=f"facture_{client_nom}_{prochain_num}.pdf", mime="application/pdf")

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

# -----------------------------
# Onglet 5 : Paiements partiels
# -----------------------------
elif tab_choice == "💳 Paiements partiels":
    st.header("État des paiements partiels")
    df_ventes = load_sheet("Ventes")
    if not df_ventes.empty:
        df_partiels = df_ventes[df_ventes["Reste à payer"] > 0]
        if not df_partiels.empty:
            st.dataframe(df_partiels[["Produit", "Nom", "Montant payé", "Reste à payer"]], use_container_width=True)
        else:
            st.write("Aucun paiement partiel en cours.")
    else:
        st.write("Aucune vente enregistrée.")
