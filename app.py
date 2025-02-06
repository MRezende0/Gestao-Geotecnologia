import streamlit as st
import pandas as pd
import plotly.express as px
import os
from dateutil.relativedelta import relativedelta
from datetime import datetime

########################################## CONFIGURAÇÃO ##########################################

# Configuração inicial da página
st.set_page_config(
    page_title="Gestão Geotecnologia",
    page_icon="imagens/logo-cocal.png",
    layout="wide",
)

# Estilo personalizado
def add_custom_css():
    st.markdown("""
        <style>
            [data-testid="stSidebar"] {
                background-color: #f8f9fa;
                padding: 20px;
            }
            h1, h2, h3 {
                color: #ff6411;
                font-weight: bold;
            }
            .card {
                background-color: #f8f9fa;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
                margin: 10px;
                text-align: center;
            }
            .card h3 {
                margin-bottom: 10px;
                color: #333333;
            }
            .card p {
                font-size: 1.5rem;
                font-weight: bold;
                color: #4caf50;
            }
            .stApp {
                background-color: #fff;
            }
        </style>
    """, unsafe_allow_html=True)

add_custom_css()

########################################## DADOS ##########################################

# Caminho dos arquivos CSV
BASE_PATH = "dados/base.csv"
TAREFAS_PATH = "dados/tarefas.csv"

# Função para carregar dados
def carregar_dados(caminho, colunas):
    if os.path.exists(caminho):
        return pd.read_csv(caminho)
    else:
        return pd.DataFrame(columns=colunas)

# Carrega os dados iniciais
df_tarefas = carregar_dados(TAREFAS_PATH, ["Setor", "Status", "Data", "Colaborador", "Tipo"])

########################################## TRANSAÇÕES ##########################################

# Função para salvar dados
def salvar_dados(df, caminho):
    df.to_csv(caminho, index=False)

# Página de Tarefas Semanais
def tarefas_semanais():
    st.title("📅 Tarefas Semanais")

    # Filtros
    st.sidebar.title("Filtros")
    responsavel = st.sidebar.selectbox("Responsável", ["Todos"] + list(df_tarefas["Responsável"].unique()))
    status = st.sidebar.selectbox("Status", ["Todos"] + list(df_tarefas["Status"].unique()))
    prioridade = st.sidebar.selectbox("Prioridade", ["Todos"] + list(df_tarefas["Prioridade"].unique()))

    # Aplicar filtros
    df_filtrado = df_tarefas.copy()
    if responsavel != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Responsável"] == responsavel]
    if status != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Status"] == status]
    if prioridade != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Prioridade"] == prioridade]

    # Exibir tabela de tarefas
    st.write("### Tarefas Filtradas")
    st.dataframe(df_filtrado)

    # Gráficos
    st.write("### Gráficos de Tarefas")
    col1, col2 = st.columns(2)
    with col1:
        fig_status = px.pie(df_filtrado, names="Status", title="Distribuição por Status")
        st.plotly_chart(fig_status)
    with col2:
        fig_prioridade = px.pie(df_filtrado, names="Prioridade", title="Distribuição por Prioridade")
        st.plotly_chart(fig_prioridade)

# Página de Registrar Tarefas
def registrar_tarefas():
    st.title("📝 Registrar Tarefas")

    with st.form("form_tarefa"):
        Data = st.date_input("Data")
        Descrição = st.text_input("Descrição")
        Responsável = st.selectbox("Responsável", ["Bia", "Flávio", "Outro"])
        Status = st.selectbox("Status", ["A fazer", "Em andamento", "Concluído"])
        Prioridade = st.selectbox("Prioridade", ["Baixa", "Média", "Alta"])
        submit = st.form_submit_button("Salvar Tarefa")

    if submit:
        nova_tarefa = pd.DataFrame({
            "Data": [Data],
            "Descrição": [Descrição],
            "Responsável": [Responsável],
            "Status": [Status],
            "Prioridade": [Prioridade]
        })
        df_tarefas = pd.concat([df_tarefas, nova_tarefa], ignore_index=True)
        salvar_dados(df_tarefas, TAREFAS_PATH)
        st.success("Tarefa registrada com sucesso!")

# Página de Acompanhamento Reforma e Passagem
def acompanhamento_reforma_passagem():
    st.title("🏗️ Acompanhamento Reforma e Passagem")
    st.write("Aqui você pode visualizar o progresso das reformas e passagens.")

    # Exemplo de métricas
    st.write("### Métricas de Reforma")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Área Total", "1000 m²")
    with col2:
        st.metric("Área Reformada", "600 m²")
    with col3:
        st.metric("Área Restante", "400 m²")

    st.write("### Métricas de Passagem")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Área Total", "500 m²")
    with col2:
        st.metric("Área Concluída", "300 m²")
    with col3:
        st.metric("Área Restante", "200 m²")

# Página de Auditoria
def auditoria():
    st.title("🔍 Auditoria")
    st.write("Aqui você pode visualizar os dados de auditoria.")

    # Exemplo de gráficos
    st.write("### Gráficos de Auditoria")
    df_auditoria = pd.DataFrame({
        "Tipo": ["Conformidade", "Não Conformidade"],
        "Quantidade": [80, 20]
    })
    fig_auditoria = px.pie(df_auditoria, names="Tipo", values="Quantidade", title="Conformidade vs Não Conformidade")
    st.plotly_chart(fig_auditoria)

# Página de Atividades Extras
def atividades_extras():
    st.title("📊 Atividades Extras")
    st.write("Aqui você pode visualizar as atividades extras realizadas.")

    # Exemplo de gráficos
    st.write("### Gráficos de Atividades Extras")
    df_extras = pd.DataFrame({
        "Tipo": ["Manutenção", "Melhorias", "Outros"],
        "Quantidade": [30, 50, 20]
    })
    fig_extras = px.bar(df_extras, x="Tipo", y="Quantidade", title="Distribuição de Atividades Extras")
    st.plotly_chart(fig_extras)

########################################## PÁGINA PRINCIPAL ##########################################

# Página Principal
def main_app():
    # st.sidebar.image("imagens/logo-cocal.png")
    st.sidebar.title("Menu")
    menu_option = st.sidebar.radio(
        "Selecione a funcionalidade:",
        ("Tarefas Semanais", "Registrar Tarefas", "Acompanhamento Reforma e Passagem", "Auditoria", "Atividades Extras")
    )

    st.sidebar.markdown("---")  # Linha separadora

    if menu_option == "Tarefas Semanais":
        tarefas_semanais()
    elif menu_option == "Registrar Tarefas":
        registrar_tarefas()
    elif menu_option == "Acompanhamento Reforma e Passagem":
        acompanhamento_reforma_passagem()
    elif menu_option == "Auditoria":
        auditoria()
    elif menu_option == "Atividades Extras":
        atividades_extras()

########################################## EXECUÇÃO ##########################################

if __name__ == "__main__":
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

    if st.session_state["logged_in"]:
        main_app()