import streamlit as st
import pandas as pd
import plotly.express as px
import unicodedata

# ---------------------------------------------------
# CONFIGURAÇÃO STREAMLIT
# ---------------------------------------------------

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

# ---------------------------------------------------
# FUNÇÕES AUXILIARES
# ---------------------------------------------------

def normalize_ascii(x):
    if pd.isna(x):
        return ""
    x = unicodedata.normalize("NFD", str(x))
    x = "".join(ch for ch in x if unicodedata.category(ch) != "Mn")
    return x.upper().strip()


def cluster_sp_area(row):

    cg = str(row.get("CLUSTER_GEOGRAFICO", "")).strip().upper()

    if cg == "SP":

        area = str(row.get("AREA", "")).strip().upper()

        if area == "" or area == "#N/D":
            return "SP (N/D)"

        if "AREA 1" in area:
            return "SP (AREA 1)"

        elif "AREA 2" in area:
            return "SP (AREA 2)"

        elif "AREA 3" in area:
            return "SP (AREA 3)"

        else:
            return "SP (OUTRA)"

    return cg


# ---------------------------------------------------
# CARREGAR BASE
# ---------------------------------------------------

@st.cache_data
def carregar_dados():

    df = pd.read_csv(
        "clusterizacao_streamlit.csv",
        sep=";",
        encoding="utf-8-sig"
    )

    df.columns = (
        df.columns
        .str.strip()
        .str.upper()
        .str.replace(" ", "_")
    )

    df["CLUSTER_GEOGRAFICO"] = (
        df["CLUSTER_GEOGRAFICO"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    df["HP_TECNICA"] = (
        pd.to_numeric(df["HP_TECNICA"], errors="coerce")
        .fillna(0)
        .astype(int)
    )

    df["CLUSTER_ANALITICO"] = df.apply(cluster_sp_area, axis=1)

    matriz = df.pivot_table(
        index="AREA_TECNICA",
        columns="CLUSTER_GEOGRAFICO",
        values="HP_TECNICA",
        aggfunc="sum",
        fill_value=0
    )

    matriz_pct = (
        matriz.div(matriz.sum(axis=1), axis=0) * 100
    ).fillna(0).round(1)

    # Área 14

    df_area14 = df[
        (df["AREA_TECNICA"] == "AREA 14") &
        (df["CLUSTER_ANALITICO"].isin(["SP (AREA 1)", "SP (AREA 2)"]))
    ]

    tabela_bairros = (
        df_area14
        .groupby(["CLUSTER_ANALITICO", "CIDADE_SUB_CLUSTER"])
        .agg(
            HP_TOTAL=("HP_TECNICA", "sum"),
            PC_CLASSE_AB1=("PC_CLASSE_AB1", "mean")
        )
        .reset_index()
        .sort_values(
            ["CLUSTER_ANALITICO", "HP_TOTAL"],
            ascending=[True, False]
        )
    )

    return df, matriz, matriz_pct, tabela_bairros


df, matriz, matriz_pct, tabela_bairros = carregar_dados()

# ---------------------------------------------------
# MÉTRICAS
# ---------------------------------------------------

max_por_area = matriz_pct.max(axis=1)

matriz_nao_100 = matriz_pct[max_por_area < 100]
matriz_100 = matriz_pct[max_por_area == 100]

st.markdown("### Resumo Executivo")

col1, col2, col3 = st.columns(3)

col1.metric("Total de Áreas", len(matriz_pct))
col2.metric("Áreas 100% Concentradas", len(matriz_100))
col3.metric("Áreas com Distribuição", len(matriz_nao_100))

# ---------------------------------------------------
# ABAS
# ---------------------------------------------------

tab1, tab2, tab3, tab4 = st.tabs([
    "Heatmap",
    "Heatmap (Cluster SP)",
    "Áreas 100% em um Cluster",
    "Análise por Cluster"
])

# ---------------------------------------------------
# HEATMAP GERAL
# ---------------------------------------------------

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

    fig.update_layout(height=440)

    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------
# HEATMAP SP
# ---------------------------------------------------

with tab2:

    st.markdown("### Heatmap Cluster SP")

    df_aux = df.copy()

    matriz_geo = df_aux.pivot_table(
        index="AREA_TECNICA",
        columns="CLUSTER_GEOGRAFICO",
        values="HP_TECNICA",
        aggfunc="sum",
        fill_value=0
    )

    matriz_geo_pct = (
        matriz_geo.div(matriz_geo.sum(axis=1), axis=0) * 100
    ).fillna(0)

    if "SP" not in matriz_geo_pct.columns:
        st.error("Cluster SP não encontrado na base.")
        st.stop()

    areas_nao_integrais_em_SP = matriz_geo_pct.index[
        (matriz_geo_pct["SP"] > 0) &
        (matriz_geo_pct["SP"] < 100)
    ]

    if len(areas_nao_integrais_em_SP) == 0:
        st.warning("Nenhuma área possui distribuição parcial em SP.")
        st.stop()

    df_sp = df_aux.loc[
        df_aux["AREA_TECNICA"].isin(areas_nao_integrais_em_SP) &
        (df_aux["CLUSTER_GEOGRAFICO"] == "SP")
    ].copy()

    matriz_sp_analitico = df_sp.pivot_table(
        index="AREA_TECNICA",
        columns="CLUSTER_ANALITICO",
        values="HP_TECNICA",
        aggfunc="sum",
        fill_value=0
    )

    matriz_sp_analitico_pct = (
        matriz_sp_analitico.div(
            matriz_sp_analitico.sum(axis=1),
            axis=0
        ) * 100
    ).fillna(0).round(1)

    df_heat_sp = (
        matriz_sp_analitico_pct
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

    st.markdown("### Subclusters da Área 14 e % de Classe AB1")

    if tabela_bairros.empty:

        st.warning("Nenhum registro encontrado para Área 14.")

    else:

        tabela_view = tabela_bairros.copy()

        tabela_view["PC_CLASSE_AB1"] = (
            tabela_view["PC_CLASSE_AB1"] * 100
        ).round(1).astype(str) + "%"

        tabela_view = tabela_view.rename(columns={
            "CLUSTER_ANALITICO": "CLUSTER",
            "CIDADE_SUB_CLUSTER": "SUBCLUSTER",
            "HP_TOTAL": "HP",
            "PC_CLASSE_AB1": "% CLASSE AB1"
        })

        st.dataframe(
            tabela_view,
            use_container_width=True
        )

# ---------------------------------------------------
# ÁREAS 100%
# ---------------------------------------------------

with tab3:

    st.markdown("### Áreas 100% Concentradas")

    areas_100_long = (
        matriz_100
        .stack()
        .reset_index()
    )

    areas_100_long.columns = [
        "AREA_TECNICA",
        "CLUSTER_GEOGRAFICO",
        "PERCENTUAL"
    ]

    areas_100_long = areas_100_long[
        areas_100_long["PERCENTUAL"] == 100
    ]

    hp_total_area = matriz.sum(axis=1)

    areas_100_long["HP_TOTAL"] = areas_100_long["AREA_TECNICA"].map(
        hp_total_area
    )

    areas_100_long = areas_100_long[
        ["CLUSTER_GEOGRAFICO", "AREA_TECNICA", "HP_TOTAL"]
    ].sort_values(
        ["CLUSTER_GEOGRAFICO", "HP_TOTAL"],
        ascending=[True, False]
    )

    st.dataframe(
        areas_100_long,
        use_container_width=True
    )

# ---------------------------------------------------
# ANÁLISE POR CLUSTER
# ---------------------------------------------------

with tab4:

    st.markdown("### Distribuição por Cluster")

    clusters_selecionados = st.multiselect(
        "Selecione os Clusters",
        matriz_pct.columns,
        default=matriz_pct.columns.tolist()
    )

    cols_per_row = 3

    for row_start in range(0, len(clusters_selecionados), cols_per_row):

        row_clusters = clusters_selecionados[row_start:row_start + cols_per_row]
        cols = st.columns(cols_per_row)

        for col, cluster in zip(cols, row_clusters):

            data_cluster = matriz_nao_100[cluster]
            data_cluster = data_cluster[data_cluster > 0].sort_index()

            df_plot = data_cluster.reset_index()
            df_plot.columns = ["AREA_TECNICA", "PERCENTUAL"]

            fig = px.bar(
                df_plot,
                x="AREA_TECNICA",
                y="PERCENTUAL",
                text="PERCENTUAL",
                color_discrete_sequence=["#DA2319"],
                title=cluster
            )

            fig.update_traces(
                texttemplate='%{text:.1f}%',
                textposition='outside'
            )

            fig.update_layout(
                height=360,
                template="plotly_white",
                yaxis=dict(range=[0, 100]),
                xaxis_tickangle=-60,
                showlegend=False
            )

            col.plotly_chart(fig, use_container_width=True)
