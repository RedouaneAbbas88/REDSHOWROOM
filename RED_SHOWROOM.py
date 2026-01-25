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
tabs_labels = ["🛒 Ajouter Stock", "💰 Enregistrer Vente", "📦 État Stock", "📄 Historique Ventes", "💳 Paiements partiels", "🧾 Charges quotidiennes"]
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
            st.success(f"{quantite_stock} x {produit_stock} ajouté(s) au stock.")

# -----------------------------
# Onglet 2 : Enregistrer Vente
# -----------------------------
elif tab_choice == "💰 Enregistrer Vente":
    st.header("Enregistrer une vente multi-produits")

    produit_vente = st.selectbox("Produit vendu *", produits_dispo)
    prix_unitaire = float(df_produits.loc[df_produits['Produit'] == produit_vente, 'Prix unitaire'].values[0]) if produit_vente else 0.0
    quantite_vente = st.number_input("Quantité vendue *", min_value=1, step=1)

    timbre = 100
    total_ht = prix_unitaire * quantite_vente
    tva = round(total_ht * 0.19, 2)
    total_ttc = round(total_ht + tva + timbre, 2)
    st.write(f"Prix unitaire : {prix_unitaire} DA | Total HT : {total_ht} DA | TVA : {tva} DA | Timbre : {timbre} DA | 💰 TTC : {total_ttc} DA")

    # Infos client
    client_nom = st.text_input("Nom du client *")
    client_tel = st.text_input("Téléphone du client *")
    client_adresse = st.text_input("Adresse du client")

    montant_paye = st.number_input("Montant payé par le client", min_value=0.0, max_value=total_ttc, value=0.0, step=1.0)
    reste_a_payer = total_ttc - montant_paye
    st.write(f"Reste à payer : {reste_a_payer:.2f} DA")

    if st.button("Ajouter au panier"):
        if not produit_vente or quantite_vente <= 0 or not client_nom.strip() or not client_tel.strip():
            st.error("⚠️ Remplir tous les champs obligatoires")
        else:
            st.session_state.panier.append({
                "Produit": produit_vente,
                "Quantité": quantite_vente,
                "Prix unitaire": prix_unitaire,
                "Total HT": total_ht,
                "TVA": tva,
                "Timbre": timbre,
                "Total TTC": total_ttc,
                "Montant payé": montant_paye,
                "Reste à payer": reste_a_payer,
                "Client Nom": client_nom,
                "Client Tel": client_tel,
                "Client Adresse": client_adresse
            })
            st.success(f"{quantite_vente} x {produit_vente} ajouté(s) au panier.")

    # Affichage panier
    if st.session_state.panier:
        st.subheader("Panier actuel")
        df_panier = pd.DataFrame(st.session_state.panier)
        st.dataframe(df_panier[['Produit','Quantité','Prix unitaire','Total HT','TVA','Timbre','Total TTC','Montant payé','Reste à payer']], use_container_width=True)

        indices_a_supprimer = []
        for i, item in enumerate(st.session_state.panier):
            col1, col2, col3 = st.columns([4,2,1])
            with col1:
                st.write(item["Produit"])
            with col2:
                nouvelle_qte = st.number_input(f"Qté {i}", min_value=1, value=item["Quantité"], key=f"qty_{i}")
                st.session_state.panier[i]["Quantité"] = nouvelle_qte
                st.session_state.panier[i]["Total HT"] = nouvelle_qte * item["Prix unitaire"]
                st.session_state.panier[i]["TVA"] = round(st.session_state.panier[i]["Total HT"] * 0.19,2)
                st.session_state.panier[i]["Total TTC"] = round(st.session_state.panier[i]["Total HT"] + st.session_state.panier[i]["TVA"] + timbre,2)
                st.session_state.panier[i]["Reste à payer"] = st.session_state.panier[i]["Total TTC"] - st.session_state.panier[i]["Montant payé"]
            with col3:
                if st.button("❌ Supprimer", key=f"del_{i}"):
                    indices_a_supprimer.append(i)
        for idx in sorted(indices_a_supprimer, reverse=True):
            st.session_state.panier.pop(idx)

        # Enregistrer et PDF
        if st.button("Enregistrer la vente"):
            df_stock = load_sheet("Stock")
            df_ventes = load_sheet("Ventes")
            vente_valide = True
            for item in st.session_state.panier:
                stock_dispo = df_stock[df_stock['Produit']==item["Produit"]]['Quantité'].sum()
                ventes_sum = df_ventes[df_ventes['Produit']==item["Produit"]]['Quantité'].sum() if not df_ventes.empty else 0
                if item["Quantité"] > (stock_dispo - ventes_sum):
                    st.error(f"Stock insuffisant pour {item['Produit']}")
                    vente_valide=False
            if vente_valide:
                prochain_num = f"{len(df_ventes)+1:03d}/2025" if not df_ventes.empty else "001/2025"
                for item in st.session_state.panier:
                    row = [str(datetime.now()), item["Client Nom"], item["Client Tel"], item["Client Adresse"],
                           item["Produit"], item["Quantité"], item["Prix unitaire"], item["Total HT"],
                           item["TVA"], item["Timbre"], item["Total TTC"], item["Montant payé"], item["Reste à payer"],
                           prochain_num]
                    spreadsheet.worksheet("Ventes").append_row(row)

                # PDF
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial",'B',16)
                pdf.cell(200,10,txt="NORTH AFRICA ELECTRONICS",ln=True,align="C")
                pdf.set_font("Arial",'B',14)
                pdf.cell(200,10,txt="Facture",ln=True,align="C")
                pdf.set_font("Arial",size=12)
                pdf.cell(200,10,txt=f"Date : {datetime.now().strftime('%d/%m/%Y')}",ln=True)
                pdf.cell(200,10,txt=f"Facture N° : {prochain_num}",ln=True)
                pdf.cell(200,10,txt=f"Client : {item['Client Nom']}",ln=True)
                pdf.cell(200,10,txt=f"Téléphone : {item['Client Tel']}",ln=True)
                pdf.cell(200,10,txt=f"Adresse : {item['Client Adresse']}",ln=True)
                pdf.ln(5)
                pdf.set_font("Arial",'B',12)
                pdf.cell(80,10,"Produit",1)
                pdf.cell(30,10,"Qté",1)
                pdf.cell(40,10,"Prix TTC",1)
                pdf.cell(40,10,"Total TTC",1,ln=True)
                pdf.set_font("Arial",12)
                total_global = 0
                for item in st.session_state.panier:
                    total_global += item["Total TTC"]
                    pdf.cell(80,10,item["Produit"],1)
                    pdf.cell(30,10,str(item["Quantité"]),1)
                    pdf.cell(40,10,f"{item['Total TTC']/item['Quantité']:.2f}",1)
                    pdf.cell(40,10,f"{item['Total TTC']:.2f}",1,ln=True)
                pdf.set_font("Arial",'B',12)
                pdf.cell(150,10,"TOTAL TTC",1)
                pdf.cell(40,10,f"{total_global:.2f}",1,ln=True)
                pdf_bytes = pdf.output(dest='S').encode('latin1')
                pdf_io = io.BytesIO(pdf_bytes)
                st.download_button("📄 Télécharger la facture PDF", data=pdf_io, file_name=f"facture_{prochain_num}.pdf", mime="application/pdf")
                st.success("Vente enregistrée ✅")
                st.session_state.panier=[]

# Les onglets 3 à 6 restent identiques (stock, historique, paiements partiels, charges)
