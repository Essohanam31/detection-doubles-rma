# NOTE: Ce script nécessite que le module 'streamlit' soit installé dans votre environnement Python.
# Installez-le avec : pip install streamlit

import streamlit as st
import pandas as pd
import requests
import base64
from datetime import datetime, timedelta

st.set_page_config(page_title="DHIS2 - Doublons & Audit", layout="wide")

# Onglet Connexion
st.sidebar.header("🔐 Connexion à DHIS2")
dhis2_url = st.sidebar.text_input("URL DHIS2", value="https://ton_instance.dhis2.org/dhis")
username = st.sidebar.text_input("Nom d'utilisateur", type="default")
password = st.sidebar.text_input("Mot de passe", type="password")

# Authentification de base
@st.cache_data(show_spinner=False)
def get_auth_header(username, password):
    token = f"{username}:{password}"
    encoded = base64.b64encode(token.encode()).decode("utf-8")
    return {"Authorization": f"Basic {encoded}"}

# Obtenir les unités d'organisation
@st.cache_data(show_spinner=False)
def get_organisation_units(base_url, headers):
    url = f"{base_url}/api/organisationUnits.json"
    params = {"paging": "false", "fields": "id,name"}
    r = requests.get(url, headers=headers, params=params)
    if r.status_code == 200:
        return r.json().get("organisationUnits", [])
    return []

# Obtenir les utilisateurs
def get_users(base_url, headers, org_unit_id):
    url = f"{base_url}/api/users.json"
    params = {
        "paging": "false",
        "fields": "id,username,name,organisationUnits[id]"
    }
    r = requests.get(url, headers=headers, params=params)
    if r.status_code != 200:
        st.error("Erreur lors de la récupération des utilisateurs.")
        return []
    users = r.json().get("users", [])
    # Filtrer par unité d'organisation
    filtered = []
    for user in users:
        user_ous = [ou['id'] for ou in user.get('organisationUnits', [])]
        if org_unit_id in user_ous:
            filtered.append(user)
    return filtered

# Obtenir les connexions des utilisateurs (audit)
@st.cache_data(show_spinner=False)
def get_user_logins(base_url, headers):
    url = f"{base_url}/api/userCredentials?fields=username,lastLogin&paging=false"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json().get("userCredentials", [])
    else:
        return []

# Fonction pour formater la date de dernière connexion
def format_last_login(last_login):
    if pd.isna(last_login):
        return "Jamais connecté"
    
    last_login = pd.to_datetime(last_login)
    delta = datetime.now() - last_login
    
    if delta.days == 0:
        return "Aujourd'hui"
    elif delta.days == 1:
        return "Hier"
    elif delta.days < 30:
        return f"Il y a {delta.days} jours"
    elif delta.days < 365:
        months = delta.days // 30
        return f"Il y a {months} mois"
    else:
        years = delta.days // 365
        return f"Il y a {years} ans"

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
                # Créer le DataFrame des utilisateurs
                df_users = pd.DataFrame(users)[['id', 'username', 'name']]
                
                # Récupérer les données de connexion
                login_data = get_user_logins(dhis2_url, headers)
                df_login = pd.DataFrame(login_data)
                df_login['lastLogin'] = pd.to_datetime(df_login['lastLogin'], errors='coerce')
                
                # Fusionner avec les données utilisateurs
                df_users = df_users.merge(df_login, on='username', how='left')
                
                # Formater la dernière connexion
                df_users['Dernière connexion'] = df_users['lastLogin'].apply(format_last_login)
                
                # Marquer les doublons
                df_users['doublon'] = df_users.duplicated(subset='name', keep=False)
                df_users['doublon'] = df_users['doublon'].apply(lambda x: "Oui" if x else "Non")

                # Sélectionner et ordonner les colonnes
                display_cols = ['id', 'username', 'name', 'Dernière connexion', 'doublon']
                df_display = df_users[display_cols].rename(columns={
                    'name': 'Nom complet',
                    'username': 'Nom utilisateur'
                })

                st.success(f"✅ {len(df_users)} utilisateurs trouvés.")
                st.dataframe(
                    df_display,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "id": "ID",
                        "Nom utilisateur": "Username",
                        "Nom complet": "Nom complet",
                        "Dernière connexion": "Dernière connexion",
                        "doublon": "Doublon"
                    }
                )

                csv = df_users[display_cols].to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📄 Télécharger la liste CSV",
                    data=csv,
                    file_name="utilisateurs_dhis2.csv",
                    mime='text/csv'
                )
            else:
                st.warning("Aucun utilisateur trouvé pour cette unité.")

    # Partie Audit (inchangée)
    st.sidebar.subheader("📊 Période d'analyse des connexions")
    start_date = st.sidebar.date_input("Début", datetime.today() - timedelta(days=30))
    end_date = st.sidebar.date_input("Fin", datetime.today())

    if start_date > end_date:
        st.sidebar.error("La date de début doit être antérieure à la date de fin.")
    elif st.sidebar.button("📈 Analyser l'activité"):
        st.subheader("🔍 Audit d'activité des utilisateurs DHIS2")
        data = get_user_logins(dhis2_url, headers)
        df = pd.DataFrame(data)
        df['lastLogin'] = pd.to_datetime(df['lastLogin'], errors='coerce')

        df['Actif durant la période'] = df['lastLogin'].apply(
            lambda x: "Oui" if pd.notnull(x) and start_date <= x.date() <= end_date else "Non"
        )

        st.dataframe(df.sort_values("lastLogin", ascending=False), use_container_width=True)

        filtered = df[df["Actif durant la période"] == "Oui"]
        if not filtered.empty:
            excel_data = filtered.to_excel(index=False, engine='openpyxl')
            st.download_button(
                "📤 Exporter les actifs (Excel)",
                data=excel_data,
                file_name="utilisateurs_actifs.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("Aucun utilisateur actif trouvé durant la période.")
