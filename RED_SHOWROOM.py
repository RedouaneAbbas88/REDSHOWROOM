import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from fpdf import FPDF
import io
from num2words import num2words

# ---------------- CONFIGURATION GOOGLE SHEETS ----------------
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds_dict = st.secrets["google"]
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
client = gspread.authorize(creds)

SPREADSHEET_ID = "1r4xnyKDaY6jzYGLUORKHlPeGKMCCLkkIx_XvSkIobhc"
spreadsheet = client.open_by_key(SPREADSHEET_ID)

# ---------------- SESSION STATE ----------------
if "onglet_actif" not in st.session_state:
    st.session_state["onglet_actif"] = "Ajouter Stock"

if "panier" not in st.session_state:
    st.session_state["panier"] = []

# ---------------- NAVIGATION ----------------
onglets = ["Ajouter Stock", "Enregistrer Vente", "État Stock", "Historique Ventes"]
onglet = st.radio("Navigation", onglets, index=onglets.index(st.session_state["onglet_actif"]))
st.session_state["onglet_actif"] = onglet

# ---------------- ONGLET AJOUTER STOCK ----------------
if onglet == "Ajouter Stock":
    st.header("Ajouter du Stock")
    df_produits = pd.DataFrame(spreadsheet.worksheet("Produits").get_all_records())
    produits_dispo = df_produits['Produit'].tolist() if not df_produits.empty else []

    produit = st.selectbox("Produit", produits_dispo)
    quantite = st.number_input("Quantité", min_value=1, step=1)
    prix = st.number_input("Prix Unitaire", min_value=0.0, step=0.1)

    if st.button("Ajouter au Stock"):
        spreadsheet.worksheet("Stock").append_row([str(datetime.now()), produit, quantite, prix])
        st.success("Stock ajouté ✅")
        st.session_state["onglet_actif"] = "Ajouter Stock"

# ---------------- ONGLET ENREGISTRER VENTE ----------------
elif onglet == "Enregistrer Vente":
    st.header("Enregistrer une Vente")
    df_produits = pd.DataFrame(spreadsheet.worksheet("Produits").get_all_records())
    produits_dispo = df_produits['Produit'].tolist() if not df_produits.empty else []

    with st.form("form_vente"):
        client_nom = st.text_input("Nom Client")
        produit = st.selectbox("Produit", produits_dispo)
        quantite = st.number_input("Quantité", min_value=1, step=1)
        generer_pdf = st.checkbox("Générer Facture PDF")

        prix_unitaire = float(df_produits.loc[df_produits['Produit'] == produit, 'Prix unitaire'].values[0]) if not df_produits.empty else 0.0
        total = prix_unitaire * quantite
        st.write(f"Prix Unitaire: {prix_unitaire} | Total HT: {total:.2f} | Total TTC: {round(total*1.19,2)}")

        if st.form_submit_button("Ajouter au Panier"):
            st.session_state["panier"].append({
                "Client": client_nom,
                "Produit": produit,
                "Quantité": quantite,
                "Prix unitaire": prix_unitaire,
                "Total": total
            })
            st.success("Produit ajouté au panier ✅")
            st.session_state["onglet_actif"] = "Enregistrer Vente"

    # ---------------- PANIER ----------------
    if st.session_state["panier"]:
        st.subheader("Panier")
        df_panier = pd.DataFrame(st.session_state["panier"])
        st.dataframe(df_panier, use_container_width=True)

        # Modifier / Supprimer
        indices_a_supprimer = []
        for i, item in enumerate(st.session_state["panier"]):
            col1, col2, col3 = st.columns([4, 2, 1])
            with col1:
                st.write(item["Produit"])
            with col2:
                new_qty = st.number_input(f"Quantité {i}", min_value=1, value=item["Quantité"], key=f"qty_{i}")
                st.session_state["panier"][i]["Quantité"] = new_qty
                st.session_state["panier"][i]["Total"] = new_qty * item["Prix unitaire"]
            with col3:
                if st.button("❌ Supprimer", key=f"del_{i}"):
                    indices_a_supprimer.append(i)

        for index in sorted(indices_a_supprimer, reverse=True):
            st.session_state["panier"].pop(index)

        st.markdown("---")

        # ---------------- ENREGISTRER VENTE ----------------
        if st.button("Enregistrer Vente", key="enregistrer_vente"):
            df_stock = pd.DataFrame(spreadsheet.worksheet("Stock").get_all_records())
            df_ventes = pd.DataFrame(spreadsheet.worksheet("Ventes").get_all_records())
            vente_valide = True

            # Vérification stock
            for item in st.session_state["panier"]:
                stock_dispo = df_stock[df_stock['Produit'] == item["Produit"]]['Quantité'].sum()
                ventes_sum = df_ventes[df_ventes['Produit'] == item["Produit"]]['Quantité'].sum() if not df_ventes.empty else 0
                if item["Quantité"] > (stock_dispo - ventes_sum):
                    st.error(f"Stock insuffisant pour {item['Produit']}")
                    vente_valide = False

            if vente_valide:
                for item in st.session_state["panier"]:
                    numero_facture = f"{len(df_ventes)+1}/{datetime.now().year}" if generer_pdf else ""
                    spreadsheet.worksheet("Ventes").append_row([
                        str(datetime.now()), item["Client"], item["Produit"], item["Quantité"],
                        item["Prix unitaire"], item["Total"], round(item["Total"]*1.19,2), numero_facture
                    ])
                st.success("Vente enregistrée ✅")
                st.session_state["onglet_actif"] = "Enregistrer Vente"

                # Génération PDF
                if generer_pdf:
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", "B", 14)
                    pdf.cell(0, 10, f"Facture Numéro: {numero_facture}", ln=True, align="C")
                    pdf.ln(5)
                    for item in st.session_state["panier"]:
                        pdf.cell(0, 8, f"{item['Produit']} x {item['Quantité']} = {item['Total']:.2f} DA", ln=True)
                    pdf_bytes = pdf.output(dest='S').encode('latin1')
                    pdf_io = io.BytesIO(pdf_bytes)
                    st.download_button("📥 Télécharger Facture PDF", data=pdf_io, file_name=f"facture_{numero_facture}.pdf", mime="application/pdf")

                st.session_state["panier"] = []

# ---------------- ONGLET ÉTAT STOCK ----------------
elif onglet == "État Stock":
    st.header("État du Stock")
    df_stock = pd.DataFrame(spreadsheet.worksheet("Stock").get_all_records())
    df_ventes = pd.DataFrame(spreadsheet.worksheet("Ventes").get_all_records())
    if not df_stock.empty:
        stock_reel = df_stock.groupby("Produit")["Quantité"].sum().reset_index()
        if not df_ventes.empty:
            ventes_group = df_ventes.groupby("Produit")["Quantité"].sum().reset_index()
            stock_reel = stock_reel.merge(ventes_group, on="Produit", how="left", suffixes=('', '_vendu'))
            stock_reel['Quantité_vendu'] = stock_reel['Quantité_vendu'].fillna(0)
            stock_reel['Stock restant'] = stock_reel['Quantité'] - stock_reel['Quantité_vendu']
        else:
            stock_reel['Stock restant'] = stock_reel['Quantité']
        st.dataframe(stock_reel[['Produit','Stock restant']], use_container_width=True)
    else:
        st.info("Aucun stock enregistré.")

# ---------------- ONGLET HISTORIQUE VENTES ----------------
elif onglet == "Historique Ventes":
    st.header("Historique des Ventes")
    df_ventes = pd.DataFrame(spreadsheet.worksheet("Ventes").get_all_records())
    if not df_ventes.empty:
        st.dataframe(df_ventes, use_container_width=True)
    else:
        st.info("Aucune vente enregistrée.")
