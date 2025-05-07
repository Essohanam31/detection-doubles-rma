import streamlit as st
import pandas as pd
import requests
import base64
from datetime import datetime, timedelta

st.set_page_config(page_title="DHIS2 - Gestion Utilisateurs", layout="wide")

# Section Connexion - Barre latérale
st.sidebar.header("🔐 Connexion à DHIS2")
dhis2_url = st.sidebar.text_input("URL DHIS2", value="https://togo.dhis2.org/dhis")
username = st.sidebar.text_input("Nom d'utilisateur")
password = st.sidebar.text_input("Mot de passe", type="password")

# Authentification
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
    url = f"{base_url}/api/userCredentials?fields=username,lastLogin,disabled&paging=false"
    r = requests.get(url, headers=headers)
    return r.json().get("userCredentials", []) if r.status_code == 200 else []

# Formatage des données
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
    
    # Bouton de chargement principal
    if st.sidebar.button("Charger tous les utilisateurs", type="primary"):
        with st.spinner("Chargement des utilisateurs..."):
            users = get_all_users(dhis2_url, headers)
            logins = get_user_logins(dhis2_url, headers)
            
            if users:
                # Préparation des données
                df_users = pd.DataFrame(users)
                
                # Extraction des noms d'organisations
                df_users['Unités d\'organisation'] = df_users['organisationUnits'].apply(
                    lambda x: ', '.join([ou['name'] for ou in x]) if isinstance(x, list) else ''
                
                # Ajout des données de connexion
                df_logins = pd.DataFrame(logins)
                df_logins['lastLogin'] = pd.to_datetime(df_logins['lastLogin'], errors='coerce')
                df_users = df_users.merge(df_logins, on='username', how='left')
                
                # Formatage des dates
                df_users['Dernière connexion'] = df_users['lastLogin'].apply(format_last_login)
                
                # Détection des doublons
                df_users['Doublon'] = df_users.duplicated(subset='name', keep=False)
                df_users['Doublon'] = df_users['Doublon'].apply(lambda x: "Oui" if x else "Non")

                # Affichage
                st.success(f"✅ {len(df_users)} utilisateurs trouvés")
                
                # Configuration du tableau
                st.dataframe(
                    df_users[['id', 'username', 'name', 'Unités d\'organisation', 'Dernière connexion', 'Doublon']]
                    .rename(columns={
                        'name': 'Nom complet',
                        'username': 'Nom utilisateur'
                    }),
                    column_config={
                        "id": "ID",
                        "Nom utilisateur": st.column_config.TextColumn("Username"),
                        "Nom complet": st.column_config.TextColumn("Nom complet"),
                        "Unités d'organisation": st.column_config.TextColumn("Unités"),
                        "Dernière connexion": st.column_config.TextColumn("Dernière connexion"),
                        "Doublon": st.column_config.TextColumn("Doublon")
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
                # Export CSV
                csv = df_users.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📤 Exporter en CSV",
                    data=csv,
                    file_name="utilisateurs_dhis2.csv",
                    mime="text/csv"
                )
            else:
                st.warning("Aucun utilisateur trouvé")

    # Section Audit dans la barre latérale
    st.sidebar.divider()
    st.sidebar.subheader("📊 Analyse des connexions")
    start_date = st.sidebar.date_input("Début", datetime.today() - timedelta(days=30))
    end_date = st.sidebar.date_input("Fin", datetime.today())
    
    if st.sidebar.button("Analyser les connexions"):
        if start_date > end_date:
            st.error("La date de début doit être antérieure à la date de fin")
        else:
            logins = get_user_logins(dhis2_url, headers)
            df_audit = pd.DataFrame(logins)
            df_audit['lastLogin'] = pd.to_datetime(df_audit['lastLogin'], errors='coerce')
            
            df_audit['Période active'] = df_audit['lastLogin'].apply(
                lambda x: "Oui" if pd.notnull(x) and start_date <= x.date() <= end_date else "Non")
            
            st.dataframe(
                df_audit.sort_values("lastLogin", ascending=False),
                use_container_width=True,
                hide_index=True
            )
