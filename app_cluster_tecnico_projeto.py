import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px


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

# carregar os dados


@st.cache_data
def carregar_dados():

    df = pd.read_csv(
        "cluster_marcelina_limpo.csv",
        sep=";",
        encoding="utf-8-sig"
    )

    # Padronizar nomes das colunas
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

    # ---------------- IDENTIFICAR N/D ---------------- #

    mask_nd = df["AREA_TECNICA"].isna()

    df_nd = df[mask_nd].copy()
    df_valid = df[~mask_nd].copy()

    # Padronizar apenas válidos
    df_valid["AREA_TECNICA"] = (
        df_valid["AREA_TECNICA"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    # ---------------- MATRIZ (somente válidos) ---------------- #

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

    return df, df_valid, df_nd, matriz, matriz_pct


df, df_valid, df_nd, matriz, matriz_pct = carregar_dados()

# Separar áreas que estão em mais de um cluster

max_por_area = matriz_pct.max(axis=1)

matriz_nao_100 = matriz_pct[max_por_area < 100]
matriz_100 = matriz_pct[max_por_area == 100]

total_registros = len(df)
total_nd = len(df_nd)
percentual_nd = round(100 * total_nd / total_registros, 2)

# ---------------- MÉTRICAS ---------------- #

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
    "Áreas 100%",
    "Análise por Cluster",
    "NODES Não Encontrados"
])

# ---------------- ABA 1 - HEATMAP ---------------- #

with tab1:

    st.markdown("### Heatmap")

    import plotly.express as px

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
        plot_bgcolor="white",
        font=dict(size=14),
        xaxis_title="Cluster Projeto SP",
        yaxis_title="Área Técnica",
        xaxis=dict(tickfont=dict(size=13)),
        yaxis=dict(tickfont=dict(size=13)),
        coloraxis_colorbar=dict(
            title="%",
            tickfont=dict(size=12),
            title_font=dict(size=13)
        )
    )

    fig.update_traces(
        textfont=dict(size=13),
        hovertemplate="Cluster: %{x}<br>Área: %{y}<br>%: %{z:.1f}<extra></extra>"
    )

    st.plotly_chart(fig, use_container_width=True)


# ---------------- ABA 2 - ÁREAS 100% ---------------- #

with tab2:

    st.markdown("### Áreas 100% Concentradas")

    areas_100_long = (
        matriz_100
        .stack()
        .reset_index()
    )

    areas_100_long.columns = ["AREA_TECNICA",
                              "CLUSTER_GEOGRAFICO", "PERCENTUAL"]
    areas_100_long = areas_100_long[areas_100_long["PERCENTUAL"] == 100]

    hp_total_area = matriz.sum(axis=1)
    areas_100_long["HP_TOTAL"] = areas_100_long["AREA_TECNICA"].map(
        hp_total_area)

    areas_100_long = areas_100_long[
        ["CLUSTER_GEOGRAFICO", "AREA_TECNICA", "HP_TOTAL"]
    ].sort_values(
        ["CLUSTER_GEOGRAFICO", "HP_TOTAL"],
        ascending=[True, False]
    )

    st.dataframe(
        areas_100_long.reset_index(drop=True),
        use_container_width=True
    )


# ---------------- ABA 3 - ANÁLISE POR CLUSTER ---------------- #

with tab3:

    st.markdown("### Distribuição por Cluster")

    clusters_selecionados = st.multiselect(
        "Selecione os Clusters",
        matriz_pct.columns,
        default=matriz_pct.columns.tolist()
    )

    if "area_selecionada" not in st.session_state:
        st.session_state.area_selecionada = None

    cols_per_row = 3
    clusters_lista = clusters_selecionados

    for row_start in range(0, len(clusters_lista), cols_per_row):

        row_clusters = clusters_lista[row_start:row_start + cols_per_row]
        cols = st.columns(cols_per_row)

        for col, cluster in zip(cols, row_clusters):

            data_cluster = matriz_nao_100[cluster]
            data_cluster = data_cluster[data_cluster > 0].sort_index()

            df_plot = data_cluster.reset_index()
            df_plot.columns = ["AREA_TECNICA", "PERCENTUAL"]

            df_plot["COR"] = df_plot["AREA_TECNICA"].apply(
                lambda x: "Selecionada"
                if x == st.session_state.area_selecionada
                else "Normal"
            )

            fig = px.bar(
                df_plot,
                x="AREA_TECNICA",
                y="PERCENTUAL",
                color="COR",
                text="PERCENTUAL",
                color_discrete_map={
                    "Selecionada": "#E4C767",
                    "Normal": "#DA2319"
                },
                title=cluster,
                template="plotly_white"
            )

            fig.update_layout(
                height=360,
                template="plotly_white",
                xaxis_title="Área Técnica",
                yaxis_title=None,
                yaxis=dict(range=[0, 100]),
                xaxis_tickangle=-60,
                margin=dict(l=30, r=10, t=40, b=60),
                showlegend=False
            )

            fig.update_traces(
                texttemplate='%{text:.1f}%',
                textposition='outside',
                textfont_size=10
            )

            selected = col.plotly_chart(
                fig,
                use_container_width=True,
                on_select="rerun"
            )

            if selected and selected.get("points"):
                area = selected["points"][0]["x"]
                st.session_state.area_selecionada = area

    if st.session_state.area_selecionada:
        st.info(f"Área selecionada: {st.session_state.area_selecionada}")
        if st.button("Limpar seleção"):
            st.session_state.area_selecionada = None

# ---------------- ABA 4 - IMPACTO N/D ---------------- #

with tab4:

    st.markdown("### Análise dos Registros sem Área Técnica")

    # ---------------- KPI ---------------- #

    total_registros = len(df)
    total_nd = len(df_nd)
    percentual_nd = round(100 * total_nd / total_registros, 2)

    col1, col2 = st.columns(2)
    col1.metric("Total Registros N/D", f"{total_nd:,}")
    col2.metric("Percentual sobre Base", f"{percentual_nd}%")

    # ---------------- PREPARAÇÃO DOS DADOS ---------------- #

    # Quantidade de registros N/D por cluster
    nd_por_cluster = (
        df_nd
        .groupby("CLUSTER_GEOGRAFICO")
        .size()
    )

    # Total de registros por cluster
    total_por_cluster = (
        df
        .groupby("CLUSTER_GEOGRAFICO")
        .size()
    )

    # Percentual dentro de cada cluster
    impacto_cluster_pct = (
        100 * nd_por_cluster / total_por_cluster
    ).fillna(0).round(2).sort_values(ascending=False)

    # ---------------- GRÁFICO (PERCENTUAL) ---------------- #

    import plotly.express as px

    st.markdown("### Percentual de Registros sem Área Técnica por Cluster")

    df_plot = impacto_cluster_pct.reset_index()
    df_plot.columns = ["CLUSTER_GEOGRAFICO", "PERCENTUAL"]

    fig_nd = px.bar(
        df_plot,
        x="CLUSTER_GEOGRAFICO",
        y="PERCENTUAL",
        text="PERCENTUAL"
    )

    fig_nd.update_traces(
        marker_color="#DA2319",
        texttemplate='%{text:.1f}%',
        textposition='outside'
    )

    fig_nd.update_layout(
        height=320,
        template="plotly_white",
        xaxis_title="Cluster",
        yaxis_title=None,
        yaxis=dict(range=[0, 100]),
        xaxis_tickangle=-45,
        showlegend=False
    )

    st.plotly_chart(fig_nd, use_container_width=True)

    # ---------------- TABELA (VALORES ABSOLUTOS) ---------------- #

    st.markdown(
        "### Quantidade Absoluta de NODES sem Correspondência da Área Técnica")

    tabela_abs = (
        nd_por_cluster
        .sort_values(ascending=False)
        .reset_index()
        .rename(columns={
            "CLUSTER_GEOGRAFICO": "Cluster",
            0: "Qtd Registros N/D"
        })
    )

    st.dataframe(
        tabela_abs,
        use_container_width=True
    )


