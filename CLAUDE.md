# Radar_Pédagogique — Contexte projet Claude Code

## Description
Application web d'analyse statistique des données d'un radar pédagogique
(Elan Cité / logiciel Evocom). Visualise les passages de véhicules détectés
au-dessus de la limite de vitesse configurée.

## Stack technique
- **Application** : Python 3.12 + Streamlit
- **Visualisations** : Plotly
- **Données** : Pandas
- **Déploiement** : Docker

## Structure du projet
```
Radar_Pédagogique/
├── app.py                  # Application Streamlit (point d'entrée)
├── parser/
│   ├── __init__.py
│   └── dbz1_parser.py     # Parser du format .dbz1 (Elan Cité)
├── input_files/           # Dossier des fichiers .dbz1 surveillé
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── CLAUDE.md
```

## Ports
| Service   | Port hôte | Port container |
|-----------|-----------|----------------|
| Streamlit | 8510      | 8501           |

## Commandes
```bash
# Développement local (sans Docker)
pip install -r requirements.txt
streamlit run app.py

# Docker
docker compose up -d --build
docker compose logs -f
docker compose down
```

## Format des fichiers .dbz1 (Elan Cité / Evocom)

### Structure externe
Un fichier = N blocs journaliers consécutifs. Chaque bloc :
- `uint32 BE` : longueur de la chaîne filename
- `N bytes` : UTF-16 BE = `/YYYYMMDDHHMMSS.bin`
- `4 bytes` : padding + métadonnées
- `4 bytes` : taille décompressée
- Reste : données zlib compressées

### Données décompressées (par bloc)
- Magic : `0xA0B0C0D0`
- Header TLV (UTF-16 LE) : version, commune, MAC, OS, firmware
- Enregistrements de **8 octets** chacun :
  - `0xFFFD` (2o) = séparateur
  - `uint16 BE` (2o) = **slot_temps** × 10 min depuis minuit
  - `uint16 BE` (2o) = **vitesse_limite** km/h (constante par installation)
  - `uint16 BE` (2o) = **vitesse_mesurée** km/h

### Fichier de référence analysé
- `stats-0004A34A8390.dbz1`
- **554 blocs** (journées) du 14/09/2024 au 21/03/2026
- **139 570 passages** au total
- Commune : **Hourton**
- Limite configurée : **64 km/h**
- Plage horaire : 6h10 à 21h10
- Vitesses : 65 à 108 km/h

### Points d'attention
- Le radar n'enregistre que les véhicules **au-dessus** de la limite
- Le champ `slot_temps` × 10 = minutes depuis minuit (ex: slot 54 = 9h00)
- La limite 64 km/h est inhabituelle (non standard France) — peut être un seuil
  personnalisé plutôt que la limite légale du tronçon
- Pas de champ "sens de passage" dans ce format
- Firmware : "4.8.x" avec un caractère Unicode U+0135 en fin (artefact hardware)
