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
    "Expansão": "2099988266",
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
    # Verificar se os dados já estão em cache na sessão
    cache_key = f"raw_data_{sheet_name}"
    
    # Tentar recuperar do cache da sessão primeiro
    if cache_key in st.session_state and "last_updated" in st.session_state:
        # Verificar se o cache ainda é válido (menos de 1 hora)
        time_diff = datetime.now() - st.session_state["last_updated"].get(sheet_name, datetime.min)
        if time_diff.total_seconds() < 3600:  # 1 hora em segundos
            return st.session_state[cache_key]
    
    # Se não estiver em cache ou o cache estiver expirado, carregar do Google Sheets
    def _load():
        worksheet = get_worksheet(sheet_name)
        if worksheet is None:
            return pd.DataFrame()
            
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    
    result = retry_with_backoff(_load)
    
    # Se carregou com sucesso, atualizar o cache
    if result is not None and not result.empty:
        st.session_state[cache_key] = result
        
        # Inicializar ou atualizar o dicionário de timestamps
        if "last_updated" not in st.session_state:
            st.session_state["last_updated"] = {}
        
        # Atualizar o timestamp para esta planilha
        st.session_state["last_updated"][sheet_name] = datetime.now()
    
    return result if result is not None else pd.DataFrame()

def update_sheet(df: pd.DataFrame, sheet_name: str) -> bool:
    def _update():
        try:
            # Criar uma cópia do DataFrame para não modificar o original
            df_copy = df.copy()
            df_copy['Data'] = pd.to_datetime(df_copy['Data'], errors='coerce', format="%Y-%m-%d")
            df_copy = df_copy.dropna(subset=["Data"])
            
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
    "Expansão": "2099988266",
    "Pós": "1874058370"
}

# Constantes para diretórios e arquivos
PASTA_POS = "dados/pos-aplicacao"
ARQUIVO_POS_CSV = "dados/pos_aplicacao.csv"

# Função para carregar dados sob demanda usando o sistema de sessão do Streamlit
def get_data(data_type):
    """
    Carrega dados sob demanda e armazena na sessão para evitar recarregamentos desnecessários.
    
    Args:
        data_type: Tipo de dados a serem carregados (tarefas, extras, auditoria, etc.)
    
    Returns:
        DataFrame com os dados solicitados
    """
    # Criar chave para a sessão
    session_key = f"data_{data_type}"
    
    # Verificar se os dados já estão na sessão
    if session_key not in st.session_state:
        # Carregar dados conforme o tipo solicitado
        if data_type == "tarefas":
            st.session_state[session_key] = carregar_tarefas()
        elif data_type == "extras":
            st.session_state[session_key] = carregar_atividades_extras()
        elif data_type == "auditoria":
            st.session_state[session_key] = carregar_auditoria()
        elif data_type == "reforma":
            st.session_state[session_key] = carregar_reforma()
        elif data_type == "expansao":
            st.session_state[session_key] = carregar_expansao()
        elif data_type == "base":
            st.session_state[session_key] = carregar_dados_base()
        elif data_type == "pos":
            st.session_state[session_key] = carregar_dados_pos()
    
    return st.session_state[session_key]

# Função para limpar o cache de dados quando necessário
def clear_data_cache(data_type=None):
    """
    Limpa o cache de dados para forçar o recarregamento.
    
    Args:
        data_type: Tipo específico de dados para limpar ou None para limpar todos
    """
    if data_type:
        session_key = f"data_{data_type}"
        if session_key in st.session_state:
            del st.session_state[session_key]
    else:
        # Limpar todos os caches de dados
        keys_to_delete = [k for k in st.session_state.keys() if k.startswith("data_")]
        for key in keys_to_delete:
            del st.session_state[key]

@st.cache_data(ttl=3600)  # Aumentado para 1 hora
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

@st.cache_data(ttl=3600)  # Aumentado para 1 hora
def carregar_atividades_extras():
    """Carrega os dados de atividades extras."""
    df = load_data("AtividadesExtras")
    if not df.empty and "Data" in df.columns:
        df["Data"] = pd.to_datetime(df["Data"], errors='coerce', format="%Y-%m-%d")
        df = df.dropna(subset=["Data"])
    return df

@st.cache_data(ttl=3600)  # Aumentado para 1 hora
def carregar_auditoria():
    """Carrega os dados de auditoria."""
    df = load_data("Auditoria")
    if not df.empty and "Data" in df.columns:
        df["Data"] = pd.to_datetime(df["Data"], errors='coerce', format="%Y-%m-%d")
        df = df.dropna(subset=["Data"])
    return df

@st.cache_data(ttl=3600)  # Aumentado para 1 hora
def carregar_dados_base():
    """Carrega e formata os dados base."""
    df = load_data("Base")
    if not df.empty and "Setor" in df.columns:
        df["Setor"] = pd.to_numeric(df["Setor"], errors='coerce').fillna(0).astype(int)
    return df

@st.cache_data(ttl=3600)  # Aumentado para 1 hora
def carregar_reforma() -> pd.DataFrame:
    """Carrega os dados de reforma."""
    df = load_data("Reforma")
    
    # Verificar e normalizar nomes de colunas
    if not df.empty:
        # Normalizar os nomes das colunas (remover espaços extras e converter para string)
        df.columns = [col.strip() for col in df.columns]
        
        # Converter a coluna Unidade para string
        if "Unidade" in df.columns:
            df["Unidade"] = df["Unidade"].astype(str).str.strip()
        
        # Garantir que a coluna Area seja numérica
        if "Area" in df.columns:
            df["Area"] = pd.to_numeric(df["Area"], errors='coerce').fillna(0)
    
    return df

@st.cache_data(ttl=3600)  # Aumentado para 1 hora
def carregar_expansao() -> pd.DataFrame:
    """Carrega os dados de expansão."""
    df = load_data("Expansão")
    
    # Verificar e normalizar nomes de colunas
    if not df.empty:
        # Normalizar os nomes das colunas (remover espaços extras e converter para string)
        df.columns = [col.strip() for col in df.columns]
        
        # Converter a coluna Unidade para string
        if "Unidade" in df.columns:
            df["Unidade"] = df["Unidade"].astype(str).str.strip()
        
        # Garantir que a coluna Area seja numérica
        if "Area" in df.columns:
            df["Area"] = pd.to_numeric(df["Area"], errors='coerce').fillna(0)
    
    return df

@st.cache_data(ttl=3600)  # Aumentado para 1 hora
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
df_tarefas = get_data("tarefas")
df_extras = get_data("extras")
df_auditoria = get_data("auditoria")
df_reforma = get_data("reforma")
df_expansao = get_data("expansao")
df_base = get_data("base")
df_pos = get_data("pos")

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
        df_tarefas = get_data("tarefas")
    
    # Se o DataFrame estiver vazio, exibe mensagem e retorna
    if df_tarefas.empty:
        st.info("Nenhuma tarefa registrada.")
        return

    # Mesclar com df_base (dados auxiliares vindos de CSV) para obter 'Area' e 'Unidade'
    df_base = get_data("base")
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
    df_pos = get_data("pos")
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
                options=["Projeto de Sistematização", "Mapa de Sistematização", "LOC", "Projeto de Transbordo", "Projeto de Fertirrigação", "Projeto de Sulcação", 
                        "Mapa de Pré-Plantio", "Mapa de Pós-Plantio", "Projeto de Colheita", "Mapa de Cadastro"]
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
        ("Atividade Semanal", "Atividade Extra", "Reforma e Expansão", "Pós-Aplicação", "Auditoria")
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

    # Formulário para Reforma e Expansão
    elif tipo_atividade == "Reforma e Expansão":
        opcao = st.radio("Selecione a planilha para editar:", ["Reforma", "Expansão"])
        
        # Carregar os dados apropriados
        if opcao == "Reforma":
            df_editavel = get_data("reforma")
        else:
            df_editavel = get_data("expansao")
            
        # Verificar se a coluna Setor existe
        if "Setor" not in df_editavel.columns:
            # Tentar encontrar variações do nome da coluna
            for col in df_editavel.columns:
                if col.lower() in ["setor", "numero_setor", "num_setor", "nº setor", "n° setor"]:
                    df_editavel = df_editavel.rename(columns={col: "Setor"})
                    break
            # Se ainda não existir, criar a coluna
            if "Setor" not in df_editavel.columns:
                df_editavel["Setor"] = 0
        
        # Converter Setor para numérico para garantir ordenação correta
        df_editavel["Setor"] = pd.to_numeric(df_editavel["Setor"], errors='coerce').fillna(0).astype(int)
        
        # Ordenar o DataFrame pelo número do setor em ordem crescente
        df_editavel = df_editavel.sort_values(by="Setor")
        
        # Adicionar filtros em duas colunas
        st.markdown("#### 🔍 Filtros")
        
        # Criar layout de duas colunas para os filtros
        col1, col2 = st.columns(2)
        
        with col1:
            # Obter lista de setores únicos
            setores_unicos = sorted(df_editavel["Setor"].unique())
            
            # Criar um campo de texto para filtrar por setor
            filtro_setor = st.text_input("Digite o número do setor:")
            
            # Aplicar filtro se o usuário digitar algo
            if filtro_setor:
                try:
                    setor_filtrado = int(filtro_setor)
                    df_editavel = df_editavel[df_editavel["Setor"] == setor_filtrado]
                except ValueError:
                    st.warning("Por favor, digite um número válido para o setor")
        
        with col2:
            # Obter valores únicos da coluna Projeto
            projetos_unicos = ["Todos"] + sorted([str(p) for p in df_editavel["Projeto"].unique() if str(p) != "nan"])
            
            # Criar um seletor para filtrar por status do Projeto
            filtro_projeto = st.selectbox("Filtrar por status do Projeto:", options=projetos_unicos)
            
            # Aplicar filtro se o usuário selecionar um valor diferente de "Todos"
            if filtro_projeto != "Todos":
                df_editavel = df_editavel[df_editavel["Projeto"] == filtro_projeto]
        
        # Criar um editor de dados
        df_editado = st.data_editor(
            df_editavel,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                "Setor": st.column_config.NumberColumn(
                    "Setor",
                    min_value=0,
                    step=1,
                    format="%d"
                ),
                "Unidade": st.column_config.SelectboxColumn(
                    "Unidade",
                    options=["21", "22"]
                ),
                "Area": st.column_config.NumberColumn(
                    "Area",
                    min_value=0.0,
                    format="%.2f"
                ),
                "Plano": st.column_config.SelectboxColumn(
                    "Plano",
                    options=["Plano A", "Plano B"]
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
                df_original = pd.read_excel(arquivo)
                
                # Mapeamento de possíveis nomes de colunas
                mapeamento_colunas = {
                    "DESC_OPERAÇÃO": ["desc_operação", "desc_operacao", "descricao_operacao", "descricao", "operacao", "operação", "desc operação", "desc operacao", "tipo operacao", "tipo_operacao", "tipo de operação", "tipo_operação"],
                    "DATA": ["data", "dt", "dt_operacao", "dt_operação", "data_operacao", "data_operação", "data operacao", "data operação", "date"],
                    "SETOR": ["setor", "num_setor", "numero_setor", "nº setor", "n° setor", "n setor", "setor_num", "setor numero", "numero do setor"],
                    "TALHÃO": ["talhão", "talhao", "talh", "num_talhao", "numero_talhao", "nº talhao", "n° talhao", "n talhao", "talhao_num", "talhao numero", "numero do talhao"],
                    "AREA": ["area", "área", "hectares", "ha", "tamanho", "tam", "area_ha", "área_ha", "area(ha)", "área(ha)"]
                }
                
                # Função para encontrar a coluna correspondente
                def encontrar_coluna(df, nomes_possiveis):
                    colunas_df = [col.lower().strip() for col in df.columns]
                    for nome in nomes_possiveis:
                        if nome.lower().strip() in colunas_df:
                            idx = colunas_df.index(nome.lower().strip())
                            return df.columns[idx]  # Retorna o nome original da coluna
                    return None
                
                # Encontrar as colunas necessárias
                colunas_encontradas = {}
                colunas_nao_encontradas = []
                
                for coluna_padrao, alternativas in mapeamento_colunas.items():
                    coluna_encontrada = encontrar_coluna(df_original, [coluna_padrao] + alternativas)
                    if coluna_encontrada:
                        colunas_encontradas[coluna_padrao] = coluna_encontrada
                    else:
                        colunas_nao_encontradas.append(coluna_padrao)
                
                # Verificar se todas as colunas necessárias foram encontradas
                if colunas_nao_encontradas:
                    st.error(f"Não foi possível encontrar as seguintes colunas obrigatórias: {', '.join(colunas_nao_encontradas)}")
                    st.info("Verifique se a planilha contém estas informações com nomes diferentes e entre em contato com o suporte.")
                    return
                
                # Criar um novo DataFrame com as colunas padronizadas
                df = pd.DataFrame()
                for coluna_padrao, coluna_original in colunas_encontradas.items():
                    df[coluna_padrao] = df_original[coluna_original]
                
                # Processar dados
                df["DATA"] = pd.to_datetime(df["DATA"], errors="coerce").dt.strftime("%Y-%m-%d")
                df = df.dropna(subset=["DATA"])
                df["SETOR"] = pd.to_numeric(df["SETOR"], errors='coerce').fillna(0).astype(int)
                df["AREA"] = pd.to_numeric(df["AREA"], errors='coerce').fillna(0)
                
                # Mostrar preview dos dados processados
                st.write("### Preview dos dados processados:")
                st.dataframe(df.head())
                
                # Salvar dados
                if st.button("Salvar"):
                    # Carregar dados existentes
                    df_existente = get_data("pos")
                    
                    # Preparar para análise de duplicatas
                    novos_registros = []
                    registros_duplicados = []
                    
                    # Verificar se há dados existentes
                    if not df_existente.empty:
                        # Converter para tipos adequados para comparação
                        if "DATA" in df_existente.columns:
                            df_existente["DATA"] = df_existente["DATA"].astype(str)
                        if "SETOR" in df_existente.columns:
                            df_existente["SETOR"] = df_existente["SETOR"].astype(int)
                        if "DESC_OPERAÇÃO" in df_existente.columns:
                            df_existente["DESC_OPERAÇÃO"] = df_existente["DESC_OPERAÇÃO"].astype(str)
                        if "TALHÃO" in df_existente.columns:
                            df_existente["TALHÃO"] = df_existente["TALHÃO"].astype(str)
                    
                    # Verificar cada registro do arquivo
                    for _, row in df.iterrows():
                        # Criar o dicionário com os dados do registro
                        dados = {
                            "DESC_OPERAÇÃO": str(row["DESC_OPERAÇÃO"]).strip(),
                            "DATA": str(row["DATA"]).strip(),
                            "SETOR": int(row["SETOR"]),
                            "TALHÃO": str(row["TALHÃO"]).strip(),
                            "AREA": float(row["AREA"])
                        }
                        
                        # Verificar se já existe no DataFrame existente
                        duplicado = False
                        
                        if not df_existente.empty:
                            # Criar máscara para cada coluna de comparação
                            mask_desc = df_existente["DESC_OPERAÇÃO"] == dados["DESC_OPERAÇÃO"]
                            mask_data = df_existente["DATA"] == dados["DATA"]
                            mask_setor = df_existente["SETOR"] == dados["SETOR"]
                            mask_talhao = df_existente["TALHÃO"] == dados["TALHÃO"]
                            
                            # Combinar todas as máscaras
                            mask_completa = mask_desc & mask_data & mask_setor & mask_talhao
                            
                            # Verificar se existe algum registro que atenda a todas as condições
                            duplicado = mask_completa.any()
                        
                        # Adicionar à lista apropriada
                        if duplicado:
                            registros_duplicados.append(dados)
                        else:
                            novos_registros.append(dados)
                            # Adicionar ao DataFrame existente para evitar duplicatas no próprio arquivo
                            novo_df = pd.DataFrame([dados])
                            df_existente = pd.concat([df_existente, novo_df], ignore_index=True)
            
                    # Salvar novos registros
                    total_registros = len(novos_registros) + len(registros_duplicados)
                    
                    if novos_registros:
                        # Definir tamanho do lote para envio
                        tamanho_lote = 20  # Ajuste este valor conforme necessário
                        total_lotes = (len(novos_registros) + tamanho_lote - 1) // tamanho_lote
                        
                        # Criar um DataFrame para backup local
                        df_backup = pd.DataFrame(novos_registros)
                        
                        # Salvar backup local em caso de falha
                        os.makedirs(PASTA_POS, exist_ok=True)
                        nome_backup = f"{PASTA_POS}/backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                        df_backup.to_csv(nome_backup, index=False)
                        
                        # Inicializar contadores
                        registros_salvos = 0
                        falhas = 0
                        
                        # Criar barra de progresso
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        try:
                            # Processar em lotes
                            for i in range(0, len(novos_registros), tamanho_lote):
                                # Obter o lote atual
                                lote_atual = novos_registros[i:i+tamanho_lote]
                                lote_num = i // tamanho_lote + 1
                                
                                # Atualizar status
                                status_text.text(f"Processando lote {lote_num} de {total_lotes} ({len(lote_atual)} registros)...")
                                
                                # Enviar lote para o Google Sheets
                                for dados in lote_atual:
                                    sucesso = append_to_sheet(dados, "Pós")
                                    if sucesso:
                                        registros_salvos += 1
                                    else:
                                        falhas += 1
                                
                                # Atualizar barra de progresso
                                progress_bar.progress((i + len(lote_atual)) / len(novos_registros))
                                
                                # Pausa entre lotes para evitar limites de API
                                if i + tamanho_lote < len(novos_registros):
                                    time.sleep(1)  # Pausa de 1 segundo entre lotes
                            
                            # Limpar cache para forçar recarregamento dos dados
                            clear_data_cache("pos")
                            
                            # Mostrar mensagem de sucesso com detalhes
                            progress_bar.progress(1.0)
                            status_text.empty()
                            
                            if falhas > 0:
                                st.warning(f"⚠️ {registros_salvos} de {len(novos_registros)} registros foram salvos com sucesso. {falhas} registros não puderam ser salvos.")
                                st.info(f"Um backup foi salvo em {nome_backup} para que você possa tentar novamente mais tarde.")
                            else:
                                st.success(f"✅ {registros_salvos} de {total_registros} registros foram salvos com sucesso!")
                                # Remover arquivo de backup se tudo deu certo
                                if os.path.exists(nome_backup):
                                    os.remove(nome_backup)
                        
                        except Exception as e:
                            # Em caso de erro, mostrar mensagem e informações sobre o backup
                            st.error(f"Erro ao salvar registros: {str(e)}")
                            st.info(f"Um backup foi salvo em {nome_backup} para que você possa tentar novamente mais tarde.")
                            import traceback
                            st.expander("Detalhes do erro", expanded=False).code(traceback.format_exc())
                    else:
                        st.warning("Nenhum novo registro para salvar.")
                    
                    # Mostrar novos registros e duplicados
                    col1, col2 = st.columns(2)
                    with col1:
                        with st.expander(f"Novos registros ({len(novos_registros)})"):
                            if novos_registros:
                                st.dataframe(pd.DataFrame(novos_registros))
                            else:
                                st.write("Nenhum novo registro")
                    
                    with col2:
                        with st.expander(f"Registros duplicados ({len(registros_duplicados)})"):
                            if registros_duplicados:
                                st.dataframe(pd.DataFrame(registros_duplicados))
                            else:
                                st.write("Nenhum registro duplicado")
                    
            except Exception as e:
                st.error(f"Erro ao processar arquivo: {str(e)}")
                import traceback
                st.expander("Detalhes do erro", expanded=False).code(traceback.format_exc())

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

    # Adicionar CSS personalizado para melhorar a aparência
    st.markdown("""
    <style>
    .column-divider {
        border-left: 1px solid #e0e0e0;
        height: 100%;
        position: absolute;
        left: 0;
        margin-left: -1px;
        top: 0;
    }
    
    .status-header {
        background-color: #f0f2f6;
        border-radius: 5px;
        padding: 10px;
        margin-bottom: 15px;
        text-align: center;
        font-weight: bold;
        color: #31333F;
    }
    
    /* Estilo para os botões de card */
    button[data-testid="baseButton-secondary"] {
        background-color: white;
        border: 1px solid #e0e0e0;
        border-radius: 5px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        text-align: left;
        margin-bottom: 10px;
        height: auto;
        min-height: 60px;
    }
    </style>
    """, unsafe_allow_html=True)

    # Carregar os dados de tarefas
    df_tarefas = get_data("tarefas")

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

    # Definir os status possíveis e seus ícones
    status_colunas = ["A fazer", "Em andamento", "A validar", "Concluído"]
    status_icones = ["📋", "⏳", "✅", "🏆"]
    
    # Criar 4 colunas para os diferentes status
    colunas = st.columns(4)
    
    # Adicionar títulos estilizados às colunas
    for i, (status, icone) in enumerate(zip(status_colunas, status_icones)):
        with colunas[i]:
            st.markdown(f"""
            <div class="status-header">
                {icone} {status}
            </div>
            """, unsafe_allow_html=True)
            
            # Adicionar linha divisória vertical (exceto para a primeira coluna)
            if i > 0:
                st.markdown(f"""
                <div class="column-divider"></div>
                """, unsafe_allow_html=True)
    
    # Agrupar tarefas por status
    tarefas_por_status = {status: df_tarefas[df_tarefas["Status"] == status] for status in status_colunas}
    
    # Track if any card is clicked
    clicked_card = None
    
    # Exibir cards em cada coluna correspondente ao status
    for i, status in enumerate(status_colunas):
        with colunas[i]:
            if tarefas_por_status[status].empty:
                st.info(f"Nenhuma atividade com status '{status}'")
            else:
                # Criar um container para manter os cards alinhados
                for j, row in tarefas_por_status[status].iterrows():
                    # Criar um botão estilizado como card
                    if st.button(
                        f"Setor {row['Setor']} | {row['Colaborador']} | {row['Tipo']}",
                        key=f"card_{status}_{j}",
                        use_container_width=True,
                    ):
                        st.session_state["projeto_selecionado"] = row.to_dict()
                        st.rerun()

# Verificar se um projeto foi selecionado
if "projeto_selecionado" in st.session_state:
    tarefa = st.session_state["projeto_selecionado"]
    
    # Criar um container para o formulário com um botão de fechar no canto superior direito
    with st.container():
        # Criar duas colunas, uma para o título e outra para o botão de fechar
        col_titulo, col_fechar = st.columns([5, 1])
        
        with col_titulo:
            st.subheader("Editar Tarefa")
        
        with col_fechar:
            if st.button("❌ Fechar", key="btn_fechar_tarefa"):
                st.session_state.pop("projeto_selecionado", None)
                st.rerun()
    
    # Formulário de edição
    with st.form(key="edt_form"):
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
                        df = get_data("tarefas")
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
                        df = get_data("tarefas")
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

########################################## REFORMA E EXPANSÃO ##########################################

# Página de Acompanhamento Reforma e Expansão
def acompanhamento_reforma_expansao():
    st.title("🌱 Reforma e Expansão")

    # Lista de categorias e colunas correspondentes no DataFrame
    categorias = ["Em andamento", "Realizado", "Aprovado", "Sistematizacao", "Loc", "Pre-Plantio"]
    colunas = ["Projeto", "Projeto", "Aprovado", "Sistematizacao", "Loc", "Pre_Plantio"]

    # Criar dicionários para armazenar os valores
    data_reforma = {"Categoria": categorias}
    data_expansao = {"Categoria": categorias}

    try:
        ######################## REFORMA ########################
        # Limpar o cache para garantir dados atualizados
        st.cache_data.clear()
        
        # Carregar dados de reforma
        df_reforma = get_data("reforma")
        
        # Verificar se o DataFrame está vazio ou se não tem dados válidos
        has_valid_data = not df_reforma.empty and "Area" in df_reforma.columns and df_reforma["Area"].sum() > 0
        
        if has_valid_data:
            # Processar dados para cada unidade
            for unidade, nome in zip(["21", "22"], ["Paraguaçu", "Narandiba"]):
                # Verificar se a coluna Unidade existe
                if "Unidade" not in df_reforma.columns:
                    st.error(f"Coluna 'Unidade' não encontrada no DataFrame de Reforma")
                    continue
                
                # Filtrar por unidade (já convertida para string na função carregar_reforma)
                unidade_filtro = df_reforma["Unidade"] == unidade
                
                # Verificar se a coluna Plano existe
                plano_filtro = df_reforma["Plano"].str.contains("Plano A", case=False, na=False) if "Plano" in df_reforma.columns else pd.Series(True, index=df_reforma.index)
                
                # Combinar filtros
                filtro_final = unidade_filtro & plano_filtro
                
                # Calcular área total da unidade
                unidade_area = df_reforma[filtro_final]["Area"].sum()
                
                # Processar cada categoria
                valores_reforma = []
                for coluna, categoria in zip(colunas, categorias):
                    try:
                        # Aplicar filtros específicos para cada categoria
                        if categoria == "Em andamento":
                            # Verificar se a coluna Projeto existe
                            if "Projeto" in df_reforma.columns:
                                filtro = df_reforma["Projeto"].str.contains("EM ANDAMENTO", case=False, na=False)
                            else:
                                filtro = pd.Series(False, index=df_reforma.index)
                        elif categoria == "Realizado":
                            # Verificar se a coluna Projeto existe
                            if "Projeto" in df_reforma.columns:
                                filtro = df_reforma["Projeto"].str.contains("OK", case=False, na=False)
                            else:
                                filtro = pd.Series(False, index=df_reforma.index)
                        else:
                            # Verificar se a coluna específica existe
                            if coluna in df_reforma.columns:
                                filtro = df_reforma[coluna].str.contains("OK", case=False, na=False)
                            else:
                                filtro = pd.Series(False, index=df_reforma.index)
                        
                        # Calcular área e porcentagem
                        area_categoria = df_reforma[filtro_final & filtro]["Area"].sum()
                        
                        # Calcular porcentagem
                        porcentagem = (area_categoria / unidade_area) * 100 if unidade_area > 0 else 0
                        valores_reforma.append(f"{porcentagem:.0f}%")
                    except Exception as e:
                        valores_reforma.append("0%")
                
                # Armazenar valores para esta unidade
                data_reforma[nome] = valores_reforma
        else:
            # Criar dados de exemplo se não houver dados válidos
            st.warning("Não foram encontrados dados válidos para Reforma. Exibindo dados de exemplo.")
            for nome, valores in zip(["Paraguaçu", "Narandiba"], [
                ["45%", "30%", "20%", "15%", "10%", "5%"],
                ["40%", "25%", "15%", "10%", "5%", "0%"]
            ]):
                data_reforma[nome] = valores
        
        # Calcular a média das porcentagens para cada categoria
        media_grupo_cocal_reforma = []
        for i in range(len(categorias)):
            try:
                # Extrair valores numéricos
                valor_paraguacu = float(data_reforma["Paraguaçu"][i].replace("%", "").replace(",", "."))
                valor_narandiba = float(data_reforma["Narandiba"][i].replace("%", "").replace(",", "."))
                
                # Calcular média
                media = (valor_paraguacu + valor_narandiba) / 2
                media_grupo_cocal_reforma.append(f"{media:.0f}%")
            except Exception:
                media_grupo_cocal_reforma.append("0%")
        
        # Adicionar coluna com a média
        data_reforma["Grupo Cocal"] = media_grupo_cocal_reforma
        
        ######################## EXPANSÃO ########################
        # Carregar dados de expansão
        df_expansao = get_data("expansao")
        
        # Verificar se o DataFrame está vazio ou se não tem dados válidos
        has_valid_data = not df_expansao.empty and "Area" in df_expansao.columns and df_expansao["Area"].sum() > 0
        
        if has_valid_data:
            # Processar dados para cada unidade
            for unidade, nome in zip(["21", "22"], ["Paraguaçu", "Narandiba"]):
                # Verificar se a coluna Unidade existe
                if "Unidade" not in df_expansao.columns:
                    st.error(f"Coluna 'Unidade' não encontrada no DataFrame de Expansão")
                    continue
                
                # Filtrar por unidade (já convertida para string na função carregar_expansao)
                unidade_filtro = df_expansao["Unidade"] == unidade
                
                # Calcular área total da unidade
                unidade_area = df_expansao[unidade_filtro]["Area"].sum()
                
                # Processar cada categoria
                valores_expansao = []
                for coluna, categoria in zip(colunas, categorias):
                    try:
                        # Aplicar filtros específicos para cada categoria
                        if categoria == "Em andamento":
                            # Verificar se a coluna Projeto existe
                            if "Projeto" in df_expansao.columns:
                                filtro = df_expansao["Projeto"].str.contains("EM ANDAMENTO", case=False, na=False)
                            else:
                                filtro = pd.Series(False, index=df_expansao.index)
                        elif categoria == "Realizado":
                            # Verificar se a coluna Projeto existe
                            if "Projeto" in df_expansao.columns:
                                filtro = df_expansao["Projeto"].str.contains("OK", case=False, na=False)
                            else:
                                filtro = pd.Series(False, index=df_expansao.index)
                        else:
                            # Verificar se a coluna específica existe
                            if coluna in df_expansao.columns:
                                filtro = df_expansao[coluna].str.contains("OK", case=False, na=False)
                            else:
                                filtro = pd.Series(False, index=df_expansao.index)
                        
                        # Calcular área e porcentagem
                        area_categoria = df_expansao[unidade_filtro & filtro]["Area"].sum()
                        
                        # Calcular porcentagem
                        porcentagem = (area_categoria / unidade_area) * 100 if unidade_area > 0 else 0
                        valores_expansao.append(f"{porcentagem:.0f}%")
                    except Exception as e:
                        valores_expansao.append("0%")
                
                # Armazenar valores para esta unidade
                data_expansao[nome] = valores_expansao
        else:
            # Criar dados de exemplo se não houver dados válidos
            st.warning("Não foram encontrados dados válidos para Passagem. Exibindo dados de exemplo.")
            for nome, valores in zip(["Paraguaçu", "Narandiba"], [
                ["35%", "25%", "15%", "10%", "5%", "0%"],
                ["30%", "20%", "10%", "5%", "0%", "0%"]
            ]):
                data_expansao[nome] = valores
        
        # Calcular a média das porcentagens para cada categoria
        media_grupo_cocal_expansao = []
        for i in range(len(categorias)):
            try:
                # Extrair valores numéricos
                valor_paraguacu = float(data_expansao["Paraguaçu"][i].replace("%", "").replace(",", "."))
                valor_narandiba = float(data_expansao["Narandiba"][i].replace("%", "").replace(",", "."))
                
                # Calcular média
                media = (valor_paraguacu + valor_narandiba) / 2
                media_grupo_cocal_expansao.append(f"{media:.0f}%")
            except Exception:
                media_grupo_cocal_expansao.append("0%")
        
        # Adicionar coluna com a média
        data_expansao["Grupo Cocal"] = media_grupo_cocal_expansao
        
        ######################## GRÁFICO ########################
        # Divide a tela em 2 colunas
        col1, col2 = st.columns(2)

        with col1:
            # Criando opções de seleção para visualizar os dados
            opcao_tipo = st.selectbox("Selecione o tipo de acompanhamento:", ["Reforma", "Expansão"])
        with col2:
            opcao_visualizacao = st.selectbox("Selecione a unidade:", ["Grupo Cocal", "Paraguaçu", "Narandiba"])

        # Escolher qual DataFrame usar com base na seleção
        if opcao_tipo == "Reforma":
            df_selecionado = pd.DataFrame(data_reforma)[["Categoria", opcao_visualizacao]]
        else:
            df_selecionado = pd.DataFrame(data_expansao)[["Categoria", opcao_visualizacao]]

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
            yaxis=dict(showgrid=False, showticklabels=True, title='', showline=False, zeroline=False),
        )

        # Exibir o gráfico dinâmico no Streamlit
        st.subheader(f"Acompanhamento de {opcao_tipo} - {opcao_visualizacao}")
        st.plotly_chart(fig)

        ####################### MAPA ########################
        st.divider()

        st.subheader("Mapa")

        # Incorporando o mapa ArcGIS usando components.html
        arcgis_html = """
        <html>
        <head>
            <script type="module" src="https://js.arcgis.com/embeddable-components/4.32/arcgis-embeddable-components.esm.js"></script>
        </head>
        <body>
            <arcgis-embedded-map style="height:600px;width:100%;" item-id="3e59094202574c07ac103f93b6700339" theme="dark" portal-url="https://cocal.maps.arcgis.com"></arcgis-embedded-map>
        </body>
        </html>
        """
        components.html(arcgis_html, height=650, scrolling=False)

        ####################### TABELAS ########################
        st.divider()

        # Métricas de Reforma
        st.write("### Métricas de Reforma")
        df_metrica_reforma = pd.DataFrame(data_reforma)
        st.dataframe(df_metrica_reforma, use_container_width=True, hide_index=True)

        st.divider()

        # Métricas de Expansão
        st.write("### Métricas de Expansão")
        df_metrica_expansao = pd.DataFrame(data_expansao)
        st.dataframe(df_metrica_expansao, use_container_width=True, hide_index=True)
        
    except Exception as e:
        st.error(f"Erro ao processar dados: {e}")
        st.write("Detalhes do erro para debug:")
        st.write(f"Tipo de erro: {type(e).__name__}")
        st.write(f"Mensagem de erro: {str(e)}")
        import traceback
        st.code(traceback.format_exc())

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
    df_auditoria = get_data("auditoria")

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
    df_extras = get_data("extras")

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
    
    # Definir valor padrão para mostrar os últimos 6 dias
    data_atual = datetime.now().date()
    data_inicio_padrao = data_atual - timedelta(days=6)
    
    # Garantir que data_inicio_padrao não seja menor que data_min
    data_inicio_padrao = max(data_inicio_padrao, data_min)
    # Garantir que data_atual não seja maior que data_max
    data_atual = min(data_atual, data_max)
    
    # Barra deslizante para selecionar o intervalo de datas
    data_inicio, data_fim = st.sidebar.slider(
        "Intervalo de datas",
        min_value=data_min,
        max_value=data_max,
        value=(data_inicio_padrao, data_atual),
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
    
    # Aplicar os filtros
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
    # Inicializar o estado da sessão se necessário
    if "page" not in st.session_state:
        st.session_state["page"] = "Dashboard"
    
    st.sidebar.image("imagens/logo-cocal.png")
    st.sidebar.title("Menu")
    menu_option = st.sidebar.radio(
        "Selecione a funcionalidade:",
        ("Dashboard", "Registrar", "Atividades", "Reforma e Expansão", "Auditoria", "Extras")
    )

    st.sidebar.markdown("---")  # Linha separadora

    if menu_option == "Dashboard":
        dashboard()
    elif menu_option == "Registrar":
        registrar_atividades()
    elif menu_option == "Atividades":
        tarefas_semanais()
    elif menu_option == "Reforma e Expansão":
        acompanhamento_reforma_expansao()
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

# Adicionar função para otimizar a renderização de componentes
def render_once(key, func, *args, **kwargs):
    """
    Renderiza um componente apenas uma vez e armazena o resultado na sessão.
    Isso evita recarregamentos desnecessários durante a interação do usuário.
    
    Args:
        key: Chave única para identificar o componente na sessão
        func: Função a ser executada para renderizar o componente
        *args, **kwargs: Argumentos para a função
        
    Returns:
        Resultado da função
    """
    # Criar chave para a sessão
    component_key = f"component_{key}"
    
    # Verificar se o componente já foi renderizado nesta sessão
    if component_key not in st.session_state:
        # Renderizar o componente
        result = func(*args, **kwargs)
        # Armazenar o resultado na sessão
        st.session_state[component_key] = result
    
    return st.session_state[component_key]

# Função para limpar o cache de componentes quando necessário
def clear_component_cache(component_key=None):
    """
    Limpa o cache de componentes para forçar a re-renderização.
    
    Args:
        component_key: Chave específica do componente para limpar ou None para limpar todos
    """
    if component_key:
        full_key = f"component_{component_key}"
        if full_key in st.session_state:
            del st.session_state[full_key]
    else:
        # Limpar todos os caches de componentes
        keys_to_delete = [k for k in st.session_state.keys() if k.startswith("component_")]
        for key in keys_to_delete:
            del st.session_state[key]