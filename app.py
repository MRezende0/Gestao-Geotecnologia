import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import datetime
import glob
import sqlite3

########################################## CONFIGURAÇÃO ##########################################

st.set_page_config(
    page_title="Gestão Geotecnologia",
    page_icon="imagens/icone-cocal.png",
    layout="wide",
)

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
            .stApp {
                background-color: #fff;
            }
            .dataframe td, .dataframe th {
                white-space: nowrap;
                padding: 8px !important;
            }
        </style>
    """, unsafe_allow_html=True)

add_custom_css()

########################################## BANCO DE DADOS ##########################################

conn = sqlite3.connect('dados/dados.db', check_same_thread=False)
cursor = conn.cursor()

# Criar tabelas com constraints
cursor.execute('''
    CREATE TABLE IF NOT EXISTS tarefas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        Data DATE NOT NULL,
        Setor INTEGER NOT NULL,
        Colaborador TEXT NOT NULL,
        Tipo TEXT NOT NULL,
        Status TEXT NOT NULL,
        CHECK (Status IN ('A fazer', 'Em andamento', 'A validar', 'Concluído'))
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS atividades_extras (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        Data DATE NOT NULL,
        Colaborador TEXT NOT NULL,
        Solicitante TEXT NOT NULL,
        SetorSolicitante TEXT NOT NULL,
        Atividade TEXT NOT NULL,
        Horas TIME NOT NULL)
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS auditoria (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        Data DATE NOT NULL,
        Auditores TEXT NOT NULL,
        Unidade TEXT NOT NULL,
        Setor INTEGER NOT NULL,
        TipoPlantio_Planejado TEXT,
        TipoPlantio_Executado TEXT,
        TipoTerraco_Planejado TEXT,
        TipoTerraco_Executado TEXT,
        QuantidadeTerraco_Planejado TEXT,
        QuantidadeTerraco_Executado TEXT,
        Levantes_Planejado INTEGER,
        Levantes_Executado INTEGER,
        LevantesDesmanche_Planejado INTEGER,
        LevantesDesmanche_Executado INTEGER,
        Bigodes_Planejado INTEGER,
        Bigodes_Executado INTEGER,
        BigodesDesmanche_Planejado INTEGER,
        BigodesDesmanche_Executado INTEGER,
        Carreadores_Planejado TEXT,
        Carreadores_Executado TEXT,
        Patios_Projetado INTEGER,
        Patios_Executado INTEGER,
        Observacao TEXT)
''')

conn.commit()

########################################## FUNÇÕES GENÉRICAS ##########################################

def atualizar_registro(tabela, id_val, campos_valores):
    try:
        placeholders = ', '.join([f"{col} = ?" for col in campos_valores.keys()])
        valores = list(campos_valores.values())
        valores.append(id_val)
        
        cursor.execute(f'''
            UPDATE {tabela}
            SET {placeholders}
            WHERE id = ?
        ''', valores)
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar: {str(e)}")
        return False

def excluir_registros(tabela, ids):
    try:
        placeholders = ', '.join(['?'] * len(ids))
        cursor.execute(f'''
            DELETE FROM {tabela}
            WHERE id IN ({placeholders})
        ''', ids)
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir: {str(e)}")
        return False

########################################## FUNÇÕES DE CARREGAMENTO ##########################################

def carregar_tarefas():
    return pd.read_sql_query("SELECT * FROM tarefas", conn)

def carregar_atividades_extras():
    return pd.read_sql_query("SELECT * FROM atividades_extras", conn)

def carregar_auditoria():
    return pd.read_sql_query("SELECT * FROM auditoria", conn)

########################################## DASHBOARD ##########################################

def dashboard():
    st.title("📊 Dashboard")
    df_tarefas = carregar_tarefas()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        total_area = df_tarefas['Setor'].nunique()
        st.metric("Total de Setores", total_area)
    with col2:
        st.metric("Atividades Registradas", df_tarefas.shape[0])
    with col3:
        st.metric("Colaboradores Ativos", df_tarefas['Colaborador'].nunique())

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        fig = px.pie(df_tarefas, names='Status', title='Distribuição por Status')
        st.plotly_chart(fig)
    
    with col2:
        fig = px.bar(df_tarefas.groupby('Tipo').size().reset_index(name='Count'), 
                     x='Tipo', y='Count', title='Atividades por Tipo')
        st.plotly_chart(fig)

########################################## REGISTRAR ##########################################

def registrar_atividades():
    st.title("📝 Registrar")

    tipo_atividade = st.radio("Tipo de registro:", 
                            ("Atividade Semanal", "Atividade Extra", "Auditoria"))

    if tipo_atividade == "Atividade Semanal":
        with st.form("nova_tarefa"):
            Data = st.date_input("Data")
            Setor = st.number_input("Setor", min_value=1)
            Colaborador = st.selectbox("Colaborador", ["Ana", "Camila", "Gustavo", "Maico", "Márcio", "Pedro", "Talita", "Washington", "Willian", "Iago"])
            Tipo = st.selectbox("Tipo", ["Projeto de Sistematização", "Mapa de Sistematização", "LOC", "Projeto de Transbordo", "Auditoria"])
            Status = st.selectbox("Status", ["A fazer", "Em andamento", "A validar", "Concluído"])
            
            if st.form_submit_button("Salvar"):
                cursor.execute('''
                    INSERT INTO tarefas (Data, Setor, Colaborador, Tipo, Status)
                    VALUES (?, ?, ?, ?, ?)
                ''', (Data, Setor, Colaborador, Tipo, Status))
                conn.commit()
                st.success("Atividade registrada!")

    elif tipo_atividade == "Atividade Extra":
        with st.form("nova_extra"):
            Data = st.date_input("Data")
            Colaborador = st.selectbox("Colaborador", ["Ana", "Camila", "Gustavo", "Maico", "Márcio", "Pedro", "Talita", "Washington", "Willian", "Iago"])
            Solicitante = st.text_input("Solicitante")
            SetorSolicitante = st.text_input("Setor Solicitante")
            Atividade = st.selectbox("Atividade", ["Impressão", "Voo Drone", "Processamento", "Outro"])
            Horas = st.time_input("Horas")
            
            if st.form_submit_button("Salvar"):
                cursor.execute('''
                    INSERT INTO atividades_extras (Data, Colaborador, Solicitante, SetorSolicitante, Atividade, Horas)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (Data, Colaborador, Solicitante, SetorSolicitante, Atividade, Horas.strftime("%H:%M")))
                conn.commit()
                st.success("Atividade extra registrada!")

    elif tipo_atividade == "Auditoria":
        with st.form("nova_auditoria"):
            Data = st.date_input("Data")
            Auditores = st.multiselect("Auditores", ["Camila", "Guilherme", "Maico", "Sebastião", "Willian"])
            Unidade = st.selectbox("Unidade", ["Paraguaçu", "Narandiba"])
            Setor = st.number_input("Setor", min_value=1)
            
            col1, col2 = st.columns(2)
            with col1:
                TipoPlantio_Planejado = st.selectbox("Plantio Planejado", ["ESD", "Convencional"])
                TipoTerraco_Planejado = st.selectbox("Terraço Planejado", ["Base Larga", "Embutida"])
                Levantes_Planejado = st.number_input("Levantes Planejado", min_value=0)
                
            with col2:
                TipoPlantio_Executado = st.selectbox("Plantio Executado", ["ESD", "Convencional"])
                TipoTerraco_Executado = st.selectbox("Terraço Executado", ["Base Larga", "Embutida"])
                Levantes_Executado = st.number_input("Levantes Executado", min_value=0)
            
            if st.form_submit_button("Salvar"):
                cursor.execute('''
                    INSERT INTO auditoria (Data, Auditores, Unidade, Setor, TipoPlantio_Planejado, 
                    TipoPlantio_Executado, TipoTerraco_Planejado, TipoTerraco_Executado, 
                    Levantes_Planejado, Levantes_Executado)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (Data, ", ".join(Auditores), Unidade, Setor, TipoPlantio_Planejado,
                     TipoPlantio_Executado, TipoTerraco_Planejado, TipoTerraco_Executado,
                     Levantes_Planejado, Levantes_Executado))
                conn.commit()
                st.success("Auditoria registrada!")

########################################## ATIVIDADES ##########################################

def tarefas_semanais():
    st.title("📂 Atividades")
    df = carregar_tarefas()
    
    st.subheader("Edição de Tarefas")
    df_edit = df.copy()
    df_edit['Selecionar'] = False
    
    edited_df = st.data_editor(
        df_edit,
        column_config={
            "Selecionar": st.column_config.CheckboxColumn(required=True),
            "Data": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "id": None
        },
        hide_index=True,
        use_container_width=True
    )
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Salvar Alterações"):
            changes = edited_df[~edited_df.apply(tuple,1).isin(df.apply(tuple,1))]
            for _, row in changes.iterrows():
                campos = {
                    "Data": row['Data'],
                    "Setor": row['Setor'],
                    "Colaborador": row['Colaborador'],
                    "Tipo": row['Tipo'],
                    "Status": row['Status']
                }
                atualizar_registro('tarefas', row['id'], campos)
            st.rerun()
    
    with col2:
        if st.button("Excluir Selecionados"):
            ids = edited_df[edited_df['Selecionar']]['id'].tolist()
            if ids:
                excluir_registros('tarefas', ids)
                st.rerun()

########################################## ATIVIDADES EXTRAS ##########################################

def atividades_extras():
    st.title("📌 Atividades Extras")
    df = carregar_atividades_extras()
    
    st.subheader("Edição de Atividades")
    df_edit = df.copy()
    df_edit['Selecionar'] = False
    
    edited_df = st.data_editor(
        df_edit,
        column_config={
            "Selecionar": st.column_config.CheckboxColumn(required=True),
            "Data": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Horas": st.column_config.TimeColumn(format="HH:mm"),
            "id": None
        },
        hide_index=True,
        use_container_width=True
    )
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Salvar Mudanças"):
            changes = edited_df[~edited_df.apply(tuple,1).isin(df.apply(tuple,1))]
            for _, row in changes.iterrows():
                campos = {
                    "Data": row['Data'],
                    "Colaborador": row['Colaborador'],
                    "Solicitante": row['Solicitante'],
                    "SetorSolicitante": row['SetorSolicitante'],
                    "Atividade": row['Atividade'],
                    "Horas": row['Horas']
                }
                atualizar_registro('atividades_extras', row['id'], campos)
            st.rerun()
    
    with col2:
        if st.button("Remover Selecionados"):
            ids = edited_df[edited_df['Selecionar']]['id'].tolist()
            if ids:
                excluir_registros('atividades_extras', ids)
                st.rerun()

########################################## AUDITORIA ##########################################

def auditoria():
    st.title("🔍 Auditoria")
    df = carregar_auditoria()
    
    st.subheader("Edição de Auditorias")
    df_edit = df.copy()
    df_edit['Selecionar'] = False
    
    edited_df = st.data_editor(
        df_edit,
        column_config={
            "Selecionar": st.column_config.CheckboxColumn(required=True),
            "Data": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "id": None
        },
        hide_index=True,
        use_container_width=True
    )
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Atualizar Dados"):
            changes = edited_df[~edited_df.apply(tuple,1).isin(df.apply(tuple,1))]
            for _, row in changes.iterrows():
                campos = {col: row[col] for col in df.columns if col != 'id'}
                atualizar_registro('auditoria', row['id'], campos)
            st.rerun()
    
    with col2:
        if st.button("Excluir Itens Selecionados"):
            ids = edited_df[edited_df['Selecionar']]['id'].tolist()
            if ids:
                excluir_registros('auditoria', ids)
                st.rerun()

########################################## MENU PRINCIPAL ##########################################

def main():
    st.sidebar.image("imagens/logo-cocal.png")
    st.sidebar.title("Navegação")
    pagina = st.sidebar.radio("Selecione a página:", 
                            ["Dashboard", "Registrar", "Atividades", "Extras", "Auditoria"])

    if pagina == "Dashboard":
        dashboard()
    elif pagina == "Registrar":
        registrar_atividades()
    elif pagina == "Atividades":
        tarefas_semanais()
    elif pagina == "Extras":
        atividades_extras()
    elif pagina == "Auditoria":
        auditoria()

if __name__ == "__main__":
    main()