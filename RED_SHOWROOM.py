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
# 🔹 Données initiales
# -----------------------------
df_produits = load_sheet("Produits")
produits_dispo = df_produits['Produit'].dropna().tolist() if not df_produits.empty else []

# -----------------------------
# 🔹 Gestion des onglets
# -----------------------------
tabs_labels = ["🛒 Ajouter Stock", "💰 Enregistrer Vente", "📦 État Stock",
               "📄 Historique Ventes", "💳 Paiements partiels", "🧾 Charges quotidiennes"]
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
        prix_achat = float(df_produits.loc[df_produits['Produit'] == produit_stock, 'Prix unitaire'].values[0]) if not df_produits.empty else 0.0
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

    produit_vente = st.selectbox("Produit vendu *", produits_dispo)
    if produit_vente:
        prix_unitaire = float(df_produits.loc[df_produits['Produit'] == produit_vente, 'Prix unitaire'].values[0])
    else:
        prix_unitaire = 0.0

    quantite_vente = st.number_input("Quantité vendue *", min_value=1, step=1)
    total_ht = prix_unitaire * quantite_vente
    timbre = 100  # Timbre fixe
    tva = round(total_ht * 0.19, 2)
    total_ttc = round(total_ht + timbre + tva, 2)

    st.write(f"Prix unitaire : {prix_unitaire} DA | Total HT : {total_ht} DA | TVA : {tva} DA | TTC : {total_ttc} DA")

    # Infos client
    client_nom = st.text_input("Nom du client *")
    client_email = st.text_input("Email du client")
    client_tel = st.text_input("Téléphone du client *")

    montant_paye = st.number_input(
        "Montant payé par le client",
        min_value=0.0,
        max_value=float(total_ttc),
        value=0.0,
        step=1.0,
        format="%.2f"
    )
    reste_a_payer = total_ttc - montant_paye
    st.write(f"Reste à payer : {reste_a_payer:.2f} DA")

    generer_facture = st.button("Générer la facture")

    if generer_facture:
        df_stock = load_sheet("Stock")
        df_ventes = load_sheet("Ventes")
        vente_valide = True

        stock_dispo_total = df_stock[df_stock['Produit'] == produit_vente]['Quantité'].sum()
        ventes_sum = df_ventes[df_ventes['Produit'] == produit_vente]['Quantité'].sum() if not df_ventes.empty else 0
        stock_reel = stock_dispo_total - ventes_sum

        if quantite_vente > stock_reel:
            st.error(f"Stock insuffisant pour {produit_vente} ! Disponible : {stock_reel}")
            vente_valide = False

        if vente_valide:
            prochain_num = ""
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

            # Enregistrement dans la feuille Ventes
            row_vente = [
                str(datetime.now()), client_nom, client_email, client_tel,
                produit_vente, quantite_vente, prix_unitaire, total_ht,
                total_ttc, montant_paye, reste_a_payer,
                entreprise_rc, prochain_num
            ]
            spreadsheet.worksheet("Ventes").append_row(row_vente)

            # -------------------------------
            # Génération PDF
            # -------------------------------
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(200, 10, txt=entreprise_nom, ln=True, align="C")
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(200, 10, txt="Facture", ln=True, align="C")
            pdf.set_font("Arial", size=12)
            pdf.cell(200, 10, txt=f"Date : {datetime.now().strftime('%d/%m/%Y')}", ln=True)
            pdf.cell(200, 10, txt=f"Facture N° : {prochain_num}", ln=True)
            pdf.ln(5)
            # Facture affichera client Divers
            pdf.cell(200, 10, txt=f"Client : Divers", ln=True)
            pdf.cell(200, 10, txt=f"Téléphone : {client_tel}", ln=True)
            pdf.ln(5)

            pdf.set_font("Arial", 'B', 12)
            pdf.cell(80, 10, "Produit", 1)
            pdf.cell(30, 10, "Qté", 1)
            pdf.cell(30, 10, "Prix HT", 1)
            pdf.cell(25, 10, "Timbre", 1)
            pdf.cell(25, 10, "TVA", 1)
            pdf.cell(30, 10, "Total TTC", 1, ln=True)

            pdf.set_font("Arial", size=12)
            pdf.cell(80, 10, produit_vente, 1)
            pdf.cell(30, 10, str(quantite_vente), 1)
            pdf.cell(30, 10, f"{total_ht:.2f}", 1)
            pdf.cell(25, 10, f"{timbre:.2f}", 1)
            pdf.cell(25, 10, f"{tva:.2f}", 1)
            pdf.cell(30, 10, f"{total_ttc:.2f}", 1, ln=True)

            pdf.set_font("Arial", 'B', 12)
            pdf.cell(160, 10, "Montant en lettres", 1)
            montant_en_lettres = num2words(total_ttc, lang='fr').capitalize() + " DA"
            pdf.cell(30, 10, montant_en_lettres, 1, ln=True)

            pdf_bytes = pdf.output(dest='S').encode('latin1')
            pdf_io = io.BytesIO(pdf_bytes)
            st.download_button(
                label="📄 Télécharger la facture PDF",
                data=pdf_io,
                file_name=f"facture_{prochain_num}.pdf",
                mime="application/pdf"
            )

            st.success(f"✅ Vente enregistrée pour {client_nom}.")

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

# -----------------------------
# Onglet 5 : Paiements partiels
# -----------------------------
elif tab_choice == "💳 Paiements partiels":
    st.header("État des paiements partiels")
    df_ventes = load_sheet("Ventes")
    if not df_ventes.empty:
        df_partiels = df_ventes[df_ventes["Reste à payer"] > 0]
        if not df_partiels.empty:
            st.dataframe(df_partiels[["Produit", "Nom", "Téléphone", "Total TTC", "Montant payé", "Reste à payer"]], use_container_width=True)
        else:
            st.write("Aucun paiement partiel en attente.")
    else:
        st.write("Aucune vente enregistrée.")

# -----------------------------
# Onglet 6 : Charges quotidiennes
# -----------------------------
elif tab_choice == "🧾 Charges quotidiennes":
    st.header("Note de charges quotidiennes")

    if "charges_panier" not in st.session_state:
        st.session_state.charges_panier = []

    ref_charge = f"CHG-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    st.info(f"📌 Référence du document : {ref_charge}")

    types_dispo = ["Autre"]  # Simplifié, ou charger depuis feuille Types_Charges

    with st.form("form_ligne_charge"):
        date_charge = st.date_input("Date", value=datetime.today(), min_value=datetime.today())
        type_charge = st.selectbox("Type de charge *", types_dispo)
        description = st.text_input("Description *")
        fournisseur = st.text_input("Fournisseur / Prestataire")
        montant = st.number_input(" Montant *", min_value=0, step=100)
        add_line = st.form_submit_button("➕ Ajouter la ligne")

    if add_line:
        if not description.strip() or montant <= 0:
            st.error("⚠️ Description et montant obligatoires.")
        else:
            st.session_state.charges_panier.append({
                "Référence": ref_charge,
                "Date": str(date_charge),
                "Type de charge": type_charge,
                "Description": description,
                "Fournisseur / Prestataire": fournisseur,
                "Montant": montant
            })
            st.success("Ligne ajoutée.")

    if st.session_state.charges_panier:
        st.subheader("Lignes en cours")
        df_charges = pd.DataFrame(st.session_state.charges_panier)
        st.dataframe(df_charges, use_container_width=True, hide_index=True)
        total_session = df_charges["Montant"].sum()
        st.markdown(f"### 💰 Total de cette note : {total_session} DA")

        if st.button("✅ Valider et enregistrer les charges"):
            sheet = spreadsheet.worksheet("Charges")
            for line in st.session_state.charges_panier:
                row = [
                    line["Référence"], line["Date"], line["Type de charge"],
                    line["Description"], line["Fournisseur / Prestataire"], line["Montant"]
                ]
                sheet.append_row(row)
            st.success("✅ Charges enregistrées avec succès.")
            st.session_state.charges_panier = []
