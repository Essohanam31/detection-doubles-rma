import streamlit as st
import pandas as pd
import requests
import base64
from datetime import datetime, timedelta

# Configuration de la page
st.set_page_config(page_title="DHIS2 - Détection des Doublons", layout="wide")

# Section Connexion
st.title("Connection DHIS2")

# Authentification
with st.expander("🔐 Token d'accès personnel (PAT)"):
    col1, col2 = st.columns(2)
    with col1:
        username = st.text_input("Nom d'utilisateur", key="username")
    with col2:
        password = st.text_input("Mot de passe", type="password", key="password")
    
    dhis2_url = st.text_input("URL DHIS2", value="https://togo.dhis2.org/dhis")

def get_auth_header(username, password):
    token = f"{username}:{password}"
    encoded = base64.b64encode(token.encode()).decode("utf-8")
    return {"Authorization": f"Basic {encoded}"}

# Fonctions API
@st.cache_data(show_spinner=False)
def get_all_users(base_url, headers):
    url = f"{base_url}/api/users.json"
    params = {
        "paging": "false",
        "fields": "id,username,name,organisationUnits[name]"
    }
    r = requests.get(url, headers=headers, params=params)
    return r.json().get("users", []) if r.status_code == 200 else []

@st.cache_data(show_spinner=False)
def get_user_logins(base_url, headers):
    url = f"{base_url}/api/userCredentials?fields=username,lastLogin&paging=false"
    r = requests.get(url, headers=headers)
    return r.json().get("userCredentials", []) if r.status_code == 200 else []

# Formatage des données
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

# Interface principale
if username and password and dhis2_url:
    headers = get_auth_header(username, password)
    
    st.title("Détection des Doublons d'Utilisateurs dans DHIS2")
    
    if st.button("🔍 Charger tous les utilisateurs"):
        with st.spinner("Chargement des données..."):
            users = get_all_users(dhis2_url, headers)
            logins = get_user_logins(dhis2_url, headers)
            
            if users:
                # Préparation des données
                df_users = pd.DataFrame(users)
                
                # Extraction des noms d'organisations
                df_users['Nom unités d\'organisation'] = df_users['organisationUnits'].apply(
                    lambda x: ', '.join([ou['name'] for ou in x]) if isinstance(x, list) else ''
                
                # Ajout des données de connexion
                df_logins = pd.DataFrame(logins)
                df_logins['lastLogin'] = pd.to_datetime(df_logins['lastLogin'], errors='coerce')
                df_users = df_users.merge(df_logins, on='username', how='left')
                
                # Formatage de la dernière connexion
                df_users['Dernière connexion'] = df_users['lastLogin'].apply(format_last_login)
                
                # Détection des doublons
                df_users['doublon'] = df_users.duplicated(subset='name', keep=False)
                df_users['doublon'] = df_users['doublon'].apply(lambda x: "Oui" if x else "Non")
                
                # Sélection des colonnes à afficher
                display_cols = ['id', 'username', 'name', 'Nom unités d\'organisation', 'Dernière connexion', 'doublon']
                df_display = df_users[display_cols].rename(columns={
                    'name': 'Nom complet',
                    'username': 'Username'
                })
                
                # Affichage
                st.success(f"✅ {len(df_users)} utilisateurs trouvés.")
                
                # Configuration du tableau
                st.dataframe(
                    df_display,
                    column_config={
                        "id": "ID",
                        "Username": "Username",
                        "Nom complet": "Nom complet",
                        "Nom unités d'organisation": "Unités d'organisation",
                        "Dernière connexion": "Dernière connexion",
                        "doublon": "Doublon"
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
                # Option d'export
                csv = df_users[display_cols].to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📤 Exporter en CSV",
                    data=csv,
                    file_name="dhis2_users_with_logins.csv",
                    mime="text/csv"
                )
            else:
                st.error("Aucun utilisateur trouvé dans le système")
