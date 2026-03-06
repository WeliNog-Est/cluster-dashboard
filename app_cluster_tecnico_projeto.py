import streamlit as st
import pandas as pd
import plotly.express as px

# -----------------------------------------
# CONFIGURAÇÃO
# -----------------------------------------

st.set_page_config(
    layout="wide",
    page_title="Cluster Dashboard"
)

st.markdown("### Análise de Concentração de Áreas por Cluster")


# -----------------------------------------
# FUNÇÕES
# -----------------------------------------

def cluster_sp_area(row):

    if row["CLUSTER_GEOGRAFICO"] == "SP":

        area = row["AREA"]

        if pd.isna(area) or area == "#N/D":
            return "SP (N/D)"

        elif "Área 1" in area:
            return "SP (AREA 1)"

        elif "Área 2" in area:
            return "SP (AREA 2)"

        elif "Área 3" in area:
            return "SP (AREA 3)"

        else:
            return "SP (OUTRA)"

    else:
        return row["CLUSTER_GEOGRAFICO"]


# -----------------------------------------
# CARREGAMENTO
# -----------------------------------------

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
        pd.to_numeric(df["HP_TECNICA"], errors="coerce")
        .fillna(0)
        .astype(int)
    )

    # ---------------- Bairros / AB1 ---------------- #

    df_cluster_ab1 = pd.read_csv(
        "cluster_pc_ab1.csv",
        sep=";",
        encoding="utf-8-sig"
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

    df = df.merge(
        df_lookup,
        on="CHAVE_NODE_IBGE",
        how="left"
    )

    # ---------------- N/D ---------------- #

    mask_nd = df["AREA_TECNICA"].isna()

    df_nd = df[mask_nd].copy()
    df_valid = df[~mask_nd].copy()

    df_valid["AREA_TECNICA"] = (
        df_valid["AREA_TECNICA"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    # ---------------- CLUSTER ANALITICO ---------------- #

    df_valid["CLUSTER_ANALITICO"] = df_valid.apply(cluster_sp_area, axis=1)

    # ---------------- MATRIZ ---------------- #

    matriz = df_valid.pivot_table(
        index="AREA_TECNICA",
        columns="CLUSTER_GEOGRAFICO",
        values="HP_TECNICA",
        aggfunc="sum",
        fill_value=0
    )

    matriz_pct = matriz.div(matriz.sum(axis=1), axis=0) * 100
    matriz_pct = matriz_pct.fillna(0).round(1)

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


# -----------------------------------------
# MÉTRICAS
# -----------------------------------------

max_por_area = matriz_pct.max(axis=1)

matriz_nao_100 = matriz_pct[max_por_area < 100]
matriz_100 = matriz_pct[max_por_area == 100]

total_registros = len(df)
total_nd = len(df_nd)
percentual_nd = round(100 * total_nd / total_registros, 2)

st.markdown("### Resumo Executivo")

col1, col2, col3, col4 = st.columns(4)

col1.metric("Total de Áreas", len(matriz_pct))
col2.metric("Áreas 100% Concentradas", len(matriz_100))
col3.metric("Áreas com Distribuição", len(matriz_nao_100))
col4.metric("% NODES sem Área Técnica", f"{percentual_nd}%")


# -----------------------------------------
# ABAS
# -----------------------------------------

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Heatmap",
    "Áreas 100%",
    "Análise por Cluster",
    "NODES Não Encontrados",
    "Área 14 – Socioeconômico"
])


# -----------------------------------------
# HEATMAP
# -----------------------------------------

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
        text_auto=".1f",
        color_continuous_scale="YlOrRd"
    )

    fig.update_layout(height=500)

    st.plotly_chart(fig, use_container_width=True)


# -----------------------------------------
# ÁREAS 100%
# -----------------------------------------

with tab2:

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

    areas_100_long = areas_100_long.sort_values(
        ["CLUSTER_GEOGRAFICO", "HP_TOTAL"],
        ascending=[True, False]
    )

    st.dataframe(areas_100_long, use_container_width=True)


# -----------------------------------------
# ANALISE CLUSTER
# -----------------------------------------

with tab3:

    st.markdown("### Distribuição por Cluster")

    clusters = matriz_nao_100.columns

    for cluster in clusters:

        data = matriz_nao_100[cluster]
        data = data[data > 0].sort_index()

        df_plot = data.reset_index()
        df_plot.columns = ["AREA_TECNICA", "PERCENTUAL"]

        fig = px.bar(
            df_plot,
            x="AREA_TECNICA",
            y="PERCENTUAL",
            title=cluster,
            text="PERCENTUAL"
        )

        st.plotly_chart(fig, use_container_width=True)


# -----------------------------------------
# N/D
# -----------------------------------------

with tab4:

    st.markdown("### Impacto de NODES sem Área Técnica")

    nd_por_cluster = (
        df_nd
        .groupby("CLUSTER_GEOGRAFICO")
        .size()
    )

    total_por_cluster = (
        df
        .groupby("CLUSTER_GEOGRAFICO")
        .size()
    )

    impacto = (100 * nd_por_cluster / total_por_cluster).fillna(0)

    df_plot = impacto.reset_index()
    df_plot.columns = ["CLUSTER", "PERCENTUAL"]

    fig = px.bar(
        df_plot,
        x="CLUSTER",
        y="PERCENTUAL",
        text="PERCENTUAL"
    )

    st.plotly_chart(fig, use_container_width=True)


# -----------------------------------------
# ÁREA 14
# -----------------------------------------

with tab5:

    st.markdown("### Área 14 – Distribuição Socioeconômica")

    st.dataframe(tabela_bairros, use_container_width=True)

    st.markdown("### Gráfico de Bolhas – HP vs Classe AB1")

    fig = px.scatter(
        tabela_bairros,
        x="PC_CLASSE_AB1",
        y="HP_TOTAL",
        size="HP_TOTAL",
        color="CLUSTER_ANALITICO",
        hover_name="CIDADE_SUB_CLUSTER",
        title="HP vs Classe AB1 por Bairro (Área 14)"
    )

    st.plotly_chart(fig, use_container_width=True)
