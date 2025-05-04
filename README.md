# DETECTION DES DOUBLES ATTRIBUTION DES RMA

Cette application Streamlit permet de :
- Importer un fichier Excel contenant les liens FOSA - Services
- S’authentifier sur DHIS2
- Identifier les formations sanitaires ayant une double attribution de RMA
- Télécharger les résultats au format CSV

## Utilisation
1. Lancer l’application avec `streamlit run app.py`
2. Entrer vos identifiants DHIS2
3. Importer le fichier `fosa_services.xlsx`
4. Visualiser et télécharger les doublons détectés
