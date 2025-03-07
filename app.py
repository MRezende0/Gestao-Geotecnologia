import os
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

# Standard library imports
import glob
from datetime import datetime, timedelta
import time
from random import uniform
import warnings
import httplib2
import requests
import certifi

# Third-party imports
import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2 import service_account
import streamlit.components.v1 as components

pd.options.mode.chained_assignment = None  # Desabilita o aviso

########################################## CONFIGURAÇÃO ##########################################

# Configuração inicial da página
st.set_page_config(
    page_title="Gestão Geotecnologia",
    page_icon="imagens/icone-cocal.png",
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

########################################## GOOGLE SHEETS CONFIGURAÇÃO ##########################################

# Configuração do Google Sheets
SHEET_ID = "1EsJTZYTGJHpiRNg3U-GiqYDojjEGH7OAeKJRPzZuTIs"
SHEET_GIDS = {
    "Tarefas": "0",
    "AtividadesExtras": "1017708666",
    "Auditoria": "543590152",
    "Base": "503847224",
    "Reforma": "1252125692",
    "Passagem": "2099988266",
    "Pós": "1874058370"
}

@st.cache_resource
def get_google_sheets_client():
    try:
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        credentials_dict = dict(st.secrets["GOOGLE_CREDENTIALS"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
        
        # Criar cliente diretamente com as credenciais
        client = gspread.authorize(creds)
        
        # Configurar a sessão do cliente para ignorar verificação SSL
        if hasattr(client, 'session'):
            client.session.verify = False
        
        return client

    except Exception as e:
        st.error(f"Erro ao conectar com Google Sheets: {str(e)}")
        return None

def get_worksheet(sheet_name: str):
    """
    Get specific worksheet from Google Sheets with retry mechanism.
    
    Args:
        sheet_name: Nome da aba da planilha
        
    Returns:
        gspread.Worksheet or None: Worksheet object or None if error occurs
    """
    def _get_worksheet():
        try:
            client = get_google_sheets_client()
            if client is None:
                st.error("Erro ao conectar com Google Sheets. Tente novamente mais tarde.")
                return None
                
            spreadsheet = client.open_by_key(SHEET_ID)
            worksheet = spreadsheet.worksheet(sheet_name)
            return worksheet
        except Exception as e:
            if "Quota exceeded" in str(e):
                raise e  # Re-raise quota errors to trigger retry
            st.error(f"Erro ao acessar planilha {sheet_name}: {str(e)}")
            return None
            
    return retry_with_backoff(_get_worksheet, max_retries=5, initial_delay=2)

def retry_with_backoff(func, max_retries=5, initial_delay=1):
    """
    Executa uma função com retry e exponential backoff
    
    Args:
        func: Função a ser executada
        max_retries: Número máximo de tentativas
        initial_delay: Delay inicial em segundos
        
    Returns:
        Resultado da função ou None se falhar
    """
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if "Quota exceeded" not in str(e):
                st.error(f"Erro inesperado: {str(e)}")
                return None
                
            if attempt == max_retries - 1:
                st.error("Limite de tentativas excedido. Tente novamente mais tarde.")
                return None
                
            # Exponential backoff com jitter
            delay = initial_delay * (2 ** attempt) + uniform(0, 1)
            time.sleep(delay)
            
            # Informar usuário sobre retry
            st.warning(f"Limite de requisições atingido. Tentando novamente em {delay:.1f} segundos...")
            
    return None

def append_to_sheet(data_dict, sheet_name):
    """
    Append new data to the Google Sheet with retry mechanism
    
    Args:
        data_dict: Dictionary with data to append
        sheet_name: Nome da aba da planilha
        
    Returns:
        bool: True if success, False if error
    """
    def _append():
        try:
            worksheet = get_worksheet(sheet_name)
            if worksheet is None:
                return False
                
            # Converter objetos datetime para strings
            for key in data_dict:
                if isinstance(data_dict[key], (datetime, pd.Timestamp)):
                    data_dict[key] = data_dict[key].strftime("%Y-%m-%d")
                    
            # Get headers from worksheet
            headers = worksheet.row_values(1)
            
            # Create new row based on headers
            row = [data_dict.get(header, "") for header in headers]
            
            # Append row to worksheet
            worksheet.append_row(row)
            
            # Clear cache to force data reload
            st.cache_data.clear()
            return True
            
        except Exception as e:
            if "Quota exceeded" in str(e):
                raise e  # Re-raise quota errors to trigger retry
            st.error(f"Erro ao adicionar dados: {str(e)}")
            return False
            
    return retry_with_backoff(_append, initial_delay=2)

def load_data(sheet_name: str) -> pd.DataFrame:
    """
    Carrega dados de uma aba específica da planilha Google Sheets.
    
    Args:
        sheet_name: Nome da aba da planilha
        
    Returns:
        DataFrame com os dados carregados
    """
    def _load():
        worksheet = get_worksheet(sheet_name)
        if worksheet is None:
            return pd.DataFrame()
            
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
        
    result = retry_with_backoff(_load)
    return result if result is not None else pd.DataFrame()

def update_sheet(df: pd.DataFrame, sheet_name: str) -> bool:
    def _update():
        try:
            # Criar uma cópia do DataFrame para não modificar o original
            df_copy = df.copy()
            df_copy['Data'] = pd.to_datetime(df_copy['Data'], errors='coerce')
            
            # Converter todas as colunas de data para string no formato YYYY-MM-DD
            date_columns = df_copy.select_dtypes(include=['datetime64[ns]']).columns
            for col in date_columns:
                df_copy[col] = df_copy[col].dt.strftime("%Y-%m-%d")
            
            # Converter todos os valores NaN/None para string vazia
            df_copy = df_copy.fillna("")
            
            worksheet = get_worksheet(sheet_name)
            if worksheet is None:
                return False
                
            # Limpar a planilha
            worksheet.clear()
            
            # Obter os dados do DataFrame como lista
            data = [df_copy.columns.tolist()] + df_copy.values.tolist()
            
            # Atualizar a planilha
            worksheet.update(data)
            
            # Limpar cache para forçar recarregamento dos dados
            st.cache_data.clear()
            return True
            
        except Exception as e:
            st.error(f"Erro ao atualizar planilha: {str(e)}")
            return False
            
    return retry_with_backoff(_update, initial_delay=2)

def update_worksheet(df_editado, worksheet_name):
    """Função genérica para atualizar worksheet"""
    try:
        worksheet = get_worksheet(worksheet_name)
        if worksheet is not None:
            # Identificar as linhas alteradas
            df_original = pd.DataFrame(worksheet.get_all_records())
            df_alterado = df_editado.copy()
            
            # Remover colunas de controle antes de salvar
            if 'DELETE' in df_alterado.columns:
                df_alterado = df_alterado.drop(columns=['DELETE'])
            
            # Limpar a planilha e reescrever os dados
            worksheet.clear()
            headers = df_alterado.columns.tolist()
            worksheet.append_row(headers)
            worksheet.append_rows(df_alterado.values.tolist())
            
            st.cache_data.clear()
            st.success("Dados atualizados com sucesso!")
            st.rerun()
    except Exception as e:
        st.error(f"Erro ao atualizar planilha: {str(e)}")

########################################## DADOS ##########################################

# Configuração do Google Sheets
SHEET_ID = "1EsJTZYTGJHpiRNg3U-GiqYDojjEGH7OAeKJRPzZuTIs"
SHEET_GIDS = {
    "Tarefas": "0",
    "AtividadesExtras": "1017708666",
    "Auditoria": "543590152",
    "Base": "503847224",
    "Reforma": "1252125692",
    "Passagem": "2099988266",
    "Pós": "1874058370"
}

# Constantes para diretórios e arquivos
PASTA_POS = "dados/pos-aplicacao"
ARQUIVO_POS_CSV = "dados/pos_aplicacao.csv"

@st.cache_data(ttl=60)
def carregar_tarefas():
    """Carrega e formata os dados de tarefas."""
    df = load_data("Tarefas")
    if not df.empty:
        if "Data" in df.columns:
            df["Data"] = pd.to_datetime(df["Data"], errors='coerce', format="%Y-%m-%d")
            df = df.dropna(subset=["Data"])
        if "Setor" in df.columns:
            df["Setor"] = pd.to_numeric(df["Setor"], errors='coerce').fillna(0).astype(int)
    return df

@st.cache_data(ttl=60)
def carregar_atividades_extras():
    """Carrega os dados de atividades extras."""
    df = load_data("AtividadesExtras")
    if not df.empty and "Data" in df.columns:
        df["Data"] = pd.to_datetime(df["Data"], errors='coerce', format="%Y-%m-%d")
        df = df.dropna(subset=["Data"])
    return df

@st.cache_data(ttl=60)
def carregar_auditoria():
    """Carrega os dados de auditoria."""
    df = load_data("Auditoria")
    if not df.empty and "Data" in df.columns:
        df["Data"] = pd.to_datetime(df["Data"], errors='coerce', format="%Y-%m-%d")
        df = df.dropna(subset=["Data"])
    return df

@st.cache_data(ttl=60)
def carregar_dados_base():
    """Carrega e formata os dados base."""
    df = load_data("Base")
    if not df.empty and "Setor" in df.columns:
        df["Setor"] = pd.to_numeric(df["Setor"], errors='coerce').fillna(0).astype(int)
    return df

@st.cache_data(ttl=60)
def carregar_reforma() -> pd.DataFrame:
    """Carrega os dados de reforma."""
    return load_data("Reforma")

@st.cache_data(ttl=60)
def carregar_passagem() -> pd.DataFrame:
    """Carrega os dados de passagem."""
    return load_data("Passagem")

@st.cache_data(ttl=60)
def carregar_dados_pos() -> pd.DataFrame:
    """Carrega os dados de pós-aplicação."""
    df = load_data("Pós")
    if not df.empty:
        if "DATA" in df.columns:
            df["DATA"] = pd.to_datetime(df["DATA"])
        if "SETOR" in df.columns:
            df["SETOR"] = pd.to_numeric(df["SETOR"], errors='coerce').fillna(0).astype(int)
    return df

# Carregamento inicial dos dados
df_tarefas = carregar_tarefas()
df_extras = carregar_atividades_extras()
df_auditoria = carregar_auditoria()
df_reforma = carregar_reforma()
df_passagem = carregar_passagem()
df_base = carregar_dados_base()
df_pos = carregar_dados_pos()

# Converter tipos das colunas dos dados auxiliares, se necessário
if not df_tarefas.empty and "Setor" in df_tarefas.columns:
    df_tarefas["Setor"] = df_tarefas["Setor"].astype(int)

if not df_base.empty and "Setor" in df_base.columns:
    df_base["Setor"] = df_base["Setor"].astype(int)
    # Mesclar dados auxiliares com tarefas, se necessário
    if not df_tarefas.empty:
        df_tarefas = pd.merge(
            df_tarefas.copy(),
            df_base.copy(),
            on="Setor",
            how="left"
        )
        df_tarefas['Area'] = df_tarefas['Area'].fillna(0).astype(int)
        df_tarefas['Unidade'] = df_tarefas['Unidade'].fillna('Desconhecida')

########################################## DASHBOARD ##########################################

def dashboard():
    st.title("📊 Dashboard")

    with st.spinner('Carregando dados...'):
        df_tarefas = carregar_tarefas()
    
    # Se o DataFrame estiver vazio, exibe mensagem e retorna
    if df_tarefas.empty:
        st.info("Nenhuma tarefa registrada.")
        return

    # Mesclar com df_base (dados auxiliares vindos de CSV) para obter 'Area' e 'Unidade'
    df_base = carregar_dados_base()
    # Certifique-se de que a coluna 'Setor' está com o mesmo tipo em ambos os DataFrames
    df_tarefas["Setor"] = df_tarefas["Setor"].astype(int)
    df_base["Setor"] = df_base["Setor"].astype(int)
    
    df_tarefas = df_tarefas.merge(df_base, on="Setor", how="left")
    
    # Tratar valores nulos
    df_tarefas['Area'] = df_tarefas['Area'].fillna(0)
    df_tarefas['Unidade'] = df_tarefas['Unidade'].fillna('Desconhecida')
    
    # Aplicar filtros (supondo que a função filtros_dashboard() esteja definida)
    df_tarefas = filtros_dashboard(df_tarefas)
    
    # Exibe métricas
    col1, col2, col3 = st.columns(3)
    with col1:
        total_area = df_tarefas['Area'].sum()
        formatted_area = f"{total_area:,.0f}".replace(',', '.')
        st.metric("Área Total", f"{formatted_area} ha")
    with col2:
        st.metric("Quantidade de Atividades", df_tarefas['Colaborador'].size)
    with col3:
        st.metric("Colaboradores", df_tarefas['Colaborador'].nunique())
    
    st.divider()
    
    # Layout com 2 colunas para gráficos
    col1, linha, col2 = st.columns([4, 0.5, 4])
    
    # Gráfico: Atividades por Colaborador
    with col1:
        st.subheader("Atividades por Colaborador")
        df_contagem_responsavel = df_tarefas.groupby(["Colaborador"])["Tipo"].count().reset_index()
        df_contagem_responsavel.columns = ["Colaborador", "Quantidade de Projetos"]
        df_contagem_responsavel = df_contagem_responsavel.sort_values(by="Quantidade de Projetos", ascending=False)
        fig_responsavel = px.bar(
            df_contagem_responsavel,
            x="Quantidade de Projetos",
            y="Colaborador",
            color="Colaborador",
            orientation="h",
            text="Quantidade de Projetos",
        )
        fig_responsavel.update_traces(texttemplate="%{text}", textposition="outside")
        fig_responsavel.update_layout(
            showlegend=False,
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis=dict(showgrid=False, showticklabels=False, title='', showline=False, zeroline=False)
        )
        st.plotly_chart(fig_responsavel, use_container_width=True)
    
    # Gráfico: Quantidade de Projetos por Tipo
    with col2:
        st.subheader("Quantidade de Projetos por Tipo")
        df_contagem_tipo = df_tarefas.groupby("Tipo")["Colaborador"].count().reset_index()
        df_contagem_tipo.columns = ["Tipo", "Quantidade de Projetos"]
        df_contagem_tipo = df_contagem_tipo.sort_values(by="Quantidade de Projetos", ascending=False)
        fig_tipo = px.bar(
            df_contagem_tipo,
            x="Tipo",
            y="Quantidade de Projetos",
            color="Tipo",
            text="Quantidade de Projetos",
        )
        fig_tipo.update_traces(texttemplate="%{text}", textposition="outside")
        fig_tipo.update_layout(
            showlegend=False,
            margin=dict(l=10, r=10, t=10, b=10),
            yaxis=dict(showgrid=False, showticklabels=False, title='', showline=False, zeroline=False),
        )
        st.plotly_chart(fig_tipo, use_container_width=True)
    
    # Gráfico: Status dos Projetos
    with col1:
        st.subheader("Status dos Projetos")
        df_contagem_status = df_tarefas.groupby("Status")["Tipo"].count().reset_index()
        df_contagem_status.columns = ["Status", "Quantidade de Projetos"]
        df_contagem_status = df_contagem_status.sort_values(by="Quantidade de Projetos", ascending=False)
        fig_status = px.bar(
            df_contagem_status,
            x="Quantidade de Projetos",
            y="Status",
            color="Status",
            orientation="h",
            text="Quantidade de Projetos",
        )
        fig_status.update_traces(texttemplate="%{text}", textposition="outside")
        fig_status.update_layout(
            showlegend=False,
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis=dict(showgrid=False, showticklabels=False, title='', showline=False, zeroline=False),
        )
        st.plotly_chart(fig_status, use_container_width=True)
    
    # Gráfico: Projetos por Unidade
    with col2:
        st.subheader("Projetos por Unidade")
        df_contagem_unidade = df_tarefas.groupby("Unidade")["Tipo"].count().reset_index()
        df_contagem_unidade.columns = ["Unidade", "Quantidade de Projetos"]
        fig_pizza = px.pie(
            df_contagem_unidade,
            names="Unidade",
            values="Quantidade de Projetos",
            color="Unidade",
            hole=0.3,
            labels={'Quantidade de Projetos': 'Porcentagem de Projetos'}
        )
        st.plotly_chart(fig_pizza, use_container_width=True)
    
    st.divider()
    
    # Gráfico de Mapas de Pós-Aplicação
    st.subheader("Mapas de Pós-Aplicação")
    ordem_meses = ["Todos", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    
    mes_selecionado = st.selectbox(
        "Selecione o Mês",
        options=ordem_meses,
        index=0
    )
    
    # Converter coluna DATA de df_pos para datetime e criar coluna MÊS
    df_pos["DATA"] = pd.to_datetime(df_pos["DATA"], errors="coerce")
    df_pos["MÊS"] = df_pos["DATA"].dt.strftime("%B").str.capitalize()
    
    if mes_selecionado != "Todos":
        df_filtrado = df_pos[df_pos["MÊS"] == mes_selecionado]
    else:
        df_filtrado = df_pos
    
    df_unico = df_filtrado.drop_duplicates(subset=["MÊS", "SETOR"])
    df_contagem = df_unico.groupby("MÊS").size().reset_index(name="QUANTIDADE")
    
    if df_contagem.shape[1] == 2:  
        df_contagem.columns = ["MÊS", "QUANTIDADE"]
    else:
        st.error(f"Erro na contagem de meses: Estrutura inesperada -> {df_contagem.columns}")
        
    fig_mes = px.bar(
        df_contagem,
        x="QUANTIDADE",
        y="MÊS",
        color="MÊS",
        orientation="h",
        text="QUANTIDADE",
        category_orders={"MÊS": ordem_meses}
    )
    fig_mes.update_traces(texttemplate="%{text}", textposition="outside")
    fig_mes.update_layout(
        showlegend=False,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(showgrid=False, showticklabels=False, title='', showline=False, zeroline=False),
    )
    st.plotly_chart(fig_mes)
    
    st.divider()
    
    # Tabela
    st.write("### Detalhes das Tarefas")
    df_tarefas_ordenado = df_tarefas.sort_values(by="Data", ascending=False).reset_index(drop=True)
    df_tarefas_display = df_tarefas_ordenado[["Data", "Setor", "Colaborador", "Tipo", "Status"]]
    df_tarefas_display["Data"] = pd.to_datetime(df_tarefas_display["Data"], errors="coerce")
    
    # Criar um editor de dados
    df_editado = st.data_editor(
        df_tarefas_display,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "Setor": st.column_config.NumberColumn("Setor", min_value=0, step=1, format="%d"),
            "Colaborador": st.column_config.SelectboxColumn(
                "Colaborador",
                options=["Ana", "Camila", "Gustavo", "Maico", "Márcio", "Pedro", "Talita", "Washington", "Willian", "Iago"]
            ),
            "Tipo": st.column_config.SelectboxColumn(
                "Tipo",
                options=["Projeto de Sistematização", "Mapa de Sistematização", "LOC", "Projeto de Transbordo", "Projeto de Colheita", "Projeto de Sulcação", 
                        "Projeto de Fertirrigação", "Mapa de Pré-Plantio", "Mapa de Pós-Plantio", "Mapa de Pós-Aplicação", "Mapa de Cadastro", "Auditoria", "Outro"]
            ),
            "Status": st.column_config.SelectboxColumn(
                "Status",
                options=["A fazer", "Em andamento", "A validar", "Concluído"]
            ),
            "DELETE": st.column_config.CheckboxColumn(
                "Excluir",
                help="Selecione para excluir a linha",
                default=False
            )
        }
    )

    # Botão para salvar alterações
    if st.button("Salvar Alterações"):
        try:
            # Remover linhas marcadas para exclusão
            if "DELETE" in df_editado.columns:
                df_editado = df_editado[~df_editado["DELETE"]]
                df_editado = df_editado.drop(columns=["DELETE"])
            
            # Converter datas para o formato correto
            df_editado["Data"] = pd.to_datetime(df_editado["Data"], errors='coerce')
            
            # Atualizar a planilha
            if update_sheet(df_editado, "Tarefas"):
                st.success("Dados atualizados com sucesso!")
                st.rerun()
                
        except Exception as e:
            st.error(f"Erro ao salvar alterações: {str(e)}")

########################################## REGISTRAR ##########################################

def registrar_atividades():
    st.title("📝 Registrar")

    # Configuração de cores para cada tipo de atividade
    tipo_cores = {
        "Projeto de Sistematização": "🔴",  # Vermelho
        "Mapa de Sistematização": "🟠",     # Laranja
        "LOC": "🟡",                        # Amarelo
        "Projeto de Transbordo": "🟢",      # Verde
        "Projeto de Colheita": "🔵",        # Azul
        "Projeto de Sulcação": "🟣",        # Roxo
        "Projeto de Fertirrigação": "🟤",   # Marrom
        "Mapa de Pré-Plantio": "⚫",        # Preto
        "Mapa de Pós-Plantio": "⚪",        # Branco
        "Mapa de Pós-Aplicação": "🟪",      # Roxo Claro
        "Mapa de Cadastro": "🟫",           # Marrom Claro
        "Mapa de Expansão": "🟧",           # Laranja
        "Auditoria": "🟦",                  # Azul Claro
        "Outro": "🟩"                       # Verde Claro
    }

    # Função para formatar com emojis
    def formatar_tipo(tipo):
        if not tipo:
            return ""
        return f"{tipo_cores.get(tipo, '')} {tipo}"

    # Seleção do tipo de atividade
    tipo_atividade = st.radio(
        "Selecione o tipo de registro:",
        ("Atividade Semanal", "Atividade Extra", "Reforma e Passagem", "Pós-Aplicação", "Auditoria")
    )

    if tipo_atividade == "Atividade Semanal":
        with st.form("form_atividade_semanal"):
            st.subheader("Nova Atividade Semanal")
            Data = st.date_input("Data")
            Setor = st.number_input("Setor", min_value=0, step=1)
            Colaborador = st.selectbox("Colaborador", ["", "Ana", "Camila", "Gustavo", "Maico", "Márcio", "Pedro", "Talita", "Washington", "Willian", "Iago"])

            tipo_options = ["", "Projeto de Sistematização", "Mapa de Sistematização", "LOC", "Projeto de Transbordo",
                          "Projeto de Colheita", "Projeto de Sulcação", "Projeto de Fertirrigação", "Mapa de Pré-Plantio",
                          "Mapa de Pós-Plantio", "Mapa de Pós-Aplicação", "Mapa de Cadastro", "Mapa de Expansão", "Auditoria", "Outro"]
            
            Tipo = st.selectbox("Tipo", options=tipo_options, format_func=formatar_tipo)
            Status = st.selectbox("Status", ["A fazer", "Em andamento", "A validar", "Concluído"])
            submit = st.form_submit_button("Registrar")

            if submit:
                try:
                    nova_tarefa = {
                        "Data": str(Data),
                        "Setor": int(Setor),
                        "Colaborador": Colaborador,
                        "Tipo": Tipo,
                        "Status": Status
                    }
                    append_to_sheet(nova_tarefa, "Tarefas")
                    st.success(f"Parabéns, {Colaborador}! Tarefa do setor {Setor} registrada com sucesso!")
                except Exception as e:
                    st.error(f"{Colaborador}, erro ao registrar a tarefa do setor {Setor}: {e}")

    # Formulário para Atividade Extra
    elif tipo_atividade == "Atividade Extra":
        with st.form("form_atividade_extra"):
            st.subheader("Nova Atividade Extra")
            Data = st.date_input("Data")
            Colaborador = st.selectbox("Colaborador", ["", "Ana", "Camila", "Gustavo", "Maico", "Márcio", "Pedro", "Talita", "Washington", "Willian", "Iago"])
            Solicitante = st.text_input("Nome do Solicitante")
            SetorSolicitante = st.text_input("Setor Solicitante")
            Atividade = st.selectbox("Atividade", ["", "Impressão de Mapa", "Voo com drone", "Mapa", "Tematização de mapa", "Processamento", "Projeto", "Outro"])
            Horas = st.time_input("Horas de trabalho").strftime("%H:%M:%S")  # Converte para string
            submit = st.form_submit_button("Registrar")

            if submit:
                try:
                    nova_atividade = {
                        "Data": str(Data),
                        "Colaborador": Colaborador,
                        "Solicitante": Solicitante,
                        "SetorSolicitante": SetorSolicitante,
                        "Atividade": Atividade,
                        "Horas": Horas
                    }
                    append_to_sheet(nova_atividade, "AtividadesExtras")
                    st.success(f"Parabéns, {Colaborador}! Atividade Extra ({Atividade}) registrada com sucesso!")
                except Exception as e:
                    st.error(f"Erro ao registrar a Atividade Extra ({Atividade}): {e}")

    # Formulário para Reforma e Passagem
    elif tipo_atividade == "Reforma e Passagem":
        opcao = st.radio("Selecione a planilha para editar:", ["Reforma", "Passagem"])
        
        # Carregar os dados apropriados
        if opcao == "Reforma":
            df_editavel = carregar_reforma()
        else:
            df_editavel = carregar_passagem()
            
        # Criar um editor de dados
        df_editado = st.data_editor(
            df_editavel,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                "Unidade": st.column_config.SelectboxColumn(
                    "Unidade",
                    options=["PPT", "NRD"]
                ),
                "Area": st.column_config.NumberColumn(
                    "Area",
                    min_value=0.0,
                    format="%.2f"
                ),
                "Plano": st.column_config.SelectboxColumn(
                    "Plano",
                    options=["REFORMA PLANO A", "REFORMA PLANO B"]
                ),
                "Projeto": st.column_config.SelectboxColumn(
                    "Projeto",
                    options=["OK", "EM ANDAMENTO", "NAO", ""]
                ),
                "Aprovado": st.column_config.SelectboxColumn(
                    "Aprovado",
                    options=["OK", "EM ANDAMENTO", "NAO", ""]
                ),
                "Sistematizacao": st.column_config.SelectboxColumn(
                    "Sistematizacao",
                    options=["OK", "EM ANDAMENTO", "NAO", ""]
                ),
                "Loc": st.column_config.SelectboxColumn(
                    "Loc",
                    options=["OK", "EM ANDAMENTO", "NAO", ""]
                ),
                "Pre_Plantio": st.column_config.SelectboxColumn(
                    "Pre_Plantio",
                    options=["OK", "EM ANDAMENTO", "NAO", ""]
                ),
                "DELETE": st.column_config.CheckboxColumn(
                    "Excluir",
                    help="Selecione para excluir a linha",
                    default=False
                )
            }
        )

        # Botão para salvar alterações
        if st.button("Salvar Alterações"):
            try:
                # Remover linhas marcadas para exclusão
                if "DELETE" in df_editado.columns:
                    df_editado = df_editado[~df_editado["DELETE"]]
                    df_editado = df_editado.drop(columns=["DELETE"])
                
                # Atualizar a planilha
                if update_worksheet(df_editado, opcao):
                    st.success(f"Dados de {opcao} atualizados com sucesso!")
                    st.rerun()
                    
            except Exception as e:
                st.error(f"Erro ao salvar alterações: {str(e)}")

    elif tipo_atividade == "Pós-Aplicação":
        st.subheader("Upload de Arquivo - Pós-Aplicação")
        arquivo = st.file_uploader("Carregue um arquivo Excel", type=["xls", "xlsx"])

        if arquivo:
            try:
                # Ler o arquivo Excel
                df = pd.read_excel(arquivo)
                
                # Verificar colunas necessárias
                colunas = ["DESC_OPERAÇÃO", "DATA", "SETOR", "TALHÃO", "AREA"]
                if not all(col in df.columns for col in colunas):
                    st.error("Arquivo deve conter: DESC_OPERAÇÃO, DATA, SETOR, TALHÃO, AREA")
                    return
                
                # Processar dados
                df = df[colunas]
                df["DATA"] = pd.to_datetime(df["DATA"], errors="coerce").dt.strftime("%Y-%m-%d")
                df = df.dropna(subset=["DATA"])
                df["SETOR"] = pd.to_numeric(df["SETOR"], errors='coerce').fillna(0).astype(int)
                df["AREA"] = pd.to_numeric(df["AREA"], errors='coerce').fillna(0)
                
                # Mostrar preview
                st.write("### Preview dos dados:")
                st.dataframe(df.head())
                
                # Salvar dados
                if st.button("Salvar"):
                    # Verificar duplicatas
                    df_existente = carregar_dados_pos()
                    novos_registros = []
                    duplicatas = 0
                    
                    for _, row in df.iterrows():
                        dados = {
                            "DESC_OPERAÇÃO": row["DESC_OPERAÇÃO"],
                            "DATA": row["DATA"],
                            "SETOR": int(row["SETOR"]),
                            "TALHÃO": row["TALHÃO"],
                            "AREA": float(row["AREA"])
                        }
                        
                        # Verificar se já existe
                        if df_existente.empty or not (
                            (df_existente["SETOR"] == dados["SETOR"]) &
                            (df_existente["TALHÃO"] == dados["TALHÃO"]) &
                            (df_existente["DATA"] == dados["DATA"]) &
                            (df_existente["DESC_OPERAÇÃO"] == dados["DESC_OPERAÇÃO"])
                        ).any():
                            novos_registros.append(dados)
                        else:
                            duplicatas += 1
                    
                    # Salvar novos registros
                    if novos_registros:
                        for dados in novos_registros:
                            append_to_sheet(dados, "Pós")
                        st.success(f"Salvos {len(novos_registros)} novos registros!")
                    
                    if duplicatas:
                        st.warning(f"{duplicatas} registros duplicados foram ignorados")
                    
                    st.cache_data.clear()
                    
            except Exception as e:
                st.error(f"Erro ao processar arquivo: {str(e)}")

    elif tipo_atividade == "Auditoria":
        with st.form("form_auditoria"):
            st.subheader("Nova Auditoria")
            
            # Campos básicos
            Data = st.date_input("Data referente à auditoria")
            Auditores = st.multiselect("Auditores", ["Camila", "Maico", "Willian", "Sebastião", "Guilherme", "Outro"])
            Unidade = st.selectbox("Unidade", ["", "Paraguaçu", "Narandiba"])
            Setor = st.number_input("Setor", min_value=0, step=1)
            
            # Campos de Levantes
            col1, col2 = st.columns(2)
            with col1:
                Levantes_Planejado = st.number_input("Levantes Planejados", min_value=0, step=1)
            with col2:
                Levantes_Executado = st.number_input("Levantes Executados", min_value=0, step=1)
                
            # Campos de Bigodes
            col3, col4 = st.columns(2)
            with col3:
                Bigodes_Planejado = st.number_input("Bigodes Planejados", min_value=0, step=1)
            with col4:
                Bigodes_Executado = st.number_input("Bigodes Executados", min_value=0, step=1)
                
            # Campos de Tipo de Plantio
            col5, col6 = st.columns(2)
            with col5:
                TipoPlantio_Planejado = st.selectbox("Tipo de Plantio Planejado", ["", "ESD", "Convencional", "ESD e Convencional"])
            with col6:
                TipoPlantio_Executado = st.selectbox("Tipo de Plantio Executado", ["", "ESD", "Convencional", "ESD e Convencional"])
                
            # Campos de Tipo de Terraço
            col7, col8 = st.columns(2)
            with col7:
                TipoTerraco_Planejado = st.selectbox("Tipo de Terraço Planejado", ["", "Base Larga", "Embutida", "ESD", "Base Large e ESD", "Base Larga e Embutida", "Embutida e ESD"])
            with col8:
                TipoTerraco_Executado = st.selectbox("Tipo de Terraço Executado", ["", "Base Larga", "Embutida", "ESD", "Base Large e ESD", "Base Larga e Embutida", "Embutida e ESD"])
                
            # Campos de Quantidade de Terraço
            col9, col10 = st.columns(2)
            with col9:
                QuantidadeTerraco_Planejado = st.selectbox("Quantidade de Terraço Planejada", ["", "Ok", "Não"])
            with col10:
                QuantidadeTerraco_Executado = st.selectbox("Quantidade de Terraço Executada", ["", "Ok", "Não"])
                
            # Campos de Levantes para Desmanche
            col11, col12 = st.columns(2)
            with col11:
                LevantesDesmanche_Planejado = st.number_input("Levantes para Desmanche Planejados", min_value=0, step=1)
            with col12:
                LevantesDesmanche_Executado = st.number_input("Levantes para Desmanche Executados", min_value=0, step=1)
                
            # Campos de Bigodes para Desmanche
            col13, col14 = st.columns(2)
            with col13:
                BigodesDesmanche_Planejado = st.number_input("Bigodes para Desmanche Planejados", min_value=0, step=1)
            with col14:
                BigodesDesmanche_Executado = st.number_input("Bigodes para Desmanche Executados", min_value=0, step=1)
                
            # Campos de Carreadores
            col15, col16 = st.columns(2)
            with col15:
                Carreadores_Planejado = st.selectbox("Carreadores Planejados", ["", "Ok", "Não"])
            with col16:
                Carreadores_Executado = st.selectbox("Carreadores Executados", ["", "Ok", "Não"])
            
            # Campos de Pátios
            col17, col18 = st.columns(2)
            with col17:
                Patios_Planejado = st.number_input("Pátios Planejados", min_value=0, step=1)
            with col18:
                Patios_Executado = st.number_input("Pátios Executados", min_value=0, step=1)

            Observacao = st.text_area("Observação")
            
            submit = st.form_submit_button("Registrar Auditoria")

            if submit:
                # Validar campos obrigatórios
                if not Unidade:
                    st.error("Por favor, selecione a Unidade.")
                    return
                if Setor == 0:
                    st.error("Por favor, informe o Setor.")
                    return
                if not Auditores:
                    st.error("Por favor, selecione pelo menos um Auditor.")
                    return
                
                try:
                    nova_auditoria = {
                        "Data": str(Data),
                        "Auditores": ", ".join(Auditores) if Auditores else "",
                        "Unidade": Unidade,
                        "Setor": int(Setor),
                        "Levantes_Planejado": int(Levantes_Planejado),
                        "Levantes_Executado": int(Levantes_Executado),
                        "Bigodes_Planejado": int(Bigodes_Planejado),
                        "Bigodes_Executado": int(Bigodes_Executado),
                        "TipoPlantio_Planejado": TipoPlantio_Planejado or "",
                        "TipoPlantio_Executado": TipoPlantio_Executado or "",
                        "TipoTerraco_Planejado": TipoTerraco_Planejado or "",
                        "TipoTerraco_Executado": TipoTerraco_Executado or "",
                        "QuantidadeTerraco_Planejado": QuantidadeTerraco_Planejado or "",
                        "QuantidadeTerraco_Executado": QuantidadeTerraco_Executado or "",
                        "LevantesDesmanche_Planejado": int(LevantesDesmanche_Planejado),
                        "LevantesDesmanche_Executado": int(LevantesDesmanche_Executado),
                        "BigodesDesmanche_Planejado": int(BigodesDesmanche_Planejado),
                        "BigodesDesmanche_Executado": int(BigodesDesmanche_Executado),
                        "Carreadores_Planejado": Carreadores_Planejado or "",
                        "Carreadores_Executado": Carreadores_Executado or "",
                        "Patios_Planejado": int(Patios_Planejado),
                        "Patios_Executado": int(Patios_Executado),
                        "Observacao": Observacao or ""
                    }
                    
                    if append_to_sheet(nova_auditoria, "Auditoria"):
                        st.success(f"Auditoria do setor {Setor} registrada com sucesso!")
                        st.cache_data.clear()
                    else:
                        st.error("Erro ao registrar a auditoria. Por favor, tente novamente.")
                        
                except Exception as e:
                    st.error(f"Erro ao registrar a auditoria do setor {Setor}: {str(e)}")

########################################## ATIVIDADES ##########################################

# Função para exibir os projetos como cards clicáveis
def tarefas_semanais():
    st.title("📂 Atividades")

    # Carregar os dados de tarefas
    df_tarefas = carregar_tarefas()

    # Verificar se há dados
    if df_tarefas.empty:
        st.info("Nenhuma atividade registrada.")
        return

    # Aplicando os filtros e retornando o DataFrame filtrado
    df_tarefas = filtros_atividades(df_tarefas)

    # Converter a coluna 'Setor' para inteiro, se possível
    df_tarefas.loc[:, "Setor"] = pd.to_numeric(df_tarefas["Setor"], errors="coerce").astype("Int64")

    # Criar duas colunas para os filtros
    col_filtro1, col_filtro2 = st.columns(2)

    with col_filtro1:
        # Filtro de Setor
        filtro_setor = st.selectbox(
            "🔍 Filtrar por Setor",
            options=[""] + sorted(df_tarefas["Setor"].dropna().unique().tolist()),
            index=0
        )

    with col_filtro2:
        # Filtro de Colaborador
        filtro_colaborador = st.selectbox(
            "👤 Filtrar por Colaborador",
            options=[""] + sorted(df_tarefas["Colaborador"].dropna().astype(str).unique().tolist()),
            index=0
        )

    # Aplicar os filtros sequencialmente
    if filtro_setor:
        df_tarefas = df_tarefas[df_tarefas["Setor"] == filtro_setor]
        
    if filtro_colaborador:
        df_tarefas = df_tarefas[df_tarefas["Colaborador"] == filtro_colaborador]

    # Divide a tela em 3 colunas
    col1, col2, col3 = st.columns(3)

        # Track if any card is clicked
    clicked_card = None

    for i, row in df_tarefas.iterrows():
        # Determine which column to use
        current_col = col1 if i % 3 == 0 else (col2 if i % 3 == 1 else col3)
        
        with current_col:
            # Create a single button for the entire card
            if st.button(
                f"Setor {row['Setor']} | {row['Colaborador']} | {row['Tipo']}",
                key=f"card_{i}",
                use_container_width=True,
            ):
                st.session_state["projeto_selecionado"] = row.to_dict()
                st.rerun()

# Verificar se um projeto foi selecionado
if "projeto_selecionado" in st.session_state:
    tarefa = st.session_state["projeto_selecionado"]

    with st.form(key="edt_form"):
            st.subheader("Editar Tarefa")
            Data = st.date_input("Data", value=datetime.today().date())
            Setor = st.number_input("Setor", value=tarefa["Setor"])
            Colaborador = st.selectbox("Colaborador", options=["", "Ana", "Camila", "Gustavo", "Maico", "Márcio", "Pedro", "Talita", "Washington", "Willian", "Iago"], 
                                     index=["", "Ana", "Camila", "Gustavo", "Maico", "Márcio", "Pedro", "Talita", "Washington", "Willian", "Iago"].index(tarefa["Colaborador"]))
            Tipo = st.selectbox("Tipo", options=["", "Projeto de Sistematização", "Mapa de Sistematização", "LOC", "Projeto de Transbordo", "Auditoria", "Projeto de Fertirrigação", "Projeto de Sulcação", "Mapa de Pré-Plantio", "Mapa de Pós-Plantio", "Projeto de Colheita", "Mapa de Cadastro"],
                              index=["", "Projeto de Sistematização", "Mapa de Sistematização", "LOC", "Projeto de Transbordo", "Auditoria", "Projeto de Fertirrigação", "Projeto de Sulcação", "Mapa de Pré-Plantio", "Mapa de Pós-Plantio", "Projeto de Colheita", "Mapa de Cadastro"].index(tarefa["Tipo"]))
            Status = st.selectbox("Status", options=["", "A fazer", "Em andamento", "A validar", "Concluído"],
                                index=["", "A fazer", "Em andamento", "A validar", "Concluído"].index(tarefa["Status"]))

            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("Salvar Alterações"):
                    try:
                        df = carregar_tarefas()
                        mask = (df['Data'] == tarefa['Data']) & (df['Setor'] == tarefa['Setor']) & (df['Colaborador'] == tarefa['Colaborador']) & (df['Tipo'] == tarefa['Tipo'])
                        if mask.any():
                            df.loc[mask, ['Data', 'Setor', 'Colaborador', 'Tipo', 'Status']] = [str(Data), Setor, Colaborador, Tipo, Status]
                            update_sheet(df, "Tarefas")
                            st.success("Atividade atualizada com sucesso!")
                            st.session_state.pop("projeto_selecionado", None)
                        else:
                            st.error("Não foi possível encontrar a atividade para atualizar.")
                    except Exception as e:
                        st.error(f"Erro ao atualizar: {str(e)}")
                
                if st.form_submit_button("🗑️ Excluir Tarefa"):
                    try:
                        df = carregar_tarefas()
                        mask = (df['Data'] == tarefa['Data']) & (df['Setor'] == tarefa['Setor']) & (df['Colaborador'] == tarefa['Colaborador']) & (df['Tipo'] == tarefa['Tipo'])
                        if mask.any():
                            df = df[~mask]
                            update_sheet(df, "Tarefas")
                            st.success("Tarefa excluída com sucesso!")
                            st.session_state.pop("projeto_selecionado", None)
                        else:
                            st.error("Não foi possível encontrar a tarefa para excluir.")
                    except Exception as e:
                        st.error(f"Erro ao excluir: {str(e)}")

########################################## REFORMA E PASSAGEM ##########################################

# Página de Acompanhamento Reforma e Passagem
def acompanhamento_reforma_passagem():

    st.title("🌱 Reforma e Passagem")

    # Lista de categorias e colunas correspondentes no DataFrame
    categorias = ["Em andamento", "Realizado", "Aprovado", "Sistematizacao", "Loc", "Pre-Plantio"]
    colunas = ["Projeto", "Projeto", "Aprovado", "Sistematizacao", "Loc", "Pre_Plantio"]

    # Criar um dicionário para armazenar os valores
    data_reforma = {"Categoria": categorias}
    data_passagem = {"Categoria": categorias}
    data = {"Categoria": categorias}

######################## REFORMA ########################

    for unidade, nome in zip(["PPT", "NRD"], ["Paraguaçu", "Narandiba"]):
        unidade_area = df_reforma[(df_reforma["Unidade"] == unidade) & (df_reforma["Plano"] == "REFORMA PLANO A")]["Area"].sum()
        valores_reforma = []
        for coluna, categoria in zip(colunas, categorias):
            if categoria == "Em andamento":
                filtro = df_reforma["Projeto"] == "EM ANDAMENTO"
            else:
                filtro = df_reforma[coluna] == "OK"
            
            area_categoria = df_reforma[(df_reforma["Unidade"] == unidade) & (df_reforma["Plano"] == "REFORMA PLANO A") & filtro]["Area"].sum()
            porcentagem = (area_categoria / unidade_area) * 100 if unidade_area > 0 else 0
            valores_reforma.append(f"{porcentagem:,.0f}%")  # Formatar como porcentagem com 2 casas decimais
        data_reforma[nome] = valores_reforma

    # Calcular a média das porcentagens para cada categoria na tabela de Reforma
    media_grupo_cocal_reforma = []
    for i in range(len(categorias)):
        # Convertendo os valores para números e calculando a média
        media = (float(data_reforma["Paraguaçu"][i].replace("%", "").replace(",", ".")) + 
                float(data_reforma["Narandiba"][i].replace("%", "").replace(",", "."))) / 2
        
        # Formatando a média como porcentagem
        media_grupo_cocal_reforma.append(f"{media:,.0f}%")  # Formatar como porcentagem com 2 casas decimais

    # Adicionar a coluna 'Grupo Cocal' com a média das porcentagens na tabela de Reforma
    data_reforma["Grupo Cocal"] = media_grupo_cocal_reforma

    # Criar DataFrame para exibição
    df_metrica_reforma = pd.DataFrame(data_reforma)

######################## PASSAGEM ########################

    # Resetar o dicionário para a tabela de Passagem
    data_passagem = {"Categoria": categorias}

    for unidade, nome in zip(["PPT", "NRD"], ["Paraguaçu", "Narandiba"]):
        unidade_area = df_passagem[(df_passagem["Unidade"] == unidade)]["Area"].sum()
        valores_passagem = []
        for coluna, categoria in zip(colunas, categorias):
            if categoria == "Em andamento":
                filtro = df_passagem["Projeto"] == "EM ANDAMENTO"
            else:
                filtro = df_passagem[coluna] == "OK"
            
            area_categoria = df_passagem[(df_passagem["Unidade"] == unidade) & filtro]["Area"].sum()
            porcentagem = (area_categoria / unidade_area) * 100 if unidade_area > 0 else 0
            valores_passagem.append(f"{porcentagem:,.0f}%")  # Formatar como porcentagem com 2 casas decimais
        data_passagem[nome] = valores_passagem

    # Calcular a média das porcentagens para cada categoria na tabela de Passagem
    media_grupo_cocal_passagem = []
    for i in range(len(categorias)):
        # Convertendo os valores para números e calculando a média
        media = (float(data_passagem["Paraguaçu"][i].replace("%", "").replace(",", ".")) + 
                float(data_passagem["Narandiba"][i].replace("%", "").replace(",", "."))) / 2
        
        # Formatando a média como porcentagem
        media_grupo_cocal_passagem.append(f"{media:,.0f}%")  # Formatar como porcentagem com 2 casas decimais

    # Adicionar a coluna 'Grupo Cocal' com a média das porcentagens na tabela de Passagem
    data_passagem["Grupo Cocal"] = media_grupo_cocal_passagem

    # Criar DataFrame para exibição
    df_metrica_passagem = pd.DataFrame(data_passagem)

####################### GRÁFICO ########################

    # Divide a tela em 3 colunas
    col1, col2 = st.columns(2)

    with col1:
        # Criando opções de seleção para visualizar os dados
        opcao_tipo = st.selectbox("Selecione o tipo de acompanhamento:", ["Reforma", "Passagem"])

    with col2:
        opcao_visualizacao = st.selectbox("Selecione a unidade:", ["Grupo Cocal", "Paraguaçu", "Narandiba"])

    # Escolher qual DataFrame usar com base na seleção
    if opcao_tipo == "Reforma":
        df_selecionado = df_metrica_reforma[["Categoria", opcao_visualizacao]]
    else:
        df_selecionado = df_metrica_passagem[["Categoria", opcao_visualizacao]]

    df_selecionado = df_selecionado.rename(columns={opcao_visualizacao: "Porcentagem"})

    # Convertendo os valores de string para número
    df_selecionado["Porcentagem"] = df_selecionado["Porcentagem"].str.replace("%", "").str.replace(",", ".").astype(float)

    # Criando o gráfico dinâmico
    fig = px.bar(
        df_selecionado,
        x="Porcentagem",
        y="Categoria",
        orientation="h",
        text="Porcentagem",
        labels={"Porcentagem": "Porcentagem (%)", "Categoria": "Categoria"},
    )

    # Adicionar esta linha para fixar o eixo X até 100%
    fig.update_xaxes(range=[0, 105])

    fig.update_traces(marker_color="#76b82a", texttemplate="%{text:.0f}%", textposition='outside')

    fig.update_layout(
        showlegend=False,  
        xaxis=dict(showgrid=False, showticklabels=True, title='Porcentagem (%)', showline=False, zeroline=False),
        yaxis=dict(showgrid=False, showticklabels=True, title='', showline=False, zeroline=False)
    )

    # Exibir o gráfico dinâmico no Streamlit
    st.subheader(f"Acompanhamento de {opcao_tipo} - {opcao_visualizacao}")
    st.plotly_chart(fig)

####################### MAPA ########################

    st.divider()

    st.subheader("Mapa")

    # Exemplo: adicionando um parâmetro (verifique na documentação se 'scrollWheelZoom' está disponível)
    url_mapa = ("https://cocal.maps.arcgis.com/apps/Embed/index.html?"
                "webmap=e8cd98419206476ca3d0dc64bd12f93f&scrollWheelZoom=true")

    components.iframe(url_mapa, height=400, scrolling=True)

####################### TABELAS ########################

    st.divider()

    # Métricas de Reforma
    st.write("### Métricas de Reforma")
    st.dataframe(df_metrica_reforma, use_container_width=True, hide_index=True)

    st.divider()

    # Métricas de Passagem
    st.write("### Métricas de Passagem")
    st.dataframe(df_metrica_passagem, use_container_width=True, hide_index=True)

########################################## AUDITORIA ##########################################

# Função para calcular a aderência
def calcular_aderencia(planejado, executado):
    # Se os valores são strings (não numéricos)
    if isinstance(planejado, str) or isinstance(executado, str):
        # Remover espaços e converter para minúsculas para comparação
        planejado_str = str(planejado).strip().lower()
        executado_str = str(executado).strip().lower()
        
        # Se ambos estão vazios, considerar 100% de aderência
        if not planejado_str and not executado_str:
            return 100
        # Se um está vazio e outro não, considerar 0% de aderência
        if not planejado_str or not executado_str:
            return 0
        # Se são iguais, 100% de aderência
        if planejado_str == executado_str:
            return 100
        # Se são diferentes, 0% de aderência
        return 0
    
    # Para valores numéricos
    try:
        planejado_num = float(planejado)
        executado_num = float(executado)

        if planejado_num == 0 and executado_num == 0:
            return 100
        if planejado_num == 0 or executado_num == 0:
            return 0

        menor = min(planejado_num, executado_num)
        maior = max(planejado_num, executado_num)
        return (menor / maior) * 100
    
    except (ValueError, TypeError):
        # Se houver erro na conversão, tratar como strings
        return 100 if str(planejado).strip().lower() == str(executado).strip().lower() else 0

# Página de Auditoria
def auditoria():
    st.title("🔍 Auditoria")

    # Carregar os dados do banco de dados
    df_auditoria = carregar_auditoria()

    # Criar novas colunas de aderência para o DataFrame filtrado
    colunas_planejado = [col for col in df_auditoria.columns if "_Planejado" in col]
    colunas_executado = [col.replace("_Planejado", "_Executado") for col in colunas_planejado]

    # Aplicar a função calcular_aderencia para cada linha do DataFrame filtrado
    for planejado, executado in zip(colunas_planejado, colunas_executado):
        df_auditoria[f"Aderência_{planejado.replace('_Planejado', '')}"] = df_auditoria.apply(
            lambda row: calcular_aderencia(row[planejado], row[executado]), axis=1
        )

    # Criar tabela formatada
    colunas_tabela = ["Unidade", "Setor"] + colunas_planejado + colunas_executado + [f"Aderência_{col.replace('_Planejado', '')}" for col in colunas_planejado]
    df_tabela = df_auditoria[colunas_tabela]

    # Identificar colunas numéricas e formatá-las corretamente
    colunas_numericas = df_tabela.select_dtypes(include=["number"]).columns

    # Formatar os valores numéricos diretamente no DataFrame
    for col in colunas_numericas:
        df_tabela[col] = df_tabela[col].apply(lambda x: f"{x:.0f}")

    # Calcular a média de cada item de aderência (como "Aderência_Levantes", "Aderência_Bigodes", etc.)
    colunas_aderencia = [col for col in df_auditoria.columns if "Aderência" in col]

    df_media_itens = df_auditoria[colunas_aderencia].mean().reset_index()
    df_media_itens.columns = ["Item", "Média Aderência (%)"]

    # Dicionário para renomear os itens
    renomear_itens = {
        "Aderência_Levantes": "Levantes",
        "Aderência_Bigodes": "Bigodes",
        "Aderência_TipoPlantio": "Tipo de plantio",
        "Aderência_TipoTerraco": "Tipo de terraço",
        "Aderência_QuantidadeTerraco": "Quantidade de terraço",
        "Aderência_LevantesDesmanche": "Levantes para desmanche",
        "Aderência_BigodesDesmanche": "Bigodes para desmanche",
        "Aderência_Carreadores": "Carreadores"
    }

    # Renomear os itens de acordo com o dicionário
    df_media_itens["Item"] = df_media_itens["Item"].map(renomear_itens).fillna(df_media_itens["Item"])

    # Criar gráfico de barras horizontais com a média de cada item
    fig_aderencia = px.bar(df_media_itens, 
                        x="Item",                 
                        y="Média Aderência (%)",  
                        text="Média Aderência (%)",
                        orientation="v",         
                        color="Item",             
                        color_discrete_sequence=px.colors.qualitative.Set1,  
                        )

    # Ajustar a posição do rótulo para fora da barra
    fig_aderencia.update_traces(textposition='outside')

    # Ajustar os valores no gráfico para mostrar sem casas decimais
    fig_aderencia.update_traces(texttemplate='%{text:.0f}%')

    fig_aderencia.update_layout(
        showlegend=False,  
        xaxis=dict(showgrid=False, showticklabels=True, title='', showline=False, zeroline=False),
        yaxis=dict(showgrid=False, showticklabels=False, showline=False, zeroline=False))

    # Exibir gráfico
    st.write("### Aderência")
    st.plotly_chart(fig_aderencia, use_container_width=True)

    st.divider()

    # Tabela de auditoria
    st.write("### Detalhes das Auditorias")
    df_auditoria_display = df_auditoria
    df_auditoria_display["Data"] = pd.to_datetime(df_auditoria_display["Data"]).dt.strftime("%d/%m/%Y")
    
    # Criar um editor de dados com funcionalidade de exclusão de linhas
    df_editado = st.data_editor(
        df_auditoria_display,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "DELETE": st.column_config.CheckboxColumn(
                "Excluir",
                help="Selecione para excluir a linha",
                default=False
            ),
            "Setor": st.column_config.NumberColumn(
                "Setor",
                format="%d"  # Formato inteiro sem decimais
            ),
        }
    )

    # Botão para salvar alterações
    if st.button("Salvar Alterações"):
        try:
            # Remover linhas marcadas para exclusão
            if "DELETE" in df_editado.columns:
                df_editado = df_editado[~df_editado["DELETE"]]
                df_editado = df_editado.drop(columns=["DELETE"])
            
            # Converter colunas de data para o formato 'yyyy-mm-dd
            for col in df_editado.columns:
                if 'data' in col.lower():
                    df_editado[col] = pd.to_datetime(df_editado[col], errors='coerce').dt.strftime('%Y-%m-%d')
                    # # Adiciona apenas um apóstrofo no início da string
                    # df_editado[col] = "'" + df_editado[col]
            
            # Atualizar a planilha
            worksheet = get_worksheet("Auditoria")
            if worksheet is not None:
                # Limpar e reescrever todos os dados
                worksheet.clear()
                headers = df_editado.columns.tolist()
                worksheet.append_row(headers)
                worksheet.append_rows(df_editado.values.tolist())
                
                # Limpar o cache e mostrar mensagem de sucesso
                st.cache_data.clear()
                st.success("Dados atualizados com sucesso!")
                st.rerun()
        except Exception as e:
            st.error(f"Erro ao salvar alterações: {str(e)}")

########################################## EXTRAS ##########################################

# Página de Atividades Extras
def atividades_extras():
    st.title("📌 Atividades Extras")
    
    # Carregar os dados do banco de dados
    df_extras = carregar_atividades_extras()

    # Verificar se há dados
    if df_extras.empty:
        st.info("Nenhuma atividade extra registrada.")
        return
    
    # Aplicando os filtros e retornando o DataFrame filtrado
    df_extras = filtros_extras(df_extras)
    
    # Gráfico 1: Quantidade de Atividades por Colaborador
    col1, linha, col2 = st.columns([4, 0.5, 4])

    with col1:
        atividade_colab = df_extras.groupby('Colaborador').size().reset_index(name="Quantidade de Atividades")
        atividade_colab = atividade_colab.sort_values(by="Quantidade de Atividades", ascending=False)
        fig_colab = px.bar(
            atividade_colab, 
            x="Colaborador", 
            y="Quantidade de Atividades", 
            title="Atividades por Colaborador",
            color="Colaborador",  # Colorir as barras por colaborador
            text="Quantidade de Atividades",  # Adicionar o texto na barra
        )
        fig_colab.update_traces(texttemplate="%{text}", textposition="outside")
        fig_colab.update_layout(
            showlegend=False,  # Não mostrar a legenda
            xaxis=dict(showgrid=False, showticklabels=True, title='', showline=False, zeroline=False),
            yaxis=dict(showgrid=False, showticklabels=False, title='', showline=False, zeroline=False),
            title_font_size=24
        )
        st.plotly_chart(fig_colab, use_container_width=True)
    
    # Gráfico 2: Quantidade de Atividades por Setor Solicitante
    with col2:
        atividade_setor = df_extras.groupby('SetorSolicitante').size().reset_index(name="Quantidade de Atividades")
        fig_setor = px.pie(
            atividade_setor, 
            names="SetorSolicitante", 
            values="Quantidade de Atividades", 
            title="Atividades por Setor Solicitante"
        )
        # Aumentar o tamanho da fonte do título
        fig_setor.update_layout(
            title_font_size=24
        )
        fig_setor.update_traces(textinfo="value")  # Mostrar os valores absolutos (quantidade)
        st.plotly_chart(fig_setor, use_container_width=True)
    
    # Tabela
    st.write("### Detalhes das Atividades")

    # Ordenar e preparar dataframe
    df_extras_ordenado = df_extras.sort_values(by="Data", ascending=False).reset_index(drop=True)
    atividades_realizadas = df_extras_ordenado[["Data", "Colaborador", "Atividade", "Solicitante", "SetorSolicitante", "Horas"]]

    # Criar um editor de dados
    df_editado = st.data_editor(
        atividades_realizadas,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "Data": st.column_config.DateColumn(
                "Data",
                format="DD/MM/YYYY",
                help="Selecione a data da atividade"
            ),
            "Colaborador": st.column_config.SelectboxColumn(
                "Colaborador",
                options=["Ana", "Camila", "Gustavo", "Maico", "Márcio", "Pedro", "Talita", "Washington", "Willian", "Iago"]
            ),
            "Atividade": st.column_config.SelectboxColumn(
                "Atividade",
                options=["Impressão de Mapa", "Voo com drone", "Mapa", "Tematização de mapa", 
                        "Processamento", "Projeto", "Outro"]
            ),
            "SetorSolicitante": st.column_config.TextColumn(  # Alterado para TextColumn
                "Setor Solicitante",
                help="Digite o número do setor ou outra identificação"
            ),
            "Horas": st.column_config.TextColumn(  # Alterado para TextColumn
                "Horas",
                help="Digite o tempo gasto (formato livre, ex: 1.5 ou 1:30)",
                default="0"
            ),
            "DELETE": st.column_config.CheckboxColumn(
                "Excluir",
                help="Selecione para excluir a linha",
                default=False
            )
        }
    )

    # Botão para salvar alterações
    if st.button("Salvar Alterações"):
        try:
            # Remover linhas marcadas para exclusão
            if "DELETE" in df_editado.columns:
                df_editado = df_editado[~df_editado["DELETE"]]
                df_editado = df_editado.drop(columns=["DELETE"])
            
            # Converter formatos para compatibilidade
            df_editado["Data"] = pd.to_datetime(df_editado["Data"], errors='coerce')
            
            # Atualizar a planilha
            if update_sheet(df_editado, "AtividadesExtras"):
                st.success("Dados atualizados com sucesso!")
                st.rerun()
                
        except Exception as e:
            st.error(f"Erro ao salvar alterações: {str(e)}")

########################################## FILTROS ##########################################

# Função para filtros da aba Dashboard
def filtros_dashboard(df):
    df = df.copy()  # Trabalhar com uma cópia para não afetar o DataFrame original
    if not df.empty:
        df['Data'] = pd.to_datetime(df['Data'], errors='coerce')

    st.sidebar.title("Filtros")

    # Verificar se há dados
    if not df.empty:
        data_min = df['Data'].min().date()
        data_max = df['Data'].max().date()
    else:
        data_min = data_max = datetime.today().date()

    # Se as datas forem iguais, adiciona um dia a `data_max`
    if data_min == data_max:
        data_max = data_max + pd.Timedelta(days=1)
    
    # Barra deslizante para selecionar o intervalo de datas
    data_inicio, data_fim = st.sidebar.slider(
        "Intervalo de datas",
        min_value=data_min,
        max_value=data_max,
        value=(data_min, data_max),
        format="DD/MM/YYYY"
    )

    # Convertendo novamente para datetime para aplicar no filtro
    data_inicio = pd.to_datetime(data_inicio)
    data_fim = pd.to_datetime(data_fim)

    # Filtrando o DataFrame com base nas datas selecionadas
    df_tarefas = df[(df["Data"] >= data_inicio) & 
                            (df["Data"] <= data_fim)]
    
    # Filtro de Colaborador
    colaboradores_unicos = df_tarefas["Colaborador"].unique()  # Obter a lista de colaboradores únicos
    colaboradores_unicos = ["Todos"] + list(colaboradores_unicos)  # Adiciona a opção "Todos"
    
    # Selecionando apenas "Todos" inicialmente
    colaboradores_selecionados = st.sidebar.multiselect(
        "Colaboradores",
        options=colaboradores_unicos,
        default=["Todos"]  # Seleciona apenas "Todos" por padrão
    )

        # Filtro de Tipo com opção de "Todos"
    tipos_unicos = df_tarefas["Tipo"].unique()  # Obter a lista de tipos únicos
    tipos_unicos = ["Todos"] + list(tipos_unicos)  # Adiciona a opção "Todos"
    
    # Selecionando apenas "Todos" inicialmente
    tipos_selecionados = st.sidebar.multiselect(
        "Tipos de Atividade",
        options=tipos_unicos,
        default=["Todos"]  # Seleciona apenas "Todos" por padrão
    )

    # Filtrando o DataFrame com base no(s) colaborador(es) selecionado(s)
    if "Todos" in colaboradores_selecionados:
        # Se "Todos" estiver selecionado, não filtra por colaborador
        df_tarefas = df_tarefas
    else:
        df_tarefas = df_tarefas[df_tarefas["Colaborador"].isin(colaboradores_selecionados)]
    
    # Filtrando o DataFrame com base no(s) tipo(s) selecionado(s)
    if "Todos" in tipos_selecionados:
        # Se "Todos" estiver selecionado, não filtra por tipo
        df_tarefas = df_tarefas
    else:
        df_tarefas = df_tarefas[df_tarefas["Tipo"].isin(tipos_selecionados)]

    return df_tarefas

def filtros_atividades(df_tarefas):
    st.sidebar.header("Filtros")

    if df_tarefas.empty:
        return df_tarefas
    
    # Converter coluna Data para datetime
    df_tarefas['Data'] = pd.to_datetime(df_tarefas['Data'], errors='coerce')
    
    # Verificar se há dados suficientes
    if df_tarefas.empty or df_tarefas['Data'].nunique() < 2:
        st.warning("Não há dados suficientes para exibir o filtro de datas.")
        return df_tarefas
    
    # Definir min_date e max_date
    min_date = df_tarefas['Data'].min().to_pydatetime()
    max_date = df_tarefas['Data'].max().to_pydatetime()
    
    # Se as datas forem iguais, ajustar o intervalo
    if min_date == max_date:
        min_date = min_date - timedelta(days=1)  # Subtrai 1 dia do min_date
        max_date = max_date + timedelta(days=1)  # Adiciona 1 dia ao max_date
    
    # Criar slider de datas
    data_inicio, data_fim = st.sidebar.slider(
        "Selecione o período:",
        min_value=min_date,
        max_value=max_date,
        value=(min_date, max_date),
        format="DD/MM/YYYY"
    )
    
    # Aplicar filtros
    df_tarefas = df_tarefas[
        (df_tarefas['Data'] >= data_inicio) & 
        (df_tarefas['Data'] <= data_fim)
    ]
    
    return df_tarefas

# Função para filtros da aba Extras
def filtros_extras(df_extras):

    st.sidebar.title("Filtros")

    if df_extras.empty:
        return df_extras

    # Garantir que a coluna "Data" está em formato datetime
    df_extras["Data"] = pd.to_datetime(df_extras["Data"], errors='coerce')

    # Definindo o intervalo de datas
    data_min = df_extras["Data"].min().date()  # Convertendo para date
    data_max = df_extras["Data"].max().date()  # Convertendo para date

    # Se as datas forem iguais, adiciona um dia a data_max
    if data_min == data_max:
        data_max = data_max + pd.Timedelta(days=1)
    
    # Barra deslizante para selecionar o intervalo de datas
    data_inicio, data_fim = st.sidebar.slider(
        "Selecione o intervalo de datas",
        min_value=data_min,
        max_value=data_max,
        value=(data_min, data_max),
        format="DD/MM/YYYY"
    )

    # Convertendo novamente para datetime para aplicar no filtro
    data_inicio = pd.to_datetime(data_inicio)
    data_fim = pd.to_datetime(data_fim)

    # Filtrando o DataFrame com base nas datas selecionadas
    df_extras = df_extras[(df_extras["Data"] >= data_inicio) & 
                                   (df_extras["Data"] <= data_fim)]
    
    return df_extras

# Função para filtros da aba Auditoria
def filtros_auditoria(df_auditoria):
    st.sidebar.title("Filtros")

    # Filtro de Data - Mês e Ano
    # Garantir que a coluna "Data" está em formato datetime
    df_auditoria["Data"] = pd.to_datetime(df_auditoria["Data"], errors='coerce')

    # Extraindo ano e mês para um filtro de seleção
    df_auditoria['Ano_Mes'] = df_auditoria["Data"].dt.to_period('M')

    # Lista de Ano-Mês únicos
    anos_mes_unicos = df_auditoria['Ano_Mes'].unique()
    anos_mes_unicos = sorted(anos_mes_unicos, reverse=True)  # Ordenando do mais recente para o mais antigo

    # Adicionando a opção de "Todos os dados"
    anos_mes_unicos = ["Todos os dados"] + list(anos_mes_unicos)

    # Barra de seleção para escolher o ano e mês
    ano_mes_selecionado = st.sidebar.selectbox(
        "Selecione o Mês e Ano",
        options=anos_mes_unicos,
        format_func=lambda x: x.strftime('%m/%Y') if isinstance(x, pd.Period) else x  # Exibindo o formato mês/ano
    )

    # Filtrando o DataFrame com base no mês e ano selecionados
    if ano_mes_selecionado != "Todos os dados":
        df_auditoria = df_auditoria[df_auditoria['Ano_Mes'] == ano_mes_selecionado]

    # Filtro de Setor - Seleção de apenas 1 setor por vez
    setores_unicos = df_auditoria["Setor"].unique()  # Obter a lista de setores únicos
    setores_unicos = sorted(set(setores_unicos))  # Ordenando os setores do menor para o maior
    setores_unicos = ["Selecione o setor"] + list(setores_unicos)  # Adiciona a opção de "Selecione o setor"
    
    # Seleção do setor
    setor_selecionado = st.sidebar.selectbox(
        "Selecione o Setor",
        options=setores_unicos,
        index=0  # Definindo como padrão a opção "Selecione o setor"
    )

    # Filtrando o DataFrame com base no setor selecionado
    if setor_selecionado != "Selecione o setor":
        df_auditoria = df_auditoria[df_auditoria["Setor"] == setor_selecionado]

    return df_auditoria

########################################## PÁGINA PRINCIPAL ##########################################

# Página Principal
def main_app():
    
    st.sidebar.image("imagens/logo-cocal.png")
    st.sidebar.title("Menu")
    menu_option = st.sidebar.radio(
        "Selecione a funcionalidade:",
        ("Dashboard", "Registrar", "Atividades", "Reforma e Passagem", "Auditoria", "Extras")
    )

    st.sidebar.markdown("---")  # Linha separadora

    if menu_option == "Dashboard":
        dashboard()
    elif menu_option == "Registrar":
        registrar_atividades()
    elif menu_option == "Atividades":
        tarefas_semanais()
    elif menu_option == "Reforma e Passagem":
        acompanhamento_reforma_passagem()
    elif menu_option == "Auditoria":
        auditoria()
    elif menu_option == "Extras":
        atividades_extras()

########################################## EXECUÇÃO ##########################################

if __name__ == "__main__":
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = True

    try:
        if st.session_state["logged_in"]:
            main_app()
    except Exception as e:
        st.error(f"Erro ao executar a aplicação: {e}")
        st.stop()