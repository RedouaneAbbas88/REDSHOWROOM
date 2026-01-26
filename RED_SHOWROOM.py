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
# 🔹 Fonctions utilitaires
# -----------------------------
@st.cache_data(ttl=10)
def load_sheet(sheet_name):
    try:
        sheet = spreadsheet.worksheet(sheet_name)
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

def generate_reference(prefix="CHG"):
    return f"{prefix}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

# -----------------------------
# 🔹 Données produits
# -----------------------------
df_produits = load_sheet("Produits")
produits_dispo = df_produits["Produit"].dropna().tolist() if not df_produits.empty else []

# -----------------------------
# 🔹 Session State
# -----------------------------
if "active_tab" not in st.session_state:
    st.session_state.active_tab = 0

if "panier" not in st.session_state:
    st.session_state.panier = []

if "charges_panier" not in st.session_state:
    st.session_state.charges_panier = []

# -----------------------------
# 🔹 Onglets
# -----------------------------
tabs = [
    "🛒 Ajouter Stock",
    "💰 Enregistrer Vente",
    "📦 État Stock",
    "📄 Historique Ventes",
    "💳 Paiements partiels",
    "🧾 Charges quotidiennes"
]

tab_choice = st.radio("Choisir un onglet", tabs, index=st.session_state.active_tab)
st.session_state.active_tab = tabs.index(tab_choice)

# =====================================================
# 🛒 ONGLET 1 — AJOUT STOCK
# =====================================================
if tab_choice == "🛒 Ajouter Stock":
    st.header("Ajouter du stock")

    with st.form("form_stock"):
        produit = st.selectbox("Produit *", produits_dispo)
        prix_achat = float(
            df_produits.loc[df_produits["Produit"] == produit, "Prix unitaire"].values[0]
        ) if not df_produits.empty else 0

        quantite = st.number_input("Quantité achetée", min_value=1, step=1)
        submit = st.form_submit_button("Ajouter au stock")

    if submit:
        row = [str(datetime.now()), produit, quantite, prix_achat]
        spreadsheet.worksheet("Stock").append_row(row)
        st.success("Stock ajouté avec succès")

# =====================================================
# 💰 ONGLET 2 — VENTE MULTI-PRODUITS
# =====================================================
elif tab_choice == "💰 Enregistrer Vente":
    st.header("Enregistrer une vente")

    # -----------------------------
    # Sélection produit
    # -----------------------------
    produit = st.selectbox("Produit vendu *", produits_dispo)

    prix_unitaire = float(
        df_produits.loc[df_produits["Produit"] == produit, "Prix unitaire"].values[0]
    ) if produit else 0

    quantite = st.number_input("Quantité *", min_value=1, step=1)

    total_ht = prix_unitaire * quantite
    total_ttc = int(round(total_ht * 1.19, 0))

    st.info(f"Prix unitaire : {prix_unitaire} DA | Total TTC : {total_ttc} DA")

    # -----------------------------
    # Infos client
    # -----------------------------
    client_nom = st.text_input("Nom du client *")
    client_tel = st.text_input("Téléphone *")
    client_email = st.text_input("Email")
    client_rc = st.text_input("RC")
    client_nif = st.text_input("NIF")
    client_art = st.text_input("ART")
    client_adresse = st.text_input("Adresse")

    montant_paye = st.number_input(
        "Montant payé",
        min_value=0,
        max_value=total_ttc,
        step=1
    )

    reste = total_ttc - montant_paye
    st.warning(f"Reste à payer : {reste} DA")

    generer_facture = st.checkbox("Générer une facture PDF")

    # -----------------------------
    # Ajouter au panier
    # -----------------------------
    if st.button("➕ Ajouter au panier"):
        if not produit or not client_nom or not client_tel:
            st.error("Merci de remplir les champs obligatoires")
        else:
            st.session_state.panier.append({
                "Produit": produit,
                "Quantité": quantite,
                "Prix": prix_unitaire,
                "Total TTC": total_ttc,
                "Payé": montant_paye,
                "Reste": reste,
                "Nom": client_nom,
                "Téléphone": client_tel,
                "Email": client_email,
                "RC": client_rc,
                "NIF": client_nif,
                "ART": client_art,
                "Adresse": client_adresse
            })
            st.success("Produit ajouté au panier")

    # -----------------------------
    # Affichage panier
    # -----------------------------
    if st.session_state.panier:
        st.subheader("🧺 Panier")
        df_panier = pd.DataFrame(st.session_state.panier)
        st.dataframe(df_panier, use_container_width=True)

        # -----------------------------
        # Validation vente
        # -----------------------------
        if st.button("✅ Enregistrer la vente"):
            df_stock = load_sheet("Stock")
            df_ventes = load_sheet("Ventes")

            # Numéro facture
            prochain_num = ""
            if generer_facture and not df_ventes.empty:
                factures = df_ventes["Numéro de facture"].dropna()
                nums = factures.str.split("/").str[0]
                nums = nums[nums.str.isnumeric()].astype(int)
                dernier = nums.max() if not nums.empty else 0
                prochain_num = f"{dernier + 1:03d}/2025"

            entreprise_nom = "NORTH AFRICA ELECTRONICS"

            # Enregistrement Google Sheets
            for item in st.session_state.panier:
                row = [
                    str(datetime.now()),
                    item["Nom"],
                    item["Email"],
                    item["Téléphone"],
                    item["RC"],
                    item["NIF"],
                    item["ART"],
                    item["Adresse"],
                    item["Produit"],
                    item["Quantité"],
                    item["Prix"],
                    item["Total TTC"],
                    item["Payé"],
                    item["Reste"],
                    prochain_num
                ]
                spreadsheet.worksheet("Ventes").append_row(row)

            # -----------------------------
            # PDF — FACTURE OU BON
            # -----------------------------
            pdf = FPDF()
            pdf.add_page()

            pdf.set_font("Arial", "B", 16)
            pdf.cell(200, 10, entreprise_nom, ln=True, align="C")

            pdf.set_font("Arial", "B", 14)
            if generer_facture:
                titre = "FACTURE"
                nom_pdf = "Clients Divers"
                nom_fichier = f"facture_{prochain_num.replace('/', '-')}.pdf"
            else:
                titre = "BON DE VENTE"
                nom_pdf = client_nom
                nom_fichier = f"bon_vente_{client_nom}.pdf"

            pdf.cell(200, 10, titre, ln=True, align="C")

            pdf.set_font("Arial", size=12)
            pdf.cell(200, 10, f"Date : {datetime.now().strftime('%d/%m/%Y')}", ln=True)

            if generer_facture:
                pdf.cell(200, 10, f"Facture N° : {prochain_num}", ln=True)

            pdf.cell(200, 10, f"Client : {nom_pdf}", ln=True)
            pdf.cell(200, 10, f"Téléphone : {client_tel}", ln=True)

            pdf.ln(5)
            pdf.set_font("Arial", "B", 12)
            pdf.cell(80, 10, "Produit", 1)
            pdf.cell(30, 10, "Qté", 1)
            pdf.cell(40, 10, "Prix TTC", 1)
            pdf.cell(40, 10, "Total TTC", 1, ln=True)

            total_global = 0
            pdf.set_font("Arial", size=12)

            for item in st.session_state.panier:
                total_global += item["Total TTC"]
                pdf.cell(80, 10, item["Produit"], 1)
                pdf.cell(30, 10, str(item["Quantité"]), 1)
                pdf.cell(40, 10, f"{item['Total TTC'] / item['Quantité']:.2f}", 1)
                pdf.cell(40, 10, f"{item['Total TTC']:.2f}", 1, ln=True)

            pdf.set_font("Arial", "B", 12)
            pdf.cell(150, 10, "TOTAL", 1)
            pdf.cell(40, 10, f"{total_global:.2f}", 1, ln=True)

            pdf_bytes = pdf.output(dest="S").encode("latin1")
            pdf_io = io.BytesIO(pdf_bytes)

            st.download_button(
                "📄 Télécharger le document",
                pdf_io,
                nom_fichier,
                "application/pdf"
            )

            st.success("Vente enregistrée avec succès")
            st.session_state.panier = []

# =====================================================
# 📦 ONGLET 3 — STOCK
# =====================================================
elif tab_choice == "📦 État Stock":
    st.header("Stock restant")

    df_stock = load_sheet("Stock")
    df_ventes = load_sheet("Ventes")

    if not df_stock.empty:
        stock = df_stock.groupby("Produit")["Quantité"].sum().reset_index()

        if not df_ventes.empty:
            ventes = df_ventes.groupby("Produit")["Quantité"].sum().reset_index()
            stock = stock.merge(ventes, on="Produit", how="left", suffixes=("", "_vendu"))
            stock["Quantité_vendu"] = stock["Quantité_vendu"].fillna(0)
            stock["Stock restant"] = stock["Quantité"] - stock["Quantité_vendu"]

        st.dataframe(stock[["Produit", "Stock restant"]], use_container_width=True)

# =====================================================
# 📄 ONGLET 4 — HISTORIQUE
# =====================================================
elif tab_choice == "📄 Historique Ventes":
    df = load_sheet("Ventes")
    st.dataframe(df, use_container_width=True)

# =====================================================
# 💳 ONGLET 5 — PAIEMENTS PARTIELS
# =====================================================
elif tab_choice == "💳 Paiements partiels":
    df = load_sheet("Ventes")

    if not df.empty:
        partiels = df[df["Reste"] > 0]
        st.dataframe(partiels, use_container_width=True)

# =====================================================
# 🧾 ONGLET 6 — CHARGES
# =====================================================
elif tab_choice == "🧾 Charges quotidiennes":
    st.header("Note de charges")

    ref = generate_reference()
    st.info(f"Référence : {ref}")

    with st.form("form_charge"):
        date = st.date_input("Date", datetime.today())
        type_charge = st.text_input("Type de charge *")
        desc = st.text_input("Description *")
        fournisseur = st.text_input("Fournisseur")
        montant = st.number_input("Montant *", min_value=0, step=100)

        submit = st.form_submit_button("Ajouter")

    if submit:
        if not desc or montant <= 0:
            st.error("Description et montant obligatoires")
        else:
            st.session_state.charges_panier.append([
                ref, str(date), type_charge, desc, fournisseur, montant
            ])
            st.success("Charge ajoutée")

    if st.session_state.charges_panier:
        df = pd.DataFrame(
            st.session_state.charges_panier,
            columns=["Référence", "Date", "Type", "Description", "Fournisseur", "Montant"]
        )

        st.dataframe(df, use_container_width=True)
        st.success(f"Total : {df['Montant'].sum()} DA")

        if st.button("Valider charges"):
            sheet = spreadsheet.worksheet("Charges")
            for row in st.session_state.charges_panier:
                sheet.append_row(row)

            st.session_state.charges_panier = []
            st.success("Charges enregistrées")
