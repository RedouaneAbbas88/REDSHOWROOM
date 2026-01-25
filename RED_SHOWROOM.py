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
    st.write(f"Prix unitaire : {prix_unitaire} DA | 💰 Total TTC : {total_ttc} DA")

    # Infos client pour saisie (restent dans le système)
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

    # -------------------------------
    # Affichage du panier
    # -------------------------------
    if st.session_state.panier:
        st.subheader("Panier actuel")
        df_panier = pd.DataFrame(st.session_state.panier)
        st.dataframe(df_panier[['Produit', 'Quantité', 'Prix unitaire', 'Total HT', 'Total TTC', 'Montant payé', 'Reste à payer']], use_container_width=True, hide_index=True)

        indices_a_supprimer = []
        for i, item in enumerate(st.session_state.panier):
            col1, col2, col3 = st.columns([4, 2, 1])
            with col1:
                st.write(item["Produit"])
            with col2:
                nouvelle_quantite = st.number_input(f"Qté {i}", min_value=1, value=item["Quantité"], key=f"qty_{i}")
                st.session_state.panier[i]["Quantité"] = nouvelle_quantite
                st.session_state.panier[i]["Total HT"] = nouvelle_quantite * item["Prix unitaire"]
                st.session_state.panier[i]["Total TTC"] = int(round(st.session_state.panier[i]["Total HT"] * 1.19, 0))
                st.session_state.panier[i]["Reste à payer"] = st.session_state.panier[i]["Total TTC"] - st.session_state.panier[i]["Montant payé"]
            with col3:
                if st.button("❌ Supprimer", key=f"del_{i}"):
                    indices_a_supprimer.append(i)
        for index in sorted(indices_a_supprimer, reverse=True):
            st.session_state.panier.pop(index)

        # -------------------------------
        # Enregistrer la vente et PDF
        # -------------------------------
        if st.button("Enregistrer la vente"):
            df_stock = load_sheet("Stock")
            df_ventes = load_sheet("Ventes")
            vente_valide = True

            for item in st.session_state.panier:
                stock_dispo = df_stock[df_stock['Produit'] == item["Produit"]]['Quantité'].sum()
                ventes_sum = df_ventes[df_ventes['Produit'] == item["Produit"]]['Quantité'].sum() if not df_ventes.empty else 0
                stock_reel = stock_dispo - ventes_sum
                if item["Quantité"] > stock_reel:
                    st.error(f"Stock insuffisant pour {item['Produit']} ! Disponible : {stock_reel}")
                    vente_valide = False

            if vente_valide:
                prochain_num = ""
                if generer_facture:
                    factures_existantes = df_ventes[df_ventes["Numéro de facture"].notnull()] if not df_ventes.empty else pd.DataFrame()
                    if not factures_existantes.empty:
                        numeros_valides = factures_existantes["Numéro de facture"].str.split("/").str[0]
                        numeros_valides = numeros_valides[numeros_valides.str.isnumeric()].astype(int)
                        dernier_num = numeros_valides.max() if not numeros_valides.empty else 0
                    else:
                        dernier_num = 0
                    prochain_num = f"{dernier_num + 1:03d}/2025"

                # Données entreprise
                entreprise_nom = "NORTH AFRICA ELECTRONICS"
                entreprise_adresse = "123 Rue Principale, Alger"
                entreprise_rc = "RC: 16/00-1052043 B23"
                entreprise_nif = "NIF: 002316105204354"
                entreprise_art = "ART: 002316300298344"

               # -------------------------------
# Génération facture PDF
# -------------------------------
if generer_facture:
    pdf_facture = FPDF()
    pdf_facture.add_page()
    pdf_facture.set_font("Arial", 'B', 16)
    pdf_facture.cell(200, 10, txt=entreprise_nom, ln=True, align="C")
    pdf_facture.set_font("Arial", size=12)
    pdf_facture.cell(200, 10, txt=entreprise_adresse, ln=True, align="C")
    pdf_facture.ln(5)
    pdf_facture.set_font("Arial", 'B', 14)
    pdf_facture.cell(200, 10, txt="FACTURE", ln=True, align="C")
    pdf_facture.set_font("Arial", size=12)
    pdf_facture.cell(200, 10, txt=f"Numéro : {prochain_num}", ln=True)
    pdf_facture.cell(200, 10, txt=f"Date : {datetime.now().strftime('%d/%m/%Y')}", ln=True)
    pdf_facture.ln(5)

    # Client divers
    pdf_facture.cell(200, 10, txt=f"Client : CLIENTS DIVERS", ln=True)
    pdf_facture.ln(5)

    # Table produits
    pdf_facture.set_font("Arial", 'B', 12)
    pdf_facture.cell(80, 10, "Produit", 1)
    pdf_facture.cell(30, 10, "Qté", 1)
    pdf_facture.cell(30, 10, "Prix Unitaire", 1)
    pdf_facture.cell(30, 10, "Total HT", 1, ln=True)
    pdf_facture.set_font("Arial", size=12)

    total_ht_global = 0
    for item in st.session_state.panier:
        total_ht_global += item["Total HT"]
        pdf_facture.cell(80, 10, item["Produit"], 1)
        pdf_facture.cell(30, 10, str(item["Quantité"]), 1)
        pdf_facture.cell(30, 10, f"{item['Prix unitaire']:.2f}", 1)
        pdf_facture.cell(30, 10, f"{item['Total HT']:.2f}", 1, ln=True)

    # Calcul TVA
    tva = total_ht_global * 0.19

    # Calcul Timbre sur (HT + TVA)
    base_timbre = total_ht_global + tva
    if base_timbre <= 30000:
        timbre = round(base_timbre * 0.01)
    elif base_timbre <= 100000:
        timbre = round(base_timbre * 0.015)
    else:
        timbre = round(base_timbre * 0.02)

    # Total TTC = HT + TVA + Timbre
    total_ttc_facture = total_ht_global + tva + timbre

    # Affichage tableau facture
    pdf_facture.ln(5)
    pdf_facture.set_font("Arial", 'B', 12)
    pdf_facture.cell(100, 10, "Total HT", 1)
    pdf_facture.cell(30, 10, f"{total_ht_global:.2f}", 1, ln=True)
    pdf_facture.cell(100, 10, "TVA 19%", 1)
    pdf_facture.cell(30, 10, f"{tva:.2f}", 1, ln=True)
    pdf_facture.cell(100, 10, "Timbre", 1)
    pdf_facture.cell(30, 10, f"{timbre}", 1, ln=True)
    pdf_facture.cell(100, 10, "TOTAL TTC", 1)
    pdf_facture.cell(30, 10, f"{total_ttc_facture:.2f}", 1, ln=True)

    pdf_bytes = pdf_facture.output(dest='S').encode('latin1')
    pdf_io = io.BytesIO(pdf_bytes)
    st.download_button(
        label="📄 Télécharger la facture PDF",
        data=pdf_io,
        file_name=f"facture_{prochain_num}.pdf",
        mime="application/pdf"
    )


                # -------------------------------
                # Enregistrement dans Google Sheets
                # -------------------------------
                for item in st.session_state.panier:
                    row_vente = [
                        str(datetime.now()), item["Client Nom"], item["Client Email"], item["Client Tel"],
                        item["Client RC"], item["Client NIF"], item["Client ART"], item["Client Adresse"],
                        item["Produit"], item["Quantité"], item["Prix unitaire"], item["Total HT"],
                        item["Total TTC"], item["Montant payé"], item["Reste à payer"],
                        entreprise_rc, entreprise_nif, entreprise_art, entreprise_adresse,
                        prochain_num
                    ]
                    spreadsheet.worksheet("Ventes").append_row(row_vente)

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
            stock_reel = stock_reel.merge(ventes_group, on="Produit", how="left", suffixes=('', '_vendu'))
            stock_reel['Quantité_vendu'] = stock_reel['Quantité_vendu'].fillna(0)
            stock_reel['Stock restant'] = stock_reel['Quantité'] - stock_reel['Quantité_vendu']
        else:
            stock_reel['Stock restant'] = stock_reel['Quantité']
        st.dataframe(stock_reel[['Produit', 'Stock restant']], use_container_width=True)
    else:
        st.write("Aucun stock enregistré.")

# =============================
# Onglet 4 : Historique Ventes
# =============================
elif tab_choice == "📄 Historique Ventes":
    st.header("Historique des ventes")
    df_ventes = load_sheet("Ventes")
    if not df_ventes.empty:
        st.dataframe(df_ventes, use_container_width=True)
    else:
        st.write("Aucune vente enregistrée.")

# =============================
# Onglet 5 : Paiements partiels
# =============================
elif tab_choice == "💳 Paiements partiels":
    st.header("État des paiements partiels")
    df_ventes = load_sheet("Ventes")
    if not df_ventes.empty:
        df_partiels = df_ventes[df_ventes["Reste à payer"] > 0]
        if not df_partiels.empty:
            st.dataframe(df_partiels[["Produit", "Nom", "Téléphone", "Total TTC", "Montant payé", "Reste à payer"]], use_container_width=True)
        else:
            st.write("Aucun paiement partiel en attente.")
    else:
        st.write("Aucune vente enregistrée.")

# =============================
# Onglet 6 : Charges quotidiennes
# =============================
elif tab_choice == "🧾 Charges quotidiennes":
    st.header("Note de charges quotidiennes")

    # -----------------------------
    # TOTAL GLOBAL DEPUIS GOOGLE SHEETS
    # -----------------------------
    def calcul_total_charges():
        try:
            sheet = spreadsheet.worksheet("Charges")
            data = sheet.get_all_records()

            total = 0
            for row in data:
                try:
                    valeur = str(row["Montant"]) \
                        .replace(" ", "") \
                        .replace(",", ".") \
                        .replace("DA", "") \
                        .strip()

                    if valeur:
                        total += float(valeur)
                except:
                    pass

            return total
        except:
            return 0

    total_global = calcul_total_charges()
    st.metric("💰 Total cumulé de toutes les charges", f"{total_global:,.2f} DA")

    st.divider()

    # -----------------------------
    # Initialisation du panier
    # -----------------------------
    if "charges_panier" not in st.session_state:
        st.session_state.charges_panier = []

    # Référence automatique
    ref_charge = f"CHG-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    st.info(f"📌 Référence du document : {ref_charge}")

    # -----------------------------
    # Charger les types de charges
    # -----------------------------
    def load_types_charges():
        try:
            sheet = spreadsheet.worksheet("Types_Charges")
            header = sheet.row_values(1)

            col_index = header.index("Type de charge") + 1
            values = sheet.col_values(col_index)[1:]

            types = [v for v in values if v.strip()]
            return types if types else ["Autre"]
        except:
            return ["Autre"]

    types_dispo = load_types_charges()

    # -----------------------------
    # Formulaire de saisie
    # -----------------------------
    with st.form("form_ligne_charge"):
        date_charge = st.date_input(
            "Date",
            value=datetime.today(),
            min_value=datetime.today()
        )
        type_charge = st.selectbox("Type de charge *", types_dispo)
        description = st.text_input("Description *")
        fournisseur = st.text_input("Fournisseur / Payé à *")
        montant = st.number_input("Montant (DA) *", min_value=0.0, step=10.0)

        if st.form_submit_button("Ajouter la ligne"):
            st.session_state.charges_panier.append({
                "Date": date_charge.strftime("%d/%m/%Y"),
                "Type": type_charge,
                "Description": description,
                "Fournisseur": fournisseur,
                "Montant": montant
            })
            st.success("Ligne ajoutée au panier")

    # -----------------------------
    # Affichage du panier
    # -----------------------------
    if st.session_state.charges_panier:
        st.subheader("Panier des charges")
        df_panier_charges = pd.DataFrame(st.session_state.charges_panier)
        st.dataframe(df_panier_charges, use_container_width=True, hide_index=True)

        indices_a_supprimer = []
        for i, item in enumerate(st.session_state.charges_panier):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"{item['Date']} - {item['Type']} - {item['Description']} - {item['Fournisseur']} - {item['Montant']}")
            with col2:
                if st.button("❌ Supprimer", key=f"del_charge_{i}"):
                    indices_a_supprimer.append(i)
        for index in sorted(indices_a_supprimer, reverse=True):
            st.session_state.charges_panier.pop(index)

        # -----------------------------
        # Enregistrement
        # -----------------------------
        if st.button("Enregistrer les charges"):
            sheet_charges = spreadsheet.worksheet("Charges")
            for item in st.session_state.charges_panier:
                sheet_charges.append_row([
                    ref_charge,
                    item["Date"],
                    item["Type"],
                    item["Description"],
                    item["Fournisseur"],
                    item["Montant"]
                ])
            st.success(f"{len(st.session_state.charges_panier)} charge(s) enregistrée(s)")
            st.session_state.charges_panier = []
