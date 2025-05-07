import streamlit as st
import pandas as pd
import requests
import base64
from datetime import datetime, timedelta

st.set_page_config(page_title="DHIS2 - Doublons & Audit", layout="wide")

# Onglet Connexion
st.sidebar.header("🔐 Connexion à DHIS2")
dhis2_url = st.sidebar.text_input("URL DHIS2", value="https://togo.dhis2.org/dhis")
username = st.sidebar.text_input("Nom d'utilisateur", type="default")
password = st.sidebar.text_input("Mot de passe", type="password")

# Authentification
@st.cache_data(show_spinner=False)
def get_auth_header(username, password):
    token = f"{username}:{password}"
    encoded = base64.b64encode(token.encode()).decode("utf-8")
    return {"Authorization": f"Basic {encoded}"}

# Unités d'organisation
@st.cache_data(show_spinner=False)
def get_organisation_units(base_url, headers):
    url = f"{base_url}/api/organisationUnits.json"
    params = {"paging": "false", "fields": "id,name"}
    r = requests.get(url, headers=headers, params=params)
    if r.status_code == 200:
        return r.json().get("organisationUnits", [])
    return []

# Utilisateurs
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

# Connexions des utilisateurs
@st.cache_data(show_spinner=False)
def get_user_logins(base_url, headers):
    url = f"{base_url}/api/userCredentials?fields=username,lastLogin&paging=false"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json().get("userCredentials", [])
    return []

# Style de coloration
def color_login(val):
    if pd.isna(val):
        return 'background-color: #f8d7da'  # Rouge clair
    days = (datetime.today() - val).days
    if days <= 30:
        return 'background-color: #d4edda'  # Vert clair
    elif days <= 90:
        return 'background-color: #fff3cd'  # Jaune clair
    else:
        return 'background-color: #f8d7da'  # Rouge clair

# Traitement principal
if username and password and dhis2_url:
    headers = get_auth_header(username, password)

    st.sidebar.subheader("🏥 Sélection de l'unité d'organisation")
    units = get_organisation_units(dhis2_url, headers)
    unit_options = {unit['name']: unit['id'] for unit in units}

    if unit_options:
        selected_name = st.sidebar.selectbox("Choisir une unité", list(unit_options.keys()))
        selected_id = unit_options[selected_name]

        if st.sidebar.button("📥 Charger les utilisateurs"):
            st.info(f"Chargement des utilisateurs pour : {selected_name}")
            users = get_users(dhis2_url, headers, selected_id)
            if users:
                df_users = pd.DataFrame(users)[['id', 'username', 'name']]

                # Ajout des connexions
                login_data = get_user_logins(dhis2_url, headers)
                df_login = pd.DataFrame(login_data)[['username', 'lastLogin']]
                df_login['lastLogin'] = pd.to_datetime(df_login['lastLogin'], errors='coerce')

                df_users = df_users.merge(df_login, on='username', how='left')

                # Marquer les doublons
                df_users['doublon'] = df_users.duplicated(subset='name', keep=False)
                df_users['doublon'] = df_users['doublon'].apply(lambda x: "Oui" if x else "Non")

                st.success(f"✅ {len(df_users)} utilisateurs trouvés.")

                # Appliquer style
                styled = df_users.style.applymap(color_login, subset=['lastLogin'])
                st.dataframe(styled, use_container_width=True)

                # Export
                csv = df_users.to_csv(index=False).encode('utf-8')
                st.download_button("📄 Télécharger CSV", data=csv, file_name="utilisateurs_dhis2.csv", mime='text/csv')
            else:
                st.warning("Aucun utilisateur trouvé pour cette unité.")

    # Audit
    st.sidebar.subheader("📊 Analyse des connexions")
    start_date = st.sidebar.date_input("Début", datetime.today() - timedelta(days=30))
    end_date = st.sidebar.date_input("Fin", datetime.today())

    if start_date > end_date:
        st.sidebar.error("La date de début doit être antérieure à la date de fin.")
    elif st.sidebar.button("📈 Analyser l'activité"):
        st.subheader("🔍 Audit des connexions utilisateurs")
        data = get_user_logins(dhis2_url, headers)
        df = pd.DataFrame(data)
        df['lastLogin'] = pd.to_datetime(df['lastLogin'], errors='coerce')

        df['Actif durant la période'] = df['lastLogin'].apply(
            lambda x: "Oui" if pd.notnull(x) and start_date <= x.date() <= end_date else "Non"
        )

        styled = df.sort_values("lastLogin", ascending=False).style.applymap(color_login, subset=['lastLogin'])
        st.dataframe(styled, use_container_width=True)

        actifs = df[df["Actif durant la période"] == "Oui"]
        if not actifs.empty:
            excel = actifs.to_excel(index=False, engine='openpyxl')
            st.download_button("📤 Exporter les actifs (Excel)", data=excel, file_name="utilisateurs_actifs.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.info("Aucun utilisateur actif trouvé durant la période.")
