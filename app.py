
import streamlit as st
import pandas as pd
import requests
import base64
from collections import defaultdict
from io import BytesIO

st.set_page_config(page_title="Détection des doubles attributions de RMA", layout="wide")
st.title("🔍 Détection des Doubles Attributions de RMA")

# === Étape 1 : Saisie des identifiants DHIS2 ===
st.sidebar.header("🔑 Connexion DHIS2")
username = st.sidebar.text_input("Nom d'utilisateur", type="default")
password = st.sidebar.text_input("Mot de passe", type="password")

# === Étape 2 : Importer le fichier Excel fosa_services.xlsx ===
st.header("📂 Importer le fichier des relations FOSA - Services")
uploaded_file = st.file_uploader("Choisissez le fichier fosa_services.xlsx", type=["xlsx"])

if uploaded_file and username and password:
    # Authentification DHIS2
    auth_str = f"{username}:{password}"
    auth_bytes = auth_str.encode("utf-8")
    auth_b64 = base64.b64encode(auth_bytes).decode("utf-8")
    headers = {"Authorization": f"Basic {auth_b64}"}

    try:
        df = pd.read_excel(uploaded_file)
        st.success("✅ Fichier chargé avec succès.")

        # Construire le mapping FOSA → [services]
        fosa_to_services = defaultdict(set)
        for _, row in df.iterrows():
            fosa_to_services[row["FOSA ID"]].add(row["Service ID"])

        # Requête vers DHIS2 pour récupérer les datasets
        url = "https://togo.dhis2.org/dhis/api/dataSets.json"
        params = {"paging": "false", "fields": "id,name,organisationUnits[id]"}
        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            data = response.json().get("dataSets", [])
            doublons = []

            for dataset in data:
                dataset_id = dataset["id"]
                dataset_name = dataset["name"]
                ou_ids = [ou["id"] for ou in dataset.get("organisationUnits", [])]

                for fosa_id, service_ids in fosa_to_services.items():
                    attributs = set()
                    if fosa_id in ou_ids:
                        attributs.add("fosa")
                    attrib_services = service_ids.intersection(ou_ids)
                    if attrib_services:
                        attributs.update(attrib_services)
                    if len(attributs) > 1:
                        doublons.append({
                            "dataset_id": dataset_id,
                            "dataset_name": dataset_name,
                            "fosa_id": fosa_id,
                            "attribué_à": list(attributs)
                        })

            df_doublons = pd.DataFrame(doublons)

            if not df_doublons.empty:
                df_doublons['service_id_extrait'] = df_doublons['attribué_à'].apply(lambda x: [elem for elem in x if elem != 'fosa'])
                df_doublons['service_id_extrait_str'] = df_doublons['service_id_extrait'].apply(lambda x: ','.join(x) if isinstance(x, list) else x)
                doublons_services = df_doublons.groupby(['dataset_id', 'fosa_id'])['service_id_extrait_str'].apply(lambda x: len(set(','.join(x).split(','))) > 1).reset_index(name='doublon_detecté')
                doublons_detectés = doublons_services[doublons_services['doublon_detecté'] == True]

                st.success(f"✅ {len(doublons_detectés)} doublon(s) détecté(s).")
                st.dataframe(df_doublons)

                # Télécharger le fichier CSV
                csv_buffer = BytesIO()
                doublons_detectés.to_csv(csv_buffer, index=False)
                st.download_button(
                    label="📥 Télécharger les doublons détectés (CSV)",
                    data=csv_buffer.getvalue(),
                    file_name="doublons_detectés.csv",
                    mime="text/csv"
                )
            else:
                st.info("Aucun doublon détecté.")

        else:
            st.error("Erreur lors de la récupération des datasets depuis DHIS2. Vérifiez vos identifiants.")

    except Exception as e:
        st.error(f"Erreur lors du traitement : {e}")
else:
    st.info("Veuillez importer un fichier Excel et entrer vos identifiants DHIS2.")
