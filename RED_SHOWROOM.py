import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from num2words import num2words
from fpdf import FPDF

# -----------------------------
# 🔹 Connexion Google Sheets
# -----------------------------
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
spreadsheet = client.open("RedShowroom")

# -----------------------------
# 🔹 Gestion des utilisateurs simples
# -----------------------------
UTILISATEURS_AUTORISES = ["user1", "user2", "user3"]

if "utilisateur" not in st.session_state:
    st.session_state.utilisateur = None

if not st.session_state.utilisateur:
    st.subheader("🔑 Connexion")
    user = st.selectbox("Choisissez votre nom :", [""] + UTILISATEURS_AUTORISES)
    if st.button("Se connecter"):
        if user and user in UTILISATEURS_AUTORISES:
            st.session_state.utilisateur = user
            st.success(f"✅ Connecté en tant que {user}")
            st.rerun()
        else:
            st.error("Nom d’utilisateur invalide 🚫")
    st.stop()
else:
    st.sidebar.success(f"👤 Utilisateur : {st.session_state.utilisateur}")
    if st.sidebar.button("🚪 Déconnexion"):
        st.session_state.utilisateur = None
        st.rerun()

# -----------------------------
# 🔹 Fonctions utilitaires
# -----------------------------

def load_sheet(sheet_name):
    try:
        data = spreadsheet.worksheet(sheet_name).get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Erreur lors du chargement de la feuille '{sheet_name}': {e}")
        return pd.DataFrame()

def montant_en_lettres(montant):
    return num2words(montant, lang='fr') + " dinars algériens"

def generer_facture_pdf(row_vente):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(200, 10, txt="FACTURE", ln=True, align="C")
    pdf.ln(10)

    for i, val in enumerate(row_vente):
        pdf.cell(200, 10, txt=str(val), ln=True, align="L")

    filename = f"facture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf.output(filename)
    st.success(f"📄 Facture générée : {filename}")

# -----------------------------
# 🔹 Interface Streamlit
# -----------------------------

tabs_labels = ["📦 Ajouter Stock", "💰 Enregistrer Vente", "📊 État Stock", "🧾 Historique Ventes", "💳 Paiements partiels"]
tab_choice = st.sidebar.radio("Navigation", tabs_labels)

# -----------------------------
# 📦 Onglet Ajouter Stock
# -----------------------------
if tab_choice == "📦 Ajouter Stock":
    st.header("Ajouter du stock")

    with st.form("form_stock"):
        marque = st.text_input("Marque")
        categorie = st.text_input("Catégorie")
        famille = st.text_input("Famille")
        produit_stock = st.text_input("Produit")
        quantite_stock = st.number_input("Quantité", min_value=1, step=1)
        prix_achat = st.number_input("Prix unitaire", min_value=0.0, step=0.01)

        if st.form_submit_button("Ajouter au stock"):
            row = [str(datetime.now()), marque, categorie, famille, produit_stock, quantite_stock, prix_achat, st.session_state.utilisateur]
            spreadsheet.worksheet("Stock").append_row(row)
            st.success("✅ Stock ajouté avec succès")

# -----------------------------
# 💰 Onglet Enregistrer Vente
# -----------------------------
elif tab_choice == "💰 Enregistrer Vente":
    st.header("Enregistrer une vente")

    df_stock = load_sheet("Stock")
    produits_dispo = df_stock["Produit"].dropna().unique().tolist() if not df_stock.empty else []

    if "panier" not in st.session_state:
        st.session_state.panier = []

    with st.form("form_vente"):
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

        prix_unitaire = float(df_stock.loc[df_stock['Produit'] == produit_vente, 'Prix unitaire'].values[0]) if not df_stock.empty else 0.0
        total_vente = prix_unitaire * quantite_vente
        st.write(f"Prix unitaire : {prix_unitaire} | Total HT : {total_vente:.2f} | Total TTC : {round(total_vente*1.19,2)}")

        montant_paye = st.number_input("Montant payé maintenant", min_value=0.0, max_value=float(total_vente), step=0.01)
        reste_a_payer = total_vente - montant_paye

        if st.form_submit_button("Ajouter au panier"):
            st.session_state.panier.append({
                "Produit": produit_vente,
                "Quantité": quantite_vente,
                "Prix unitaire": prix_unitaire,
                "Total": total_vente,
                "Montant payé": montant_paye,
                "Reste à payer": reste_a_payer
            })

    if st.session_state.panier:
        st.subheader("🛒 Panier actuel")
        st.table(st.session_state.panier)

        if st.button("✅ Enregistrer la vente"):
            df_ventes = load_sheet("Ventes")
            prochain_num = len(df_ventes) + 1

            for item in st.session_state.panier:
                row_vente = [
                    str(datetime.now()), client_nom, client_email, client_tel,
                    client_rc, client_nif, client_art, client_adresse,
                    "", "", "", item["Produit"], item["Quantité"],
                    item["Prix unitaire"], item["Total"], round(item["Total"]*1.19, 2),
                    item["Montant payé"], item["Reste à payer"], "", "", "", "", prochain_num,
                    st.session_state.utilisateur
                ]
                spreadsheet.worksheet("Ventes").append_row(row_vente)

            st.success("💰 Vente enregistrée avec succès !")
            st.session_state.panier = []

# -----------------------------
# 📊 Onglet État Stock
# -----------------------------
elif tab_choice == "📊 État Stock":
    st.header("État du stock")
    df_stock = load_sheet("Stock")
    if not df_stock.empty:
        st.dataframe(df_stock)
    else:
        st.write("Aucun stock enregistré.")

# -----------------------------
# 🧾 Onglet Historique Ventes
# -----------------------------
elif tab_choice == "🧾 Historique Ventes":
    st.header("Historique des ventes")
    df_ventes = load_sheet("Ventes")
    if not df_ventes.empty:
        st.dataframe(df_ventes)
    else:
        st.write("Aucune vente enregistrée.")

# -----------------------------
# 💳 Onglet Paiements partiels
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
