import streamlit as st
import pandas as pd
import requests
import base64
from datetime import datetime, timedelta

# Configuration de la page
st.set_page_config(page_title="DHIS2 - Gestion Utilisateurs", layout="wide")

# Section Connexion
st.header("# Connexion à DHIS2")

col1, col2 = st.columns(2)
with col1:
    dhis2_url = st.text_input("URL DHIS2", value="https://togo.dhis2.org/dhis")
with col2:
    username = st.text_input("Nom d'utilisateur")

password = st.text_input("Mot de passe", type="password")

# Authentification
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
    
    st.divider()
    st.subheader("### Sélection de l'unité d'organisation")
    
    units = get_organisation_units(dhis2_url, headers)
    if units:
        selected_unit = st.selectbox("Choisir une unité", 
                                  [unit['name'] for unit in units],
                                  index=0)
        
        col1, col2 = st.columns([3,1])
        with col2:
            if st.button("Charger les utilisateurs", type="primary"):
                unit_id = [u['id'] for u in units if u['name'] == selected_unit][0]
                users = get_users_by_org_unit(dhis2_url, headers, unit_id)
                
                if users:
                    # Traitement des données
                    df_users = pd.DataFrame(users)[['id', 'username', 'name']]
                    
                    # Récupération des infos de connexion
                    login_data = get_user_logins(dhis2_url, headers)
                    df_login = pd.DataFrame(login_data)[['username', 'lastLogin', 'disabled']]
                    df_login['lastLogin'] = pd.to_datetime(df_login['lastLogin'], errors='coerce')
                    df_login['Statut'] = df_login['disabled'].apply(lambda x: "Désactivé" if x else "Actif")
                    df_login['Dernière connexion'] = df_login['lastLogin'].apply(format_last_login)
                    
                    # Fusion des données
                    df_users = df_users.merge(df_login, on='username', how='left')
                    
                    # Détection des doublons
                    df_users['Doublon'] = df_users.duplicated(subset='name', keep=False)
                    df_users['Doublon'] = df_users['Doublon'].apply(lambda x: "Oui" if x else "Non")
                    
                    # Affichage
                    st.divider()
                    st.subheader(f"### Chargement des utilisateurs pour l'unité : {selected_unit}")
                    st.info(f"{len(df_users)} utilisateurs trouvés.")
                    
                    # Sélection des colonnes à afficher
                    display_cols = ['id', 'username', 'name', 'Dernière connexion', 'Statut', 'Doublon']
                    df_display = df_users[display_cols].rename(columns={
                        'name': 'Nom complet',
                        'username': "Nom d'utilisateur"
                    })
                    
                    # Affichage du tableau
                    st.dataframe(
                        df_display,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "id": "ID",
                            "Nom d'utilisateur": "Username",
                            "Nom complet": "Nom complet",
                            "Dernière connexion": "Dernière connexion",
                            "Statut": "Statut",
                            "Doublon": "Doublon"
                        }
                    )
                    
                    # Export CSV
                    csv = df_users.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        "Télécharger CSV",
                        data=csv,
                        file_name=f"utilisateurs_{selected_unit}.csv",
                        mime='text/csv'
                    )
                else:
                    st.warning("Aucun utilisateur trouvé pour cette unité.")
    else:
        st.warning("Aucune unité d'organisation trouvée")

    # Section Audit
    st.divider()
    st.subheader("### Période d'analyse des connexions")
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Début", datetime.today() - timedelta(days=30))
    with col2:
        end_date = st.date_input("Fin", datetime.today())
    
    if st.button("Analyser les connexions", type="primary"):
        if start_date > end_date:
            st.error("La date de début doit être antérieure à la date de fin")
        else:
            logins = get_user_logins(dhis2_url, headers)
            df_audit = pd.DataFrame(logins)
            df_audit['lastLogin'] = pd.to_datetime(df_audit['lastLogin'], errors='coerce')
            
            df_audit['Période active'] = df_audit['lastLogin'].apply(
                lambda x: "Oui" if pd.notnull(x) and start_date <= x.date() <= end_date else "Non")
            
            st.success(f"Analyse du {start_date} au {end_date}")
            st.dataframe(
                df_audit.sort_values("lastLogin", ascending=False),
                use_container_width=True,
                hide_index=True
            )
