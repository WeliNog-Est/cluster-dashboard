import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import unicodedata

# STREAMLIT
st.set_page_config(
    layout="wide",
    page_title="Cluster Dashboard"
)

st.markdown("""
    <style>
        :root {
            --background-color: #FFFFFF;
            --secondary-background-color: #F8F9FA;
            --text-color: #2B2B2B;
        }

        .stApp {
            background-color: #FFFFFF !important;
        }

        html, body {
            background-color: #FFFFFF !important;
            color: #2B2B2B !important;
        }
    </style>
""", unsafe_allow_html=True)

st.markdown("### Análise de Concentração de Áreas por Cluster")

# ---------------- FUNÇÕES AUXILIARES ---------------- #

def strip_upper(x: str) -> str:
    if pd.isna(x):
        return ""
    return str(x).strip().upper()


def normalize_ascii(x: str) -> str:
    if pd.isna(x):
        return ""
    x = str(x)
    x = unicodedata.normalize("NFD", x)
    x = "".join(ch for ch in x if unicodedata.category(ch) != "Mn")
    return x.upper().strip()


def cluster_sp_area(row):

    cg = strip_upper(row.get("CLUSTER_GEOGRAFICO", ""))

    if cg == "SP":

        area_raw = row.get("AREA_BASE", None)

        if pd.isna(area_raw) or str(area_raw).strip() == "" or str(area_raw).strip().upper() == "#N/D":
            return "SP (N/D)"

        area_norm = normalize_ascii(area_raw)

        if "AREA 1" in area_norm:
            return "SP (AREA 1)"
        elif "AREA 2" in area_norm:
            return "SP (AREA 2)"
        elif "AREA 3" in area_norm:
            return "SP (AREA 3)"
        else:
            return "SP (OUTRA)"

    else:
        return cg


# ---------------- CARREGAR DADOS ---------------- #

@st.cache_data
def carregar_dados():

    df = pd.read_csv(
        "cluster_marcelina_limpo.csv",
        sep=";",
        encoding="utf-8-sig"
    )

    df.columns = (
        df.columns
        .str.strip()
        .str.upper()
        .str.replace(" ", "_")
    )

    df["HP_TECNICA"] = (
        pd.to_numeric(df.get("HP_TECNICA", 0), errors="coerce")
        .fillna(0)
        .astype(int)
    )

    mask_nd = df["AREA_TECNICA"].isna()

    df_nd = df[mask_nd].copy()
    df_valid = df[~mask_nd].copy()

    df_valid["AREA_TECNICA"] = (
        df_valid["AREA_TECNICA"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    df_valid["AREA_BASE"] = df_valid["AREA"]

    df_valid["CLUSTER_ANALITICO"] = df_valid.apply(cluster_sp_area, axis=1)

    # MATRIZ
    matriz = df_valid.pivot_table(
        index="AREA_TECNICA",
        columns="CLUSTER_GEOGRAFICO",
        values="HP_TECNICA",
        aggfunc="sum",
        fill_value=0
    )

    matriz_pct = matriz.div(matriz.sum(axis=1), axis=0) * 100
    matriz_pct = matriz_pct.fillna(0)
    matriz_pct = matriz_pct.round(1)

    # ---------------- BASE BAIRROS ---------------- #

    df_cluster_ab1 = pd.read_excel(
        "cluster_pc_ab1.xlsx",
        sheet_name="cluster_ab1"
    )

    df_cluster_ab1["PC_CLASSE_AB1"] = (
        df_cluster_ab1["PC_CLASSE_AB1"]
        .astype(str)
        .str.replace("%", "", regex=False)
    )

    df_cluster_ab1["PC_CLASSE_AB1"] = (
        pd.to_numeric(df_cluster_ab1["PC_CLASSE_AB1"], errors="coerce") / 100
    )

    df_lookup = df_cluster_ab1[
        ["CHAVE_NODE_IBGE", "CIDADE_SUB_CLUSTER", "PC_CLASSE_AB1"]
    ].drop_duplicates()

    df_valid = df_valid.merge(
        df_lookup,
        on="CHAVE_NODE_IBGE",
        how="left"
    )

    # ---------------- AREA 14 ---------------- #

    df_area14 = df_valid[
        (df_valid["AREA_TECNICA"] == "AREA 14") &
        (df_valid["CLUSTER_ANALITICO"].isin(["SP (AREA 1)", "SP (AREA 2)"]))
    ]

    tabela_bairros = (
        df_area14
        .groupby(["CLUSTER_ANALITICO", "CIDADE_SUB_CLUSTER"])
        .agg(
            HP_TOTAL=("HP_TECNICA", "sum"),
            PC_CLASSE_AB1=("PC_CLASSE_AB1", "mean")
        )
        .reset_index()
    )

    tabela_bairros = tabela_bairros.sort_values(
        ["CLUSTER_ANALITICO", "HP_TOTAL"],
        ascending=[True, False]
    )

    return df, df_valid, df_nd, matriz, matriz_pct, tabela_bairros


df, df_valid, df_nd, matriz, matriz_pct, tabela_bairros = carregar_dados()

# ---------------- MÉTRICAS ---------------- #

max_por_area = matriz_pct.max(axis=1)

matriz_nao_100 = matriz_pct[max_por_area < 100]
matriz_100 = matriz_pct[max_por_area == 100]

total_registros = len(df)
total_nd = len(df_nd)
percentual_nd = round(100 * total_nd / total_registros, 2)

st.markdown("### Resumo Executivo")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total de Áreas", len(matriz_pct))

with col2:
    st.metric("Áreas 100% Concentradas", len(matriz_100))

with col3:
    st.metric("Áreas com Distribuição", len(matriz_nao_100))

with col4:
    col4.metric("% NODES sem Área Técnica", f"{percentual_nd}%")


# ---------------- ABAS ---------------- #

tab1, tab2, tab3, tab4 = st.tabs([
    "Heatmap",
    "Heatmap (Cluster SP)",
    "Áreas 100%",
    "Análise por Cluster"
])


# ---------------- ABA 1 ---------------- #

with tab1:

    st.markdown("### Heatmap")

    df_heat = matriz_nao_100.reset_index()

    df_heat_long = df_heat.melt(
        id_vars="AREA_TECNICA",
        var_name="CLUSTER_GEOGRAFICO",
        value_name="PERCENTUAL"
    )

    fig = px.density_heatmap(
        df_heat_long,
        x="CLUSTER_GEOGRAFICO",
        y="AREA_TECNICA",
        z="PERCENTUAL",
        color_continuous_scale="YlOrRd",
        text_auto=".1f",
        template="plotly_white"
    )

    fig.update_layout(
        height=440,
        paper_bgcolor="white",
        plot_bgcolor="white"
    )

    st.plotly_chart(fig, use_container_width=True)


# ---------------- ABA 2 ---------------- #

with tab2:

    st.markdown("### Heatmap Cluster SP")

    df_sp = df_valid[df_valid["CLUSTER_GEOGRAFICO"] == "SP"]

    matriz_sp = df_sp.pivot_table(
        index="AREA_TECNICA",
        columns="CLUSTER_ANALITICO",
        values="HP_TECNICA",
        aggfunc="sum",
        fill_value=0
    )

    matriz_sp_pct = (
        matriz_sp.div(matriz_sp.sum(axis=1), axis=0) * 100
    ).fillna(0).round(1)

    df_heat_sp = (
        matriz_sp_pct
        .reset_index()
        .melt(
            id_vars="AREA_TECNICA",
            var_name="CLUSTER_ANALITICO",
            value_name="PERCENTUAL"
        )
    )

    fig_sp = px.density_heatmap(
        df_heat_sp,
        x="CLUSTER_ANALITICO",
        y="AREA_TECNICA",
        z="PERCENTUAL",
        color_continuous_scale="YlOrRd",
        text_auto=".1f",
        template="plotly_white"
    )

    fig_sp.update_layout(height=500)

    st.plotly_chart(fig_sp, use_container_width=True)

    st.markdown("### Bairros da Área 14 divididos entre SP (AREA 1) e SP (AREA 2)")

    tabela_view = tabela_bairros.copy()

    tabela_view["PC_CLASSE_AB1"] = (
        tabela_view["PC_CLASSE_AB1"] * 100
    ).round(1).astype(str) + "%"

    st.dataframe(
        tabela_view,
        use_container_width=True
    )


# ---------------- ABA 3 ---------------- #

with tab3:

    st.markdown("### Áreas 100% Concentradas")

    areas_100_long = (
        matriz_100
        .stack()
        .reset_index()
    )

    areas_100_long.columns = ["AREA_TECNICA", "CLUSTER_GEOGRAFICO", "PERCENTUAL"]

    areas_100_long = areas_100_long[areas_100_long["PERCENTUAL"] == 100]

    hp_total_area = matriz.sum(axis=1)

    areas_100_long["HP_TOTAL"] = areas_100_long["AREA_TECNICA"].map(hp_total_area)

    areas_100_long = areas_100_long[
        ["CLUSTER_GEOGRAFICO", "AREA_TECNICA", "HP_TOTAL"]
    ]

    st.dataframe(
        areas_100_long,
        use_container_width=True
    )


# ---------------- ABA 4 ---------------- #

with tab4:

    st.markdown("### Distribuição por Cluster")

    for cluster in matriz_nao_100.columns:

        data_cluster = matriz_nao_100[cluster]
        data_cluster = data_cluster[data_cluster > 0].sort_index()

        df_plot = data_cluster.reset_index()
        df_plot.columns = ["AREA_TECNICA", "PERCENTUAL"]

        fig = px.bar(
            df_plot,
            x="AREA_TECNICA",
            y="PERCENTUAL",
            text="PERCENTUAL",
            title=cluster,
            template="plotly_white"
        )

        fig.update_layout(
            height=350,
            yaxis=dict(range=[0, 100])
        )

        st.plotly_chart(fig, use_container_width=True)
