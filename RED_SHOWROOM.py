# -----------------------------
# Onglet 2 : Enregistrer Vente avec paiement partiel
# -----------------------------
elif tab_choice == "💰 Enregistrer Vente":
    st.header("Enregistrer une vente multi-produits")

    with st.form("form_vente_multi"):
        # Sélection produit et quantité
        produit_vente = st.selectbox("Produit vendu *", produits_dispo)
        quantite_vente = st.number_input("Quantité vendue *", min_value=1, step=1)

        # Infos client
        client_nom = st.text_input("Nom du client *")
        client_email = st.text_input("Email du client")
        client_tel = st.text_input("Téléphone du client *")
        client_rc = st.text_input("RC du client")
        client_nif = st.text_input("NIF du client")
        client_art = st.text_input("ART du client")
        client_adresse = st.text_input("Adresse du client")

        # Option facture
        generer_facture = st.checkbox("Générer une facture PDF")

        # Prix et total
        prix_unitaire = float(
            df_produits.loc[df_produits['Produit'] == produit_vente, 'Prix unitaire'].values[0]
        ) if not df_produits.empty else 0.0
        total_vente = prix_unitaire * quantite_vente
        total_ttc = round(total_vente * 1.19, 2)

        # Paiement partiel
        paiement_recu = st.number_input("Montant payé par le client", min_value=0.0, max_value=total_ttc, value=total_ttc, step=1.0)
        reste_a_payer = total_ttc - paiement_recu

        st.write(
            f"Prix unitaire : {prix_unitaire} | "
            f"Total HT : {total_vente:.2f} | "
            f"Total TTC : {total_ttc:.2f} | "
            f"Montant payé : {paiement_recu:.2f} | "
            f"Reste à payer : {reste_a_payer:.2f}"
        )

        # Ajout au panier
        if st.form_submit_button("Ajouter au panier"):
            if not produit_vente or quantite_vente <= 0 or not client_nom.strip() or not client_tel.strip():
                st.error("⚠️ Merci de remplir tous les champs obligatoires : Produit, Quantité, Nom du client et Téléphone.")
            else:
                st.session_state.panier.append({
                    "Produit": produit_vente,
                    "Quantité": quantite_vente,
                    "Prix unitaire": prix_unitaire,
                    "Total": total_vente,
                    "Total TTC": total_ttc,
                    "Paiement reçu": paiement_recu,
                    "Reste à payer": reste_a_payer
                })
                st.success(f"{quantite_vente} x {produit_vente} ajouté(s) au panier.")

    # Affichage du panier
    if st.session_state.panier:
        st.subheader("Panier actuel (modifiable)")
        df_panier = pd.DataFrame(st.session_state.panier)
        st.dataframe(df_panier, use_container_width=True, hide_index=True)

        indices_a_supprimer = []
        for i, item in enumerate(st.session_state.panier):
            col1, col2, col3 = st.columns([4,2,1])
            with col1:
                st.write(item["Produit"])
            with col2:
                nouvelle_quantite = st.number_input(f"Quantité {i}", min_value=1, value=item["Quantité"], key=f"qty_{i}")
                st.session_state.panier[i]["Quantité"] = nouvelle_quantite
                st.session_state.panier[i]["Total"] = nouvelle_quantite * item["Prix unitaire"]
                st.session_state.panier[i]["Total TTC"] = round(st.session_state.panier[i]["Total"] * 1.19,2)
                # Mettre à jour reste à payer
                paiement_recu_panier = st.session_state.panier[i].get("Paiement reçu", st.session_state.panier[i]["Total TTC"])
                st.session_state.panier[i]["Reste à payer"] = st.session_state.panier[i]["Total TTC"] - paiement_recu_panier
            with col3:
                if st.button("❌ Supprimer", key=f"del_{i}"):
                    indices_a_supprimer.append(i)
        for index in sorted(indices_a_supprimer, reverse=True):
            st.session_state.panier.pop(index)

        st.markdown("---")

        # Enregistrer la vente
        if st.button("Enregistrer la vente", key="enregistrer_vente"):
            df_stock = load_sheet("Stock")
            df_ventes = load_sheet("Ventes")
            vente_valide = True

            # Vérification stock
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

                # Ajouter ventes à Google Sheet
                for item in st.session_state.panier:
                    row_vente = [
                        str(datetime.now()), client_nom, client_email, client_tel,
                        client_rc, client_nif, client_art, client_adresse,
                        item["Produit"], item["Quantité"], item["Prix unitaire"], item["Total"],
                        item["Total TTC"], item["Paiement reçu"], item["Reste à payer"],
                        entreprise_rc, entreprise_nif, entreprise_art, entreprise_adresse,
                        prochain_num
                    ]
                    spreadsheet.worksheet("Ventes").append_row(row_vente)

                st.success(f"Vente enregistrée pour {client_nom} avec {len(st.session_state.panier)} produits.")

                # Génération PDF
                if generer_facture:
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", 'B', 14)
                    pdf.cell(200, 10, txt=f"Facture Num : {prochain_num}", ln=True, align="C")
                    pdf.ln(5)
                    pdf.set_font("Arial", size=12)
                    pdf.cell(200,5, txt=f"{entreprise_nom}", ln=True)
                    pdf.cell(200,5, txt=f"{entreprise_adresse}", ln=True)
                    pdf.cell(200,5, txt=f"{entreprise_rc} | {entreprise_nif} | {entreprise_art}", ln=True)
                    pdf.ln(5)
                    pdf.cell(200,5, txt=f"Client: {client_nom}", ln=True)
                    pdf.cell(200,5, txt=f"Email: {client_email} | Tel: {client_tel}", ln=True)
                    pdf.cell(200,5, txt=f"RC: {client_rc} | NIF: {client_nif} | ART: {client_art} | Adresse: {client_adresse}", ln=True)
                    pdf.ln(5)
                    pdf.cell(50, 10, "Produit", 1)
                    pdf.cell(30, 10, "Quantité", 1)
                    pdf.cell(40, 10, "Prix HT", 1)
                    pdf.cell(40, 10, "Total HT", 1)
                    pdf.cell(30, 10, "Total TTC", 1)
                    pdf.cell(30, 10, "Paiement reçu", 1)
                    pdf.cell(30, 10, "Reste à payer", 1, ln=True)

                    total_ht = 0
                    total_ttc = 0
                    total_paye = 0
                    total_reste = 0
                    for item in st.session_state.panier:
                        total_ht += item["Total"]
                        total_ttc += item["Total TTC"]
                        total_paye += item["Paiement reçu"]
                        total_reste += item["Reste à payer"]
                        pdf.cell(50,10,str(item["Produit"]),1)
                        pdf.cell(30,10,str(item["Quantité"]),1)
                        pdf.cell(40,10,f"{item['Prix unitaire']:.2f}",1)
                        pdf.cell(40,10,f"{item['Total']:.2f}",1)
                        pdf.cell(30,10,f"{item['Total TTC']:.2f}",1)
                        pdf.cell(30,10,f"{item['Paiement reçu']:.2f}",1)
                        pdf.cell(30,10,f"{item['Reste à payer']:.2f}",1, ln=True)

                    total_tva = total_ttc - total_ht
                    pdf.ln(5)
                    pdf.cell(160,10,"Total HT:",0,align="R")
                    pdf.cell(30,10,f"{total_ht:.2f}",1,ln=True)
                    pdf.cell(160,10,"Total TVA 19%:",0,align="R")
                    pdf.cell(30,10,f"{total_tva:.2f}",1,ln=True)
                    pdf.cell(160,10,"Total TTC:",0,align="R")
                    pdf.cell(30,10,f"{total_ttc:.2f}",1,ln=True)
                    pdf.cell(160,10,"Total payé:",0,align="R")
                    pdf.cell(30,10,f"{total_paye:.2f}",1,ln=True)
                    pdf.cell(160,10,"Reste à payer:",0,align="R")
                    pdf.cell(30,10,f"{total_reste:.2f}",1,ln=True)

                    ttc_int = int(total_ttc)
                    ttc_centimes = int(round((total_ttc - ttc_int) * 100))
                    if ttc_centimes > 0:
                        montant_lettres = num2words(ttc_int, lang='fr') + " dinars et " + num2words(ttc_centimes, lang='fr') + " centimes algériens"
                    else:
                        montant_lettres = num2words(ttc_int, lang='fr') + " dinars algériens"
                    pdf.ln(10)
                    pdf.set_font("Arial",'I',11)
                    pdf.multi_cell(0,10,f"Arrêté la présente facture à la somme de : {montant_lettres}")

                    pdf_bytes = pdf.output(dest='S').encode('latin1')
                    pdf_io = io.BytesIO(pdf_bytes)
                    st.download_button(label="📥 Télécharger la facture", data=pdf_io,
                                       file_name=f"facture_{client_nom}_{prochain_num}.pdf", mime="application/pdf")

                # Vider le panier
                st.session_state.panier = []
