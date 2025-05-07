# NOTE: Ce script nécessite : streamlit, pandas, requests, openpyxl
# Installez-les avec : pip install streamlit pandas requests openpyxl

import streamlit as st
import pandas as pd
import requests
import base64
from datetime import datetime, timedelta

st.set_page_config(page_title="DHIS2 - Doublons & Audit", layout="wide")

# === Barre latérale : Connexion DHIS2 ===
st.sidebar.header("🔐 Connexion à DHIS2")
dhis2_url = st.sidebar.text_input("URL DHIS2", value="https://ton_instance.dhis2.org/dhis")
username = st.sidebar.text_input("Nom d'utilisateur", type="default")
password = st.sidebar.text_input("Mot de passe", type="password")

# === Authentification ===
@st.cache_data(show_spinner=False)
def get_auth_header(username, password):
    token = f"{username}:{password}"
    encoded = base64.b64encode(token.encode()).decode("utf-8")
    return {"Authorization": f"Basic {encoded}"}

# === Obtenir les unités d'organisation ===
@st.cache_data(show_spinner=False)
def get_organisation_units(base_url, headers):
    url = f"{base_url}/api/organisationUnits.json"
    params = {"paging": "false", "fields": "id,name"}
    r = requests.get(url, headers=headers, params=params)
    if r.status_code == 200:
        return r.json().get("organisationUnits", [])
    return []

# === Obtenir les utilisateurs pour une unité ===
def get_users(base_url, headers, org_unit_id):
    url = f"{base_url}/api/users.json"
    params = {"paging": "false", "fields": "id,username,name,organisationUnits[id]"}
    r = requests.get(url, headers=headers, params=params)
    if r.status_code != 200:
        st.error("Erreur lors de la récupération des utilisateurs.")
        return []
    users = r.json().get("users", [])
    return [
        user for user in users
        if org_unit_id in [ou['id'] for ou in user.get('organisationUnits', [])]
    ]

# === Obtenir les connexions des utilisateurs ===
@st.cache_data(show_spinner=False)
def get_user_logins(base_url, headers):
    url = f"{base_url}/api/userCredentials?fields=username,lastLogin&paging=false"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json().get("userCredentials", [])
    else:
        return []

if username and password and dhis2_url:
    headers = get_auth_header(username, password)

    st.sidebar.subheader("🏥 Sélection de l'unité d'organisation")
    units = get_organisation_units(dhis2_url, headers)
    unit_options = {unit['name']: unit['id'] for unit in units}

    if unit_options:
        selected_name = st.sidebar.selectbox("Choisir une unité", list(unit_options.keys()))
        selected_id = unit_options[selected_name]

        if st.sidebar.button("📥 Charger les utilisateurs"):
            st.info(f"Chargement des utilisateurs pour l'unité : {selected_name}")
            users = get_users(dhis2_url, headers, selected_id)

            if users:
                df_users = pd.DataFrame(users)[['id', 'username', 'name']]

                # Obtenir et fusionner les connexions
                logins = get_user_logins(dhis2_url, headers)
                df_logins = pd.DataFrame(logins)[['username', 'lastLogin']]
                df_logins['lastLogin'] = pd.to_datetime(df_logins['lastLogin'], errors='coerce')
                df_users = df_users.merge(df_logins, on='username', how='left')

                # Marquer les doublons de noms
                df_users['doublon'] = df_users.duplicated(subset='name', keep=False)
                df_users['doublon'] = df_users['doublon'].apply(lambda x: "Oui" if x else "Non")

                # Trier par activité
                df_users = df_users.sort_values(by='lastLogin', ascending=False)

                st.success(f"✅ {len(df_users)} utilisateurs trouvés.")

                # Style avec coloration selon la date de dernière connexion
                def color_login(val):
                    if pd.isna(val):
                        return 'background-color: #f8d7da'  # rouge clair pour aucune connexion
                    days = (datetime.today() - val).days
                    if days <= 30:
                        return 'background-color: #d4edda'  # vert clair si actif
                    elif days <= 90:
                        return 'background-color: #fff3cd'  # jaune clair si inactif récent
                    else:
                        return 'background-color: #f8d7da'  # rouge clair si inactif prolongé
                styled_df = df_users.style.applymap(color_login, subset=['lastLogin'])

                st.dataframe(styled_df, use_container_width=True)

                csv = df_users.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📄 Télécharger la liste CSV",
                    data=csv,
                    file_name="utilisateurs_dhis2.csv",
                    mime='text/csv'
                )
            else:
                st.warning("Aucun utilisateur trouvé pour cette unité.")

    # === Audit période activité globale ===
    st.sidebar.subheader("📊 Période d'analyse des connexions")
    start_date = st.sidebar.date_input("Début", datetime.today() - timedelta(days=30))
    end_date = st.sidebar.date_input("Fin", datetime.today())

    if start_date > end_date:
        st.sidebar.error("La date de début doit être antérieure à la date de fin.")
    elif st.sidebar.button("📈 Analyser l'activité globale"):
        st.subheader("🔍 Audit global de l'activité des utilisateurs DHIS2")
        data = get_user_logins(dhis2_url, headers)
        df = pd.DataFrame(data)
        df['lastLogin'] = pd.to_datetime(df['lastLogin'], errors='coerce')
        df['Actif durant la période'] = df['lastLogin'].apply(
            lambda x: "Oui" if pd.notnull(x) and start_date <= x.date() <= end_date else "Non"
        )

        st.dataframe(df.sort_values("lastLogin", ascending=False), use_container_width=True)

        actifs = df[df["Actif durant la période"] == "Oui"]
        if not actifs.empty:
            excel_data = actifs.to_excel(index=False, engine='openpyxl')
            st.download_button(
                "📤 Exporter les utilisateurs actifs (Excel)",
                data=excel_data,
                file_name="utilisateurs_actifs.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("Aucun utilisateur actif trouvé durant la période.")
