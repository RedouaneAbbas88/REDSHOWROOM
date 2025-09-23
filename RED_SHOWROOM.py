import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from fpdf import FPDF
import base64
import datetime

# -------------------------------
# Connexion Google Sheets
# -------------------------------
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

# Ouvrir le fichier et la feuille
spreadsheet = client.open("Gestion_Stock_Ventes")
stocks_sheet = spreadsheet.worksheet("Stocks")
ventes_sheet = spreadsheet.worksheet("Ventes")

# -------------------------------
# Fonctions utilitaires
# -------------------------------
def charger_stocks():
    data = stocks_sheet.get_all_records()
    return pd.DataFrame(data)

def enregistrer_stock(produit, quantite, prix):
    stocks_sheet.append_row([produit, quantite, prix])

def maj_stock(produit, quantite_vendue):
    df = charger_stocks()
    if produit in df["Produit"].values:
        index = df[df["Produit"] == produit].index[0]
        nouvelle_qte = int(df.loc[index, "Quantité"]) - quantite_vendue
        stocks_sheet.update_cell(index+2, 2, nouvelle_qte)

def generer_numero_facture():
    factures_existantes = pd.DataFrame(ventes_sheet.get_all_records())
    if not factures_existantes.empty and "Numéro de facture" in factures_existantes.columns:
        try:
            dernier_num = (
                factures_existantes["Numéro de facture"]
                .str.split("/")
                .str[0]
                .astype(int)
                .max()
            )
        except Exception:
            dernier_num = 0
    else:
        dernier_num = 0
    annee = datetime.datetime.now().year
    return f"{dernier_num+1:03d}/{annee}"

def enregistrer_vente(vente):
    ventes_sheet.append_row(vente)

def generer_pdf(vente, numero_facture):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)

    # Numéro de facture
    pdf.cell(200, 10, f"Facture N° {numero_facture}", ln=True, align="C")
    pdf.ln(10)

    # Coordonnées client
    pdf.set_font("Arial", "", 12)
    pdf.cell(200, 10, "Coordonnées Client :", ln=True)
    pdf.multi_cell(200, 10, f"Nom : {vente['Nom']}\nAdresse : {vente['Adresse_Client']}")
    pdf.ln(5)

    # Produits
    pdf.cell(200, 10, "Détails Produits :", ln=True)
    for produit in vente["Produits"]:
        pdf.cell(200, 10, f"- {produit['Produit']} x{produit['Quantité']} = {produit['Total']} DA", ln=True)
    pdf.ln(5)

    # Total
    pdf.set_font("Arial", "B", 14)
    pdf.cell(200, 10, f"Total TTC : {vente['Total TTC']} DA", ln=True, align="R")

    # Sauvegarde
    filename = f"facture_{numero_facture}.pdf"
    pdf.output(filename)
    return filename

def telecharger_pdf(path):
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f'<a href="data:application/pdf;base64,{b64}" download="{path}">📥 Télécharger la facture</a>'

# -------------------------------
# Session State
# -------------------------------
if "panier" not in st.session_state:
    st.session_state.panier = []
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "Ajouter Stock"

# -------------------------------
# Interface principale
# -------------------------------
st.title("📊 Gestion des Stocks et Ventes")

tab_names = ["Ajouter Stock", "Enregistrer Vente", "Historique"]

# Correction bug onglet actif
if st.session_state.active_tab not in tab_names:
    st.session_state.active_tab = tab_names[0]

tabs = st.tabs(tab_names)

# -------------------------------
# Onglet 1 : Ajouter Stock
# -------------------------------
with tabs[0]:
    st.header("➕ Ajouter du stock")

    produit = st.text_input("Produit")
    quantite = st.number_input("Quantité", min_value=1, step=1)
    prix = st.number_input("Prix unitaire (DA)", min_value=0, step=100)

    if st.button("Enregistrer Stock"):
        enregistrer_stock(produit, quantite, prix)
        st.success(f"{quantite} unités de {produit} ajoutées au stock ✅")
        st.session_state.active_tab = "Ajouter Stock"

# -------------------------------
# Onglet 2 : Enregistrer Vente
# -------------------------------
with tabs[1]:
    st.header("🛒 Enregistrer une vente")

    # Infos client
    nom = st.text_input("Nom du client")
    adresse_client = st.text_input("Adresse du client")

    # Sélection produit
    stocks = charger_stocks()
    if not stocks.empty:
        produit = st.selectbox("Produit", stocks["Produit"].unique())
        quantite = st.number_input("Quantité vendue", min_value=1, step=1)
        if st.button("Ajouter au panier"):
            prix_unit = int(stocks[stocks["Produit"] == produit]["Prix"].values[0])
            total = prix_unit * quantite
            st.session_state.panier.append({"Produit": produit, "Quantité": quantite, "Prix": prix_unit, "Total": total})
            st.success(f"{quantite} x {produit} ajoutés au panier 🛒")
            st.session_state.active_tab = "Enregistrer Vente"

    # Afficher panier
    if st.session_state.panier:
        st.subheader("📋 Panier actuel")
        df_panier = pd.DataFrame(st.session_state.panier)
        st.table(df_panier)

        # Modifier / Supprimer
        for i, item in enumerate(st.session_state.panier):
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                nv_qte = st.number_input(f"Quantité ({item['Produit']})", min_value=1, step=1, value=item["Quantité"], key=f"qte_{i}")
                st.session_state.panier[i]["Quantité"] = nv_qte
                st.session_state.panier[i]["Total"] = nv_qte * item["Prix"]
            with col2:
                if st.button(f"❌ Supprimer {item['Produit']}", key=f"sup_{i}"):
                    st.session_state.panier.pop(i)
                    st.session_state.active_tab = "Enregistrer Vente"
                    st.experimental_rerun()

        total_ttc = sum(item["Total"] for item in st.session_state.panier)
        st.markdown(f"### 💰 Total TTC : {total_ttc} DA")

        if st.button("✅ Enregistrer Vente"):
            numero_facture = generer_numero_facture()
            vente = {
                "Nom": nom,
                "Adresse_Client": adresse_client,
                "Produits": st.session_state.panier,
                "Total TTC": total_ttc
            }
            enregistrer_vente([
                str(datetime.date.today()), nom, "", "", "", "", "", adresse_client,
                ", ".join([p["Produit"] for p in st.session_state.panier]),
                sum(p["Quantité"] for p in st.session_state.panier),
                "", sum(p["Total"] for p in st.session_state.panier),
                total_ttc, "", "", "", "",
                numero_facture
            ])
            for item in st.session_state.panier:
                maj_stock(item["Produit"], item["Quantité"])
            pdf_path = generer_pdf(vente, numero_facture)
            st.markdown(telecharger_pdf(pdf_path), unsafe_allow_html=True)
            st.success("Vente enregistrée et facture générée ✅")
            st.session_state.panier = []
            st.session_state.active_tab = "Enregistrer Vente"

# -------------------------------
# Onglet 3 : Historique
# -------------------------------
with tabs[2]:
    st.header("📜 Historique des ventes")
    ventes = pd.DataFrame(ventes_sheet.get_all_records())
    if not ventes.empty:
        st.dataframe(ventes)
    else:
        st.info("Aucune vente enregistrée pour le moment.")
