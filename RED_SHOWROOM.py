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
# Fonction sélection hiérarchique
# -----------------------------
def selection_produit(df):
    marques_dispo = df['Marque'].unique().tolist() if not df.empty else []
    marque_choisie = st.selectbox("Marque *", marques_dispo)

    categories_dispo = df[df['Marque'] == marque_choisie]['Catégorie'].unique().tolist()
    categorie_choisie = st.selectbox("Catégorie *", categories_dispo)

    familles_dispo = df[(df['Marque'] == marque_choisie) &
                        (df['Catégorie'] == categorie_choisie)]['Famille'].unique().tolist()
    famille_choisie = st.selectbox("Famille *", familles_dispo)

    produits_dispo = df[(df['Marque'] == marque_choisie) &
                        (df['Catégorie'] == categorie_choisie) &
                        (df['Famille'] == famille_choisie)]['Produit'].tolist()
    produit_choisi = st.selectbox("Produit *", produits_dispo)

    prix_unitaire = float(
        df[(df['Marque'] == marque_choisie) &
           (df['Catégorie'] == categorie_choisie) &
           (df['Famille'] == famille_choisie) &
           (df['Produit'] == produit_choisi)]['Prix unitaire'].values[0]
    ) if not df.empty else 0.0

    return marque_choisie, categorie_choisie, famille_choisie, produit_choisi, prix_unitaire

# -----------------------------
# Onglet 1 : Ajouter Stock
# -----------------------------
if tab_choice == "🛒 Ajouter Stock":
    st.header("Ajouter du stock")
    with st.form("form_stock"):
        marque, categorie, famille, produit_stock, prix_achat = selection_produit(df_produits)
        quantite_stock = st.number_input("Quantité achetée", min_value=1, step=1)

        if st.form_submit_button("Ajouter au stock"):
            row = [str(datetime.now()), marque, categorie, famille, produit_stock, quantite_stock, prix_achat]
            spreadsheet.worksheet("Stock").append_row(row)
            st.success(f"{quantite_stock} {produit_stock} ajouté(s) au stock.")

# -----------------------------
# Onglet 2 : Enregistrer Vente
# -----------------------------
elif tab_choice == "💰 Enregistrer Vente":
    st.header("Enregistrer une vente multi-produits")

    with st.form("form_vente_multi"):
        marque, categorie, famille, produit_vente, prix_unitaire = selection_produit(df_produits)
        quantite_vente = st.number_input("Quantité vendue *", min_value=1, step=1)

        client_nom = st.text_input("Nom du client *")
        client_email = st.text_input("Email du client")
        client_tel = st.text_input("Téléphone du client *")
        client_rc = st.text_input("RC du client")
        client_nif = st.text_input("NIF du client")
        client_art = st.text_input("ART du client")
        client_adresse = st.text_input("Adresse du client")

        generer_facture = st.checkbox("Générer une facture PDF")

        total_vente = prix_unitaire * quantite_vente
        st.write(f"Prix unitaire : {prix_unitaire} | Total HT : {total_vente:.2f} | Total TTC : {round(total_vente*1.19,2)}")

        if st.form_submit_button("Ajouter au panier"):
            if not produit_vente or quantite_vente <= 0 or not client_nom.strip() or not client_tel.strip():
                st.error("⚠️ Merci de remplir tous les champs obligatoires.")
            else:
                st.session_state.panier.append({
                    "Marque": marque,
                    "Catégorie": categorie,
                    "Famille": famille,
                    "Produit": produit_vente,
                    "Quantité": quantite_vente,
                    "Prix unitaire": prix_unitaire,
                    "Total": total_vente
                })
                st.success(f"{quantite_vente} x {produit_vente} ajouté(s) au panier.")

    if st.session_state.panier:
        st.subheader("Panier actuel")
        df_panier = pd.DataFrame(st.session_state.panier)
        st.dataframe(df_panier, use_container_width=True, hide_index=True)

        indices_a_supprimer = []
        for i, item in enumerate(st.session_state.panier):
            col1, col2, col3 = st.columns([4,2,1])
            with col1: st.write(item["Produit"])
            with col2:
                nouvelle_quantite = st.number_input(f"Quantité {i}", min_value=1, value=item["Quantité"], key=f"qty_{i}")
                st.session_state.panier[i]["Quantité"] = nouvelle_quantite
                st.session_state.panier[i]["Total"] = nouvelle_quantite * item["Prix unitaire"]
            with col3:
                if st.button("❌ Supprimer", key=f"del_{i}"):
                    indices_a_supprimer.append(i)
        for index in sorted(indices_a_supprimer, reverse=True):
            st.session_state.panier.pop(index)

        if st.button("Enregistrer la vente", key="enregistrer_vente"):
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

                for item in st.session_state.panier:
                    row_vente = [
                        str(datetime.now()), client_nom, client_email, client_tel,
                        client_rc, client_nif, client_art, client_adresse,
                        item["Marque"], item["Catégorie"], item["Famille"],
                        item["Produit"], item["Quantité"], item["Prix unitaire"], item["Total"],
                        round(item["Total"]*1.19, 2),
                        entreprise_rc, entreprise_nif, entreprise_art, entreprise_adresse,
                        prochain_num
                    ]
                    spreadsheet.worksheet("Ventes").append_row(row_vente)

                st.success(f"Vente enregistrée pour {client_nom} avec {len(st.session_state.panier)} produits.")

                if generer_facture:
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", 'B', 14)
                    pdf.cell(200, 10, txt=f"Facture Num : {prochain_num}", ln=True, align="C")
                    pdf.ln(5)
                    pdf.set_font("Arial", size=12)
                    pdf.cell(200,5, txt=f"{entreprise_nom}", ln=True)
                    pdf.cell(200,5, txt=f"{entreprise_adresse}", ln=True)
                    pdf.cell(200,5, txt=f"{entreprise_rc} | {entreprise_nif} | {entreprise_art}", ln=True)
                    pdf.ln(5)
                    pdf.cell(200,5, txt=f"Client: {client_nom}", ln=True)
                    pdf.cell(200,5, txt=f"Email: {client_email} | Tel: {client_tel}", ln=True)
                    pdf.cell(200,5, txt=f"RC: {client_rc} | NIF: {client_nif} | ART: {client_art} | Adresse: {client_adresse}", ln=True)
                    pdf.ln(5)
                    pdf.cell(40, 10, "Marque", 1)
                    pdf.cell(40, 10, "Produit", 1)
                    pdf.cell(20, 10, "Qté", 1)
                    pdf.cell(30, 10, "Prix HT", 1)
                    pdf.cell(30, 10, "Total HT", 1)
                    pdf.cell(30, 10, "Total TTC", 1, ln=True)

                    total_ht, total_ttc = 0, 0
                    for item in st.session_state.panier:
                        total_ht += item["Total"]
                        total_ttc += item["Total"] * 1.19
                        pdf.cell(40,10,item["Marque"],1)
                        pdf.cell(40,10,item["Produit"],1)
                        pdf.cell(20,10,str(item["Quantité"]),1)
                        pdf.cell(30,10,f"{item['Prix unitaire']:.2f}",1)
                        pdf.cell(30,10,f"{item['Total']:.2f}",1)
                        pdf.cell(30,10,f"{item['Total']*1.19:.2f}",1, ln=True)

                    total_tva = total_ttc - total_ht
                    pdf.cell(160,10,"Total HT:",0,align="R")
                    pdf.cell(30,10,f"{total_ht:.2f}",1,ln=True)
                    pdf.cell(160,10,"Total TVA 19%:",0,align="R")
                    pdf.cell(30,10,f"{total_tva:.2f}",1,ln=True)
                    pdf.cell(160,10,"Total TTC:",0,align="R")
                    pdf.cell(30,10,f"{total_ttc:.2f}",1,ln=True)

                    montant_lettres = num2words(int(total_ttc), lang='fr') + " dinars algériens"
                    pdf.ln(10)
                    pdf.set_font("Arial",'I',11)
                    pdf.multi_cell(0,10,f"Arrêté la présente facture à la somme de : {montant_lettres}")

                    pdf_bytes = pdf.output(dest='S').encode('latin1')
                    pdf_io = io.BytesIO(pdf_bytes)
                    st.download_button(label="📥 Télécharger la facture", data=pdf_io,
                                       file_name=f"facture_{client_nom}_{prochain_num}.pdf", mime="application/pdf")

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
