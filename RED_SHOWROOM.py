import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from fpdf import FPDF
import io
from num2words import num2words

# ------------------------
# Configuration Streamlit
# ------------------------
st.set_page_config(page_title="Showroom Stock & Vente", layout="wide")
st.title("📊 Gestion Showroom")

# ------------------------
# Connexion Google Sheets
# ------------------------
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds_dict = st.secrets["google"]                    # Ton secrets.toml doit contenir [google] {...}
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
client = gspread.authorize(creds)

SPREADSHEET_ID = "1r4xnyKDaY6jzYGLUORKHlPeGKMCCLkkIx_XvSkIobhc"  # Ton ID de sheet
spreadsheet = client.open_by_key(SPREADSHEET_ID)

# ------------------------
# Utilitaires
# ------------------------
@st.cache_data(ttl=10)
def load_sheet(sheet_name):
    """Charge une feuille Google Sheets en DataFrame (gestion d'erreur incluse)."""
    try:
        sh = spreadsheet.worksheet(sheet_name)
        data = sh.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Erreur lors du chargement de la feuille '{sheet_name}': {e}")
        return pd.DataFrame()

def next_invoice_number(df_ventes, year=None):
    """Calcule le prochain numéro de facture (format 001/2025)."""
    if year is None:
        year = datetime.now().year
    if df_ventes is None or df_ventes.empty or "Numéro de facture" not in df_ventes.columns:
        return f"{1:03d}/{year}"
    # Extraire la partie avant le slash, convertir en int (sécurisé)
    nums = df_ventes["Numéro de facture"].astype(str).str.split("/").str[0]
    nums = pd.to_numeric(nums, errors="coerce")
    if nums.dropna().empty:
        n = 1
    else:
        n = int(nums.max()) + 1
    return f"{n:03d}/{year}"

# ------------------------
# Données initiales
# ------------------------
df_produits = load_sheet("Produits")
produits_dispo = df_produits['Produit'].tolist() if not df_produits.empty else []

# ------------------------
# Onglets
# ------------------------
tabs = st.tabs(["🛒 Ajouter Stock", "💰 Enregistrer Vente", "📦 État Stock", "📄 Historique Ventes"])

# ------------------------
# Onglet 1 : Ajouter Stock
# ------------------------
with tabs[0]:
    st.header("Ajouter du stock")
    with st.form("form_stock"):
        produit_stock = st.selectbox("Produit", produits_dispo) if produits_dispo else st.text_input("Produit")
        quantite_stock = st.number_input("Quantité achetée", min_value=1, step=1, value=1)
        prix_achat = st.number_input("Prix d'achat unitaire", min_value=0.0, step=0.01, format="%.2f")
        submit_stock = st.form_submit_button("Ajouter au stock")
        if submit_stock:
            try:
                spreadsheet.worksheet("Stock").append_row([str(datetime.now()), produit_stock, int(quantite_stock), float(prix_achat)])
                st.success(f"{quantite_stock} x {produit_stock} ajouté(s) au stock.")
            except Exception as e:
                st.error(f"Erreur lors de l'ajout au stock : {e}")

# ------------------------
# Onglet 2 : Enregistrer Vente (multi-produits)
# ------------------------
with tabs[1]:
    st.header("Enregistrer une vente multi-produits")

    # panier en session
    if "panier" not in st.session_state:
        st.session_state.panier = []

    # Formulaire d'ajout au panier
    with st.form("form_vente_multi"):
        produit_vente = st.selectbox("Produit vendu", produits_dispo) if produits_dispo else st.text_input("Produit vendu")
        quantite_vente = st.number_input("Quantité vendue", min_value=1, step=1, value=1)
        # Infos client (saisies)
        client_nom = st.text_input("Nom du client")
        client_email = st.text_input("Email du client")
        client_tel = st.text_input("Téléphone du client")
        client_rc = st.text_input("RC du client")
        client_nif = st.text_input("NIF du client")
        client_art = st.text_input("ART du client")
        client_adresse = st.text_input("Adresse du client")
        generer_facture = st.checkbox("Générer une facture PDF pour cette vente")

        # Récup prix unitaire depuis Produits si existant
        try:
            prix_unitaire = float(df_produits.loc[df_produits['Produit'] == produit_vente, 'Prix unitaire'].values[0]) if not df_produits.empty else 0.0
        except Exception:
            prix_unitaire = 0.0
        total_ht_item = round(prix_unitaire * quantite_vente, 2)
        st.write(f"Prix unitaire : {prix_unitaire:.2f} | Total HT : {total_ht_item:.2f} | Total TTC (19%) : {round(total_ht_item*1.19,2):.2f}")

        add_to_cart = st.form_submit_button("Ajouter au panier")
        if add_to_cart:
            st.session_state.panier.append({
                "Produit": produit_vente,
                "Quantité": int(quantite_vente),
                "Prix unitaire": float(prix_unitaire),
                "Total": float(total_ht_item)
            })
            st.success(f"{quantite_vente} x {produit_vente} ajouté(s) au panier.")

    # Affichage et modification du panier (modifiable avant validation)
    if st.session_state.panier:
        st.subheader("Panier actuel (modifiable)")
        # afficher tableau
        df_panier = pd.DataFrame(st.session_state.panier)
        st.dataframe(df_panier, use_container_width=True)

        # modifications ligne par ligne
        indices_to_remove = []
        for i, item in enumerate(list(st.session_state.panier)):  # copie pour itérer
            cols = st.columns([4,2,2,1])
            with cols[0]:
                st.markdown(f"**{item['Produit']}**")
            with cols[1]:
                new_q = st.number_input(f"Quantité {i}", min_value=1, value=item["Quantité"], key=f"qty_{i}")
            with cols[2]:
                new_p = st.number_input(f"Prix unitaire {i}", min_value=0.0, value=item["Prix unitaire"], format="%.2f", key=f"prix_{i}")
            with cols[3]:
                if st.button("❌", key=f"del_{i}"):
                    indices_to_remove.append(i)
            # appliquer modifications au panier
            st.session_state.panier[i]["Quantité"] = int(new_q)
            st.session_state.panier[i]["Prix unitaire"] = float(new_p)
            st.session_state.panier[i]["Total"] = round(int(new_q) * float(new_p), 2)

        # supprimer éléments marqués
        for idx in sorted(indices_to_remove, reverse=True):
            st.session_state.panier.pop(idx)
            st.success("Élément supprimé du panier.")

        st.markdown("---")

        # Bouton pour valider/enregistrer la vente (en dehors du form)
        if st.button("Enregistrer la vente"):
            # recharger stock/ventes
            df_stock = load_sheet("Stock")
            df_ventes = load_sheet("Ventes")

            # Vérification stock pour chaque item
            vente_valide = True
            for item in st.session_state.panier:
                stock_total = 0
                if not df_stock.empty and "Produit" in df_stock.columns and "Quantité" in df_stock.columns:
                    stock_total = df_stock[df_stock['Produit'] == item["Produit"]]['Quantité'].sum()
                ventes_total = 0
                if not df_ventes.empty and "Produit" in df_ventes.columns and "Quantité" in df_ventes.columns:
                    ventes_total = df_ventes[df_ventes['Produit'] == item["Produit"]]['Quantité'].sum()
                stock_reel = stock_total - ventes_total
                if item["Quantité"] > stock_reel:
                    st.error(f"Stock insuffisant pour {item['Produit']} — disponible : {stock_reel}")
                    vente_valide = False

            if not vente_valide:
                st.warning("Corrigez le panier avant d'enregistrer la vente.")
            else:
                # calculer prochain numéro facture si demandé
                df_ventes_now = load_sheet("Ventes")
                invoice_num = ""
                if generer_facture:
                    invoice_num = next_invoice_number(df_ventes_now)

                # infos entreprise (fixes)
                entreprise_nom = "NORTH AFRICA ELECTRONICS"
                entreprise_adresse = "123 Rue Principale, Alger"
                entreprise_rc = "RC: 16/00-1052043 B23"
                entreprise_nif = "NIF: 002316105204354"
                entreprise_art = "ART: 002316300298344"

                # écrire chaque ligne dans Google Sheets (colonnes conformes au format attendu)
                # Ordre des colonnes attendu (exemple utilisateur) :
                # Date, Nom, Email, Téléphone, RC_Client, NIF_Client, ART_Client, Adresse_Client,
                # Produit, Quantité, Prix unitaire, Total, Total TTC, RC_Entreprise, NIF_Entreprise, ART_Entreprise, Adresse_Entreprise, Numéro de facture
                try:
                    for item in st.session_state.panier:
                        total_ttc_item = round(item["Total"] * 1.19, 2)
                        row = [
                            str(datetime.now()), client_nom, client_email, client_tel,
                            client_rc, client_nif, client_art, client_adresse,
                            item["Produit"], int(item["Quantité"]), float(item["Prix unitaire"]), float(item["Total"]),
                            float(total_ttc_item),
                            entreprise_rc, entreprise_nif, entreprise_art, entreprise_adresse,
                            invoice_num
                        ]
                        spreadsheet.worksheet("Ventes").append_row(row)
                    st.success("Vente(s) enregistrée(s) avec succès.")
                except Exception as e:
                    st.error(f"Erreur lors de l'enregistrement des ventes : {e}")

                # Génération et téléchargement du PDF si demandé
                if generer_facture:
                    # Construire PDF
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", 'B', 14)
                    pdf.cell(0, 10, f"Facture Num : {invoice_num}", ln=True, align="C")
                    pdf.ln(5)

                    # Infos entreprise
                    pdf.set_font("Arial", size=11)
                    pdf.cell(0, 6, entreprise_nom, ln=True)
                    pdf.cell(0, 6, entreprise_adresse, ln=True)
                    pdf.cell(0, 6, f"{entreprise_rc} | {entreprise_nif} | {entreprise_art}", ln=True)
                    pdf.ln(6)

                    # Infos client
                    pdf.cell(0, 6, f"Client: {client_nom}", ln=True)
                    pdf.cell(0, 6, f"Email: {client_email} | Tel: {client_tel}", ln=True)
                    pdf.cell(0, 6, f"RC: {client_rc} | NIF: {client_nif} | ART: {client_art}", ln=True)
                    pdf.cell(0, 6, f"Adresse: {client_adresse}", ln=True)
                    pdf.ln(6)

                    # Entête tableau
                    pdf.set_font("Arial", 'B', 10)
                    pdf.cell(60, 8, "Produit", 1)
                    pdf.cell(25, 8, "Qté", 1)
                    pdf.cell(40, 8, "Prix HT", 1)
                    pdf.cell(40, 8, "Total HT", 1)
                    pdf.cell(25, 8, "Total TTC", 1, ln=True)

                    # Lignes produits
                    pdf.set_font("Arial", size=10)
                    total_ht = 0.0
                    total_ttc = 0.0
                    for item in st.session_state.panier:
                        total_ht += float(item["Total"])
                        total_ttc += float(item["Total"]) * 1.19
                        pdf.cell(60, 8, str(item["Produit"]), 1)
                        pdf.cell(25, 8, str(item["Quantité"]), 1)
                        pdf.cell(40, 8, f"{item['Prix unitaire']:.2f}", 1)
                        pdf.cell(40, 8, f"{item['Total']:.2f}", 1)
                        pdf.cell(25, 8, f"{item['Total'] * 1.19:.2f}", 1, ln=True)

                    total_tva = total_ttc - total_ht
                    pdf.ln(3)
                    pdf.cell(135, 8, "", 0)
                    pdf.cell(35, 8, "Total HT", 1)
                    pdf.cell(25, 8, f"{total_ht:.2f}", 1, ln=True)
                    pdf.cell(135, 8, "", 0)
                    pdf.cell(35, 8, "TVA 19%", 1)
                    pdf.cell(25, 8, f"{total_tva:.2f}", 1, ln=True)
                    pdf.cell(135, 8, "", 0)
                    pdf.cell(35, 8, "Total TTC", 1)
                    pdf.cell(25, 8, f"{total_ttc:.2f}", 1, ln=True)

                    # Montant en lettres (robuste)
                    ttc_int = int(total_ttc)
                    ttc_cent = int(round((total_ttc - ttc_int) * 100))
                    if ttc_cent > 0:
                        montant_lettres = f"{num2words(ttc_int, lang='fr')} dinars et {num2words(ttc_cent, lang='fr')} centimes algériens"
                    else:
                        montant_lettres = f"{num2words(ttc_int, lang='fr')} dinars algériens"

                    pdf.ln(6)
                    pdf.set_font("Arial", 'I', 10)
                    pdf.multi_cell(0, 6, f"Arrêté la présente facture à la somme de : {montant_lettres}")

                    # Préparer le téléchargement (pas d'enregistrement local obligatoire)
                    pdf_bytes = pdf.output(dest='S').encode('latin1')
                    pdf_io = io.BytesIO(pdf_bytes)
                    st.download_button(
                        label="📥 Télécharger la facture (PDF)",
                        data=pdf_io,
                        file_name=f"facture_{client_nom}_{invoice_num}.pdf",
                        mime="application/pdf",
                    )

                # vider le panier après enregistrement
                st.session_state.panier = []

# ------------------------
# Onglet 3 : État Stock
# ------------------------
with tabs[2]:
    st.header("État du stock")
    df_stock = load_sheet("Stock")
    df_ventes = load_sheet("Ventes")
    if not df_stock.empty and "Produit" in df_stock.columns and "Quantité" in df_stock.columns:
        stock_tot = df_stock.groupby("Produit")["Quantité"].sum().reset_index()
        if not df_ventes.empty and "Produit" in df_ventes.columns and "Quantité" in df_ventes.columns:
            ventes_group = df_ventes.groupby("Produit")["Quantité"].sum().reset_index()
            merged = stock_tot.merge(ventes_group, on="Produit", how="left", suffixes=('', '_vendu'))
            merged['Quantité_vendu'] = merged['Quantité_vendu'].fillna(0)
            merged['Stock restant'] = merged['Quantité'] - merged['Quantité_vendu']
        else:
            merged = stock_tot.copy()
            merged['Stock restant'] = merged['Quantité']
        st.dataframe(merged[['Produit', 'Stock restant']], use_container_width=True)
    else:
        st.write("Aucun stock enregistré ou colonnes manquantes ('Produit','Quantité').")

# ------------------------
# Onglet 4 : Historique Ventes
# ------------------------
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
