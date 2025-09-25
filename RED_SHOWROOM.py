import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from fpdf import FPDF
import io
from num2words import num2words

# -----------------------------
# Config & Google Sheets auth
# -----------------------------
st.set_page_config(page_title="Showroom Stock & Vente", layout="wide")
st.title("📊 Gestion Showroom")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]

# Try to use Streamlit secrets if present, otherwise fallback to credentials.json
try:
    if "google" in st.secrets:
        creds = Credentials.from_service_account_info(st.secrets["google"], scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    client = gspread.authorize(creds)
except Exception as e:
    st.error("Impossible d'authentifier Google Sheets. Vérifie st.secrets ou credentials.json.")
    st.stop()

# Replace with your spreadsheet key or name
SPREADSHEET_KEY = "1r4xnyKDaY6jzYGLUORKHlPeGKMCCLkkIx_XvSkIobhc"
try:
    spreadsheet = client.open_by_key(SPREADSHEET_KEY)
except Exception as e:
    st.error(f"Impossible d'ouvrir la feuille Google Sheets : {e}")
    st.stop()

# -----------------------------
# Utilitaires Google Sheets
# -----------------------------
@st.cache_data(ttl=10)
def load_sheet(sheet_name: str) -> pd.DataFrame:
    """Charge la feuille et nettoie les noms de colonnes."""
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
        rows = worksheet.get_all_records()
        df = pd.DataFrame(rows)
        if df.empty:
            # still return empty but ensure columns cleaned
            df.columns = df.columns.str.strip()
            return df
        # Nettoyage colonne names (strip)
        df = df.loc[:, df.columns.str.strip() != '']
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        # Afficher message d'erreur mais ne planter l'app
        st.warning(f"Feuille '{sheet_name}' : {e}")
        return pd.DataFrame()

def append_dict_to_sheet(sheet_name: str, row_dict: dict):
    """
    Ajoute une ligne à la feuille `sheet_name`.
    On récupère la première ligne (headers) du sheet et on aligne valeurs selon l'ordre des headers.
    """
    try:
        ws = spreadsheet.worksheet(sheet_name)
        headers = ws.row_values(1)
        # if no headers, we'll append values in arbitrary order of row_dict
        if not headers:
            vals = list(row_dict.values())
        else:
            vals = [row_dict.get(h, "") for h in headers]
        ws.append_row(vals)
    except Exception as e:
        st.error(f"Erreur lors de l'ajout à la feuille '{sheet_name}': {e}")

def update_cell_in_sheet(sheet_name: str, row_idx: int, col_name: str, value):
    """
    Met à jour une cellule en repérant la colonne par le nom (col_name).
    row_idx doit être l'index dans worksheet (1-indexed, header row = 1).
    """
    try:
        ws = spreadsheet.worksheet(sheet_name)
        headers = ws.row_values(1)
        if col_name in headers:
            col_idx = headers.index(col_name) + 1
            ws.update_cell(row_idx, col_idx, value)
        else:
            st.error(f"Colonne '{col_name}' introuvable dans la feuille '{sheet_name}'.")
    except Exception as e:
        st.error(f"Erreur update_cell_in_sheet: {e}")

# -----------------------------
# Utilisateurs (simple)
# -----------------------------
USERS = ["user1", "user2", "user3"]

if "user" not in st.session_state:
    st.session_state.user = None

# Login simple
if not st.session_state.user:
    st.header("🔐 Connexion")
    user_choice = st.selectbox("Choisissez votre utilisateur :", [""] + USERS)
    if st.button("Se connecter"):
        if user_choice and user_choice in USERS:
            st.session_state.user = user_choice
            st.experimental_rerun()
        else:
            st.error("Utilisateur invalide.")
    st.stop()
else:
    st.sidebar.write(f"👤 Connecté : **{st.session_state.user}**")
    if st.sidebar.button("Se déconnecter"):
        st.session_state.user = None
        st.experimental_rerun()

# -----------------------------
# Chargement données initiales
# -----------------------------
df_produits = load_sheet("Produits")  # doit contenir Marque, Catégorie, Famille, Produit, Prix unitaire
df_stock = load_sheet("Stock")        # doit contenir au moins Produit, Quantité (et Marque/Catégorie/Famille si utilisées)
df_ventes = load_sheet("Ventes")      # historique ventes

# Normaliser colonnes communes (strip)
for df in (df_produits, df_stock, df_ventes):
    if not df.empty:
        df.columns = df.columns.str.strip()

# S'assurer que colonnes Montant payé / Reste à payer existent dans df_ventes (sinon on les ajoute côté UI)
if "Montant payé" not in df_ventes.columns:
    df_ventes["Montant payé"] = 0
if "Reste à payer" not in df_ventes.columns:
    df_ventes["Reste à payer"] = 0
if "Numéro de facture" not in df_ventes.columns:
    df_ventes["Numéro de facture"] = ""

# -----------------------------
# Helpers UI
# -----------------------------
def selection_produit_ui(df_products):
    """Selection hiérarchique Marque->Catégorie->Famille->Produit. Retourne (marque, cat, fam, produit, prix)"""
    if df_products.empty:
        st.warning("La feuille 'Produits' est vide ou introuvable.")
        return "", "", "", "", 0.0

    marques = [""] + sorted(df_products['Marque'].dropna().unique().tolist())
    marque = st.selectbox("Marque *", marques)
    categories = []
    if marque:
        categories = [""] + sorted(df_products[df_products['Marque'] == marque]['Catégorie'].dropna().unique().tolist())
    categorie = st.selectbox("Catégorie *", categories)

    familles = []
    if marque and categorie:
        familles = [""] + sorted(df_products[
            (df_products['Marque'] == marque) & (df_products['Catégorie'] == categorie)
        ]['Famille'].dropna().unique().tolist())
    famille = st.selectbox("Famille *", familles)

    produits = []
    if marque and categorie and famille:
        produits = [""] + sorted(df_products[
            (df_products['Marque'] == marque) & (df_products['Catégorie'] == categorie) & (df_products['Famille'] == famille)
        ]['Produit'].dropna().unique().tolist())
    produit = st.selectbox("Produit *", produits)

    prix = 0.0
    try:
        if produit:
            prix = float(df_products[
                (df_products['Marque'] == marque) & (df_products['Catégorie'] == categorie) &
                (df_products['Famille'] == famille) & (df_products['Produit'] == produit)
            ]['Prix unitaire'].values[0])
    except Exception:
        prix = 0.0

    return marque or "", categorie or "", famille or "", produit or "", prix

def gen_invoice_pdf(client_info: dict, items: list, total_ht: float, total_ttc: float, total_paid: float, total_rest: float, invoice_num: str):
    """
    client_info: dict with keys 'Nom','Email','Téléphone','RC','NIF','ART','Adresse'
    items: list of dicts with Marque/Produit/Quantité/Prix unitaire/Total HT/Total TTC/Montant payé per line (we sum)
    returns bytesIO for download
    """
    pdf = FPDF()
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, f"FACTURE N°: {invoice_num}", ln=True, align="C")
    pdf.ln(4)
    pdf.set_font("Arial", size=11)
    # Company / client
    pdf.cell(0, 6, "NORTH AFRICA ELECTRONICS", ln=True)
    pdf.cell(0, 6, "123 Rue Principale, Alger", ln=True)
    pdf.cell(0, 6, "RC: 16/00-1052043 B23 | NIF: 002316105204354 | ART: 002316300298344", ln=True)
    pdf.ln(6)
    pdf.cell(0, 6, f"Client: {client_info.get('Nom','')}", ln=True)
    pdf.cell(0, 6, f"Email: {client_info.get('Email','')} | Tel: {client_info.get('Téléphone','')}", ln=True)
    pdf.cell(0, 6, f"RC: {client_info.get('RC','')} | NIF: {client_info.get('NIF','')} | ART: {client_info.get('ART','')}", ln=True)
    pdf.cell(0, 6, f"Adresse: {client_info.get('Adresse','')}", ln=True)
    pdf.ln(6)

    # Table header
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(45, 8, "Marque", 1)
    pdf.cell(55, 8, "Produit", 1)
    pdf.cell(20, 8, "Qté", 1, align="C")
    pdf.cell(30, 8, "Prix HT", 1, align="R")
    pdf.cell(40, 8, "Total HT", 1, align="R")
    pdf.ln()

    pdf.set_font("Arial", size=10)
    for it in items:
        pdf.cell(45, 8, str(it.get("Marque","")), 1)
        pdf.cell(55, 8, str(it.get("Produit",""))[:30], 1)
        pdf.cell(20, 8, str(it.get("Quantité","")), 1, align="C")
        pdf.cell(30, 8, f"{it.get('Prix unitaire',0):.2f}", 1, align="R")
        pdf.cell(40, 8, f"{it.get('Total HT',0):.2f}", 1, align="R")
        pdf.ln()

    # Totals
    pdf.ln(4)
    pdf.cell(150, 8, "Total HT:", 0, align="R")
    pdf.cell(40, 8, f"{total_ht:.2f}", 1, align="R", ln=True)
    pdf.cell(150, 8, "Total TVA 19%:", 0, align="R")
    pdf.cell(40, 8, f"{(total_ttc - total_ht):.2f}", 1, align="R", ln=True)
    pdf.cell(150, 8, "Total TTC:", 0, align="R")
    pdf.cell(40, 8, f"{total_ttc:.2f}", 1, align="R", ln=True)
    pdf.cell(150, 8, "Montant payé:", 0, align="R")
    pdf.cell(40, 8, f"{total_paid:.2f}", 1, align="R", ln=True)
    pdf.cell(150, 8, "Reste à payer:", 0, align="R")
    pdf.cell(40, 8, f"{total_rest:.2f}", 1, align="R", ln=True)

    # Amount in words
    pdf.ln(6)
    montant_lettres = num2words(int(round(total_ttc)), lang='fr') + " dinars algériens"
    pdf.set_font("Arial", 'I', 10)
    pdf.multi_cell(0, 8, f"Arrêté la présente facture à la somme de : {montant_lettres}")

    # Output bytes
    pdf_bytes = pdf.output(dest='S').encode('latin1', errors='replace')
    return io.BytesIO(pdf_bytes)

# -----------------------------
# Navigation / onglets
# -----------------------------
tabs = ["🛒 Ajouter Stock", "💰 Enregistrer Vente", "📦 État Stock", "📄 Historique Ventes", "💳 Paiements partiels"]
choice = st.radio("Onglets", tabs, index=0, horizontal=True)

# -----------------------------
# Onglet: Ajouter Stock
# -----------------------------
if choice == "🛒 Ajouter Stock":
    st.header("Ajouter du stock")
    with st.form("form_add_stock"):
        m, c, f, p, prix = selection_produit_ui(df_produits)
        quant = st.number_input("Quantité achetée", min_value=1, step=1, value=1)
        # prix d'achat désactivé si tu veux: ici on laisse modification possible
        prix_achat = st.number_input("Prix d'achat unitaire (optionnel)", min_value=0.0, step=0.01, value=prix)
        if st.form_submit_button("Ajouter au stock"):
            row_dict = {
                "Date": str(datetime.now()),
                "Marque": m,
                "Catégorie": c,
                "Famille": f,
                "Produit": p,
                "Quantité": quant,
                "Prix": prix_achat,
                "Utilisateur": st.session_state.user
            }
            append_dict_to_sheet("Stock", row_dict)
            st.success(f"{quant} x {p} ajouté(s) au stock.")
            st.experimental_rerun()

# -----------------------------
# Onglet: Enregistrer Vente
# -----------------------------
elif choice == "💰 Enregistrer Vente":
    st.header("Enregistrer une vente multi-produits")
    # recharge produits (au cas où)
    df_produits = load_sheet("Produits")
    if df_produits.empty:
        st.warning("Feuille 'Produits' vide ou introuvable.")
    else:
        if "panier" not in st.session_state:
            st.session_state.panier = []

        with st.form("form_vente"):
            m, c, f, produit, prix_un = selection_produit_ui(df_produits)
            qte = st.number_input("Quantité vendue *", min_value=1, step=1, value=1)

            client_nom = st.text_input("Nom *")
            client_email = st.text_input("Email")
            client_tel = st.text_input("Téléphone *")
            client_rc = st.text_input("RC")
            client_nif = st.text_input("NIF")
            client_art = st.text_input("ART")
            client_adresse = st.text_input("Adresse")

            total_ht = prix_un * qte
            total_ttc = round(total_ht * 1.19, 2)
            st.markdown(f"**Total HT:** {total_ht:.2f} | **Total TTC:** {total_ttc:.2f}")

            montant_paye = st.number_input("Montant payé maintenant", min_value=0.0, max_value=total_ttc, value=total_ttc, step=0.01)
            reste = round(total_ttc - montant_paye, 2)
            st.write(f"Reste à payer : {reste:.2f}")

            generer_facture = st.checkbox("Générer une facture PDF")

            if st.form_submit_button("Ajouter au panier"):
                if not produit or not client_nom.strip() or not client_tel.strip():
                    st.error("Remplir les champs obligatoires (Produit, Nom, Téléphone).")
                else:
                    st.session_state.panier.append({
                        "Marque": m, "Catégorie": c, "Famille": f,
                        "Produit": produit, "Quantité": qte,
                        "Prix unitaire": prix_un, "Total HT": total_ht,
                        "Total TTC": total_ttc, "Montant payé": montant_paye,
                        "Reste à payer": reste
                    })
                    st.success(f"{qte} x {produit} ajouté(s) au panier.")

        # affichage panier
        if st.session_state.panier:
            st.subheader("Panier")
            df_panier = pd.DataFrame(st.session_state.panier)
            st.dataframe(df_panier, use_container_width=True)

            # enregistrer la vente (en bloc)
            if st.button("Enregistrer la vente"):
                # reload stock/ventes
                df_stock = load_sheet("Stock")
                df_ventes = load_sheet("Ventes")

                # check stock availability (simple check by Produit)
                vente_valide = True
                for it in st.session_state.panier:
                    stock_dispo = 0
                    if not df_stock.empty and 'Quantité' in df_stock.columns:
                        stock_dispo = df_stock[df_stock['Produit'] == it['Produit']]['Quantité'].sum()
                    ventes_sum = 0
                    if not df_ventes.empty and 'Quantité' in df_ventes.columns:
                        ventes_sum = df_ventes[df_ventes['Produit'] == it['Produit']]['Quantité'].sum()
                    stock_reel = stock_dispo - ventes_sum
                    if it['Quantité'] > stock_reel:
                        st.error(f"Stock insuffisant pour {it['Produit']} (disponible: {stock_reel})")
                        vente_valide = False

                if not vente_valide:
                    st.stop()

                # build invoice number (simple incremental based on current ventes)
                df_ventes = load_sheet("Ventes")
                if df_ventes.empty or 'Numéro de facture' not in df_ventes.columns:
                    next_num = 1
                else:
                    # try extract numeric prefix if present
                    try:
                        nums = pd.to_numeric(df_ventes['Numéro de facture'].astype(str).str.split("/").str[0], errors='coerce')
                        next_num = int((nums.max() or 0) + 1)
                    except Exception:
                        next_num = len(df_ventes) + 1
                invoice_num = f"{next_num:03d}/2025"

                # client info for PDF
                client_info = {
                    "Nom": client_nom, "Email": client_email, "Téléphone": client_tel,
                    "RC": client_rc, "NIF": client_nif, "ART": client_art, "Adresse": client_adresse
                }

                # append each line to Ventes sheet
                for it in st.session_state.panier:
                    row = {
                        "Date": str(datetime.now()),
                        "Nom": client_nom,
                        "Email": client_email,
                        "Téléphone": client_tel,
                        "RC_Client": client_rc,
                        "NIF_Client": client_nif,
                        "ART_Client": client_art,
                        "Adresse_Client": client_adresse,
                        "Marque": it.get("Marque",""),
                        "Catégorie": it.get("Catégorie",""),
                        "Famille": it.get("Famille",""),
                        "Produit": it.get("Produit",""),
                        "Quantité": it.get("Quantité",0),
                        "Prix unitaire": it.get("Prix unitaire",0.0),
                        "Total": it.get("Total HT",0.0),
                        "Total TTC": it.get("Total TTC",0.0),
                        "Montant payé": it.get("Montant payé",0.0),
                        "Reste à payer": it.get("Reste à payer",0.0),
                        "RC": "", "NIF": "", "ART": "", "ADRESSE": "",
                        "Numéro de facture": invoice_num,
                        "Utilisateur": st.session_state.user
                    }
                    append_dict_to_sheet("Ventes", row)

                # Generate PDF if requested (aggregate items)
                if generer_facture:
                    items_for_pdf = []
                    total_ht_sum = 0.0
                    total_ttc_sum = 0.0
                    total_paid_sum = 0.0
                    for it in st.session_state.panier:
                        items_for_pdf.append({
                            "Marque": it.get("Marque",""),
                            "Produit": it.get("Produit",""),
                            "Quantité": it.get("Quantité",0),
                            "Prix unitaire": it.get("Prix unitaire",0.0),
                            "Total HT": it.get("Total HT",0.0)
                        })
                        total_ht_sum += it.get("Total HT",0.0)
                        total_ttc_sum += it.get("Total TTC",0.0)
                        total_paid_sum += it.get("Montant payé",0.0)
                    total_rest_sum = total_ttc_sum - total_paid_sum

                    pdf_io = gen_invoice_pdf(client_info, items_for_pdf, total_ht_sum, total_ttc_sum, total_paid_sum, total_rest_sum, invoice_num)
                    st.download_button("📥 Télécharger la facture (PDF)", data=pdf_io, file_name=f"facture_{invoice_num}.pdf", mime="application/pdf")

                st.success("Vente enregistrée.")
                st.session_state.panier = []
                st.experimental_rerun()

# -----------------------------
# Onglet: État Stock
# -----------------------------
elif choice == "📦 État Stock":
    st.header("État du stock")
    df_stock = load_sheet("Stock")
    df_ventes = load_sheet("Ventes")
    if df_stock.empty:
        st.write("Aucun stock enregistré.")
    else:
        # calcul simple par produit
        df_stock = df_stock.copy()
        if 'Quantité' not in df_stock.columns:
            st.warning("La feuille 'Stock' ne contient pas la colonne 'Quantité'.")
            st.dataframe(df_stock)
        else:
            stock_tot = df_stock.groupby("Produit", dropna=False)["Quantité"].sum().reset_index()
            if not df_ventes.empty and 'Quantité' in df_ventes.columns:
                ventes_tot = df_ventes.groupby("Produit", dropna=False)["Quantité"].sum().reset_index().rename(columns={"Quantité":"Quantité_vendue"})
                view = stock_tot.merge(ventes_tot, on="Produit", how="left")
                view["Quantité_vendue"] = view["Quantité_vendue"].fillna(0).astype(float)
                view["Stock restant"] = view["Quantité"] - view["Quantité_vendue"]
            else:
                view = stock_tot.copy()
                view["Stock restant"] = view["Quantité"]
            st.dataframe(view[["Produit","Stock restant"]], use_container_width=True)

# -----------------------------
# Onglet: Historique Ventes
# -----------------------------
elif choice == "📄 Historique Ventes":
    st.header("Historique des ventes")
    df_ventes = load_sheet("Ventes")
    if df_ventes.empty:
        st.write("Aucune vente enregistrée.")
    else:
        st.dataframe(df_ventes, use_container_width=True)

# -----------------------------
# Onglet: Paiements partiels
# -----------------------------
elif choice == "💳 Paiements partiels":
    st.header("Paiements partiels (Reste à payer > 0)")
    df_ventes = load_sheet("Ventes")
    if df_ventes.empty:
        st.write("Aucune vente enregistrée.")
    else:
        # sanitize numeric columns
        for col in ["Montant payé", "Reste à payer", "Total TTC"]:
            if col in df_ventes.columns:
                df_ventes[col] = pd.to_numeric(df_ventes[col], errors='coerce').fillna(0.0)

        # filter
        if "Reste à payer" in df_ventes.columns:
            df_part = df_ventes[df_ventes["Reste à payer"] > 0].copy()
            if df_part.empty:
                st.write("Aucun paiement partiel en cours.")
            else:
                # Show important columns
                display_cols = [c for c in ["Numéro de facture", "Date", "Nom", "Produit", "Total TTC", "Montant payé", "Reste à payer", "Utilisateur"] if c in df_part.columns]
                st.dataframe(df_part[display_cols], use_container_width=True)

                st.markdown("---")
                st.subheader("Enregistrer un paiement pour une facture existante")
                invoice_choices = df_part["Numéro de facture"].astype(str).tolist() if "Numéro de facture" in df_part.columns else []
                invoice_selected = st.selectbox("Choisir une facture", [""] + invoice_choices)
                if invoice_selected:
                    row_idx = df_ventes[df_ventes["Numéro de facture"].astype(str) == invoice_selected].index[0]  # dataframe index (0-based)
                    # sheet row index = row_idx + 2  (1 for header)
                    sheet_row = row_idx + 2
                    current_paid = float(df_ventes.at[row_idx, "Montant payé"]) if "Montant payé" in df_ventes.columns else 0.0
                    current_reste = float(df_ventes.at[row_idx, "Reste à payer"]) if "Reste à payer" in df_ventes.columns else 0.0
                    st.write(f"Montant déjà payé: {current_paid:.2f} | Reste actuel: {current_reste:.2f}")
                    pay_now = st.number_input("Saisir montant reçu maintenant", min_value=0.0, max_value=current_reste, step=1.0)
                    if st.button("Enregistrer le paiement"):
                        nouveau_paye = round(current_paid + pay_now, 2)
                        nouveau_reste = round(current_reste - pay_now, 2)
                        # update sheet cells
                        update_cell_in_sheet("Ventes", sheet_row, "Montant payé", nouveau_paye)
                        update_cell_in_sheet("Ventes", sheet_row, "Reste à payer", nouveau_reste)
                        st.success("Paiement enregistré.")
                        st.experimental_rerun()
        else:
            st.warning("La feuille 'Ventes' ne contient pas la colonne 'Reste à payer'. Ajoute-la dans Google Sheets.")

# -----------------------------
# FIN
# -----------------------------
