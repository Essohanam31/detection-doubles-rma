import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from requests.auth import HTTPBasicAuth

st.set_page_config(page_title="Suivi des utilisateurs DHIS2", layout="wide")

st.title("🔐 Connexion à DHIS2 et Analyse des Utilisateurs")

# --- Connexion à DHIS2
dhis2_url = st.text_input("🌍 URL de l'instance DHIS2", "https://play.dhis2.org/40.0")
username = st.text_input("👤 Nom d'utilisateur", type="default")
password = st.text_input("🔑 Mot de passe", type="password")

if st.button("Se connecter"):
    with st.spinner("Connexion à DHIS2..."):
        response = requests.get(
            f"{dhis2_url}/api/me",
            auth=HTTPBasicAuth(username, password)
        )
        if response.status_code == 200:
            st.success("✅ Connexion réussie.")
            user_info = response.json()
            st.write("👤 Utilisateur :", user_info["displayName"])
        else:
            st.error("❌ Échec de la connexion. Vérifiez les identifiants.")
            st.stop()

    # --- Récupération des utilisateurs
    st.subheader("👥 Récupération des utilisateurs...")
    users_url = f"{dhis2_url}/api/users?fields=id,name,created,userCredentials[username],organisationUnits[id,name]&paging=false"
    res_users = requests.get(users_url, auth=HTTPBasicAuth(username, password))
    users = res_users.json()["users"]

    data = []
    for user in users:
        org_units = [ou["name"] for ou in user.get("organisationUnits", [])]
        data.append({
            "Nom complet": user.get("name", ""),
            "Nom d'utilisateur": user.get("userCredentials", {}).get("username", ""),
            "Date de création": user.get("created", ""),
            "Unités d'organisation": ", ".join(org_units)
        })

    df = pd.DataFrame(data)

    # Convertir la date de création en datetime
    df["Date de création"] = pd.to_datetime(df["Date de création"])

    # --- Détection des doublons
    st.subheader("🔍 Doublons (par nom)")
    dupes = df[df.duplicated("Nom complet", keep=False)]
    st.dataframe(dupes)

    # --- Dernière activité (commande)
    st.subheader("📦 Dernière commande enregistrée")

    # Exemple : extraire dernière activité via `dataValueSets` (à adapter selon ton instance)
    # On prend la date du dernier formulaire soumis par utilisateur fictif
    def get_days_since_last_submission(user_name):
        return pd.Timestamp.now() - pd.Timestamp("2024-12-01")  # valeur fictive

    df["Jours depuis dernière activité"] = df["Nom d'utilisateur"].apply(
        lambda x: get_days_since_last_submission(x).days
    )

    st.dataframe(df)

    # --- Export CSV
    st.download_button(
        label="⬇️ Télécharger CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="utilisateurs_dhis2.csv",
        mime="text/csv"
    )
