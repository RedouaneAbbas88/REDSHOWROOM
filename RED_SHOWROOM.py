# =============================
# Onglet 2 : Enregistrer Vente
# =============================
elif tab_choice == "💰 Enregistrer Vente":
    st.header("Enregistrer une vente multi-produits")

    produit_vente = st.selectbox("Produit vendu *", produits_dispo)

    prix_unitaire = 0.0
    if not df_produits.empty and produit_vente:
        prix_unitaire = float(
            df_produits.loc[
                df_produits["Produit"] == produit_vente,
                "Prix unitaire"
            ].values[0]
        )

    quantite_vente = st.number_input(
        "Quantité vendue *",
        min_value=1,
        step=1
    )

    total_ht = prix_unitaire * quantite_vente
    total_ttc = int(round(total_ht * 1.19, 0))

    st.write(f"Prix unitaire : {prix_unitaire} DA")
    st.write(f"Total TTC : {total_ttc} DA")
    st.write(f"Montant en lettres : {montant_en_lettres(total_ttc)}")

    # Infos client (saisie normale)
    client_nom = st.text_input("Nom du client *")
    client_email = st.text_input("Email du client")
    client_tel = st.text_input("Téléphone du client *")
    client_rc = st.text_input("RC du client")
    client_nif = st.text_input("NIF du client")
    client_art = st.text_input("ART du client")
    client_adresse = st.text_input("Adresse du client")

    montant_paye = st.number_input(
        "Montant payé",
        min_value=0,
        max_value=int(total_ttc),
        value=0,
        step=1
    )

    reste_a_payer = total_ttc - montant_paye
    st.write(f"Reste à payer : {reste_a_payer} DA")

    generer_facture = st.checkbox("Générer FACTURE PDF (Clients divers)")
    generer_bon = st.checkbox("Générer BON DE VENTE PDF (Client réel)")

    if st.button("Ajouter au panier"):
        if not produit_vente or not client_nom.strip() or not client_tel.strip():
            st.error("⚠️ Champs obligatoires manquants")
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
            st.success("Produit ajouté au panier")

    if st.session_state.panier:
        st.subheader("Panier")
        df_panier = pd.DataFrame(st.session_state.panier)
        st.dataframe(df_panier, use_container_width=True)

        if st.button("Enregistrer la vente"):
            df_stock = load_sheet("Stock")
            df_ventes = load_sheet("Ventes")

            # Numéro facture
            prochain_num = "001/2026"
            if not df_ventes.empty and "Numéro de facture" in df_ventes.columns:
                nums = df_ventes["Numéro de facture"].dropna().str.split("/").str[0]
                nums = nums[nums.str.isnumeric()].astype(int)
                if not nums.empty:
                    prochain_num = f"{nums.max()+1:03d}/2026"

            entreprise_nom = "NORTH AFRICA ELECTRONICS"
            entreprise_adresse = "123 Rue Principale, Alger"
            entreprise_rc = "RC: 16/00-1052043 B23"
            entreprise_nif = "NIF: 002316105204354"
            entreprise_art = "ART: 002316300298344"

            client_divers_nom = "CLIENTS DIVERS"
            client_divers_adresse = "BBA"

            total_ht_global = sum(i["Total HT"] for i in st.session_state.panier)
            tva = total_ht_global * 0.19
            base = total_ht_global + tva

            if base <= 30000:
                timbre = round(base * 0.01)
            elif base <= 100000:
                timbre = round(base * 0.015)
            else:
                timbre = round(base * 0.02)

            total_ttc_facture = total_ht_global + tva + timbre

            # FACTURE PDF
            if generer_facture:
                pdf = FPDF()
                pdf.add_page()

                pdf.set_font("Arial", "B", 16)
                pdf.cell(200, 10, entreprise_nom, ln=True, align="C")

                pdf.set_font("Arial", size=12)
                pdf.cell(200, 8, entreprise_adresse, ln=True, align="C")
                pdf.cell(200, 8, f"{entreprise_rc} | {entreprise_nif} | {entreprise_art}", ln=True, align="C")

                pdf.ln(5)
                pdf.set_font("Arial", "B", 14)
                pdf.cell(200, 10, "FACTURE", ln=True, align="C")

                pdf.set_font("Arial", size=12)
                pdf.cell(200, 8, f"Numéro : {prochain_num}", ln=True)
                pdf.cell(200, 8, f"Date : {datetime.now().strftime('%d/%m/%Y')}", ln=True)

                pdf.ln(5)
                pdf.cell(200, 8, f"Client : {client_divers_nom}", ln=True)
                pdf.cell(200, 8, f"Adresse : {client_divers_adresse}", ln=True)

                pdf.ln(5)
                pdf.set_font("Arial", "B", 12)
                pdf.cell(80, 10, "Produit", 1)
                pdf.cell(30, 10, "Qté", 1)
                pdf.cell(40, 10, "PU", 1)
                pdf.cell(40, 10, "Total HT", 1, ln=True)

                pdf.set_font("Arial", size=12)
                for item in st.session_state.panier:
                    pdf.cell(80, 10, item["Produit"], 1)
                    pdf.cell(30, 10, str(item["Quantité"]), 1)
                    pdf.cell(40, 10, f'{item["Prix unitaire"]:.2f}', 1)
                    pdf.cell(40, 10, f'{item["Total HT"]:.2f}', 1, ln=True)

                pdf.ln(5)
                pdf.set_font("Arial", "B", 12)
                pdf.cell(120, 10, "TOTAL HT", 1)
                pdf.cell(40, 10, f"{total_ht_global:.2f}", 1, ln=True)
                pdf.cell(120, 10, "TVA 19%", 1)
                pdf.cell(40, 10, f"{tva:.2f}", 1, ln=True)
                pdf.cell(120, 10, "Timbre", 1)
                pdf.cell(40, 10, f"{timbre}", 1, ln=True)
                pdf.cell(120, 10, "TOTAL TTC", 1)
                pdf.cell(40, 10, f"{total_ttc_facture:.2f}", 1, ln=True)

                pdf.ln(5)
                pdf.set_font("Arial", size=8)
                pdf.multi_cell(0, 5, f"Montant en lettres : {montant_en_lettres(total_ttc_facture)}")

                pdf_bytes = pdf.output(dest="S").encode("latin1")
                st.download_button(
                    "📄 Télécharger la facture",
                    data=io.BytesIO(pdf_bytes),
                    file_name=f"facture_{prochain_num}.pdf",
                    mime="application/pdf"
                )

            # Enregistrement Google Sheets
            for item in st.session_state.panier:
                row = [
                    str(datetime.now()),
                    item["Client Nom"],
                    item["Client Email"],
                    item["Client Tel"],
                    item["Client RC"],
                    item["Client NIF"],
                    item["Client ART"],
                    item["Client Adresse"],
                    item["Produit"],
                    item["Quantité"],
                    item["Prix unitaire"],
                    item["Total HT"],
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

            st.success("✅ Vente enregistrée avec succès")
            st.session_state.panier = []
