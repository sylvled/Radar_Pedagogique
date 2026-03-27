"""
Radar Pédagogique — Application d'analyse statistique
Données Elan Cité / Evocom (.dbz1)
"""

VERSION = "1.3.0"
VERSION_DATE = "2026-03-27"

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import sys
import json
import datetime

# Ajouter le répertoire racine au path pour importer le parser
sys.path.insert(0, str(Path(__file__).parent))
from parser.dbz1_parser import parse_dbz1, RadarDataset

# ---------------------------------------------------------------------------
# Configuration Streamlit
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Radar Pédagogique",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# CSS personnalisé
# ---------------------------------------------------------------------------
st.markdown("""
<style>
.metric-card {
    background: #f0f2f6;
    border-radius: 10px;
    padding: 16px;
    text-align: center;
}
.metric-value {
    font-size: 2rem;
    font-weight: bold;
    color: #1f77b4;
}
.metric-label {
    font-size: 0.85rem;
    color: #666;
}
.warning-box {
    background: #fff3cd;
    border: 1px solid #ffc107;
    border-radius: 6px;
    padding: 10px 14px;
    font-size: 0.88rem;
}
/* Navigation radio stylisée comme des onglets */
div[data-testid="stRadio"] > div {
    gap: 0 !important;
    border-bottom: 1px solid #e0e0e0;
}
div[data-testid="stRadio"] > div > label {
    border-radius: 0 !important;
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
    padding: 6px 16px !important;
    font-size: 0.875rem;
    color: #555;
    background: transparent !important;
    box-shadow: none !important;
}
div[data-testid="stRadio"] > div > label:hover {
    color: #262730;
    background: #f5f5f5 !important;
}
div[data-testid="stRadio"] > div > label:has(input:checked) {
    border-bottom-color: #ff4b4b;
    color: #ff4b4b;
    font-weight: 600;
}
/* Radar list items */
.radar-item {
    padding: 4px 0;
    font-size: 0.82rem;
    color: #444;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
/* Animation loader */
@keyframes radar-spin {
    0%   { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}
@keyframes radar-pulse {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.4; }
}
.loader-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 40px 20px;
    gap: 16px;
}
.loader-ring {
    width: 56px; height: 56px;
    border: 5px solid #f0f2f6;
    border-top: 5px solid #ff4b4b;
    border-radius: 50%;
    animation: radar-spin 0.9s linear infinite;
}
.loader-text {
    font-size: 1rem;
    color: #555;
    animation: radar-pulse 1.4s ease-in-out infinite;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
SAMPLE_FOLDER = Path(__file__).parent / "sample_data"
STATS_FILE    = Path(__file__).parent / "stats" / "visits.json"

# Mot de passe admin (priorité : st.secrets > variable d'env > défaut)
try:
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
except Exception:
    ADMIN_PASSWORD = "radar2024"

# ---------------------------------------------------------------------------
# Statistiques de visites
# ---------------------------------------------------------------------------

def load_stats() -> dict:
    """Charge les statistiques de visites depuis le fichier JSON."""
    try:
        if STATS_FILE.exists():
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"total": 0, "daily": {}, "first_visit": None}


def save_stats(stats: dict) -> None:
    """Sauvegarde atomique des statistiques (fichier temporaire → rename)."""
    try:
        STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATS_FILE.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        tmp.replace(STATS_FILE)
    except Exception:
        pass


def record_visit() -> None:
    """Enregistre une nouvelle session (appelé une seule fois par session navigateur)."""
    stats = load_stats()
    today = datetime.date.today().isoformat()
    stats["total"] = stats.get("total", 0) + 1
    stats.setdefault("daily", {})
    stats["daily"][today] = stats["daily"].get(today, 0) + 1
    if not stats.get("first_visit"):
        stats["first_visit"] = today
    save_stats(stats)


DAYS_FR = {0: "Lundi", 1: "Mardi", 2: "Mercredi", 3: "Jeudi",
           4: "Vendredi", 5: "Samedi", 6: "Dimanche"}

MONTHS_FR = {
    1: "Jan", 2: "Fév", 3: "Mar", 4: "Avr", 5: "Mai", 6: "Juin",
    7: "Juil", 8: "Août", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Déc"
}

# ---------------------------------------------------------------------------
# Fonctions utilitaires
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def load_dataset(source_bytes: bytes, filename: str) -> tuple[dict, pd.DataFrame]:
    """Parse et met en cache un fichier .dbz1 → (metadata_dict, dataframe)."""
    ds = parse_dbz1(source_bytes)

    records = []
    for r in ds.records:
        records.append({
            "date": r.recording_date,
            "slot": r.time_slot,
            "heure_min": r.slot_minutes,
            "heure": f"{r.slot_minutes // 60:02d}:{r.slot_minutes % 60:02d}",
            "limite": r.speed_limit,
            "vitesse": r.speed,
            "exces": r.excess,
        })

    df = pd.DataFrame(records)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df["jour_semaine"] = df["date"].dt.dayofweek
        df["mois"] = df["date"].dt.month
        df["annee"] = df["date"].dt.year
        df["semaine"] = df["date"].dt.isocalendar().week.astype(int)

    meta = {
        "commune": ds.device.commune or "Inconnue",
        "device_id": ds.device.device_id or "—",
        "firmware": ds.device.firmware or "—",
        "os": ds.device.os_info or "—",
        "limite": ds.speed_limit,
        "total": ds.total_detections,
        "jours": ds.unique_days,
        "date_debut": ds.date_range[0],
        "date_fin": ds.date_range[1],
        "avg_speed": ds.avg_speed,
        "max_speed": ds.max_speed,
    }
    return meta, df


def speed_category(v: int, limit: int) -> str:
    excess = v - limit
    if excess <= 5:
        return f"+1 à +5 km/h"
    elif excess <= 10:
        return f"+6 à +10 km/h"
    elif excess <= 20:
        return f"+11 à +20 km/h"
    elif excess <= 30:
        return f"+21 à +30 km/h"
    else:
        return f"+30 km/h"


@st.cache_data(show_spinner=False)
def get_radar_label(data_bytes: bytes, filename: str) -> str:
    """Retourne un label lisible pour un radar (commune + device_id)."""
    try:
        meta, _ = load_dataset(data_bytes, filename)
        commune = (meta.get("commune") or "").strip()
        device_id = (meta.get("device_id") or "").strip()
        if commune and commune != "Inconnue":
            if device_id and device_id != "—":
                return f"📍 {commune}  [{device_id}]"
            return f"📍 {commune}"
        if device_id and device_id != "—":
            return f"📡 {device_id}"
        stem = Path(filename).stem
        return f"📡 {stem}"
    except Exception:
        return f"📡 {Path(filename).stem}"


# ---------------------------------------------------------------------------
# Initialisation session state
# ---------------------------------------------------------------------------
if "radars" not in st.session_state:
    # dict {unique_key: bytes}
    st.session_state.radars = {}

# Enregistrement de la session (une seule fois par onglet navigateur)
if "session_recorded" not in st.session_state:
    st.session_state.session_recorded = True
    record_visit()

# Auto-chargement des fichiers de démonstration au premier lancement
if not st.session_state.radars and SAMPLE_FOLDER.exists():
    for p in sorted(SAMPLE_FOLDER.glob("*.dbz1")):
        demo_key = f"[Démo] {p.name}"
        if demo_key not in st.session_state.radars:
            st.session_state.radars[demo_key] = p.read_bytes()


# ---------------------------------------------------------------------------
# Sidebar — Gestion des radars
# ---------------------------------------------------------------------------
with st.sidebar:
    st.image(
        "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cf/Speed_camera_icon.svg/100px-Speed_camera_icon.svg.png",
        width=60,
    )
    st.title("Radar Pédagogique")
    st.caption(f"v{VERSION} — {VERSION_DATE}")
    st.markdown("---")

    # ── Uploader ──────────────────────────────────────────────────────────────
    st.subheader("📁 Ajouter des fichiers")
    uploaded_files = st.file_uploader(
        "Déposer un ou plusieurs fichiers .dbz1",
        type=["dbz1"],
        accept_multiple_files=True,
        help="Fichiers statistiques Elan Cité / Evocom",
        label_visibility="collapsed",
    )
    for f in uploaded_files or []:
        key = f.name
        if key not in st.session_state.radars:
            st.session_state.radars[key] = f.read()

    # ── Liste des radars chargés ───────────────────────────────────────────────
    radar_keys = list(st.session_state.radars.keys())

    if radar_keys:
        st.markdown("---")
        st.subheader(f"📡 Radars chargés ({len(radar_keys)})")

        to_delete = None
        for rk in radar_keys:
            lbl = get_radar_label(st.session_state.radars[rk], rk)
            col1, col2 = st.columns([5, 1])
            col1.markdown(f"<div class='radar-item'>{lbl}</div>", unsafe_allow_html=True)
            if col2.button("✕", key=f"del_{rk}", help="Retirer ce radar"):
                to_delete = rk
        if to_delete:
            del st.session_state.radars[to_delete]
            # Réinitialiser la sélection si le radar actif est supprimé
            if st.session_state.get("sel_radar") == to_delete:
                remaining = [k for k in radar_keys if k != to_delete]
                st.session_state["sel_radar"] = remaining[0] if remaining else None
            st.rerun()

        st.markdown("---")

        # ── Sélecteur du radar actif ──────────────────────────────────────────
        if len(radar_keys) > 1:
            st.subheader("🎯 Radar actif")
            labels = {rk: get_radar_label(st.session_state.radars[rk], rk) for rk in radar_keys}
            # Garder la sélection précédente si elle existe encore
            prev = st.session_state.get("sel_radar")
            default_idx = radar_keys.index(prev) if prev in radar_keys else 0
            active_key = st.selectbox(
                "Sélectionner le radar à analyser",
                options=radar_keys,
                index=default_idx,
                format_func=lambda k: labels[k],
                label_visibility="collapsed",
                key="sel_radar",
            )
        else:
            active_key = radar_keys[0]
            lbl = get_radar_label(st.session_state.radars[active_key], active_key)
            st.info(lbl)

    else:
        active_key = None

    # ── Filtres (affichés après chargement) ───────────────────────────────────
    filters_placeholder = st.empty()


# ---------------------------------------------------------------------------
# Zone principale : pas de radar chargé
# ---------------------------------------------------------------------------
if not active_key:
    st.markdown("## 🚦 Radar Pédagogique — Analyse statistique")
    st.markdown("""
    **Chargez un fichier `.dbz1`** (format Elan Cité / Evocom) via le panneau latéral
    pour visualiser les statistiques de passage.

    **Données analysées :**
    - Vitesse de chaque passage (km/h)
    - Répartition horaire
    - Tendance journalière / hebdomadaire / mensuelle
    - Distribution des excès de vitesse
    - Matrices calendaires de dépassements

    **Vous pouvez charger plusieurs radars** et basculer entre eux via le sélecteur.
    """)
    st.stop()


# ---------------------------------------------------------------------------
# Chargement et parsing du radar actif
# ---------------------------------------------------------------------------
_load_placeholder = st.empty()
_is_cached = load_dataset.cache_info().currsize > 0 if hasattr(load_dataset, "cache_info") else False

with _load_placeholder.container():
    st.markdown("""
    <div class="loader-wrap">
        <div class="loader-ring"></div>
        <div class="loader-text">⏳ Décompression et analyse du fichier radar…</div>
    </div>
    """, unsafe_allow_html=True)

try:
    meta, df = load_dataset(
        st.session_state.radars[active_key],
        active_key,
    )
except Exception as e:
    _load_placeholder.empty()
    st.error(f"Erreur de lecture du fichier : {e}")
    st.stop()

_load_placeholder.empty()


# ---------------------------------------------------------------------------
# Filtres dynamiques (dans sidebar, après chargement)
# ---------------------------------------------------------------------------
with st.sidebar:
    if not df.empty:
        st.markdown("---")
        st.subheader("🔧 Filtres")

        years = sorted(df["annee"].unique().tolist())
        year_options = ["Tous"] + [str(y) for y in years]
        # Clé unique par radar pour éviter les conflits de session_state
        rk_safe = active_key.replace(" ", "_").replace("[", "").replace("]", "")
        sel_year = st.selectbox("Année", year_options, key=f"fy_{rk_safe}")

        day_options = ["Tous"] + [DAYS_FR[i] for i in range(7)]
        sel_day = st.selectbox("Jour de la semaine", day_options, key=f"fd_{rk_safe}")

        speed_range = st.slider(
            "Plage de vitesse (km/h)",
            min_value=int(df["vitesse"].min()),
            max_value=int(df["vitesse"].max()),
            value=(int(df["vitesse"].min()), int(df["vitesse"].max())),
            key=f"fs_{rk_safe}",
        )
    else:
        sel_year = "Tous"
        sel_day = "Tous"
        speed_range = None


# ---------------------------------------------------------------------------
# Application des filtres
# ---------------------------------------------------------------------------
df_f = df.copy()

if sel_year != "Tous":
    df_f = df_f[df_f["annee"] == int(sel_year)]

if sel_day != "Tous":
    day_idx = [k for k, v in DAYS_FR.items() if v == sel_day][0]
    df_f = df_f[df_f["jour_semaine"] == day_idx]

if speed_range is not None:
    lo, hi = speed_range
    df_f = df_f[(df_f["vitesse"] >= lo) & (df_f["vitesse"] <= hi)]


# ---------------------------------------------------------------------------
# En-tête
# ---------------------------------------------------------------------------
radar_label = get_radar_label(st.session_state.radars[active_key], active_key)
st.markdown(f"## 🚦 {meta['commune']} — Radar `{meta['device_id']}`")

d1 = meta["date_debut"].strftime("%d/%m/%Y") if meta["date_debut"] else "—"
d2 = meta["date_fin"].strftime("%d/%m/%Y") if meta["date_fin"] else "—"
st.markdown(f"**Période :** {d1} → {d2} &nbsp;|&nbsp; **Limite configurée :** {meta['limite']} km/h")

if df_f.shape[0] < df.shape[0]:
    st.info(f"Filtres actifs — {df_f.shape[0]:,} passages affichés sur {df.shape[0]:,}")


# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------
k1, k2, k3, k4, k5 = st.columns(5)
limit = meta["limite"] or 64

with k1:
    st.metric("Total passages", f"{df_f.shape[0]:,}")
with k2:
    st.metric("Jours de données", f"{df_f['date'].nunique():,}")
with k3:
    avg = df_f["vitesse"].mean() if not df_f.empty else 0
    st.metric("Vitesse moyenne", f"{avg:.1f} km/h")
with k4:
    mx = df_f["vitesse"].max() if not df_f.empty else 0
    st.metric("Vitesse max", f"{mx} km/h")
with k5:
    avg_day = df_f.shape[0] / df_f["date"].nunique() if not df_f.empty and df_f["date"].nunique() > 0 else 0
    st.metric("Moy. / jour", f"{avg_day:.0f} passages")

st.markdown("---")


# ---------------------------------------------------------------------------
# Navigation par onglets (session_state — ne se réinitialise pas au rerun)
# ---------------------------------------------------------------------------
TAB_NAMES = [
    "📊 Distribution vitesses",
    "🕐 Profil horaire",
    "📅 Tendances",
    "📆 Calendrier",
    "📋 Données brutes",
    "🔐 Admin",
]
if "active_tab" not in st.session_state:
    st.session_state.active_tab = TAB_NAMES[0]

active_tab = st.radio(
    "Navigation",
    TAB_NAMES,
    horizontal=True,
    key="active_tab",
    label_visibility="collapsed",
)


# ============================================================================
# Tab 1 : Distribution des vitesses
# ============================================================================
if active_tab == TAB_NAMES[0]:
    col_l, col_r = st.columns([2, 1])

    with col_l:
        st.subheader("Distribution des vitesses")
        if not df_f.empty:
            speed_dist = df_f["vitesse"].value_counts().sort_index().reset_index()
            speed_dist.columns = ["vitesse", "passages"]

            fig = px.bar(
                speed_dist,
                x="vitesse",
                y="passages",
                color="vitesse",
                color_continuous_scale="RdYlGn_r",
                labels={"vitesse": "Vitesse (km/h)", "passages": "Nombre de passages"},
                title=f"Répartition des vitesses (limite = {limit} km/h)",
            )
            fig.add_vline(
                x=limit, line_dash="dash", line_color="red",
                annotation_text=f"Limite {limit} km/h",
                annotation_position="top right"
            )
            fig.update_layout(coloraxis_showscale=False, height=420)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Aucune donnée avec les filtres actuels.")

    with col_r:
        st.subheader("Catégories d'excès")
        if not df_f.empty:
            df_f["categorie"] = df_f["vitesse"].apply(lambda v: speed_category(v, limit))
            cat_order = ["+1 à +5 km/h", "+6 à +10 km/h", "+11 à +20 km/h", "+21 à +30 km/h", "+30 km/h"]
            cat_counts = df_f["categorie"].value_counts().reindex(cat_order, fill_value=0).reset_index()
            cat_counts.columns = ["categorie", "passages"]
            cat_counts["pct"] = (cat_counts["passages"] / df_f.shape[0] * 100).round(1)

            fig2 = px.pie(
                cat_counts,
                values="passages",
                names="categorie",
                color_discrete_sequence=px.colors.sample_colorscale("RdYlGn_r", 5),
                hole=0.4,
            )
            fig2.update_layout(height=300, margin=dict(t=10, b=10))
            st.plotly_chart(fig2, use_container_width=True)

            st.dataframe(
                cat_counts[["categorie", "passages", "pct"]].rename(columns={
                    "categorie": "Catégorie",
                    "passages": "Passages",
                    "pct": "% total"
                }),
                use_container_width=True,
                hide_index=True,
            )

    # Boîte à moustaches par mois
    if not df_f.empty:
        st.subheader("Vitesses par mois (boîte à moustaches)")
        df_f["mois_label"] = df_f["mois"].map(MONTHS_FR)
        month_order = [MONTHS_FR[m] for m in sorted(df_f["mois"].unique())]
        fig3 = px.box(
            df_f, x="mois_label", y="vitesse",
            category_orders={"mois_label": month_order},
            labels={"mois_label": "Mois", "vitesse": "Vitesse (km/h)"},
            color="mois_label",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig3.add_hline(y=limit, line_dash="dash", line_color="red",
                       annotation_text=f"Limite {limit} km/h")
        fig3.update_layout(showlegend=False, height=380)
        st.plotly_chart(fig3, use_container_width=True)

    # Top 50 des plus grandes vitesses
    st.subheader("🏎️ Top 50 des vitesses les plus élevées")
    if not df_f.empty:
        top50 = (
            df_f[["date", "heure", "vitesse", "exces"]]
            .sort_values("vitesse", ascending=False)
            .head(50)
            .copy()
        )
        top50["date"] = top50["date"].dt.strftime("%d/%m/%Y")
        top50 = top50.reset_index(drop=True)
        top50.index += 1
        top50.columns = ["Date", "Heure", "Vitesse (km/h)", "Excès (km/h)"]
        st.dataframe(top50, use_container_width=True, height=400)
    else:
        st.info("Aucune donnée avec les filtres actuels.")


# ============================================================================
# Tab 2 : Profil horaire
# ============================================================================
elif active_tab == TAB_NAMES[1]:
    st.subheader("Répartition par tranche horaire (10 min)")

    if not df_f.empty:
        hourly = df_f.groupby("heure_min").agg(
            passages=("vitesse", "count"),
            vitesse_moy=("vitesse", "mean"),
            vitesse_max=("vitesse", "max"),
        ).reset_index()
        hourly["heure"] = hourly["heure_min"].apply(
            lambda m: f"{m//60:02d}:{m%60:02d}"
        )

        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            subplot_titles=("Nombre de passages", "Vitesse moyenne (km/h)"),
            vertical_spacing=0.12,
        )
        fig.add_trace(
            go.Bar(x=hourly["heure"], y=hourly["passages"],
                   marker_color="#4c9be8", name="Passages"),
            row=1, col=1
        )
        fig.add_trace(
            go.Scatter(x=hourly["heure"], y=hourly["vitesse_moy"],
                       mode="lines+markers", line_color="#e84c4c",
                       name="Vitesse moy."),
            row=2, col=1
        )
        fig.add_hline(y=limit, line_dash="dash", line_color="orange",
                      annotation_text=f"{limit} km/h", row=2, col=1)
        fig.update_layout(height=550, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

        # Heatmap heure × jour semaine
        st.subheader("Carte de chaleur : heure × jour de la semaine")
        df_f["heure_h"] = df_f["heure_min"] // 60
        pivot = df_f.groupby(["jour_semaine", "heure_h"]).size().unstack(fill_value=0)
        pivot.index = [DAYS_FR[i] for i in pivot.index]

        fig_heat = px.imshow(
            pivot,
            labels={"x": "Heure", "y": "Jour", "color": "Passages"},
            color_continuous_scale="Blues",
            aspect="auto",
        )
        fig_heat.update_layout(height=320)
        st.plotly_chart(fig_heat, use_container_width=True)
    else:
        st.info("Aucune donnée avec les filtres actuels.")


# ============================================================================
# Tab 3 : Tendances
# ============================================================================
elif active_tab == TAB_NAMES[2]:
    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("Passages journaliers")
        if not df_f.empty:
            daily = df_f.groupby("date").agg(
                passages=("vitesse", "count"),
                vitesse_moy=("vitesse", "mean"),
            ).reset_index()
            fig = px.bar(
                daily, x="date", y="passages",
                labels={"date": "Date", "passages": "Passages / jour"},
                color="vitesse_moy",
                color_continuous_scale="RdYlGn_r",
                color_continuous_midpoint=limit + 5,
            )
            fig.update_layout(height=350, coloraxis_colorbar_title="Vit. moy.")
            st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.subheader("Passages par jour de la semaine")
        if not df_f.empty:
            dow = df_f.groupby("jour_semaine").agg(
                total=("vitesse", "count"),
                vitesse_moy=("vitesse", "mean"),
            ).reset_index()
            dow["jour"] = dow["jour_semaine"].map(DAYS_FR)
            dow = dow.sort_values("jour_semaine")
            fig = px.bar(
                dow, x="jour", y="total",
                color="vitesse_moy",
                color_continuous_scale="RdYlGn_r",
                labels={"jour": "Jour", "total": "Total passages"},
            )
            fig.update_layout(height=350, coloraxis_colorbar_title="Vit. moy.")
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("Évolution mensuelle")
    if not df_f.empty:
        monthly = df_f.groupby(["annee", "mois"]).agg(
            passages=("vitesse", "count"),
            vitesse_moy=("vitesse", "mean"),
            vitesse_max=("vitesse", "max"),
        ).reset_index()
        monthly["periode"] = monthly.apply(
            lambda r: f"{MONTHS_FR[int(r['mois'])]} {int(r['annee'])}", axis=1
        )

        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            subplot_titles=("Passages / mois", "Vitesse moyenne (km/h)"),
            vertical_spacing=0.1
        )
        fig.add_trace(
            go.Bar(x=monthly["periode"], y=monthly["passages"],
                   marker_color="#4c9be8", name="Passages"),
            row=1, col=1
        )
        fig.add_trace(
            go.Scatter(x=monthly["periode"], y=monthly["vitesse_moy"],
                       mode="lines+markers", line_color="#e84c4c",
                       name="Vit. moy."),
            row=2, col=1
        )
        fig.add_trace(
            go.Scatter(x=monthly["periode"], y=monthly["vitesse_max"],
                       mode="lines", line=dict(color="orange", dash="dot"),
                       name="Vit. max"),
            row=2, col=1
        )
        fig.add_hline(y=limit, line_dash="dash", line_color="red",
                      annotation_text=f"Limite {limit}", row=2, col=1)
        fig.update_layout(height=560, showlegend=True)
        st.plotly_chart(fig, use_container_width=True)


# ============================================================================
# Tab 4 : Calendrier
# ============================================================================
elif active_tab == TAB_NAMES[3]:

    # ── Heatmap passages totaux / jour ────────────────────────────────────────
    st.subheader("Carte de chaleur — passages totaux par jour")
    if not df_f.empty:
        daily_c = df_f.groupby("date").size().reset_index(name="passages")
        daily_c["semaine"] = daily_c["date"].dt.isocalendar().week.astype(int)
        daily_c["jour"] = daily_c["date"].dt.dayofweek
        daily_c["annee"] = daily_c["date"].dt.year

        for year in sorted(daily_c["annee"].unique()):
            yr_data = daily_c[daily_c["annee"] == year]
            pivot = yr_data.pivot(index="jour", columns="semaine", values="passages")
            pivot.index = [DAYS_FR[i] for i in pivot.index]
            fig = px.imshow(
                pivot,
                labels={"x": "Semaine", "y": "Jour", "color": "Passages"},
                color_continuous_scale="Blues",
                title=f"Année {year}",
                aspect="auto",
            )
            fig.update_layout(height=280, margin=dict(t=40))
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Aucune donnée avec les filtres actuels.")

    st.markdown("---")

    # ── Matrice dynamique par seuil de vitesse ────────────────────────────────
    st.subheader("🎯 Matrice de dépassements par seuil de vitesse")
    st.caption("Chaque cellule = 1 jour. Couleur = nombre de passages dépassant le seuil. "
               "Données complètes (indépendant des filtres sidebar).")

    if not df.empty:
        v_min_all = int(df["vitesse"].min())
        v_max_all = int(df["vitesse"].max())
        rk_safe = active_key.replace(" ", "_").replace("[", "").replace("]", "")
        threshold = st.slider(
            "Seuil de vitesse (km/h)",
            min_value=v_min_all, max_value=v_max_all,
            value=min(limit + 10, v_max_all),
            step=1, key=f"cal_threshold_{rk_safe}",
        )

        # Agrégation par jour
        df_above = df[df["vitesse"] >= threshold]
        daily_exc = df_above.groupby("date").agg(
            n=("vitesse", "count"),
            vmax=("vitesse", "max"),
        ).reset_index()

        c1, c2, c3 = st.columns(3)
        c1.metric("Jours avec dépassements", len(daily_exc))
        c2.metric("Sur jours mesurés", df["date"].nunique())
        c3.metric("Vitesse max", f"{int(daily_exc['vmax'].max()) if not daily_exc.empty else '—'} km/h")

        if daily_exc.empty:
            st.info(f"Aucun passage ≥ {threshold} km/h dans les données.")
        else:
            daily_exc["date_str"]  = daily_exc["date"].dt.strftime("%d/%m/%Y")
            daily_exc["jour_sem"]  = daily_exc["date"].dt.dayofweek
            daily_exc["semaine"]   = daily_exc["date"].dt.isocalendar().week.astype(int)
            daily_exc["mois"]      = daily_exc["date"].dt.month
            daily_exc["jour_mois"] = daily_exc["date"].dt.day
            daily_exc["annee"]     = daily_exc["date"].dt.year

            GH_SCALE = [
                [0.0,   "#ebedf0"],
                [0.001, "#c6e48b"],
                [0.25,  "#7bc96f"],
                [0.60,  "#239a3b"],
                [1.0,   "#196127"],
            ]

            full_range = pd.date_range(df["date"].min(), df["date"].max(), freq="D")
            all_days = pd.DataFrame({
                "date":     full_range,
                "jour_sem": full_range.dayofweek,
                "semaine":  full_range.isocalendar().week.astype(int),
                "annee":    full_range.year,
                "mois":     full_range.month,
                "date_str": full_range.strftime("%d/%m/%Y"),
            })
            measured_dates = set(df["date"].dt.normalize().unique())
            all_days["in_data"] = all_days["date"].isin(measured_dates)
            all_days = all_days.merge(
                daily_exc[["date", "n", "vmax"]], on="date", how="left"
            )
            all_days["n"]    = all_days["n"].fillna(0).astype(int)
            all_days["vmax"] = all_days["vmax"].fillna(0).astype(int)

            # ── Vue 1 : Style GitHub ──────────────────────────────────────────
            st.markdown("#### 📅 Vue 1 — Style GitHub : semaines × jours de semaine")

            zmax_global = max(1, int(daily_exc["n"].max()))

            for year in sorted(all_days["annee"].unique()):
                yr = all_days[all_days["annee"] == year]
                weeks    = sorted(yr["semaine"].unique())
                week_idx = {w: i for i, w in enumerate(weeks)}
                n_weeks  = len(weeks)

                Z     = [[float("nan")] * n_weeks for _ in range(7)]
                Hover = [[""]           * n_weeks for _ in range(7)]

                for _, row in yr.iterrows():
                    dow = int(row["jour_sem"])
                    wi  = week_idx[int(row["semaine"])]
                    if row["in_data"]:
                        Z[dow][wi] = int(row["n"])
                        txt = f"{row['date_str']}<br>{int(row['n'])} passage(s) ≥ {threshold} km/h"
                        if row["n"] > 0:
                            txt += f"<br>Vit. max : {int(row['vmax'])} km/h"
                        Hover[dow][wi] = txt

                seen, month_annots = set(), []
                for _, row in yr.sort_values("date").iterrows():
                    m = int(row["mois"])
                    if m not in seen:
                        seen.add(m)
                        month_annots.append({
                            "x": week_idx[int(row["semaine"])],
                            "text": MONTHS_FR[m],
                        })

                fig_gh = go.Figure(go.Heatmap(
                    z=Z,
                    x=list(range(n_weeks)),
                    y=[DAYS_FR[i] for i in range(7)],
                    text=Hover,
                    hovertemplate="%{text}<extra></extra>",
                    colorscale=GH_SCALE,
                    showscale=True,
                    colorbar=dict(title="Passages", thickness=12),
                    zmin=0,
                    zmax=zmax_global,
                ))
                fig_gh.update_layout(
                    title=f"Année {year} — dépassements ≥ {threshold} km/h",
                    height=230,
                    margin=dict(t=55, b=10, l=70, r=20),
                    annotations=[
                        dict(x=a["x"], y=7.2, text=a["text"],
                             showarrow=False, font=dict(size=10), xanchor="left")
                        for a in month_annots
                    ],
                    xaxis=dict(showticklabels=False, title="", showgrid=False),
                    yaxis=dict(title="", autorange="reversed"),
                )
                st.plotly_chart(fig_gh, use_container_width=True)

            # ── Vue 2 : Grille mois × jour du mois ───────────────────────────
            st.markdown("#### 📆 Vue 2 — Grille mois × jour du mois")

            all_days["jour_mois"] = all_days["date"].dt.day
            all_days["mois_label"] = (
                all_days["annee"].astype(str) + " " + all_days["mois"].map(MONTHS_FR)
            )
            month_order = (
                all_days.drop_duplicates("mois_label")
                .sort_values("date")["mois_label"].tolist()
            )

            piv_val = (
                all_days[all_days["in_data"]]
                .pivot_table(index="mois_label", columns="jour_mois",
                             values="n", aggfunc="sum")
                .reindex(index=month_order, columns=range(1, 32))
            )

            hover_dict = {}
            for _, row in all_days[all_days["in_data"]].iterrows():
                key_h = (row["mois_label"], int(row["jour_mois"]))
                txt = f"{row['date_str']}<br>{int(row['n'])} passage(s) ≥ {threshold} km/h"
                if row["n"] > 0:
                    txt += f"<br>Vit. max : {int(row['vmax'])} km/h"
                hover_dict[key_h] = txt

            hover2 = [
                [hover_dict.get((ml, d), "") for d in range(1, 32)]
                for ml in month_order
            ]

            fig_g2 = go.Figure(go.Heatmap(
                z=piv_val.values.astype(float),
                x=[str(d) for d in range(1, 32)],
                y=month_order,
                text=hover2,
                hovertemplate="%{text}<extra></extra>",
                colorscale=GH_SCALE,
                showscale=True,
                colorbar=dict(title="Passages", thickness=12),
                zmin=0,
                zmax=zmax_global,
            ))
            n_months = len(month_order)
            fig_g2.update_layout(
                title=f"Dépassements ≥ {threshold} km/h — mois × jour du mois",
                height=max(420, n_months * 26 + 120),
                margin=dict(t=60, b=50, l=100, r=20),
                xaxis=dict(title="Jour du mois", tickmode="linear",
                           dtick=1, tickfont=dict(size=10)),
                yaxis=dict(title=""),
            )
            st.plotly_chart(fig_g2, use_container_width=True)


# ============================================================================
# Tab 5 : Données brutes
# ============================================================================
elif active_tab == TAB_NAMES[4]:
    st.subheader("Données brutes")

    if not df_f.empty:
        display_df = df_f[["date", "heure", "vitesse", "limite", "exces"]].copy()
        display_df["date"] = display_df["date"].dt.strftime("%d/%m/%Y")
        display_df.columns = ["Date", "Heure (tranche)", "Vitesse (km/h)", "Limite (km/h)", "Excès (km/h)"]

        st.dataframe(
            display_df.sort_values("Date"),
            use_container_width=True,
            hide_index=True,
            height=500,
        )

        csv = display_df.to_csv(index=False, sep=";").encode("utf-8-sig")
        st.download_button(
            "⬇️ Télécharger en CSV",
            data=csv,
            file_name=f"radar_{meta['commune']}_{meta['device_id']}.csv",
            mime="text/csv",
        )
    else:
        st.info("Aucune donnée avec les filtres actuels.")


# ============================================================================
# Tab 6 : Admin
# ============================================================================
elif active_tab == TAB_NAMES[5]:
    st.subheader("🔐 Zone Administration")

    # ── Authentification ──────────────────────────────────────────────────────
    if not st.session_state.get("admin_auth", False):
        st.markdown(
            "Cette zone est réservée à l'administrateur. "
            "Entrez le mot de passe pour accéder aux statistiques d'utilisation."
        )
        col_pwd, col_btn, _ = st.columns([2, 1, 3])
        with col_pwd:
            pwd_input = st.text_input("Mot de passe", type="password",
                                      key="admin_pwd_input", label_visibility="collapsed",
                                      placeholder="Mot de passe…")
        with col_btn:
            if st.button("🔓 Connexion", use_container_width=True):
                if pwd_input == ADMIN_PASSWORD:
                    st.session_state.admin_auth = True
                    st.rerun()
                else:
                    st.error("Mot de passe incorrect.")
    else:
        # ── Dashboard statistiques ────────────────────────────────────────────
        col_logout, _ = st.columns([1, 5])
        with col_logout:
            if st.button("🔒 Déconnexion"):
                st.session_state.admin_auth = False
                st.rerun()

        st.markdown("---")
        stats = load_stats()
        daily = stats.get("daily", {})

        # KPIs globaux
        today_str    = datetime.date.today().isoformat()
        week_ago     = (datetime.date.today() - datetime.timedelta(days=6)).isoformat()
        month_ago    = (datetime.date.today() - datetime.timedelta(days=29)).isoformat()

        total        = stats.get("total", 0)
        visits_today = daily.get(today_str, 0)
        visits_week  = sum(v for k, v in daily.items() if k >= week_ago)
        visits_month = sum(v for k, v in daily.items() if k >= month_ago)
        first_visit  = stats.get("first_visit", "—")

        ka, kb, kc, kd = st.columns(4)
        ka.metric("🌐 Sessions totales",  f"{total:,}")
        kb.metric("📅 Aujourd'hui",        f"{visits_today:,}")
        kc.metric("📆 7 derniers jours",   f"{visits_week:,}")
        kd.metric("🗓️ 30 derniers jours",  f"{visits_month:,}")

        st.caption(f"Première visite enregistrée : **{first_visit}**")
        st.markdown("---")

        # Graphique : sessions par jour (30 derniers jours)
        st.subheader("📈 Sessions par jour — 30 derniers jours")
        if daily:
            all_dates = pd.date_range(
                start=(datetime.date.today() - datetime.timedelta(days=29)).isoformat(),
                end=today_str,
                freq="D",
            )
            df_stats = pd.DataFrame({
                "date":     all_dates,
                "sessions": [daily.get(d.date().isoformat(), 0) for d in all_dates],
            })
            fig_admin = px.bar(
                df_stats, x="date", y="sessions",
                labels={"date": "Date", "sessions": "Sessions"},
                color="sessions",
                color_continuous_scale="Blues",
            )
            fig_admin.update_layout(
                height=320,
                coloraxis_showscale=False,
                margin=dict(t=10, b=10),
            )
            st.plotly_chart(fig_admin, use_container_width=True)
        else:
            st.info("Aucune donnée de visite enregistrée pour le moment.")

        # Tableau journalier détaillé
        st.subheader("📋 Détail journalier")
        if daily:
            df_detail = (
                pd.DataFrame(list(daily.items()), columns=["Date", "Sessions"])
                .sort_values("Date", ascending=False)
                .reset_index(drop=True)
            )
            df_detail.index += 1
            st.dataframe(df_detail, use_container_width=True, height=300)

            # Export CSV
            csv_admin = df_detail.to_csv(index=False, sep=";").encode("utf-8-sig")
            st.download_button(
                "⬇️ Exporter en CSV",
                data=csv_admin,
                file_name="radar_stats_visites.csv",
                mime="text/csv",
            )

        st.markdown("---")

        # Infos version
        st.subheader("🔖 Version déployée")
        try:
            import subprocess
            git_hash = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=Path(__file__).parent,
                stderr=subprocess.DEVNULL,
            ).decode().strip()
        except Exception:
            git_hash = "—"
        col_v1, col_v2, col_v3 = st.columns(3)
        col_v1.metric("Version", f"v{VERSION}")
        col_v2.metric("Date", VERSION_DATE)
        col_v3.metric("Commit Git", git_hash)

        st.caption(
            "ℹ️ Les statistiques sont stockées localement sur le serveur. "
            "Elles se réinitialisent lors d'un redéploiement sur Streamlit Community Cloud."
        )


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown(
    f"<small>📡 Radar : `{meta['device_id']}` | "
    f"Firmware : `{meta['firmware']}` | "
    f"OS : `{meta['os']}`</small>",
    unsafe_allow_html=True
)
st.markdown(
    "<small>⚠️ Note : ce radar enregistre uniquement les véhicules "
    f"dépassant {limit} km/h. Les passages en-dessous de ce seuil ne sont pas comptabilisés.</small>",
    unsafe_allow_html=True
)
st.markdown(
    f"<small style='color:#bbb'>🔖 Version {VERSION} — {VERSION_DATE}</small>",
    unsafe_allow_html=True
)
