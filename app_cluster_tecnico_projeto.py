import streamlit as st
import pandas as pd
import plotly.express as px
import unicodedata
import re
import os

# ---------------- CONFIGURAÇÃO STREAMLIT ---------------- #
st.set_page_config(
    layout="wide",
    page_title="Cluster Dashboard"
)

st.markdown("### Análise de Concentração de Áreas por Cluster")

BASE_DIR = os.path.dirname(__file__)

# ---------------- FUNÇÕES AUXILIARES ---------------- #
def normalizar_texto(texto):
    if pd.isnull(texto):
        return texto
    texto = unicodedata.normalize('NFKD', texto)
    texto = texto.encode('ASCII', 'ignore').decode('utf-8')
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip().upper()

def normalizar_node(texto):
    if pd.isnull(texto):
        return texto
    return str(texto).strip().upper()

def cluster_sp_area(row):
    if row["CLUSTER_GEOGRAFICO"] == "SP":
        area = row.get("AREA", None)
        if pd.isna(area) or area == "#N/D":
            return "SP (N/D)"
        elif "ÁREA 1" in area.upper():
            return "SP (AREA 1)"
        elif "ÁREA 2" in area.upper():
            return "SP (AREA 2)"
        elif "ÁREA 3" in area.upper():
            return "SP (AREA 3)"
        else:
            return "SP (OUTRA)"
    else:
        return row["CLUSTER_GEOGRAFICO"]


# ---------------- CARREGAR DADOS ---------------- #
@st.cache_data
def carregar_dados():

    path_cluster = os.path.join(BASE_DIR, data, "cluster_node_fev.xlsx")
    path_tec = os.path.join(BASE_DIR, data, "base_qualinet.xlsx")
    path_ab1 = os.path.join(BASE_DIR, data, "cluster_pc_ab1.xlsx")

    # Base principal
    df = pd.read_excel(path_cluster, sheet_name="cluster")
    df.columns = df.columns.str.strip().str.upper()

    if "DSC_AREA_DESPACHO" in df.columns:
        df.rename(columns={"DSC_AREA_DESPACHO": "AREA_TECNICA"}, inplace=True)

    df["DESC_CIDADE_NORM"] = df["DESC_CIDADE"].apply(normalizar_texto)
    df["COD_NODE_NORM"] = df["COD_NODE_TRAT"].apply(normalizar_node)

    # Base técnica
    df_tec = pd.read_excel(path_tec, sheet_name="Planilha1")
    df_tec.columns = df_tec.columns.str.strip().str.upper()
    df_tec.rename(columns={"HPS": "HP"}, inplace=True)

    df_tec = df_tec[["NODE","CIDADE","AREA","HP"]]
    df_tec["DESC_CIDADE_NORM"] = df_tec["CIDADE"].apply(normalizar_texto)

    cod_ibge_map = (
        df.dropna(subset=["DESC_CIDADE_NORM","COD_IBGE"])
        .drop_duplicates(subset=["DESC_CIDADE_NORM"])
        .set_index("DESC_CIDADE_NORM")["COD_IBGE"]
    )

    df_tec["COD_IBGE"] = df_tec["DESC_CIDADE_NORM"].map(cod_ibge_map)

    df_tec["NODE"] = df_tec["NODE"].apply(normalizar_node)

    df_tec["CHAVE_NODE_IBGE"] = df_tec.apply(
        lambda row: f"{row['NODE']}_{row['COD_IBGE']}"
        if pd.notnull(row["NODE"]) and pd.notnull(row["COD_IBGE"])
        else None,
        axis=1
    )

    df["CHAVE_NODE_IBGE"] = df.apply(
        lambda row: f"{row['COD_NODE_NORM']}_{row['COD_IBGE']}"
        if pd.notnull(row["COD_NODE_NORM"]) and pd.notnull(row["COD_IBGE"])
        else None,
        axis=1
    )

    df_tec_hp = (
        df_tec
        .dropna(subset=["COD_IBGE"])
        .query("HP != '-'")
        .drop_duplicates(subset=["COD_IBGE"])
        [["COD_IBGE","HP"]]
    )

    df = df.merge(df_tec_hp,on="COD_IBGE",how="left")
    df.rename(columns={"HP":"HP_TECNICA"}, inplace=True)

    df["HP_TECNICA"] = pd.to_numeric(df["HP_TECNICA"],errors="coerce").fillna(0).astype(int)

    df["CLUSTER_ANALITICO"] = df.apply(cluster_sp_area, axis=1)

    matriz = df.pivot_table(
        index="AREA_TECNICA",
        columns="CLUSTER_GEOGRAFICO",
        values="HP_TECNICA",
        aggfunc="sum",
        fill_value=0
    )

    matriz_pct = (matriz.div(matriz.sum(axis=1),axis=0)*100).fillna(0).round(1)

    # Base AB1
    df_cluster_ab1 = pd.read_excel(path_ab1, sheet_name="cluster_ab1")
    df_cluster_ab1.columns = df_cluster_ab1.columns.str.strip().str.upper()

    df_cluster_ab1["PC_CLASSE_AB1"] = (
        pd.to_numeric(
            df_cluster_ab1["PC_CLASSE_AB1"].astype(str).str.replace("%",""),
            errors="coerce"
        ) / 100
    )

    df_lookup = df_cluster_ab1[
        ["CHAVE_NODE_IBGE","CIDADE_SUB_CLUSTER","PC_CLASSE_AB1"]
    ].drop_duplicates()

    df = df.merge(df_lookup,on="CHAVE_NODE_IBGE",how="left")

    df_area14 = df[
        (df["AREA_TECNICA"]=="AREA 14") &
        (df["CLUSTER_ANALITICO"].isin(["SP (AREA 1)","SP (AREA 2)"]))
    ]

    tabela_bairros = (
        df_area14.groupby(["CLUSTER_ANALITICO","CIDADE_SUB_CLUSTER"])
        .agg(
            HP_TOTAL=("HP_TECNICA","sum"),
            PC_CLASSE_AB1=("PC_CLASSE_AB1","mean")
        )
        .reset_index()
        .sort_values(["CLUSTER_ANALITICO","HP_TOTAL"],ascending=[True,False])
    )

    return df, matriz, matriz_pct, tabela_bairros


df, matriz, matriz_pct, tabela_bairros = carregar_dados()

# ---------------- MÉTRICAS ---------------- #
max_por_area = matriz_pct.max(axis=1)
matriz_nao_100 = matriz_pct[max_por_area < 100]
matriz_100 = matriz_pct[max_por_area == 100]

st.markdown("### Resumo Executivo")

col1, col2, col3 = st.columns(3)

col1.metric("Total de Áreas", len(matriz_pct))
col2.metric("Áreas 100% Concentradas", len(matriz_100))
col3.metric("Áreas com Distribuição", len(matriz_nao_100))


# ---------------- ABAS ---------------- #

tab1, tab2, tab3, tab4 = st.tabs([
    "Heatmap",
    "Heatmap (Cluster SP)",
    "Áreas 100% em um Cluster",
    "Análise por Cluster"
])


# ---------------- ABA 1 ---------------- #

with tab1:

    st.markdown("### Heatmap")

    df_heat = matriz_nao_100.reset_index().melt(
        id_vars="AREA_TECNICA",
        var_name="CLUSTER_GEOGRAFICO",
        value_name="PERCENTUAL"
    )

    fig = px.density_heatmap(
        df_heat,
        x="CLUSTER_GEOGRAFICO",
        y="AREA_TECNICA",
        z="PERCENTUAL",
        color_continuous_scale="YlOrRd",
        text_auto=".1f",
        template="plotly_white"
    )

    st.plotly_chart(fig, use_container_width=True)


# ---------------- ABA 2 ---------------- #

with tab2:

    st.markdown("### Heatmap Cluster SP")

    matriz_geo = df.pivot_table(
        index="AREA_TECNICA",
        columns="CLUSTER_GEOGRAFICO",
        values="HP_TECNICA",
        aggfunc="sum",
        fill_value=0
    )

    matriz_geo_pct = (matriz_geo.div(matriz_geo.sum(axis=1),axis=0)*100).fillna(0)

    areas_nao_integrais_em_SP = matriz_geo_pct.index[
        (matriz_geo_pct["SP"] > 0) &
        (matriz_geo_pct["SP"] < 100)
    ]

    df_sp = df.loc[
        df["AREA_TECNICA"].isin(areas_nao_integrais_em_SP) &
        (df["CLUSTER_GEOGRAFICO"]=="SP")
    ].copy()

    matriz_sp_analitico = df_sp.pivot_table(
        index="AREA_TECNICA",
        columns="CLUSTER_ANALITICO",
        values="HP_TECNICA",
        aggfunc="sum",
        fill_value=0
    )

    matriz_sp_analitico_pct = (
        matriz_sp_analitico.div(matriz_sp_analitico.sum(axis=1),axis=0)*100
    ).fillna(0).round(1)

    df_heat_sp = matriz_sp_analitico_pct.reset_index().melt(
        id_vars="AREA_TECNICA",
        var_name="CLUSTER_ANALITICO",
        value_name="PERCENTUAL"
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

    st.plotly_chart(fig_sp,use_container_width=True)

    st.markdown("### Subclusters da Área 14 e % de Classe AB1")

    tabela_view = tabela_bairros.copy()

    tabela_view["PC_CLASSE_AB1"] = (
        (tabela_view["PC_CLASSE_AB1"]*100).round(1).astype(str)+"%"
    )

    tabela_view = tabela_view.rename(columns={
        "CLUSTER_ANALITICO":"CLUSTER",
        "CIDADE_SUB_CLUSTER":"SUBCLUSTER",
        "HP_TOTAL":"HP",
        "PC_CLASSE_AB1":"% CLASSE AB1"
    })

    st.dataframe(tabela_view,use_container_width=True)


# ---------------- ABA 3 ---------------- #

with tab3:

    st.markdown("### Áreas 100% Concentradas")

    areas_100_long = matriz_100.stack().reset_index()

    areas_100_long.columns = [
        "AREA_TECNICA",
        "CLUSTER_GEOGRAFICO",
        "PERCENTUAL"
    ]

    areas_100_long = areas_100_long[
        areas_100_long["PERCENTUAL"]==100
    ]

    hp_total_area = matriz.sum(axis=1)

    areas_100_long["HP_TOTAL"] = (
        areas_100_long["AREA_TECNICA"].map(hp_total_area)
    )

    areas_100_long = areas_100_long[
        ["CLUSTER_GEOGRAFICO","AREA_TECNICA","HP_TOTAL"]
    ].sort_values(
        ["CLUSTER_GEOGRAFICO","HP_TOTAL"],
        ascending=[True,False]
    )

    st.dataframe(
        areas_100_long.reset_index(drop=True),
        use_container_width=True
    )


# ---------------- ABA 4 ---------------- #

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

    for row_start in range(0,len(clusters_lista),cols_per_row):

        row_clusters = clusters_lista[row_start:row_start+cols_per_row]
        cols = st.columns(cols_per_row)

        for col, cluster in zip(cols,row_clusters):

            data_cluster = matriz_nao_100[cluster]
            data_cluster = data_cluster[data_cluster>0].sort_index()

            df_plot = data_cluster.reset_index()
            df_plot.columns = ["AREA_TECNICA","PERCENTUAL"]

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
                    "Selecionada":"#E4C767",
                    "Normal":"#DA2319"
                },
                title=cluster,
                template="plotly_white"
            )

            fig.update_layout(
                height=360,
                xaxis_title="Área Técnica",
                yaxis=dict(range=[0,100]),
                xaxis_tickangle=-60,
                margin=dict(l=30,r=10,t=40,b=60),
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
