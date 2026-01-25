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
    st.write(f"Prix unitaire : {prix_unitaire} DA | Total HT : {total_ht} DA")

    # Montant payé et reste à payer sans timbre
    montant_paye = st.number_input("Montant payé par le client", min_value=0, max_value=total_ht, value=0, step=1)
    reste_a_payer = total_ht - montant_paye
    st.write(f"Reste à payer : {reste_a_payer} DA")

    generer_facture = st.button("Générer la facture PDF")

    # -------------------------------
    # Ajouter au panier
    # -------------------------------
    if st.button("Ajouter au panier"):
        if not produit_vente or quantite_vente <= 0:
            st.error("⚠️ Merci de remplir tous les champs obligatoires.")
        else:
            st.session_state.panier.append({
                "Produit": produit_vente,
                "Quantité": quantite_vente,
                "Prix unitaire": prix_unitaire,
                "Total HT": total_ht,
                "Montant payé": montant_paye,
                "Reste à payer": reste_a_payer
            })
            st.success(f"{quantite_vente} x {produit_vente} ajouté(s) au panier.")

    # -------------------------------
    # Affichage du panier
    # -------------------------------
    if st.session_state.panier:
        st.subheader("Panier actuel")
        df_panier = pd.DataFrame(st.session_state.panier)
        st.dataframe(df_panier[['Produit', 'Quantité', 'Prix unitaire', 'Total HT', 'Montant payé', 'Reste à payer']], use_container_width=True, hide_index=True)

        indices_a_supprimer = []
        for i, item in enumerate(st.session_state.panier):
            col1, col2, col3 = st.columns([4, 2, 1])
            with col2:
                nouvelle_quantite = st.number_input(f"Qté {i}", min_value=1, value=item["Quantité"], key=f"qty_{i}")
                st.session_state.panier[i]["Quantité"] = nouvelle_quantite
                st.session_state.panier[i]["Total HT"] = nouvelle_quantite * item["Prix unitaire"]
                st.session_state.panier[i]["Reste à payer"] = st.session_state.panier[i]["Total HT"] - st.session_state.panier[i]["Montant payé"]
            with col3:
                if st.button("❌ Supprimer", key=f"del_{i}"):
                    indices_a_supprimer.append(i)
        for index in sorted(indices_a_supprimer, reverse=True):
            st.session_state.panier.pop(index)

        # -------------------------------
        # Enregistrer la vente et générer PDF
        # -------------------------------
        if generer_facture:
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
                # Facture PDF
                pdf_facture = FPDF()
                pdf_facture.add_page()
                pdf_facture.set_font("Arial", 'B', 16)
                pdf_facture.cell(200, 10, "NORTH AFRICA ELECTRONICS", ln=True, align="C")
                pdf_facture.set_font("Arial", 'B', 14)
                pdf_facture.cell(200, 10, "Facture", ln=True, align="C")
                pdf_facture.set_font("Arial", size=12)
                pdf_facture.cell(200, 10, f"Date : {datetime.now().strftime('%d/%m/%Y')}", ln=True, align="R")
                pdf_facture.ln(10)

                # Client par défaut
                client_nom = "DIVERS"
                pdf_facture.cell(200, 10, f"Client : {client_nom}", ln=True)
                pdf_facture.ln(5)

                # Tableau produits
                pdf_facture.set_font("Arial", 'B', 12)
                pdf_facture.cell(80, 10, "Produit", 1)
                pdf_facture.cell(30, 10, "Qté", 1)
                pdf_facture.cell(30, 10, "Prix HT", 1)
                pdf_facture.cell(30, 10, "Montant HT", 1, ln=True)

                pdf_facture.set_font("Arial", size=12)
                total_ht_global = 0
                for item in st.session_state.panier:
                    total_ht_global += item["Total HT"]
                    pdf_facture.cell(80, 10, item["Produit"], 1)
                    pdf_facture.cell(30, 10, str(item["Quantité"]), 1)
                    pdf_facture.cell(30, 10, f"{item['Prix unitaire']:.2f}", 1)
                    pdf_facture.cell(30, 10, f"{item['Total HT']:.2f}", 1, ln=True)

                # Calcul timbre et TVA
                timbre = 0.6  # exemple fixe
                tva = (total_ht_global + timbre) * 0.19
                ttc = total_ht_global + timbre + tva

                pdf_facture.ln(5)
                pdf_facture.cell(140, 10, "TOTAL HT", 1)
                pdf_facture.cell(30, 10, f"{total_ht_global:.2f}", 1, ln=True)
                pdf_facture.cell(140, 10, "TIMBRE", 1)
                pdf_facture.cell(30, 10, f"{timbre:.2f}", 1, ln=True)
                pdf_facture.cell(140, 10, "TVA 19%", 1)
                pdf_facture.cell(30, 10, f"{tva:.2f}", 1, ln=True)
                pdf_facture.cell(140, 10, "TOTAL TTC", 1)
                pdf_facture.cell(30, 10, f"{ttc:.2f}", 1, ln=True)

                # Montant en lettres
                montant_lettres = num2words(ttc, lang='fr').upper()
                pdf_facture.ln(5)
                pdf_facture.multi_cell(0, 10, f"Montant en lettres : {montant_lettres} DA", 0)

                pdf_bytes = pdf_facture.output(dest='S').encode('latin1')
                pdf_io = io.BytesIO(pdf_bytes)
                st.download_button(
                    label="📄 Télécharger la facture PDF",
                    data=pdf_io,
                    file_name=f"facture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    mime="application/pdf"
                )

                # Enregistrer la vente dans Google Sheets
                for item in st.session_state.panier:
                    row_vente = [
                        str(datetime.now()), client_nom, "", "",
                        "", "", "", "",
                        item["Produit"], item["Quantité"], item["Prix unitaire"],
                        item["Total HT"], ttc, item["Montant payé"], item["Reste à payer"],
                        "", "", "", "", ""
                    ]
                    spreadsheet.worksheet("Ventes").append_row(row_vente)

                st.success(f"Vente enregistrée et facture générée pour {client_nom}.")
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

# -----------------------------
# Onglet 5 : Paiements partiels
# -----------------------------
elif tab_choice == "💳 Paiements partiels":
    st.header("État des paiements partiels")
    df_ventes = load_sheet("Ventes")
    if not df_ventes.empty:
        df_partiels = df_ventes[df_ventes["Reste à payer"] > 0]
        if not df_partiels.empty:
            st.dataframe(df_partiels[["Produit", "Nom", "Total TTC", "Montant payé", "Reste à payer"]], use_container_width=True)
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

    df_types_charges = load_sheet("Types_Charges")
    types_dispo = df_types_charges["Type de charge"].dropna().tolist() if not df_types_charges.empty else ["Autre"]

    with st.form("form_ligne_charge"):
        date_charge = st.date_input("Date", value=datetime.today())
        type_charge = st.selectbox("Type de charge *", types_dispo)
        description = st.text_input("Description *")
        fournisseur = st.text_input("Fournisseur / Prestataire")
        montant = st.number_input("Montant *", min_value=0, step=100)
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
                row = [line["Référence"], line["Date"], line["Type de charge"],
                       line["Description"], line["Fournisseur / Prestataire"], line["Montant"]]
                sheet.append_row(row)

            # PDF
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(200, 10, "NOTE DE CHARGES", ln=True, align="C")
            pdf.set_font("Arial", size=12)
            pdf.cell(200, 10, f"Référence : {ref_charge}", ln=True)
            pdf.cell(200, 10, f"Date : {datetime.now().strftime('%d/%m/%Y')}", ln=True)
            pdf.ln(5)
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(50, 10, "Type", 1)
            pdf.cell(70, 10, "Description", 1)
            pdf.cell(40, 10, "Fournisseur", 1)
            pdf.cell(30, 10, "Montant", 1, ln=True)
            pdf.set_font("Arial", size=12)
            for line in st.session_state.charges_panier:
                pdf.cell(50, 10, line["Type de charge"], 1)
                pdf.cell(70, 10, line["Description"], 1)
                pdf.cell(40, 10, line["Fournisseur / Prestataire"], 1)
                pdf.cell(30, 10, str(line["Montant"]), 1, ln=True)
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(160, 10, "TOTAL", 1)
            pdf.cell(30, 10, str(total_session), 1, ln=True)

            pdf_bytes = pdf.output(dest='S').encode('latin1')
            pdf_io = io.BytesIO(pdf_bytes)
            st.download_button(
                label="📄 Télécharger la note de charges (PDF)",
                data=pdf_io,
                file_name=f"note_charges_{ref_charge}.pdf",
                mime="application/pdf"
            )
            st.success("✅ Charges enregistrées avec succès.")
            st.session_state.charges_panier = []
