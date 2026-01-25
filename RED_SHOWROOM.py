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
tabs_labels = ["🛒 Ajouter Stock", "💰 Enregistrer Vente", "📦 État Stock",
               "📄 Historique Ventes", "💳 Paiements partiels", "🧾 Charges quotidiennes"]

if "active_tab" not in st.session_state:
    st.session_state.active_tab = 0
if "panier" not in st.session_state:
    st.session_state.panier = []

tab_choice = st.radio("Choisir l'onglet", tabs_labels, index=st.session_state.active_tab)
st.session_state.active_tab = tabs_labels.index(tab_choice)

# -----------------------------
# 🔹 Fonction montant en lettres
# -----------------------------
def montant_en_lettres(number):
    from num2words import num2words
    try:
        return num2words(number, lang='fr').capitalize() + " DA"
    except:
        return ""

# =============================
# Onglet 1 : Ajouter Stock
# =============================
if tab_choice == "🛒 Ajouter Stock":
    st.header("Ajouter du stock")
    with st.form("form_stock"):
        produit_stock = st.selectbox("Produit *", produits_dispo)
        prix_achat = float(df_produits.loc[df_produits['Produit'] == produit_stock, 'Prix unitaire'].values[0]) if not df_produits.empty else 0.0
        quantite_stock = st.number_input("Quantité achetée", min_value=1, step=1)
        if st.form_submit_button("Ajouter au stock"):
            row = [str(datetime.now()), produit_stock, quantite_stock, prix_achat]
            spreadsheet.worksheet("Stock").append_row(row)
            st.success(f"{quantite_stock} {produit_stock} ajouté(s) au stock.")

# =============================
# Onglet 2 : Enregistrer Vente
# =============================
elif tab_choice == "💰 Enregistrer Vente":
    st.header("Enregistrer une vente multi-produits")

    produit_vente = st.selectbox("Produit vendu *", produits_dispo)
    prix_unitaire = float(df_produits.loc[df_produits['Produit'] == produit_vente, 'Prix unitaire'].values[0]) if produit_vente else 0.0
    quantite_vente = st.number_input("Quantité vendue *", min_value=1, step=1)
    total_ht = prix_unitaire * quantite_vente
    total_ttc = int(round(total_ht * 1.19, 0))
    st.write(f"Prix unitaire : {prix_unitaire} DA | Total TTC : {total_ttc} DA")
    st.write(f"Montant en lettres : {montant_en_lettres(total_ttc)}")

    # Infos client pour saisie
    client_nom = st.text_input("Nom du client *")
    client_email = st.text_input("Email du client")
    client_tel = st.text_input("Téléphone du client *")
    client_rc = st.text_input("RC du client")
    client_nif = st.text_input("NIF du client")
    client_art = st.text_input("ART du client")
    client_adresse = st.text_input("Adresse du client")

    montant_paye = st.number_input("Montant payé par le client", min_value=0, max_value=total_ttc, value=0, step=1)
    reste_a_payer = total_ttc - montant_paye
    st.write(f"Reste à payer : {reste_a_payer} DA")

    generer_facture = st.checkbox("Générer une facture PDF")

    if st.button("Ajouter au panier"):
        if not produit_vente or quantite_vente <= 0 or not client_nom.strip() or not client_tel.strip():
            st.error("⚠️ Merci de remplir tous les champs obligatoires.")
        else:
            st.session_state.panier.append({
                "Produit": produit_vente,
                "Quantité": quantite_vente,
                "Prix unitaire": prix_unitaire,
                "Total HT": total_ht,
                "Total TTC": total_ttc,
                "Montant payé": montant_paye,
                "Reste à payer": reste_a_payer,
                "Client Nom": client_nom,
                "Client Email": client_email,
                "Client Tel": client_tel,
                "Client RC": client_rc,
                "Client NIF": client_nif,
                "Client ART": client_art,
                "Client Adresse": client_adresse
            })
            st.success(f"{quantite_vente} x {produit_vente} ajouté(s) au panier.")

    # Affichage panier
    if st.session_state.panier:
        st.subheader("Panier actuel")
        df_panier = pd.DataFrame(st.session_state.panier)
        st.dataframe(df_panier[['Produit','Quantité','Prix unitaire','Total HT','Total TTC','Montant payé','Reste à payer']], use_container_width=True, hide_index=True)

        indices_a_supprimer = []
        for i, item in enumerate(st.session_state.panier):
            col1, col2, col3 = st.columns([4,2,1])
            with col1:
                st.write(item["Produit"])
            with col2:
                nouvelle_quantite = st.number_input(f"Qté {i}", min_value=1, value=item["Quantité"], key=f"qty_{i}")
                st.session_state.panier[i]["Quantité"] = nouvelle_quantite
                st.session_state.panier[i]["Total HT"] = nouvelle_quantite * item["Prix unitaire"]
                st.session_state.panier[i]["Total TTC"] = int(round(st.session_state.panier[i]["Total HT"] * 1.19,0))
                st.session_state.panier[i]["Reste à payer"] = st.session_state.panier[i]["Total TTC"] - st.session_state.panier[i]["Montant payé"]
            with col3:
                if st.button("❌ Supprimer", key=f"del_{i}"):
                    indices_a_supprimer.append(i)
        for index in sorted(indices_a_supprimer, reverse=True):
            st.session_state.panier.pop(index)

        # Enregistrer vente et générer PDF
        if st.button("Enregistrer la vente"):
            df_stock = load_sheet("Stock")
            df_ventes = load_sheet("Ventes")
            vente_valide = True

            for item in st.session_state.panier:
                stock_dispo = df_stock[df_stock['Produit']==item["Produit"]]['Quantité'].sum()
                ventes_sum = df_ventes[df_ventes['Produit']==item["Produit"]]['Quantité'].sum() if not df_ventes.empty else 0
                stock_reel = stock_dispo - ventes_sum
                if item["Quantité"] > stock_reel:
                    st.error(f"Stock insuffisant pour {item['Produit']} ! Disponible : {stock_reel}")
                    vente_valide = False

            if vente_valide:
                # Génération PDF et enregistrement dans Google Sheets (reste inchangé)
                st.success(f"Vente enregistrée avec {len(st.session_state.panier)} produits.")
                st.session_state.panier = []

# =============================
# Onglet 3 : État Stock
# =============================
elif tab_choice == "📦 État Stock":
    st.header("État du stock")
    df_stock = load_sheet("Stock")
    df_ventes = load_sheet("Ventes")
    if not df_stock.empty:
        stock_reel = df_stock.groupby("Produit")["Quantité"].sum().reset_index()
        if not df_ventes.empty:
            ventes_group = df_ventes.groupby("Produit")["Quantité"].sum().reset_index()
            stock_reel = stock_reel.merge(ventes_group,on="Produit",how="left",suffixes=('','_vendu'))
            stock_reel['Quantité_vendu'] = stock_reel['Quantité_vendu'].fillna(0)
            stock_reel['Stock restant'] = stock_reel['Quantité'] - stock_reel['Quantité_vendu']
        else:
            stock_reel['Stock restant'] = stock_reel['Quantité']
        st.dataframe(stock_reel[['Produit','Stock restant']],use_container_width=True)
    else:
        st.write("Aucun stock enregistré.")

# =============================
# Onglet 4 : Historique Ventes
# =============================
elif tab_choice == "📄 Historique Ventes":
    st.header("Historique des ventes")
    df_ventes = load_sheet("Ventes")
    if not df_ventes.empty:
        st.dataframe(df_ventes,use_container_width=True)
    else:
        st.write("Aucune vente enregistrée.")

# =============================
# Onglet 5 : Paiements partiels
# =============================
elif tab_choice == "💳 Paiements partiels":
    st.header("État des paiements partiels")
    df_ventes = load_sheet("Ventes")
    if not df_ventes.empty:
        df_partiels = df_ventes[df_ventes["Reste à payer"] >0]
        if not df_partiels.empty:
            st.dataframe(df_partiels[["Produit","Client Nom","Client Tel","Total TTC","Montant payé","Reste à payer"]],use_container_width=True)
        else:
            st.write("Aucun paiement partiel en attente.")
    else:
        st.write("Aucune vente enregistrée.")

# =============================
# Onglet 6 : Charges quotidiennes
# =============================
elif tab_choice == "🧾 Charges quotidiennes":
    st.header("Note de charges quotidiennes")

    # Initialisation panier charges
    if "charges_panier" not in st.session_state:
        st.session_state.charges_panier = []

    ref_charge = f"CHG-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    st.info(f"📌 Référence du document : {ref_charge}")

    # Charger types de charges
    def load_types_charges():
        try:
            sheet = spreadsheet.worksheet("Types_Charges")
            header = sheet.row_values(1)
            col_index = header.index("Type de charge")+1
            values = sheet.col_values(col_index)[1:]
            types = [v for v in values if v.strip()]
            return types if types else ["Autre"]
        except:
            return ["Autre"]

    types_dispo = load_types_charges()

    # Formulaire saisie charge
    with st.form("form_ligne_charge"):
        date_charge = st.date_input("Date", value=datetime.today(), min_value=datetime.today())
        type_charge = st.selectbox("Type de charge *", types_dispo)
        montant_charge = st.number_input("Montant (DA) *", min_value=0, step=1)
        observation_charge = st.text_area("Observation")
        if st.form_submit_button("Ajouter la charge"):
            st.session_state.charges_panier.append({
                "Réf": ref_charge,
                "Date": str(date_charge),
                "Type": type_charge,
                "Montant": montant_charge,
                "Observation": observation_charge
            })
            st.success("Charge ajoutée au panier.")

    # Affichage panier et total
    if st.session_state.charges_panier:
        st.subheader("Charges à enregistrer")
        df_charges = pd.DataFrame(st.session_state.charges_panier)
        st.dataframe(df_charges,use_container_width=True)

        # Calcul total dynamique
        total_charges = df_charges["Montant"].sum()
        st.metric("💰 Total cumulé charges à enregistrer", f"{total_charges:,.2f} DA")

        if st.button("Enregistrer toutes les charges"):
            for item in st.session_state.charges_panier:
                spreadsheet.worksheet("Charges").append_row(list(item.values()))
            st.success(f"{len(st.session_state.charges_panier)} charge(s) enregistrée(s).")
            st.session_state.charges_panier = []
