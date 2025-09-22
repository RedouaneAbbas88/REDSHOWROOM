# -------------------- Onglet 4 : Historique Ventes --------------------
with tabs[3]:
    st.header("Historique des ventes")

    # Charger les ventes sans cache pour voir les mises à jour immédiates
    try:
        sheet_ventes = spreadsheet.worksheet("Ventes")
        data_ventes = sheet_ventes.get_all_records()
        df_ventes = pd.DataFrame(data_ventes)
    except Exception as e:
        st.error(f"Erreur lors du chargement des ventes : {e}")
        df_ventes = pd.DataFrame()

    if not df_ventes.empty:
        st.dataframe(df_ventes, use_container_width=True)
    else:
        st.write("Aucune vente enregistrée.")
