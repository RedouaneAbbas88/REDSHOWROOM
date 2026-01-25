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
            st.success(f"{quantite_stock} {produit_stock} ajouté(s) au stock.")

# -----------------------------
# Onglet 2 : Enregistrer Vente
# -----------------------------
elif tab_choice == "💰 Enregistrer Vente":
    st.header("Enregistrer une vente multi-produits")

    produit_vente = st.selectbox("Produit vendu *", produits_dispo)
    if produit_vente:
        prix_unitaire = float(df_produits.loc[df_produits['Produit'] == produit_vente, 'Prix unitaire'].values[0])
    else:
        prix_unitaire = 0.0

    quantite_vente = st.number_input("Quantité vendue *", min_value=1, step=1)
    total_ht = prix_unitaire * quantite_vente
    total_ttc = int(round(total_ht * 1.19, 0))
    st.write(f"Prix unitaire : {prix_unitaire} DA | 💰 Total TTC : {total_ttc} DA")

    # Infos client
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

                entreprise_nom = "NORTH AFRICA ELECTRONICS"
                entreprise_adresse = "123 Rue Principale, Alger"
                entreprise_rc = "RC: 16/00-1052043 B23"
                entreprise_nif = "NIF: 002316105204354"
                entreprise_art = "ART: 002316300298344"

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

                # -------------------------------
                # Bon de Vente PDF avec date + société
                # -------------------------------
                pdf_bon = FPDF()
                pdf_bon.add_page()
                pdf_bon.set_font("Arial", 'B', 16)
                pdf_bon.cell(200, 10, txt=entreprise_nom, ln=True, align="C")
                pdf_bon.set_font("Arial", 'B', 14)
                pdf_bon.cell(200, 10, txt="Bon de Vente", ln=True, align="C")
                pdf_bon.set_font("Arial", size=12)
                pdf_bon.cell(200, 10, txt=f"Date : {datetime.now().strftime('%d/%m/%Y')}", ln=True, align="R")
                pdf_bon.ln(10)
                pdf_bon.cell(200, 10, txt=f"Client : {client_nom}", ln=True)
                pdf_bon.cell(200, 10, txt=f"Téléphone : {client_tel}", ln=True)
                pdf_bon.ln(5)
                pdf_bon.set_font("Arial", 'B', 12)
                pdf_bon.cell(80, 10, "Produit", 1)
                pdf_bon.cell(30, 10, "Qté", 1)
                pdf_bon.cell(40, 10, "Prix TTC", 1)
                pdf_bon.cell(40, 10, "Total TTC", 1, ln=True)
                total_ttc_global = 0
                pdf_bon.set_font("Arial", size=12)
                for item in st.session_state.panier:
                    total_ttc_global += item["Total TTC"]
                    pdf_bon.cell(80, 10, item["Produit"], 1)
                    pdf_bon.cell(30, 10, str(item["Quantité"]), 1)
                    pdf_bon.cell(40, 10, f"{item['Total TTC'] / item['Quantité']:.2f}", 1)
                    pdf_bon.cell(40, 10, f"{item['Total TTC']:.2f}", 1, ln=True)
                pdf_bon.set_font("Arial", 'B', 12)
                pdf_bon.cell(150, 10, "TOTAL TTC", 1)
                pdf_bon.cell(40, 10, f"{total_ttc_global:.2f}", 1, ln=True)
                pdf_bon_bytes = pdf_bon.output(dest='S').encode('latin1')
                pdf_bon_io = io.BytesIO(pdf_bon_bytes)
                st.download_button(label="📑 Télécharger le bon de vente",
                                   data=pdf_bon_io,
                                   file_name=f"bon_vente_{client_nom}.pdf",
                                   mime="application/pdf")

                st.success(f"Vente enregistrée pour {client_nom} avec {len(st.session_state.panier)} produits.")
                st.session_state.panier = []

# -----------------------------
# Onglet 3 : État Stock
# -----------------------------
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

# -----------------------------
# Onglet 4 : Historique Ventes
# -----------------------------
elif tab_choice == "📄 Historique Ventes":
    st.header("Historique des ventes")
    df_ventes = load_sheet("Ventes")
    if not df_ventes.empty:
        st.dataframe(df_ventes, use_container_width=True)
    else:
        st.write("Aucune vente enregistrée.")

# -----------------------------
# Onglet 5 : Paiements partiels
# -----------------------------
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
# -----------------------------
# Onglet 6 : Charges quotidiennes (multi-lignes + PDF + TOTAL GLOBAL)
# -----------------------------
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
        fournisseur = st.text_input("Fournisseur / Prestataire")
        montant = st.number_input(" Montant *", min_value=0, step=100)

        add_line = st.form_submit_button("➕ Ajouter la ligne")

    # -----------------------------
    # Ajout au panier
    # -----------------------------
    if add_line:
        if not description.strip() or montant <= 0:
            st.error("⚠️ Description et montant obligatoires.")
        else:
            st.session_state.charges_panier.append({
                "Référence": ref_charge,
                "Date": str(date_charge),
                "Type de charge": type_charge,
                "Description": description,
                "Fournisseur / Prestataire": fournisseur,
                "Montant": montant
            })
            st.success("Ligne ajoutée.")

    # -----------------------------
    # Affichage panier
    # -----------------------------
    if st.session_state.charges_panier:
        st.subheader("Lignes en cours")
        df_charges = pd.DataFrame(st.session_state.charges_panier)
        st.dataframe(df_charges, use_container_width=True, hide_index=True)

        total_session = df_charges["Montant (DA)"].sum()
        st.markdown(f"### 💰 Total de cette note : {total_session} DA")

        # -----------------------------
        # Validation finale
        # -----------------------------
        if st.button("✅ Valider et enregistrer les charges"):
            sheet = spreadsheet.worksheet("Charges")

            for line in st.session_state.charges_panier:
                row = [
                    line["Référence"],
                    line["Date"],
                    line["Type de charge"],
                    line["Description"],
                    line["Fournisseur / Prestataire"],
                    line["Montant"]
                ]
                sheet.append_row(row)

            # -----------------------------
            # Génération PDF
            # -----------------------------
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(200, 10, "NOTE DE CHARGES", ln=True, align="C")
            pdf.set_font("Arial", size=12)
            pdf.cell(200, 10, f"Référence : {ref_charge}", ln=True)
            pdf.cell(200, 10, f"Date : {datetime.now().strftime('%d/%m/%Y')}", ln=True)
            pdf.ln(5)

            pdf.set_font("Arial", 'B', 12)
            pdf.cell(50, 10, "Type", 1)
            pdf.cell(70, 10, "Description", 1)
            pdf.cell(40, 10, "Fournisseur", 1)
            pdf.cell(30, 10, "Montant", 1, ln=True)

            pdf.set_font("Arial", size=12)
            for line in st.session_state.charges_panier:
                pdf.cell(50, 10, line["Type de charge"], 1)
                pdf.cell(70, 10, line["Description"], 1)
                pdf.cell(40, 10, line["Fournisseur / Prestataire"], 1)
                pdf.cell(30, 10, str(line["Montant"]), 1, ln=True)

            pdf.set_font("Arial", 'B', 12)
            pdf.cell(160, 10, "TOTAL", 1)
            pdf.cell(30, 10, str(total_session), 1, ln=True)

            pdf_bytes = pdf.output(dest='S').encode('latin1')
            pdf_io = io.BytesIO(pdf_bytes)

            st.download_button(
                label="📄 Télécharger la note de charges (PDF)",
                data=pdf_io,
                file_name=f"note_charges_{ref_charge}.pdf",
                mime="application/pdf"
            )

            st.success("✅ Charges enregistrées avec succès.")
            st.session_state.charges_panier = []
