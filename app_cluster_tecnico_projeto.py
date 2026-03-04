
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
    """Remove acentos e normaliza para comparação robusta."""
    if pd.isna(x):
        return ""
    x = str(x)
    x = unicodedata.normalize("NFD", x)
    x = "".join(ch for ch in x if unicodedata.category(ch) != "Mn")
    return x.upper().strip()

def cluster_sp_area(row):
    """
    Cria um CLUSTER_ANALITICO:
      - Se CLUSTER_GEOGRAFICO == 'SP', subdivide por 'AREA' (ou AREA_TECNICA) em:
          SP (N/D), SP (AREA 1), SP (AREA 2), SP (AREA 3), SP (OUTRA)
      - Caso contrário, retorna o próprio CLUSTER_GEOGRAFICO.
    Comparações feitas de forma robusta (sem acento/caixa).
    """
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

# ---------------- CARREGAR OS DADOS ---------------- #

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

    # HP_TECNICA numérico
    df["HP_TECNICA"] = (
        pd.to_numeric(df.get("HP_TECNICA", 0), errors="coerce")
        .fillna(0)
        .astype(int)
    )

    # ---------------- IDENTIFICAR N/D ---------------- #
    mask_nd = df["AREA_TECNICA"].isna() if "AREA_TECNICA" in df.columns else df["AREA"].isna()
    df_nd = df[mask_nd].copy()
    df_valid = df[~mask_nd].copy()

    # Padronizar Área Técnica quando existir
    if "AREA_TECNICA" in df_valid.columns:
        df_valid["AREA_TECNICA"] = (
            df_valid["AREA_TECNICA"]
            .astype(str)
            .str.strip()
            .str.upper()
        )

    # Criar uma coluna base de área para a lógica analítica:
    # - Se existir 'AREA', usa ela; senão, usa 'AREA_TECNICA'.
    if "AREA" in df_valid.columns:
        df_valid["AREA_BASE"] = df_valid["AREA"]
    else:
        df_valid["AREA_BASE"] = df_valid.get("AREA_TECNICA", "")

    # Garantir colunas necessárias em formato string plain
    for col in ["CLUSTER_GEOGRAFICO", "AREA_TECNICA", "AREA_BASE"]:
        if col in df_valid.columns:
            df_valid[col] = df_valid[col].astype(str).str.strip()

    # ----------- CRIAR CLUSTER_ANALITICO AQUI ----------- #
    df_valid["CLUSTER_ANALITICO"] = df_valid.apply(cluster_sp_area, axis=1)

    # ---------------- MATRIZ (somente válidos) ---------------- #
    matriz = df_valid.pivot_table(
        index="AREA_TECNICA" if "AREA_TECNICA" in df_valid.columns else "AREA_BASE",
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

# ---------------- SEPARAÇÃO ÁREAS COM/SEM 100% ---------------- #

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
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Heatmap",
    "Heatmap SP (Cluster Analítico)",
    "Áreas 100%",
    "Análise por Cluster",
    "NODES Não Encontrados"
])

# ---------------- ABA 1 - HEATMAP GERAL ---------------- #
with tab1:
    st.markdown("### Heatmap")

    df_heat = matriz_nao_100.reset_index()
    df_heat_long = df_heat.melt(
        id_vars=df_heat.columns[0],  # AREA_TECNICA ou AREA_BASE dependendo do pivot
        var_name="CLUSTER_GEOGRAFICO",
        value_name="PERCENTUAL"
    )

    eixo_y = df_heat.columns[0]  # nome dinâmico do eixo Y

    fig = px.density_heatmap(
        df_heat_long,
        x="CLUSTER_GEOGRAFICO",
        y=eixo_y,
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

# ---------------- ABA 2 - HEATMAP SP (CLUSTER ANALÍTICO) ---------------- #
with tab2:
    st.markdown("### Heatmap Cluster SP")

    # Preparação a partir de df_valid (já tem CLUSTER_ANALITICO criado)
    df_aux = df_valid.copy()

    # Normalizar campos auxiliares para comparações
    df_aux["CLUSTER_GEOGRAFICO_NORM"] = df_aux["CLUSTER_GEOGRAFICO"].astype(str).str.strip().str.upper()
    df_aux["CLUSTER_ANALITICO_NORM"] = df_aux["CLUSTER_ANALITICO"].astype(str).str.strip().str.upper()
    df_aux["AREA_TECNICA"] = (
        df_aux.get("AREA_TECNICA", df_aux.get("AREA_BASE", ""))
        .astype(str).str.strip()
    )

    # 1) Selecionar áreas que NÃO estão integralmente em SP (SP > 0 e < 100) olhando CLUSTER_GEOGRAFICO
    matriz_geo = df_aux.pivot_table(
        index="AREA_TECNICA",
        columns="CLUSTER_GEOGRAFICO_NORM",
        values="HP_TECNICA",
        aggfunc="sum",
        fill_value=0
    )

    matriz_geo_pct = (matriz_geo.div(matriz_geo.sum(axis=1), axis=0) * 100).fillna(0)

    if "SP" not in matriz_geo_pct.columns:
        st.warning("Não há coluna 'SP' após o pivot por CLUSTER_GEOGRAFICO. Verifique a padronização dos valores (ex.: 'SP', 'Sp', 'SÃO PAULO').")
    else:
        areas_nao_integrais_em_SP = matriz_geo_pct.index[
            (matriz_geo_pct["SP"] > 0) & (matriz_geo_pct["SP"] < 100)
        ]

        # 2) Recorte SP + áreas selecionadas; pivot por CLUSTER_ANALITICO
        df_sp = df_aux.loc[
            df_aux["AREA_TECNICA"].isin(areas_nao_integrais_em_SP) &
            (df_aux["CLUSTER_GEOGRAFICO_NORM"] == "SP")
        ].copy()

        if df_sp.empty:
            st.warning("Após o filtro (áreas não integrais em SP + recorte SP), não sobrou dado.")
        else:
            matriz_sp_analitico = df_sp.pivot_table(
                index="AREA_TECNICA",
                columns="CLUSTER_ANALITICO_NORM",
                values="HP_TECNICA",
                aggfunc="sum",
                fill_value=0
            )

            # Percentual por área dentro de SP
            matriz_sp_analitico_pct = (
                matriz_sp_analitico.div(matriz_sp_analitico.sum(axis=1), axis=0)
                .replace([pd.NA, float("inf")], 0)
                * 100
            ).fillna(0).round(1)

            # Formato longo para plotly
            df_heat_sp = (
                matriz_sp_analitico_pct
                .reset_index()
                .melt(
                    id_vars="AREA_TECNICA",
                    var_name="CLUSTER_ANALITICO",
                    value_name="PERCENTUAL"
                )
            )

            # Heatmap plotly
            fig_sp = px.density_heatmap(
                df_heat_sp,
                x="CLUSTER_ANALITICO",
                y="AREA_TECNICA",
                z="PERCENTUAL",
                color_continuous_scale="YlOrRd",
                text_auto=".1f",
                template="plotly_white"
            )

            fig_sp.update_layout(
                height=500,
                paper_bgcolor="white",
                plot_bgcolor="white",
                font=dict(size=14),
                xaxis_title="Cluster Projeto SP (recorte: SP)",
                yaxis_title="Área Técnica",
                xaxis=dict(tickfont=dict(size=13)),
                yaxis=dict(tickfont=dict(size=13)),
                coloraxis_colorbar=dict(
                    title="%",
                    tickfont=dict(size=12),
                    title_font=dict(size=13)
                ),
                margin=dict(l=10, r=10, t=40, b=10)
            )

            fig_sp.update_traces(
                textfont=dict(size=12),
                hovertemplate="Cluster Projeto SP: %{x}<br>Área: %{y}<br>% em SP: %{z:.1f}<extra></extra>"
            )

            st.plotly_chart(fig_sp, use_container_width=True)

            with st.expander("Ver tabela percentual (SP x CLUSTER_ANALITICO)"):
                st.dataframe(
                    matriz_sp_analitico_pct.reset_index(),
                    use_container_width=True
                )

# ---------------- ABA 3 - ÁREAS 100% ---------------- #
with tab3:
    st.markdown("### Áreas 100% Concentradas")

    areas_100_long = (
        matriz_100
        .stack()
        .reset_index()
    )
    areas_100_long.columns = ["AREA_TECNICA" if "AREA_TECNICA" in matriz_100.index.names else "AREA_BASE",
                              "CLUSTER_GEOGRAFICO", "PERCENTUAL"]
    areas_100_long = areas_100_long[areas_100_long["PERCENTUAL"] == 100]

    hp_total_area = matriz.sum(axis=1)
    areas_100_long["HP_TOTAL"] = areas_100_long[areas_100_long.columns[0]].map(hp_total_area)

    areas_100_long = areas_100_long[
        ["CLUSTER_GEOGRAFICO", areas_100_long.columns[0], "HP_TOTAL"]
    ].sort_values(
        ["CLUSTER_GEOGRAFICO", "HP_TOTAL"],
        ascending=[True, False]
    )

    st.dataframe(
        areas_100_long.reset_index(drop=True),
        use_container_width=True
    )

# ---------------- ABA 4 - ANÁLISE POR CLUSTER ---------------- #
with tab4:
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
            # Nome dinâmico da coluna de área
            area_col_name = df_plot.columns[0]
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

# ---------------- ABA 5 - IMPACTO N/D ---------------- #
with tab5:
    st.markdown("### Análise dos Registros sem Área Técnica")

    # KPI
    total_registros = len(df)
    total_nd = len(df_nd)
    percentual_nd = round(100 * total_nd / total_registros, 2)

    col1, col2 = st.columns(2)
    col1.metric("Total Registros N/D", f"{total_nd:,}")
    col2.metric("Percentual sobre Base", f"{percentual_nd}%")

    # Preparação
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

    impacto_cluster_pct = (
        100 * nd_por_cluster / total_por_cluster
    ).fillna(0).round(2).sort_values(ascending=False)

    # Gráfico (percentual)
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

    # Tabela (valores absolutos)
    st.markdown("### Quantidade Absoluta de NODES sem Correspondência da Área Técnica")

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




