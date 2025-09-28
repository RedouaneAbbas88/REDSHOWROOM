import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from io import BytesIO
import datetime

# === Connexion Google Sheets ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(credentials)

# Charger les feuilles
sheet_produits = client.open("RED_SHOWROOM").worksheet("Produits")
sheet_ventes = client.open("RED_SHOWROOM").worksheet("Ventes")
sheet_paiements = client.open("RED_SHOWROOM").worksheet("Paiements")

# Convertir en DataFrame
df_produits = pd.DataFrame(sheet_produits.get_all_records())
df_ventes = pd.DataFrame(sheet_ventes.get_all_records())
df_paiements = pd.DataFrame(sheet_paiements.get_all_records())

# === Fonction sélection produit ===
def selection_produit(df, prefix=""):
    marques_dispo = df["Marque"].dropna().unique().tolist()
    marque = st.selectbox(f"{prefix} Marque", marques_dispo, key=f"{prefix}_marque")

    produits_dispo = df[df["Marque"] == marque]["Produit"].dropna().unique().tolist()
    produit = st.selectbox(f"{prefix} Produit", produits_dispo, key=f"{prefix}_produit")

    df_selection = df[(df["Marque"] == marque) & (df["Produit"] == produit)]
    prix_unitaire = float(df_selection["Prix unitaire"].values[0]) if not df_selection.empty else 0.0

    return marque, produit, prix_unitaire

# === Fonction numéro facture ===
def get_next_invoice_number():
    if df_ventes.empty:
        return 1
    last_invoice = df_ventes["Facture"].astype(int).max()
    return last_invoice + 1

# === Fonction export PDF ===
def export_pdf(facture_num, nom_client, panier, total_ttc):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # En-tête facture
    c.setFont("Helvetica-Bold", 14)
    c.drawString(2 * cm, height - 2 * cm, f"Facture N° {facture_num}")
    c.setFont("Helvetica", 12)
    c.drawString(2 * cm, height - 3 * cm, f"Client : {nom_client}")
    c.drawString(2 * cm, height - 4 * cm, f"Date : {datetime.datetime.today().strftime('%d/%m/%Y')}")

    # Tableau produits
    y = height - 6 * cm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(2 * cm, y, "Produit")
    c.drawString(8 * cm, y, "Quantité")
    c.drawString(12 * cm, y, "Prix TTC")
    c.drawString(16 * cm, y, "Total TTC")

    c.setFont("Helvetica", 12)
    for item in panier:
        y -= 1 * cm
        c.drawString(2 * cm, y, item["Produit"])
        c.drawString(8 * cm, y, str(item["Quantité"]))
        c.drawString(12 * cm, y, f"{item['Prix TTC']:,.2f}")
        c.drawString(16 * cm, y, f"{item['Total TTC']:,.2f}")

    # Total
    y -= 2 * cm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(10 * cm, y, f"TOTAL TTC : {total_ttc:,.2f} DA")

    c.save()
    buffer.seek(0)
    return buffer

# === Application ===
st.title("📊 RED SHOWROOM - Gestion des Ventes & Stocks")

tabs_labels = ["📦 Ajout Stock", "💰 Enregistrer Vente", "📑 Historique", "💵 Paiement Partiel"]
tab_choice = st.sidebar.radio("Navigation", tabs_labels)

# === Ajout Stock ===
if tab_choice == "📦 Ajout Stock":
    st.header("Ajout de Stock")

    marque, produit, prix_unitaire = selection_produit(df_produits, prefix="stock")
    quantite = st.number_input("Quantité", min_value=1, value=1)

    if st.button("Ajouter au stock"):
        sheet_produits.append_row([marque, produit, prix_unitaire, quantite])
        st.success("Stock ajouté avec succès ✅")

# === Enregistrer Vente ===
elif tab_choice == "💰 Enregistrer Vente":
    st.header("Nouvelle Vente")

    facture_num = get_next_invoice_number()
    st.write(f"**Numéro de facture : {facture_num}**")

    nom_client = st.text_input("Nom du client")
    panier = []

    marque, produit, prix_unitaire = selection_produit(df_produits, prefix="vente")
    quantite = st.number_input("Quantité vendue", min_value=1, value=1)

    total_ttc = prix_unitaire * quantite
    st.write(f"💵 Montant TTC : **{total_ttc:,.2f} DA**")

    if st.button("Ajouter au panier"):
        panier.append({
            "Produit": produit,
            "Quantité": quantite,
            "Prix TTC": prix_unitaire,
            "Total TTC": total_ttc
        })
        st.success("Produit ajouté au panier ✅")

    if st.button("Valider la vente"):
        for item in panier:
            sheet_ventes.append_row([facture_num, nom_client, item["Produit"], item["Quantité"], item["Prix TTC"], item["Total TTC"], datetime.datetime.today().strftime("%d/%m/%Y")])

        pdf_file = export_pdf(facture_num, nom_client, panier, total_ttc)
        st.download_button("📥 Télécharger la facture PDF", data=pdf_file, file_name=f"Facture_{facture_num}.pdf", mime="application/pdf")

# === Historique ===
elif tab_choice == "📑 Historique":
    st.header("Historique des ventes")
    st.dataframe(df_ventes)

# === Paiement Partiel ===
elif tab_choice == "💵 Paiement Partiel":
    st.header("Enregistrer un paiement partiel")

    if not df_ventes.empty:
        clients = df_ventes["Nom"].unique().tolist() if "Nom" in df_ventes.columns else []
        client = st.selectbox("Choisir un client", clients)

        montant = st.number_input("Montant payé", min_value=1.0, value=1000.0)
        if st.button("Enregistrer paiement"):
            sheet_paiements.append_row([client, montant, datetime.datetime.today().strftime("%d/%m/%Y")])
            st.success("Paiement enregistré ✅")
    else:
        st.warning("Aucune vente enregistrée.")

