import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import tempfile
import datetime

# --- CONFIG STREAMLIT ---
st.set_page_config(page_title="Showroom Stock & Vente", layout="wide")

# --- CONNEXION GOOGLE SHEETS ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

try:
    sheet_produits = client.open("RedShowroom").worksheet("Produits")
    sheet_stock = client.open("RedShowroom").worksheet("Stock")
    sheet_ventes = client.open("RedShowroom").worksheet("Ventes")
except Exception as e:
    st.error(f"Erreur de connexion à Google Sheets: {e}")
    st.stop()

# --- CHARGER LES DONNÉES ---
df_produits = pd.DataFrame(sheet_produits.get_all_records())
df_stock = pd.DataFrame(sheet_stock.get_all_records())
df_ventes = pd.DataFrame(sheet_ventes.get_all_records())

# --- SESSION PANIER ---
if "panier" not in st.session_state:
    st.session_state.panier = []

# --- UTILISATEURS AUTORISÉS ---
USERS = ["Zakaria", "Sanae", "Redouane"]

if "user" not in st.session_state:
    st.session_state.user = None

# --- PAGE LOGIN ---
if not st.session_state.user:
    st.title("🔑 Connexion utilisateur")
    user_input = st.selectbox("Choisir votre nom", [""] + USERS)
    if st.button("Se connecter"):
        if user_input in USERS:
            st.session_state.user = user_input
            st.success(f"✅ Connecté en tant que {user_input}")
            st.rerun()
        else:
            st.error("❌ Utilisateur non autorisé")
else:
    st.sidebar.success(f"👤 Utilisateur connecté : {st.session_state.user}")
    if st.sidebar.button("Se déconnecter"):
        st.session_state.user = None
        st.rerun()

    # --- ONGLET NAVIGATION ---
    tabs_labels = ["🛒 Ajouter Stock", "💰 Enregistrer Vente", "📦 État Stock", "📄 Historique Ventes", "💳 Paiements partiels"]
    tab_choice = st.sidebar.radio("Navigation", tabs_labels)

    # --- ONGLET 1 : AJOUTER STOCK ---
    if tab_choice == "🛒 Ajouter Stock":
        st.header("🛒 Ajouter du stock")
        with st.form("form_stock"):
            marques = df_produits["Marque"].dropna().unique().tolist()
            marque = st.selectbox("Marque", marques)

            categories = df_produits[df_produits["Marque"] == marque]["Catégorie"].dropna().unique().tolist()
            categorie = st.selectbox("Catégorie", categories)

            familles = df_produits[
                (df_produits["Marque"] == marque) &
                (df_produits["Catégorie"] == categorie)
            ]["Famille"].dropna().unique().tolist()
            famille = st.selectbox("Famille", familles)

            produits = df_produits[
                (df_produits["Marque"] == marque) &
                (df_produits["Catégorie"] == categorie) &
                (df_produits["Famille"] == famille)
            ]["Produit"].dropna().tolist()
            produit = st.selectbox("Produit", produits)

            prix = float(df_produits[df_produits["Produit"] == produit]["Prix unitaire"].values[0])
            quantite = st.number_input("Quantité ajoutée", min_value=1, step=1)

            if st.form_submit_button("Ajouter au stock"):
                row = [str(datetime.datetime.now()), marque, categorie, famille, produit, quantite, prix, st.session_state.user]
                sheet_stock.append_row(row)
                st.success(f"{quantite} x {produit} ajouté au stock par {st.session_state.user}")

    # --- ONGLET 2 : ENREGISTRER VENTE ---
    elif tab_choice == "💰 Enregistrer Vente":
        st.header("💰 Enregistrer une vente multi-produits")

        with st.form("form_vente_multi"):
            marques = df_produits["Marque"].dropna().unique().tolist()
            marque = st.selectbox("Marque", marques)

            categories = df_produits[df_produits["Marque"] == marque]["Catégorie"].dropna().unique().tolist()
            categorie = st.selectbox("Catégorie", categories)

            familles = df_produits[
                (df_produits["Marque"] == marque) &
                (df_produits["Catégorie"] == categorie)
            ]["Famille"].dropna().unique().tolist()
            famille = st.selectbox("Famille", familles)

            produits = df_produits[
                (df_produits["Marque"] == marque) &
                (df_produits["Catégorie"] == categorie) &
                (df_produits["Famille"] == famille)
            ]["Produit"].dropna().tolist()
            produit = st.selectbox("Produit", produits)

            prix = float(df_produits[df_produits["Produit"] == produit]["Prix unitaire"].values[0])
            quantite = st.number_input("Quantité vendue", min_value=1, step=1)

            client_nom = st.text_input("Nom client *")
            client_tel = st.text_input("Téléphone client *")
            client_email = st.text_input("Email client")
            client_rc = st.text_input("RC client")
            client_nif = st.text_input("NIF client")
            client_art = st.text_input("ART client")
            client_adresse = st.text_input("Adresse client")

            montant_paye = st.number_input("💵 Montant payé", min_value=0.0, step=100.0)
            total = prix * quantite
            reste = total - montant_paye

            st.info(f"Prix unitaire : {prix} | Total TTC : {total:.2f} | Payé : {montant_paye:.2f} | Reste : {reste:.2f}")

            if st.form_submit_button("➕ Ajouter au panier"):
                if not client_nom or not client_tel:
                    st.error("⚠️ Client nom et téléphone obligatoires")
                else:
                    st.session_state.panier.append({
                        "Date": str(datetime.datetime.now()),
                        "Nom": client_nom,
                        "Téléphone": client_tel,
                        "Email": client_email,
                        "RC": client_rc,
                        "NIF": client_nif,
                        "ART": client_art,
                        "Adresse": client_adresse,
                        "Marque": marque,
                        "Catégorie": categorie,
                        "Famille": famille,
                        "Produit": produit,
                        "Quantité": quantite,
                        "Prix unitaire": prix,
                        "Total TTC": total,
                        "Montant payé": montant_paye,
                        "Reste à payer": reste,
                        "Utilisateur": st.session_state.user
                    })
                    st.success("✅ Produit ajouté au panier")

        if st.session_state.panier:
            st.subheader("🛍️ Panier")
            st.dataframe(pd.DataFrame(st.session_state.panier))

            if st.button("💾 Enregistrer la vente"):
                for item in st.session_state.panier:
                    sheet_ventes.append_row(list(item.values()))

                st.success("✅ Vente enregistrée")

                # Générer facture PDF
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                c = canvas.Canvas(temp_file.name, pagesize=A4)
                c.drawString(100, 800, f"Facture - Client {st.session_state.panier[0]['Nom']}")
                y = 750
                for item in st.session_state.panier:
                    c.drawString(100, y, f"{item['Produit']} x{item['Quantité']} - {item['Total TTC']} DA")
                    y -= 20
                c.save()

                with open(temp_file.name, "rb") as pdf_file:
                    st.download_button("⬇️ Télécharger facture", pdf_file, file_name="facture.pdf")

                st.session_state.panier = []
                st.rerun()

    # --- ONGLET 3 : ÉTAT STOCK ---
    elif tab_choice == "📦 État Stock":
        st.header("📦 État du stock")
        if df_stock.empty:
            st.info("Stock vide")
        else:
            st.dataframe(df_stock)

    # --- ONGLET 4 : HISTORIQUE VENTES ---
    elif tab_choice == "📄 Historique Ventes":
        st.header("📄 Historique des ventes")
        if df_ventes.empty:
            st.info("Aucune vente enregistrée")
        else:
            st.dataframe(df_ventes)

    # --- ONGLET 5 : PAIEMENTS PARTIELS ---
    elif tab_choice == "💳 Paiements partiels":
        st.header("💳 Suivi paiements partiels")
        if df_ventes.empty:
            st.info("Aucune vente")
        else:
            df_partiels = df_ventes[df_ventes["Reste à payer"] > 0]
            if df_partiels.empty:
                st.success("🎉 Aucun paiement partiel en attente")
            else:
                st.dataframe(df_partiels[["Nom", "Produit", "Total TTC", "Montant payé", "Reste à payer"]])

                # Enregistrer un paiement complémentaire
                client_sel = st.selectbox("Choisir un client", df_partiels["Nom"].unique())
                montant_comp = st.number_input("Montant complémentaire payé", min_value=0.0, step=100.0)
                if st.button("💵 Enregistrer paiement complémentaire"):
                    idx = df_partiels[df_partiels["Nom"] == client_sel].index[0]
                    vente_id = idx + 2  # +2 car header + index base 0
                    montant_actuel = float(df_ventes.loc[idx, "Montant payé"])
                    reste_actuel = float(df_ventes.loc[idx, "Reste à payer"])

                    nouveau_paye = montant_actuel + montant_comp
                    nouveau_reste = max(0, reste_actuel - montant_comp)

                    sheet_ventes.update_cell(vente_id, df_ventes.columns.get_loc("Montant payé") + 1, nouveau_paye)
                    sheet_ventes.update_cell(vente_id, df_ventes.columns.get_loc("Reste à payer") + 1, nouveau_reste)

                    st.success(f"✅ Paiement mis à jour : Nouveau payé {nouveau_paye} | Reste {nouveau_reste}")
                    st.rerun()
