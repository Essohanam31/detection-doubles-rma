import streamlit as st
import pandas as pd
import requests
import base64
from datetime import datetime, timedelta

st.set_page_config(page_title="DHIS2 - Gestion Utilisateurs", layout="wide")

# Authentification
st.sidebar.header("🔐 Connexion à DHIS2")
dhis2_url = st.sidebar.text_input("URL DHIS2", value="https://togo.dhis2.org/dhis")
username = st.sidebar.text_input("Nom d'utilisateur")
password = st.sidebar.text_input("Mot de passe", type="password")

@st.cache_data(show_spinner=False)
def get_auth_header(username, password):
    token = f"{username}:{password}"
    encoded = base64.b64encode(token.encode()).decode("utf-8")
    return {"Authorization": f"Basic {encoded}"}

# Fonctions API
@st.cache_data(show_spinner=False)
def get_organisation_units(base_url, headers):
    url = f"{base_url}/api/organisationUnits.json"
    params = {"paging": "false", "fields": "id,name"}
    r = requests.get(url, headers=headers, params=params)
    return r.json().get("organisationUnits", []) if r.status_code == 200 else []

def get_users_by_org_unit(base_url, headers, org_unit_id):
    url = f"{base_url}/api/users.json"
    params = {"paging": "false", "fields": "id,username,name,organisationUnits[id]"}
    r = requests.get(url, headers=headers, params=params)
    if r.status_code != 200: return []
    return [user for user in r.json().get("users", []) 
            if org_unit_id in [ou['id'] for ou in user.get('organisationUnits', [])]]

def get_all_users(base_url, headers):
    url = f"{base_url}/api/users.json"
    params = {"paging": "false", "fields": "id,username,name"}
    r = requests.get(url, headers=headers, params=params)
    return r.json().get("users", []) if r.status_code == 200 else []

@st.cache_data(show_spinner=False)
def get_user_logins(base_url, headers):
    url = f"{base_url}/api/userCredentials?fields=username,lastLogin,disabled&paging=false"
    r = requests.get(url, headers=headers)
    return r.json().get("userCredentials", []) if r.status_code == 200 else []

# Fonctions utilitaires
def color_login(val):
    if pd.isna(val): return 'background-color: #f8d7da'
    days = (datetime.today() - val).days
    if days <= 30: return 'background-color: #d4edda'
    elif days <= 90: return 'background-color: #fff3cd'
    else: return 'background-color: #f8d7da'

def format_last_login(last_login):
    if pd.isna(last_login): return "Jamais"
    delta = datetime.now() - pd.to_datetime(last_login)
    if delta.days == 0: return "Aujourd'hui"
    elif delta.days == 1: return "Hier"
    elif delta.days < 30: return f"il y a {delta.days} jours"
    elif delta.days < 365: return f"il y a {delta.days//30} mois"
    else: return f"il y a {delta.days//365} ans"

# Interface principale
if username and password and dhis2_url:
    headers = get_auth_header(username, password)
    
    st.sidebar.subheader("🔍 Options d'affichage")
    mode = st.sidebar.radio("Mode", ["Unité spécifique", "Tous les utilisateurs"])
    
    if mode == "Unité spécifique":
        units = get_organisation_units(dhis2_url, headers)
        if units:
            selected_unit = st.sidebar.selectbox("Sélectionnez l'unité", 
                                               [unit['name'] for unit in units],
                                               index=0)
            unit_id = [u['id'] for u in units if u['name'] == selected_unit][0]
            
            if st.sidebar.button("🔍 Afficher les utilisateurs"):
                users = get_users_by_org_unit(dhis2_url, headers, unit_id)
                st.info(f"Utilisateurs pour: {selected_unit}")
        else:
            st.sidebar.warning("Aucune unité d'organisation trouvée")
            users = []
    else:
        if st.sidebar.button("🔍 Afficher TOUS les utilisateurs"):
            users = get_all_users(dhis2_url, headers)
            st.info("Liste complète de tous les utilisateurs")

    # Affichage des résultats
    if 'users' in locals() and users:
        df_users = pd.DataFrame(users)[['id', 'username', 'name']]
        
        # Fusion avec les données de connexion
        login_data = get_user_logins(dhis2_url, headers)
        df_login = pd.DataFrame(login_data)[['username', 'lastLogin', 'disabled']]
        df_login['lastLogin'] = pd.to_datetime(df_login['lastLogin'], errors='coerce')
        df_login['Statut'] = df_login['disabled'].apply(lambda x: "Désactivé" if x else "Actif")
        df_login['Dernière connexion'] = df_login['lastLogin'].apply(format_last_login)
        
        df_users = df_users.merge(df_login, on='username', how='left')
        
        # Détection des doublons
        df_users['Doublon'] = df_users.duplicated(subset='name', keep=False)
        df_users['Doublon'] = df_users['Doublon'].apply(lambda x: "🟢 Oui" if x else "🔴 Non")

        # Préparation de l'affichage
        display_cols = ['name', 'username', 'Dernière connexion', 'Statut', 'Doublon']
        df_display = df_users[display_cols].rename(columns={
            'name': 'Nom complet',
            'username': "Nom d'utilisateur"
        })

        # Application du style
        styled_df = df_display.style.applymap(color_login, subset=['Dernière connexion'])
        st.dataframe(styled_df, use_container_width=True, hide_index=True)

        # Bouton d'export
        csv = df_users.to_csv(index=False).encode('utf-8')
        st.download_button("💾 Télécharger CSV", data=csv,
                         file_name="utilisateurs_dhis2.csv",
                         mime='text/csv')
        
        st.success(f"Total: {len(df_users)} utilisateurs trouvés")
    elif 'users' in locals():
        st.warning("Aucun utilisateur trouvé")

# Section Audit
st.sidebar.subheader("📊 Audit des connexions")
if username and password and dhis2_url:
    start_date = st.sidebar.date_input("Date de début", datetime.today() - timedelta(days=30))
    end_date = st.sidebar.date_input("Date de fin", datetime.today())
    
    if st.sidebar.button("📈 Analyser les connexions"):
        logins = get_user_logins(dhis2_url, headers)
        df_audit = pd.DataFrame(logins)
        df_audit['lastLogin'] = pd.to_datetime(df_audit['lastLogin'], errors='coerce')
        
        df_audit['Période active'] = df_audit['lastLogin'].apply(
            lambda x: "Oui" if pd.notnull(x) and start_date <= x.date() <= end_date else "Non")
        
        st.subheader(f"Activité des utilisateurs ({start_date} au {end_date})")
        st.dataframe(
            df_audit.sort_values("lastLogin", ascending=False)
            .style.applymap(color_login, subset=['lastLogin']),
            use_container_width=True
        )
