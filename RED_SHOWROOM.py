import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from fpdf import FPDF
import io

# -----------------------------
# ⚙️ Configuration Streamlit
# -----------------------------
st.set_page_config(page_title="Showroom Stock & Vente", layout="wide")
st.title("📊 Gestion Showroom")

# -----------------------------
# 🔹 Connexion Google Sheets
# -----------------------------
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

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
tabs_labels = [
    "🛒 Ajouter Stock",
    "💰 Enregistrer Vente",
    "📦 État Stock",
    "📄 Historique Ventes",
    "💳 Paiements partiels",
    "🧾 Charges quotidiennes"
]

if "active_tab" not in st.session_state:
    st.session_state.active_tab = 0

if "panier" not in st.session_state:
    st.session_state.panier = []

tab_choice = st.radio("Choisir l'onglet", tabs_labels, index=st.session_state.active_tab)
st.session_state.active_tab = tabs_labels.index(tab_choice)

# -----------------------------
# FONCTION CALCUL FACTURE PDF (timbre uniquement sur PDF)
# -----------------------------
def calculer_facture_pdf(total_ht):
    """Calcul timbre + TVA pour la facture PDF uniquement"""
    timbre = total_ht * 0.01 if total_ht < 100000 else total_ht * 0.02
    base_tva = total_ht + timbre
    tva = base_tva * 0.19
    total_ttc = base_tva + tva
    return timbre, tva, total_ttc

# ======================================================
# ONGLET 1 : AJOUTER STOCK
# ======================================================
if tab_choice == "🛒 Ajouter Stock":
    st.header("Ajouter du stock")
    with st.form("form_stock"):
        produit_stock = st.selectbox("Produit *", produits_dispo)
        prix_achat = float(
            df_produits.loc[df_produits['Produit'] == produit_stock, 'Prix unitaire'].values[0]
        ) if not df_produits.empty else 0.0

        quantite_stock = st.number_input("Quantité achetée", min_value=1, step=1)
        if st.form_submit_button("Ajouter au stock"):
            row = [str(datetime.now()), produit_stock, quantite_stock, prix_achat]
            spreadsheet.worksheet("Stock").append_row(row)
            st.success(f"{quantite_stock} {produit_stock} ajouté(s) au stock.")

# ======================================================
# ONGLET 2 : ENREGISTRER VENTE
# ======================================================
elif tab_choice == "💰 Enregistrer Vente":
    st.header("Enregistrer une vente multi-produits")

    # -----------------------------
    # SAISIE PRODUIT
    # -----------------------------
    produit_vente = st.selectbox("Produit vendu *", produits_dispo)
    prix_unitaire = float(
        df_produits.loc[df_produits['Produit'] == produit_vente, 'Prix unitaire'].values[0]
    ) if produit_vente else 0.0

    quantite_vente = st.number_input("Quantité vendue *", min_value=1, step=1)

    # Calcul système (SANS timbre)
    total_ht_systeme = prix_unitaire * quantite_vente
    tva_systeme = total_ht_systeme * 0.19
    total_ttc_systeme = total_ht_systeme + tva_systeme

    st.write(
        f"PU : {prix_unitaire} DA | "
        f"HT : {total_ht_systeme:.2f} DA | "
        f"TVA système 19% : {tva_systeme:.2f} DA | "
        f"💰 Total TTC système : {total_ttc_systeme:.2f} DA"
    )

    # -----------------------------
    # INFOS CLIENT (INTERNE)
    # -----------------------------
    st.subheader("Informations client (interne uniquement)")
    client_nom = st.text_input("Nom du client *")
    client_email = st.text_input("Email du client")
    client_tel = st.text_input("Téléphone du client *")
    st.info("⚠️ La facture officielle sera toujours au nom de : Client Divers")

    montant_paye = st.number_input(
        "Montant payé par le client",
        min_value=0.0,
        max_value=float(total_ttc_systeme),
        value=0.0,
        step=10.0
    )

    reste_a_payer = round(total_ttc_systeme - montant_paye, 2)
    st.write(f"Reste à payer : {reste_a_payer} DA")

    generer_facture = st.checkbox("Générer une facture PDF")

    # -----------------------------
    # AJOUT PANIER
    # -----------------------------
    if st.button("➕ Ajouter au panier"):
        if not produit_vente or quantite_vente <= 0 or not client_nom.strip() or not client_tel.strip():
            st.error("⚠️ Merci de remplir les champs obligatoires.")
        else:
            st.session_state.panier.append({
                "Produit": produit_vente,
                "Quantité": quantite_vente,
                "Prix unitaire": prix_unitaire,
                "Total HT": total_ht_systeme,
                "TVA": tva_systeme,
                "Total TTC": total_ttc_systeme,
                "Montant payé": montant_paye,
                "Reste à payer": reste_a_payer,
                "Client saisi": client_nom,
                "Email saisi": client_email,
                "Tel saisi": client_tel,
                "Client Facture": "Client Divers",
                "Adresse Facture": "Bordj Bou Arreridj"
            })
            st.success(f"{quantite_vente} x {produit_vente} ajouté(s) au panier.")

    # -----------------------------
    # AFFICHAGE PANIER
    # -----------------------------
    if st.session_state.panier:
        st.subheader("🛒 Panier actuel")
        df_panier = pd.DataFrame(st.session_state.panier)
        st.dataframe(df_panier, use_container_width=True, hide_index=True)

        if st.button("✅ Enregistrer la vente et générer facture PDF"):
            # ---------- PDF ----------
            pdf = FPDF()
            pdf.add_page()

            pdf.set_font("Arial", 'B', 16)
            pdf.cell(200, 10, "NORTH AFRICA ELECTRONICS", ln=True, align="C")
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(200, 10, "FACTURE CLIENT DIVERS", ln=True, align="C")

            pdf.set_font("Arial", size=11)
            pdf.cell(200, 8, f"Date : {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
            pdf.cell(200, 8, f"Client : Client Divers", ln=True)
            pdf.cell(200, 8, f"Adresse : Bordj Bou Arreridj", ln=True)

            pdf.ln(5)
            pdf.set_font("Arial", 'B', 11)
            pdf.cell(70, 8, "Produit", 1)
            pdf.cell(20, 8, "Qté", 1)
            pdf.cell(30, 8, "PU", 1)
            pdf.cell(30, 8, "HT", 1)
            pdf.cell(20, 8, "TVA", 1)
            pdf.cell(20, 8, "TTC", 1, ln=True)
            pdf.set_font("Arial", size=10)

            total_ht_facture = 0
            timbre_total = 0
            tva_total = 0
            total_ttc_facture = 0

            for item in st.session_state.panier:
                # Calcul timbre + TVA uniquement pour PDF
                timbre, tva, total_ttc_pdf = calculer_facture_pdf(item["Total HT"])

                total_ht_facture += item["Total HT"]
                timbre_total += timbre
                tva_total += tva
                total_ttc_facture += total_ttc_pdf

                pdf.cell(70, 8, item["Produit"], 1)
                pdf.cell(20, 8, str(item["Quantité"]), 1)
                pdf.cell(30, 8, f"{item['Prix unitaire']:.2f}", 1)
                pdf.cell(30, 8, f"{item['Total HT']:.2f}", 1)
                pdf.cell(20, 8, f"{tva:.2f}", 1)
                pdf.cell(20, 8, f"{total_ttc_pdf:.2f}", 1, ln=True)

            pdf.ln(5)
            pdf.set_font("Arial", 'B', 11)
            pdf.cell(160, 8, "TOTAL HT", 1)
            pdf.cell(40, 8, f"{total_ht_facture:.2f} DA", 1, ln=True)
            pdf.cell(160, 8, "TOTAL TIMBRE", 1)
            pdf.cell(40, 8, f"{timbre_total:.2f} DA", 1, ln=True)
            pdf.cell(160, 8, "TOTAL TVA", 1)
            pdf.cell(40, 8, f"{tva_total:.2f} DA", 1, ln=True)
            pdf.cell(160, 8, "TOTAL TTC FACTURE", 1)
            pdf.cell(40, 8, f"{total_ttc_facture:.2f} DA", 1, ln=True)

            pdf_bytes = pdf.output(dest="S").encode("latin1")
            pdf_io = io.BytesIO(pdf_bytes)

            st.download_button(
                label="📄 Télécharger la facture PDF",
                data=pdf_io,
                file_name=f"facture_client_divers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                mime="application/pdf"
            )

            # ---------- ENREGISTREMENT SYSTEME SANS TIMBRE ----------
            sheet_ventes = spreadsheet.worksheet("Ventes")
            for item in st.session_state.panier:
                row = [
                    str(datetime.now()),
                    item["Produit"],
                    item["Quantité"],
                    item["Prix unitaire"],
                    item["Total HT"],
                    item["TVA"],
                    item["Total TTC"],
                    item["Montant payé"],
                    item["Reste à payer"],
                    item["Client saisi"],
                    item["Email saisi"],
                    item["Tel saisi"],
                    item["Client Facture"],
                    item["Adresse Facture"]
                ]
                sheet_ventes.append_row(row)

            st.success("Vente enregistrée avec succès (timbre uniquement sur PDF).")
            st.session_state.panier = []

# ======================================================
# ONGLET 3 : ÉTAT STOCK
# ======================================================
elif tab_choice == "📦 État Stock":
    st.header("État du stock")
    df_stock = load_sheet("Stock")
    df_ventes = load_sheet("Ventes")

    if not df_stock.empty:
        stock_reel = df_stock.groupby("Produit")["Quantité"].sum().reset_index()
        if not df_ventes.empty:
            ventes_group = df_ventes.groupby("Produit")["Quantité"].sum().reset_index()
            stock_reel = stock_reel.merge(
                ventes_group, on="Produit", how="left", suffixes=('', '_vendu')
            )
            stock_reel['Quantité_vendu'] = stock_reel['Quantité_vendu'].fillna(0)
            stock_reel['Stock restant'] = stock_reel['Quantité'] - stock_reel['Quantité_vendu']
        else:
            stock_reel['Stock restant'] = stock_reel['Quantité']
        st.dataframe(stock_reel[['Produit', 'Stock restant']], use_container_width=True)
    else:
        st.write("Aucun stock enregistré.")

# ======================================================
# ONGLET 4 : HISTORIQUE VENTES
# ======================================================
elif tab_choice == "📄 Historique Ventes":
    st.header("Historique des ventes")
    df_ventes = load_sheet("Ventes")
    if not df_ventes.empty:
        st.dataframe(df_ventes, use_container_width=True)
    else:
        st.write("Aucune vente enregistrée.")

# ======================================================
# ONGLET 5 : PAIEMENTS PARTIELS
# ======================================================
elif tab_choice == "💳 Paiements partiels":
    st.header("État des paiements partiels")
    df_ventes = load_sheet("Ventes")
    if not df_ventes.empty:
        df_partiels = df_ventes[df_ventes["Reste à payer"] > 0]
        if not df_partiels.empty:
            st.dataframe(
                df_partiels[[
                    "Produit",
                    "Total TTC",
                    "Montant payé",
                    "Reste à payer"
                ]],
                use_container_width=True
            )
        else:
            st.write("Aucun paiement partiel en attente.")
    else:
        st.write("Aucune vente enregistrée.")

# ======================================================
# ONGLET 6 : CHARGES QUOTIDIENNES
# ======================================================
elif tab_choice == "🧾 Charges quotidiennes":
    st.header("Note de charges quotidiennes")

    if "charges_panier" not in st.session_state:
        st.session_state.charges_panier = []

    ref_charge = f"CHG-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    st.info(f"📌 Référence du document : {ref_charge}")

    # -----------------------------
    # TYPES DE CHARGES
    # -----------------------------
    def load_types_charges():
        try:
            sheet = spreadsheet.worksheet("Types_Charges")
            header = sheet.row_values(1)
            col_index = header.index("Type de charge") + 1
            values = sheet.col_values(col_index)[1:]
            return [v for v in values if v.strip()] or ["Autre"]
        except:
            return ["Autre"]

    types_dispo = load_types_charges()

    # -----------------------------
    # FORMULAIRE
    # -----------------------------
    with st.form("form_ligne_charge"):
        date_charge = st.date_input("Date", value=datetime.today())
        type_charge = st.selectbox("Type de charge *", types_dispo)
        description = st.text_input("Description *")
        fournisseur = st.text_input("Fournisseur / Prestataire")
        montant = st.number_input("Montant *", min_value=0.0, step=100.0)
        add_line = st.form_submit_button("➕ Ajouter la ligne")

    # -----------------------------
    # AJOUT PANIER
    # -----------------------------
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

    # -----------------------------
    # AFFICHAGE PANIER
    # -----------------------------
    if st.session_state.charges_panier:
        st.subheader("Lignes en cours")
        df_charges = pd.DataFrame(st.session_state.charges_panier)
        st.dataframe(df_charges, use_container_width=True, hide_index=True)

        total_session = df_charges["Montant"].sum()
        st.markdown(f"### 💰 Total de cette note : {total_session:.2f} DA")

        if st.button("✅ Valider et enregistrer les charges"):
            sheet = spreadsheet.worksheet("Charges")
            for line in st.session_state.charges_panier:
                row = [
                    line["Référence"],
                    line["Date"],
                    line["Type de charge"],
                    line["Description"],
                    line["Fournisseur / Prestataire"],
                    line["Montant"]
                ]
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
                pdf.cell(30, 10, f'{line["Montant"]:.2f}', 1, ln=True)

            pdf.set_font("Arial", 'B', 12)
            pdf.cell(160, 10, "TOTAL", 1)
            pdf.cell(30, 10, f"{total_session:.2f}", 1, ln=True)

            pdf_bytes = pdf.output(dest="S").encode("latin1")
            pdf_io = io.BytesIO(pdf_bytes)

            st.download_button(
                label="📄 Télécharger la note de charges (PDF)",
                data=pdf_io,
                file_name=f"note_charges_{ref_charge}.pdf",
                mime="application/pdf"
            )

            st.success("✅ Charges enregistrées avec succès.")
            st.session_state.charges_panier = []
