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
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

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
    except:
        return pd.DataFrame()

# -----------------------------
# 🔹 Données Produits
# -----------------------------
df_produits = load_sheet("Produits")
produits_dispo = df_produits['Produit'].dropna().tolist() if not df_produits.empty else []

# -----------------------------
# 🔹 Onglets
# -----------------------------
tabs_labels = [
    "🛒 Ajouter Stock",
    "💰 Enregistrer Vente",
    "📦 État Stock",
    "📄 Historique Ventes",
    "💳 Paiements partiels",
    "🧾 Charges quotidiennes"
]

if "active_tab" not in st.session_state:
    st.session_state.active_tab = 0

if "panier" not in st.session_state:
    st.session_state.panier = []

if "charges_panier" not in st.session_state:
    st.session_state.charges_panier = []

tab_choice = st.radio("Choisir l'onglet", tabs_labels, index=st.session_state.active_tab)
st.session_state.active_tab = tabs_labels.index(tab_choice)

# ==========================================================
# 🛒 ONGLET 1 : AJOUTER STOCK
# ==========================================================
if tab_choice == "🛒 Ajouter Stock":
    st.header("Ajouter du stock")

    with st.form("form_stock"):
        produit_stock = st.selectbox("Produit *", produits_dispo)

        prix_achat = 0.0
        if not df_produits.empty and produit_stock:
            prix_achat = float(
                df_produits.loc[df_produits['Produit'] == produit_stock, 'Prix unitaire'].values[0]
            )

        quantite_stock = st.number_input("Quantité achetée", min_value=1, step=1)

        if st.form_submit_button("Ajouter au stock"):
            row = [
                str(datetime.now()),
                produit_stock,
                quantite_stock,
                prix_achat
            ]
            spreadsheet.worksheet("Stock").append_row(row)
            st.success(f"{quantite_stock} {produit_stock} ajouté(s) au stock.")

# ==========================================================
# 💰 ONGLET 2 : ENREGISTRER VENTE
# ==========================================================
elif tab_choice == "💰 Enregistrer Vente":
    st.header("Enregistrer une vente multi-produits")

    produit_vente = st.selectbox("Produit vendu *", produits_dispo)

    prix_unitaire = 0.0
    if not df_produits.empty and produit_vente:
        prix_unitaire = float(
            df_produits.loc[df_produits['Produit'] == produit_vente, 'Prix unitaire'].values[0]
        )

    quantite_vente = st.number_input("Quantité vendue *", min_value=1, step=1)

    # -----------------------------
    # CALCUL HT / TIMBRE / TVA / TTC
    # -----------------------------
    total_ht = prix_unitaire * quantite_vente

    if total_ht < 100000:
        timbre = total_ht * 0.01
    else:
        timbre = total_ht * 0.02

    base_tva = total_ht + timbre
    tva = base_tva * 0.19
    total_ttc = int(round(base_tva + tva, 0))

    st.markdown(f"""
    💰 **HT :** {total_ht:.2f} DA  
    🧾 **Timbre :** {timbre:.2f} DA  
    🧮 **TVA 19% :** {tva:.2f} DA  
    ✅ **Total TTC :** {total_ttc} DA
    """)

    client_tel = st.text_input("Téléphone du client *")

    montant_paye = st.number_input("Montant payé", min_value=0, max_value=total_ttc, value=0, step=100)
    reste_a_payer = total_ttc - montant_paye
    st.write(f"Reste à payer : {reste_a_payer} DA")

    generer_facture = st.checkbox("Générer une facture PDF")

    # -----------------------------
    # AJOUT PANIER
    # -----------------------------
    if st.button("➕ Ajouter au panier"):
        if not produit_vente or not client_tel.strip():
            st.error("⚠️ Produit et téléphone obligatoires.")
        else:
            st.session_state.panier.append({
                "Produit": produit_vente,
                "Quantité": quantite_vente,
                "Prix unitaire": prix_unitaire,
                "Total HT": total_ht,
                "Timbre": timbre,
                "TVA": tva,
                "Total TTC": total_ttc,
                "Montant payé": montant_paye,
                "Reste à payer": reste_a_payer,
                "Client Nom": "Client Divers",
                "Client RC": "",
                "Client NIF": "",
                "Client ART": "",
                "Client Adresse": "Bordj Bou Arreridj",
                "Client Tel": client_tel
            })
            st.success("Produit ajouté au panier.")

    # -----------------------------
    # PANIER
    # -----------------------------
    if st.session_state.panier:
        st.subheader("🛒 Panier")

        df_panier = pd.DataFrame(st.session_state.panier)
        st.dataframe(df_panier[[
            "Produit", "Quantité",
            "Total HT", "Timbre", "TVA",
            "Total TTC", "Montant payé", "Reste à payer"
        ]], use_container_width=True, hide_index=True)

        # -----------------------------
        # ENREGISTRER VENTE
        # -----------------------------
        if st.button("✅ Enregistrer la vente"):
            df_stock = load_sheet("Stock")
            df_ventes = load_sheet("Ventes")

            vente_valide = True

            for item in st.session_state.panier:
                stock_dispo = df_stock[df_stock['Produit'] == item["Produit"]]['Quantité'].sum()
                ventes_sum = 0
                if not df_ventes.empty:
                    ventes_sum = df_ventes[df_ventes['Produit'] == item["Produit"]]['Quantité'].sum()

                stock_reel = stock_dispo - ventes_sum
                if item["Quantité"] > stock_reel:
                    st.error(f"Stock insuffisant pour {item['Produit']} | Disponible : {stock_reel}")
                    vente_valide = False

            if vente_valide:
                prochain_num = ""

                if generer_facture:
                    factures_existantes = df_ventes[df_ventes["Numéro de facture"].notnull()] if not df_ventes.empty else pd.DataFrame()
                    if not factures_existantes.empty:
                        numeros = factures_existantes["Numéro de facture"].str.split("/").str[0]
                        numeros = numeros[numeros.str.isnumeric()].astype(int)
                        dernier_num = numeros.max() if not numeros.empty else 0
                    else:
                        dernier_num = 0

                    prochain_num = f"{dernier_num + 1:03d}/2025"

                entreprise_nom = "NORTH AFRICA ELECTRONICS"
                entreprise_adresse = "123 Rue Principale, Alger"
                entreprise_rc = "RC: 16/00-1052043 B23"
                entreprise_nif = "NIF: 002316105204354"
                entreprise_art = "ART: 002316300298344"

                for item in st.session_state.panier:
                    row = [
                        str(datetime.now()),
                        "Client Divers",
                        "",
                        item["Client Tel"],
                        "",
                        "",
                        "",
                        "Bordj Bou Arreridj",
                        item["Produit"],
                        item["Quantité"],
                        item["Prix unitaire"],
                        item["Total HT"],
                        item["Timbre"],
                        item["TVA"],
                        item["Total TTC"],
                        item["Montant payé"],
                        item["Reste à payer"],
                        entreprise_rc,
                        entreprise_nif,
                        entreprise_art,
                        entreprise_adresse,
                        prochain_num
                    ]
                    spreadsheet.worksheet("Ventes").append_row(row)

                # -----------------------------
                # PDF FACTURE
                # -----------------------------
                pdf = FPDF()
                pdf.add_page()

                pdf.set_font("Arial", 'B', 16)
                pdf.cell(200, 10, entreprise_nom, ln=True, align="C")

                pdf.set_font("Arial", 'B', 14)
                pdf.cell(200, 10, "FACTURE", ln=True, align="C")

                pdf.set_font("Arial", size=12)
                pdf.cell(200, 10, f"Date : {datetime.now().strftime('%d/%m/%Y')}", ln=True)
                pdf.cell(200, 10, "Client : Client Divers", ln=True)
                pdf.cell(200, 10, "Adresse : Bordj Bou Arreridj", ln=True)
                pdf.cell(200, 10, f"Facture N° : {prochain_num}", ln=True)

                pdf.ln(5)

                pdf.set_font("Arial", 'B', 12)
                pdf.cell(60, 10, "Produit", 1)
                pdf.cell(20, 10, "Qté", 1)
                pdf.cell(30, 10, "HT", 1)
                pdf.cell(30, 10, "Timbre", 1)
                pdf.cell(30, 10, "TVA", 1)
                pdf.cell(30, 10, "TTC", 1, ln=True)

                total_ht_global = 0
                timbre_global = 0
                tva_global = 0
                total_ttc_global = 0

                pdf.set_font("Arial", size=12)

                for item in st.session_state.panier:
                    total_ht_global += item["Total HT"]
                    timbre_global += item["Timbre"]
                    tva_global += item["TVA"]
                    total_ttc_global += item["Total TTC"]

                    pdf.cell(60, 10, item["Produit"], 1)
                    pdf.cell(20, 10, str(item["Quantité"]), 1)
                    pdf.cell(30, 10, f"{item['Total HT']:.2f}", 1)
                    pdf.cell(30, 10, f"{item['Timbre']:.2f}", 1)
                    pdf.cell(30, 10, f"{item['TVA']:.2f}", 1)
                    pdf.cell(30, 10, f"{item['Total TTC']:.2f}", 1, ln=True)

                pdf.set_font("Arial", 'B', 12)
                pdf.cell(140, 10, "TOTAL HT", 1)
                pdf.cell(60, 10, f"{total_ht_global:.2f}", 1, ln=True)

                pdf.cell(140, 10, "TOTAL TIMBRE", 1)
                pdf.cell(60, 10, f"{timbre_global:.2f}", 1, ln=True)

                pdf.cell(140, 10, "TOTAL TVA", 1)
                pdf.cell(60, 10, f"{tva_global:.2f}", 1, ln=True)

                pdf.cell(140, 10, "TOTAL TTC", 1)
                pdf.cell(60, 10, f"{total_ttc_global:.2f}", 1, ln=True)

                pdf_bytes = pdf.output(dest="S").encode("latin1")
                pdf_io = io.BytesIO(pdf_bytes)

                st.download_button(
                    label="📄 Télécharger la facture PDF",
                    data=pdf_io,
                    file_name=f"facture_{prochain_num}.pdf",
                    mime="application/pdf"
                )

                st.success("✅ Vente enregistrée avec succès.")
                st.session_state.panier = []

# ==========================================================
# 📦 ONGLET 3 : ÉTAT STOCK
# ==========================================================
elif tab_choice == "📦 État Stock":
    st.header("État du stock")

    df_stock = load_sheet("Stock")
    df_ventes = load_sheet("Ventes")

    if not df_stock.empty:
        stock_reel = df_stock.groupby("Produit")["Quantité"].sum().reset_index()

        if not df_ventes.empty:
            ventes_group = df_ventes.groupby("Produit")["Quantité"].sum().reset_index()
            stock_reel = stock_reel.merge(ventes_group, on="Produit", how="left", suffixes=("", "_vendu"))
            stock_reel["Quantité_vendu"] = stock_reel["Quantité_vendu"].fillna(0)
            stock_reel["Stock restant"] = stock_reel["Quantité"] - stock_reel["Quantité_vendu"]
        else:
            stock_reel["Stock restant"] = stock_reel["Quantité"]

        st.dataframe(stock_reel[["Produit", "Stock restant"]], use_container_width=True)
    else:
        st.info("Aucun stock enregistré.")

# ==========================================================
# 📄 ONGLET 4 : HISTORIQUE VENTES
# ==========================================================
elif tab_choice == "📄 Historique Ventes":
    st.header("Historique des ventes")

    df_ventes = load_sheet("Ventes")
    if not df_ventes.empty:
        st.dataframe(df_ventes, use_container_width=True)
    else:
        st.info("Aucune vente enregistrée.")

# ==========================================================
# 💳 ONGLET 5 : PAIEMENTS PARTIELS
# ==========================================================
elif tab_choice == "💳 Paiements partiels":
    st.header("Paiements en attente")

    df_ventes = load_sheet("Ventes")
    if not df_ventes.empty:
        df_partiels = df_ventes[df_ventes["Reste à payer"] > 0]
        if not df_partiels.empty:
            st.dataframe(df_partiels, use_container_width=True)
        else:
            st.info("Aucun paiement en attente.")
    else:
        st.info("Aucune vente enregistrée.")

# ==========================================================
# 🧾 ONGLET 6 : CHARGES QUOTIDIENNES
# ==========================================================
elif tab_choice == "🧾 Charges quotidiennes":
    st.header("Note de charges quotidiennes")

    # -----------------------------
    # TOTAL GLOBAL
    # -----------------------------
    def calcul_total_charges():
        try:
            sheet = spreadsheet.worksheet("Charges")
            data = sheet.get_all_records()
            total = 0
            for row in data:
                try:
                    val = str(row["Montant"]).replace("DA", "").replace(",", ".").strip()
                    if val:
                        total += float(val)
                except:
                    pass
            return total
        except:
            return 0

    total_global = calcul_total_charges()
    st.metric("💰 Total cumulé des charges", f"{total_global:,.2f} DA")

    st.divider()

    ref_charge = f"CHG-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    st.info(f"Référence : {ref_charge}")

    with st.form("form_charge"):
        date_charge = st.date_input("Date", value=datetime.today())
        type_charge = st.text_input("Type de charge *")
        description = st.text_input("Description *")
        fournisseur = st.text_input("Fournisseur")
        montant = st.number_input("Montant *", min_value=0, step=100)

        add_line = st.form_submit_button("➕ Ajouter")

    if add_line:
        if not description.strip() or montant <= 0:
            st.error("Description et montant obligatoires")
        else:
            st.session_state.charges_panier.append({
                "Référence": ref_charge,
                "Date": str(date_charge),
                "Type": type_charge,
                "Description": description,
                "Fournisseur": fournisseur,
                "Montant": montant
            })
            st.success("Ligne ajoutée")

    if st.session_state.charges_panier:
        df_charges = pd.DataFrame(st.session_state.charges_panier)
        st.dataframe(df_charges, use_container_width=True, hide_index=True)

        total_session = df_charges["Montant"].sum()
        st.markdown(f"### 💰 Total note : {total_session} DA")

        if st.button("✅ Valider et enregistrer"):
            sheet = spreadsheet.worksheet("Charges")

            for line in st.session_state.charges_panier:
                sheet.append_row([
                    line["Référence"],
                    line["Date"],
                    line["Type"],
                    line["Description"],
                    line["Fournisseur"],
                    line["Montant"]
                ])

            # -----------------------------
            # PDF CHARGES
            # -----------------------------
            pdf = FPDF()
            pdf.add_page()

            pdf.set_font("Arial", "B", 16)
            pdf.cell(200, 10, "NOTE DE CHARGES", ln=True, align="C")

            pdf.set_font("Arial", size=12)
            pdf.cell(200, 10, f"Référence : {ref_charge}", ln=True)
            pdf.cell(200, 10, f"Date : {datetime.now().strftime('%d/%m/%Y')}", ln=True)

            pdf.ln(5)

            pdf.set_font("Arial", "B", 12)
            pdf.cell(40, 10, "Type", 1)
            pdf.cell(80, 10, "Description", 1)
            pdf.cell(40, 10, "Fournisseur", 1)
            pdf.cell(30, 10, "Montant", 1, ln=True)

            pdf.set_font("Arial", size=12)
            for line in st.session_state.charges_panier:
                pdf.cell(40, 10, line["Type"], 1)
                pdf.cell(80, 10, line["Description"], 1)
                pdf.cell(40, 10, line["Fournisseur"], 1)
                pdf.cell(30, 10, str(line["Montant"]), 1, ln=True)

            pdf.set_font("Arial", "B", 12)
            pdf.cell(160, 10, "TOTAL", 1)
            pdf.cell(30, 10, str(total_session), 1, ln=True)

            pdf_bytes = pdf.output(dest="S").encode("latin1")
            pdf_io = io.BytesIO(pdf_bytes)

            st.download_button(
                "📄 Télécharger la note PDF",
                data=pdf_io,
                file_name=f"note_charges_{ref_charge}.pdf",
                mime="application/pdf"
            )

            st.success("Charges enregistrées")
            st.session_state.charges_panier = []
