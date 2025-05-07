import streamlit as st
import pandas as pd
import requests
import base64
from datetime import datetime, timedelta

st.set_page_config(page_title="DHIS2 - Audit Utilisateurs", layout="wide")

# Section Connexion uniquement dans la barre latérale
st.sidebar.header("🔐 Connexion DHIS2")
dhis2_url = st.sidebar.text_input("URL", value="https://togo.dhis2.org/dhis")
username = st.sidebar.text_input("Nom d'utilisateur")
password = st.sidebar.text_input("Mot de passe", type="password")

# Authentification
def get_auth_header(username, password):
    token = f"{username}:{password}"
    encoded = base64.b64encode(token.encode()).decode("utf-8")
    return {"Authorization": f"Basic {encoded}"}

# Récupérer TOUS les utilisateurs
@st.cache_data(show_spinner=False)
def get_all_users(base_url, headers):
    url = f"{base_url}/api/users.json"
    params = {"paging": "false", "fields": "id,username,name"}
    r = requests.get(url, headers=headers, params=params)
    return r.json().get("users", []) if r.status_code == 200 else []

# Récupérer les connexions
@st.cache_data(show_spinner=False)
def get_user_logins(base_url, headers):
    url = f"{base_url}/api/userCredentials?fields=username,lastLogin&paging=false"
    r = requests.get(url, headers=headers)
    return r.json().get("userCredentials", []) if r.status_code == 200 else []

# Formatage date connexion
def format_login_date(date):
    if pd.isna(date): return "Jamais"
    delta = datetime.now() - date
    if delta.days == 0: return "Aujourd'hui"
    elif delta.days == 1: return "Hier"
    elif delta.days < 30: return f"Il y a {delta.days} jours"
    elif delta.days < 365: return f"Il y a {delta.days//30} mois"
    return f"Il y a {delta.days//365} ans"

# Corps principal
if username and password and dhis2_url:
    headers = get_auth_header(username, password)
    
    # Bouton unique de chargement
    if st.button("🔍 Charger tous les utilisateurs"):
        with st.spinner("Récupération des données..."):
            users = get_all_users(dhis2_url, headers)
            logins = get_user_logins(dhis2_url, headers)
            
            if users:
                # Création du DataFrame
                df = pd.DataFrame(users)[['id', 'username', 'name']]
                
                # Ajout dernière connexion
                df_logins = pd.DataFrame(logins)
                df_logins['lastLogin'] = pd.to_datetime(df_logins['lastLogin'])
                df = df.merge(df_logins, on='username', how='left')
                df['Dernière connexion'] = df['lastLogin'].apply(format_login_date)
                
                # Détection doublons
                df['Doublon'] = df.duplicated('name').map({True: 'Oui', False: 'Non'})
                
                # Affichage
                st.dataframe(
                    df[['id', 'username', 'name', 'Dernière connexion', 'Doublon']],
                    column_config={
                        "id": "ID",
                        "username": "Nom d'utilisateur",
                        "name": "Nom complet",
                        "Dernière connexion": st.column_config.DatetimeColumn("Dernière connexion"),
                        "Doublon": "Doublon"
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
                # Export
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Télécharger CSV", data=csv, file_name="users.csv", mime='text/csv')
            else:
                st.warning("Aucun utilisateur trouvé")

    # Analyse de période (optionnel)
    st.sidebar.divider()
    if st.sidebar.checkbox("Analyse par période"):
        start = st.sidebar.date_input("Début", datetime.today() - timedelta(days=30))
        end = st.sidebar.date_input("Fin", datetime.today())
        
        if st.sidebar.button("Analyser"):
            logins = get_user_logins(dhis2_url, headers)
            df = pd.DataFrame(logins)
            df['lastLogin'] = pd.to_datetime(df['lastLogin'])
            df = df[df['lastLogin'].between(pd.to_datetime(start), pd.to_datetime(end))]
            st.dataframe(df, use_container_width=True)
