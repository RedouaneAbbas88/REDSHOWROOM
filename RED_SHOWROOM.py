import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from fpdf import FPDF
from datetime import datetime

# ============================
# 🔑 Connexion Google Sheets
# ============================
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

# Feuilles
sheet_ventes = client.open("RedShowroom").worksheet("Ventes")
sheet_produits = client.open("RedShowroom").worksheet("Produits")

# Charger données
df_ventes = pd.DataFrame(sheet_ventes.get_all_records())
df_produits = pd.DataFrame(sheet_produits.get_all_records())

# ============================
# 🔢 Fonction Numéro de facture auto
# ============================
def generer_numero_facture():
    if df_ventes.empty:
        return 1
    else:
        return int(df_ventes["Numéro de facture"].max()) + 1

# ============================
# 💰 Formatage des montants
# ============================
def format_montant(val):
    try:
        val = float(val)
        return f"{round(val):,}".replace(",", " ") + " DA"
    except:
        return val

# ============================
# 🧾 Génération du PDF facture
# ============================
def generer_pdf(nom_client, produit, quantite, prix_unitaire, total_ttc, montant_paye, reste, numero_facture):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, "FACTURE", ln=True, align="C")

    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, f"Numéro de facture : {numero_facture}", ln=True)
    pdf.cell(200, 10, f"Date : {datetime.now().strftime('%d/%m/%Y')}", ln=True)
    pdf.cell(200, 10, f"Client : {nom_client}", ln=True)

    pdf.ln(10)
    pdf.cell(200, 10, "Détails de la vente :", ln=True)

    pdf.set_font("Arial", size=11)
    pdf.cell(200, 10, f"Produit : {produit}", ln=True)
    pdf.cell(200, 10, f"Quantité : {quantite}", ln=True)
    pdf.cell(200, 10, f"Prix unitaire : {format_montant(prix_unitaire)}", ln=True)
    pdf.cell(200, 10, f"Total TTC : {format_montant(total_ttc)}", ln=True)
    pdf.cell(200, 10, f"Montant payé : {format_montant(montant_paye)}", ln=True)
    pdf.cell(200, 10, f"Reste à payer : {format_montant(reste)}", ln=True)

    file_name = f"facture_{numero_facture}.pdf"
    pdf.output(file_name)
    return file_name

# ============================
# 📌 Application Streamlit
# ============================
st.set_page_config(page_title="RedShowroom", layout="wide")
st.title("🛒 Gestion des ventes - RedShowroom")

menu = ["➕ Ajouter Stock", "💰 Enregistrer Vente", "📊 État Paiements Partiels"]
choice = st.sidebar.selectbox("Menu", menu)

# ============================
# ➕ Ajouter Stock
# ============================
if choice == "➕ Ajouter Stock":
    st.header("Ajouter un produit au stock")

    produit = st.text_input("Nom du produit")
    prix = st.number_input("Prix unitaire (DA)", min_value=0.0, format="%.2f")
    quantite = st.number_input("Quantité", min_value=1)

    if st.button("Ajouter au stock"):
        new_row = {"Produit": produit, "Prix unitaire": prix, "Quantité": quantite}
        sheet_produits.append_row(list(new_row.values()))
        st.success("✅ Produit ajouté au stock")

# ============================
# 💰 Enregistrer Vente
# ============================
elif choice == "💰 Enregistrer Vente":
    st.header("Nouvelle vente")

    numero_facture = generer_numero_facture()
    st.write(f"**Numéro de facture : {numero_facture}**")

    client_nom = st.text_input("Nom du client")
    produit = st.selectbox("Produit", df_produits["Produit"].unique() if not df_produits.empty else [])
    quantite = st.number_input("Quantité", min_value=1)

    if produit:
        prix_unitaire = float(df_produits.loc[df_produits["Produit"] == produit, "Prix unitaire"].values[0])
        total_ttc = round(prix_unitaire * quantite)
        montant_paye = st.number_input("Montant payé", min_value=0, value=total_ttc)
        reste = total_ttc - montant_paye

        st.metric("Montant TTC", format_montant(total_ttc))

        if st.button("Enregistrer la vente"):
            new_row = {
                "Numéro de facture": numero_facture,
                "Nom du client": client_nom,
                "Produit": produit,
                "Quantité": quantite,
                "Prix unitaire": prix_unitaire,
                "Total TTC": total_ttc,
                "Montant payé": montant_paye,
                "Reste à payer": reste
            }
            sheet_ventes.append_row(list(new_row.values()))

            pdf_file = generer_pdf(client_nom, produit, quantite, prix_unitaire, total_ttc, montant_paye, reste, numero_facture)
            st.success(f"✅ Vente enregistrée - Facture générée : {pdf_file}")

# ============================
# 📊 État Paiements Partiels
# ============================
elif choice == "📊 État Paiements Partiels":
    st.header("Suivi des paiements partiels")

    if df_ventes.empty:
        st.info("Aucune vente enregistrée.")
    else:
        df_affiche = df_ventes.copy()
        df_affiche["Total TTC"] = df_affiche["Total TTC"].apply(format_montant)
        df_affiche["Montant payé"] = df_affiche["Montant payé"].apply(format_montant)
        df_affiche["Reste à payer"] = df_affiche["Reste à payer"].apply(format_montant)

        st.dataframe(df_affiche[["Numéro de facture", "Nom du client", "Produit", "Total TTC", "Montant payé", "Reste à payer"]])
