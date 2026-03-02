import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns


# STREAMLIT

st.set_page_config(layout="centered")

st.markdown("### Análise de Concentração de Áreas por Cluster")

# carregar os dados


@st.cache_data
def carregar_dados():
    df = pd.read_excel(
        r"C:\Users\wnsos\Documents\cluster_marcelina.xlsx",
        sheet_name="cluster_marcelina"
    )

    df.columns = df.columns.str.strip().str.upper()

    df["HP_TECNICA"] = pd.to_numeric(df["HP_TECNICA"], errors="coerce")

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
    matriz_pct = matriz_pct.fillna(0).round(1)

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

st.markdown("## Resumo Executivo")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total de Áreas", len(matriz_pct))

with col2:
    st.metric("Áreas 100% Concentradas", len(matriz_100))

with col3:
    st.metric("Áreas com Distribuição", len(matriz_nao_100))

with col4:
    col4.metric("% Registros sem Área Técnica", f"{percentual_nd}%")


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

    fig, ax = plt.subplots(figsize=(4.5, 3.5))

    heatmap = sns.heatmap(
        matriz_nao_100,
        annot=True,
        fmt=".1f",
        cmap="YlOrRd",
        linewidths=0.2,
        cbar_kws={"label": "%"},
        ax=ax,
        annot_kws={"size": 5}
    )

    cbar = heatmap.collections[0].colorbar
    cbar.ax.tick_params(labelsize=4)
    cbar.set_label("%", size=5)

    ax.set_xlabel("Cluster Projeto SP", fontsize=7)
    ax.set_ylabel("Área Técnica", fontsize=7)
    ax.tick_params(axis='both', labelsize=6)

    plt.tight_layout()
    st.pyplot(fig)


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

    cols = st.columns(3)
    i = 0

    for cluster in clusters_selecionados:

        data_cluster = matriz_nao_100[cluster]
        data_cluster = data_cluster[data_cluster > 0].sort_index()

        fig2, ax2 = plt.subplots(figsize=(5, 4))
        bars = ax2.bar(data_cluster.index, data_cluster.values)

        ax2.set_ylim(0, 100)
        ax2.set_title(cluster, fontsize=11)
        ax2.tick_params(axis='x', rotation=90, labelsize=8)
        ax2.tick_params(axis='y', labelsize=8)

        for bar in bars:
            height = bar.get_height()
            ax2.text(
                bar.get_x() + bar.get_width() / 2,
                height + 1,
                f"{height:.1f}%",
                ha='center',
                va='bottom',
                fontsize=8
            )

        plt.tight_layout()

        cols[i % 3].pyplot(fig2)
        i += 1

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

    nd_por_cluster_qtd = (
        df_nd
        .groupby("CLUSTER_GEOGRAFICO")
        .size()
    )

    total_por_cluster = df.groupby("CLUSTER_GEOGRAFICO").size()

    impacto_cluster_pct = round(
        100 * nd_por_cluster_qtd / total_por_cluster,
        2
    ).sort_values(ascending=False)

    # ---------------- GRÁFICO (PERCENTUAL) ---------------- #

    st.markdown("### Percentual de Registros N/D dentro de cada Cluster")

    fig_nd, ax_nd = plt.subplots(figsize=(4, 2.5), dpi=150)

    bars = ax_nd.bar(impacto_cluster_pct.index, impacto_cluster_pct.values)

    ax_nd.set_ylabel("% N/D", fontsize=7)
    ax_nd.set_title("Impacto % N/D por Cluster", fontsize=8)
    ax_nd.set_ylim(0, impacto_cluster_pct.max() * 1.15)

    ax_nd.tick_params(axis='x', rotation=45, labelsize=6)
    ax_nd.tick_params(axis='y', labelsize=6)

    for bar in bars:
        height = bar.get_height()
        ax_nd.text(
            bar.get_x() + bar.get_width() / 2,
            height,
            f"{height:.1f}%",
            ha='center',
            va='bottom',
            fontsize=6
        )

    plt.tight_layout()
    st.pyplot(fig_nd, use_container_width=False)

    # ---------------- TABELA (VALORES ABSOLUTOS) ---------------- #

    st.markdown("### Quantidade Absoluta de Registros N/D por Cluster")

    tabela_abs = (
        nd_por_cluster_qtd
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
