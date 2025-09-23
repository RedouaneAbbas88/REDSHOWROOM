import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from fpdf import FPDF
import io
from num2words import num2words

# ---------------------------------------------------
# ⚙️ Configuration Streamlit
# ---------------------------------------------------
st.set_page_config(page_title="Showroom Stock & Vente", layout="wide")
st.title("📊 Gestion Showroom")

# ---------------------------------------------------
# 🔹 Connexion Google Sheets
# ---------------------------------------------------
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
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
# 🔹 Gestion onglet actif
# ---------------------------------------------------
if "active_tab" not in st.session_state:
    st.session_state.active_tab = 0  # par défaut premier onglet

tab_names = ["🛒 Ajouter Stock", "💰 Enregistrer Vente", "📦 État Stock", "📄 Historique Ventes"]
tabs = st.tabs(tab_names)

# ---------------------------------------------------
# Onglet 1 : Ajouter Stock
# ---------------------------------------------------
with tabs[0]:
    st.header("Ajouter du stock")
    with st.form("form_stock"):
        produit_stock = st.selectbox("Produit", produits_dispo)
        quantite_stock = st.number_input("Quantité achetée", min_value=1, step=1)
        prix_achat = st.number_input("Prix d'achat unitaire", min_value=0.0, step=1.0)
        if st.form_submit_button("Ajouter au stock"):
            row = [str(datetime.now()), produit_stock, quantite_stock, prix_achat]
            spreadsheet.worksheet("Stock").append_row(row)
            st.success(f"{quantite_stock} {produit_stock} ajouté(s) au stock.")
            st.session_state.active_tab = 0  # rester dans cet onglet

# ---------------------------------------------------
# Onglet 2 : Enregistrer Vente Multi-produits
# ---------------------------------------------------
with tabs[1]:
    st.header("Enregistrer une vente multi-produits")

    if "panier" not in st.session_state:
        st.session_state.panier = []

    with st.form("form_vente_multi"):
        produit_vente = st.selectbox("Produit vendu", produits_dispo)
        quantite_vente = st.number_input("Quantité vendue", min_value=1, step=1)

        # Infos client
        client_nom = st.text_input("Nom du client")
        client_email = st.text_input("Email du client")
        client_tel = st.text_input("Téléphone du client")
        client_rc = st.text_input("RC du client")
        client_nif = st.text_input("NIF du client")
        client_art = st.text_input("ART du client")
        client_adresse = st.text_input("Adresse du client")

        # Case à cocher pour générer facture
        generer_facture = st.checkbox("Générer une facture PDF")

        # Prix produit
        prix_unitaire = float(df_produits.loc[df_produits['Produit'] == produit_vente, 'Prix unitaire'].values[0]) if not df_produits.empty else 0.0
        total_vente = prix_unitaire * quantite_vente
        st.write(f"Prix unitaire : {prix_unitaire} | Total HT : {total_vente:.2f} | Total TTC : {round(total_vente*1.19,2)}")

        if st.form_submit_button("Ajouter au panier"):
            st.session_state.panier.append({
                "Produit": produit_vente,
                "Quantité": quantite_vente,
                "Prix unitaire": prix_unitaire,
                "Total": total_vente
            })
            st.session_state.active_tab = 1  # rester onglet ventes

    # ---------------------------------------------------
    # Affichage du panier modifiable
    # ---------------------------------------------------
    if st.session_state.panier:
        st.subheader("Panier actuel (modifiable)")

        # Tableau complet
        df_panier = pd.DataFrame(st.session_state.panier)
        st.dataframe(df_panier, use_container_width=True)

        # Champs modifiables et suppression
        indices_a_supprimer = []
        for i, item in enumerate(st.session_state.panier):
            col1, col2, col3 = st.columns([4, 2, 1])
            with col1:
                st.write(item["Produit"])
            with col2:
                nouvelle_quantite = st.number_input(
                    f"Quantité {i}", min_value=1, value=item["Quantité"], key=f"qty_{i}"
                )
                st.session_state.panier[i]["Quantité"] = nouvelle_quantite
                st.session_state.panier[i]["Total"] = nouvelle_quantite * item["Prix unitaire"]
            with col3:
                if st.button("❌ Supprimer", key=f"del_{i}"):
                    indices_a_supprimer.append(i)
                    st.session_state.active_tab = 1

        for index in sorted(indices_a_supprimer, reverse=True):
            st.session_state.panier.pop(index)

        st.markdown("---")

        # Bouton pour enregistrer la vente
        if st.button("Enregistrer la vente", key="enregistrer_vente"):
            st.session_state.active_tab = 1
            df_stock = load_sheet("Stock")
            df_ventes = load_sheet("Ventes")
            vente_valide = True

            # Vérif stock
            for item in st.session_state.panier:
                stock_dispo = df_stock[df_stock['Produit'] == item["Produit"]]['Quantité'].sum()
                ventes_sum = df_ventes[df_ventes['Produit'] == item["Produit"]]['Quantité'].sum() if not df_ventes.empty else 0
                stock_reel = stock_dispo - ventes_sum
                if item["Quantité"] > stock_reel:
                    st.error(f"Stock insuffisant pour {item['Produit']} ! Disponible : {stock_reel}")
                    vente_valide = False

            if vente_valide:
                # Générer numéro de facture si demandé
                if generer_facture:
                    factures_existantes = df_ventes[df_ventes["Numéro de facture"].notnull()] if not df_ventes.empty else pd.DataFrame()
                    if not factures_existantes.empty:
                        numeros_valides = factures_existantes["Numéro de facture"].str.split("/").str[0]
                        numeros_valides = numeros_valides[numeros_valides.str.isnumeric()].astype(int)
                        dernier_num = numeros_valides.max() if not numeros_valides.empty else 0
                    else:
                        dernier_num = 0
                    prochain_num = f"{dernier_num + 1:03d}/2025"
                else:
                    prochain_num = ""

                # Infos entreprise
                entreprise_nom = "NORTH AFRICA ELECTRONICS"
                entreprise_adresse = "123 Rue Principale, Alger"
                entreprise_rc = "RC: 16/00-1052043 B23"
                entreprise_nif = "NIF: 002316105204354"
                entreprise_art = "ART: 002316300298344"

                # Ajouter ventes à Google Sheet
                for item in st.session_state.panier:
                    row_vente = [
                        str(datetime.now()), client_nom, client_email, client_tel,
                        client_rc, client_nif, client_art, client_adresse,
                        item["Produit"], item["Quantité"], item["Prix unitaire"], item["Total"],
                        round(item["Total"] * 1.19, 2),
                        entreprise_rc, entreprise_nif, entreprise_art, entreprise_adresse,
                        prochain_num
                    ]
                    spreadsheet.worksheet("Ventes").append_row(row_vente)

                st.success(f"Vente enregistrée pour {client_nom} avec {len(st.session_state.panier)} produits.")

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
                    pdf.cell(200, 5, txt=f"RC: {client_rc} | NIF: {client_nif} | ART: {client_art} | Adresse: {client_adresse}", ln=True)
                    pdf.ln(5)

                    pdf.cell(50, 10, "Produit", 1)
                    pdf.cell(30, 10, "Quantité", 1)
                    pdf.cell(40, 10, "Prix HT", 1)
                    pdf.cell(40, 10, "Total HT", 1)
                    pdf.cell(30, 10, "Total TTC", 1, ln=True)

                    total_ht = 0
                    total_ttc = 0
                    for item in st.session_state.panier:
                        total_ht += item["Total"]
                        total_ttc += item["Total"] * 1.19
                        pdf.cell(50, 10, str(item["Produit"]), 1)
                        pdf.cell(30, 10, str(item["Quantité"]), 1)
                        pdf.cell(40, 10, f"{item['Prix unitaire']:.2f}", 1)
                        pdf.cell(40, 10, f"{item['Total']:.2f}", 1)
                        pdf.cell(30, 10, f"{item['Total'] * 1.19:.2f}", 1, ln=True)

                    total_tva = total_ttc - total_ht
                    pdf.cell(160, 10, "Total HT:", 0, align="R")
                    pdf.cell(30, 10, f"{total_ht:.2f}", 1, ln=True)
                    pdf.cell(160, 10, "Total TVA 19%:", 0, align="R")
                    pdf.cell(30, 10, f"{total_tva:.2f}", 1, ln=True)
                    pdf.cell(160, 10, "Total TTC:", 0, align="R")
                    pdf.cell(30, 10, f"{total_ttc:.2f}", 1, ln=True)

                    ttc_int = int(total_ttc)
                    ttc_centimes = int(round((total_ttc - ttc_int) * 100))
                    if ttc_centimes > 0:
                        montant_lettres = (
                            num2words(ttc_int, lang='fr') + " dinars et " +
                            num2words(ttc_centimes, lang='fr') + " centimes algériens"
                        )
                    else:
                        montant_lettres = num2words(ttc_int, lang='fr') + " dinars algériens"

                    pdf.ln(10)
                    pdf.set_font("Arial", 'I', 11)
                    pdf.multi_cell(0, 10, f"Arrêté la présente facture à la somme de : {montant_lettres}")

                    pdf_bytes = pdf.output(dest='S').encode('latin1')
                    pdf_io = io.BytesIO(pdf_bytes)

                    st.download_button(
                        label="📥 Télécharger la facture",
                        data=pdf_io,
                        file_name=f"facture_{client_nom}_{prochain_num}.pdf",
                        mime="application/pdf"
                    )

                st.session_state.panier = []

# ---------------------------------------------------
# Onglet 3 : État Stock
# ---------------------------------------------------
with tabs[2]:
    st.header("État du stock")
    df_stock = load_sheet("Stock")
    df_ventes = load_sheet("Ventes")

    if not df_stock.empty and "Produit" in df_stock.columns and "Quantité" in df_stock.columns:
        stock_reel = df_stock.groupby("Produit")["Quantité"].sum().reset_index()
        if not df_ventes.empty and "Produit" in df_ventes.columns and "Quantité" in df_ventes.columns:
            ventes_group = df_ventes.groupby("Produit")["Quantité"].sum().reset_index()
            stock_reel = stock_reel.merge(ventes_group, on="Produit", how="left", suffixes=('', '_vendu'))
            stock_reel['Quantité_vendu'] = stock_reel['Quantité_vendu'].fillna(0)
            stock_reel['Stock restant'] = stock_reel['Quantité'] - stock_reel['Quantité_vendu']
        else:
            stock_reel['Stock restant'] = stock_reel['Quantité']

        st.dataframe(stock_reel[['Produit', 'Stock restant']], use_container_width=True)
    else:
        st.write("Aucun stock enregistré.")

# ---------------------------------------------------
# Onglet 4 : Historique Ventes
# ---------------------------------------------------
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
