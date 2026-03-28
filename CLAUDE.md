# Radar_Pédagogique — Contexte projet Claude Code

## Description
Application Streamlit d'analyse statistique des données d'un radar pédagogique
(équipement Elan Cité / logiciel Evocom). Lit des fichiers binaires `.dbz1` et
produit des visualisations interactives (distribution, profil horaire, tendances,
calendrier GitHub-style, zone Admin protégée).

## Stack technique
- **Application** : Python 3.12 + Streamlit 1.55
- **Visualisations** : Plotly 6
- **Données** : Pandas 2
- **Déploiement** : Docker (local) + Streamlit Community Cloud

## Structure du projet
```
Radar_Pédagogique/
├── app.py                      # Application Streamlit (point d'entrée)
├── parser/
│   ├── __init__.py
│   └── dbz1_parser.py          # Parser du format .dbz1 (Elan Cité)
├── sample_data/                # Fichier(s) de démo embarqués dans le repo
│   └── stats-0004A34A8390.dbz1
├── input_files/                # Fichiers .dbz1 locaux (gitignorés)
├── stats/                      # Statistiques de visites (gitignorées, auto-générées)
├── .streamlit/
│   ├── secrets.toml            # Mot de passe Admin (gitignorés)
│   └── secrets.toml.example
├── .claude/
│   └── settings.local.json
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── CLAUDE.md
```

## Ports
| Service   | Port hôte | Port container |
|-----------|-----------|----------------|
| Streamlit | **8510**  | 8501           |

**URL locale :** http://localhost:8510
**URL Streamlit Cloud :** https://[app].streamlit.app (compte sylvled)
**GitHub :** https://github.com/sylvled/Radar_Pedagogique

## Version courante
`v1.3.0 — 2026-03-27` — commit `d21fc83`

## Commandes Docker
```bash
# Démarrer (reconstruction complète obligatoire après changement de code)
docker compose up -d --build

# Logs en direct
docker compose logs -f

# Arrêter
docker compose down
```

## Commandes développement direct (sans Docker)
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Fonctionnalités
- **Multi-radar** : charger N fichiers .dbz1 via uploader ou dossier `sample_data/`
- **Onglets** : Distribution vitesses | Profil horaire | Tendances | Calendrier | Données brutes | Admin
- **Calendrier** : Vue GitHub (semaines × jours) + Vue mois × jour du mois, avec slider seuil
- **Top 50** : tableau des vitesses les plus élevées
- **Zone Admin** : protégée par mot de passe, statistiques de visites journalières + export CSV

## Secrets Streamlit (mot de passe Admin)
Fichier `.streamlit/secrets.toml` (gitignorés — NE JAMAIS COMMITER) :
```toml
ADMIN_PASSWORD = "radar2024"
```
Sur Streamlit Community Cloud : App Settings → Secrets → coller le contenu.

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

### Fichier de démo embarqué
- `stats-0004A34A8390.dbz1`
- **554 blocs** (journées) du 14/09/2024 au 21/03/2026
- **139 570 passages** au total
- Commune : **Hourton**
- Limite configurée : **64 km/h** (seuil personnalisé, non standard France)
- Plage horaire : 6h10 à 21h10
- Vitesses enregistrées : 65 à 108 km/h

### Points d'attention
- Le radar n'enregistre que les véhicules **au-dessus** de la limite configurée
- `slot_temps` × 10 = minutes depuis minuit (ex: slot 54 = 9h00)
- Firmware : "4.8.x" avec caractère Unicode U+0135 en fin (artefact hardware)
- Pas de champ "sens de passage" dans ce format
