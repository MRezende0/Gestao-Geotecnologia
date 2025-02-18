import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import datetime
import sqlite3

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

########################################## BANCO DE DADOS ##########################################

# Conecta (ou cria) o banco de dados
conn = sqlite3.connect('dados/dados.db', check_same_thread=False)
cursor = conn.cursor()

# Cria a tabela se não existir
cursor.execute('''
    CREATE TABLE IF NOT EXISTS tarefas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        Data TEXT,
        Setor INTEGER,
        Colaborador TEXT,
        Tipo TEXT,
        Status TEXT
    )
''')
conn.commit()

# Função para carregar tarefas do banco de dados
def carregar_tarefas():
    return pd.read_sql_query("SELECT * FROM tarefas", conn)

########################################## DADOS ########################################## 

# Caminho dos arquivos CSV
BASE_PATH = "dados/base.csv"
EXTRAS_PATH = "dados/extras.csv"
POS_PATH = "dados/pos_aplicacao.xlsx"
REF_PAS_PATH = "dados/reforma_passagem.xlsx"
AUDITORIA_PATH = "dados/auditoria.csv"
PASTA_POS = "dados/pos-aplicacao"
ARQUIVO_POS_CSV = "dados/pos_aplicacao.csv"

# Função para carregar dados de CSV ou Excel
def carregar_dados(caminho, colunas=None, aba=None):
    if os.path.exists(caminho):
        _, extensao = os.path.splitext(caminho)
        extensao = extensao.lower()
        if extensao == ".csv":
            return pd.read_csv(caminho)
        elif extensao in [".xls", ".xlsx"]:
            return pd.read_excel(caminho, sheet_name=aba) if aba is not None else pd.read_excel(caminho)
        else:
            raise ValueError(f"Formato de arquivo {extensao} não suportado!")
    else:
        return pd.DataFrame(columns=colunas)
    
# Carrega as duas abas
df_passagem = carregar_dados(REF_PAS_PATH, aba=0)  # Carrega a primeira aba
df_reforma = carregar_dados(REF_PAS_PATH, aba=1)  # Carrega a segunda aba

# Carrega os dados iniciais
df_tarefas = carregar_tarefas()
df_base = carregar_dados(BASE_PATH, ["Unidade", "Setor", "Area"])
df_pos = carregar_dados(POS_PATH, ["UNIDADE", "SETOR", "TALHÃO", "AREA", "DESC_OPERAÇÃO", "DATA"])
df_extras = carregar_dados(EXTRAS_PATH, ["Data", "Colaborador", "Solicitante", "SetorSolicitante", "Atividade", "Horas", "Descrição"])
df_ref_pas = carregar_dados(REF_PAS_PATH, [""])
df_auditoria = carregar_dados(AUDITORIA_PATH, [
    "Data", "Auditores", "Unidade", "Setor", "TipoPlantio_Planejado", "TipoPlantio_Executado", 
    "TipoTerraco_Planejado", "TipoTerraco_Executado", "QuantidadeTerraco_Planejado", "QuantidadeTerraco_Executado", 
    "Levantes_Planejado", "Levantes_Executado", "LevantesDesmanche_Planejado", "LevantesDesmanche_Executado", 
    "Bigodes_Planejado", "Bigodes_Executado", "BigodesDesmanche_Planejado", "BigodesDesmanche_Executado", 
    "Carreadores_Planejado", "Carreadores_Executado", "Patios_Projetado", "Patios_Executado", "Observacao"
])
df_pos_csv = carregar_dados(ARQUIVO_POS_CSV, ["DESC_OPERAÇÃO","DATA","SETOR","TALHÃO","AREA"])

# Mesclar bases de dados
df_tarefas = df_tarefas.merge(df_base, on="Setor", how="left")

########################################## DASHBOARD ##########################################

def dashboard():
    st.title("📊 Dashboard")
    df_tarefas = carregar_tarefas()

    # Aplicando os filtros e retornando o DataFrame filtrado
    df_tarefas = filtros_dashboard(df_tarefas)

    # # Exibe métricas
    # col1, col2, col3 = st.columns(3)
    # with col1:
    #     total_area = df_tarefas['Area'].sum()
    #     formatted_area = f"{total_area:,.0f}".replace(',', '.')
    #     st.metric("Área Total", f"{formatted_area} ha")
    # with col2:
    #     st.metric("Quantidade de Atividades", df_tarefas['Colaborador'].size)
    # with col3:
    #     st.metric("Colaboradores", df_tarefas['Colaborador'].unique().size)

    st.divider()

    # Layout com 2 colunas e 3 linhas
    col1, linha, col2 = st.columns([4, 0.5, 4])

    # Linha 1 - Gráficos de Atividades por Colaborador e Projetos por Tipo
    with col1:
        st.subheader("Atividades por Colaborador")
        df_contagem_responsavel = df_tarefas.groupby("Colaborador")["Tipo"].count().reset_index()
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
        st.plotly_chart(fig_responsavel)

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
        st.plotly_chart(fig_tipo)

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
        st.plotly_chart(fig_status)

    # with col2:
    #     st.subheader("Projetos por Unidade")
    #     df_contagem_unidade = df_tarefas.groupby("Unidade")["Tipo"].count().reset_index()
    #     df_contagem_unidade.columns = ["Unidade", "Quantidade de Projetos"]
    #     fig_pizza = px.pie(
    #         df_contagem_unidade,
    #         names="Unidade",
    #         values="Quantidade de Projetos",
    #         color="Unidade",
    #         hole=0.3,
    #         labels={'Quantidade de Projetos': 'Porcentagem de Projetos'}
    #     )
    #     st.plotly_chart(fig_pizza)

    st.divider()

    # Gráfico de Pós-Aplicação
    st.subheader("Mapas de Pós-Aplicação")

    ordem_meses = ["Todos", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

    # Filtro de Mês
    mes_selecionado = st.selectbox(
        "Selecione o Mês",
        options=ordem_meses,  # Lista de meses ordenados
        index=0  # Define o primeiro mês como padrão
    )

    # Converter DATA para datetime e criar coluna MÊS
    df_pos["DATA"] = pd.to_datetime(df_pos["DATA"], errors="coerce")
    df_pos["MÊS"] = df_pos["DATA"].dt.strftime("%B").str.capitalize()

    # Verificar se o filtro "Todos" foi selecionado
    if mes_selecionado != "Todos":
        # Filtrar dados para o mês selecionado
        df_filtrado = df_pos[df_pos["MÊS"] == mes_selecionado]
    else:
        # Caso "Todos" seja selecionado, não filtra os dados
        df_filtrado = df_pos

    df_unico = df_filtrado.drop_duplicates(subset=["MÊS", "SETOR"])

    df_contagem = df_unico.groupby("MÊS").size().reset_index(name="QUANTIDADE")

    # Verificar a estrutura de df_contagem antes de renomear colunas
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

    df_tarefas_ordenado = df_tarefas.sort_values(by="Data", ascending=False).reset_index(drop=True)
    st.table(df_tarefas_ordenado)

########################################## REGISTRAR ##########################################

def registrar_atividades():
    st.title("📝 Registrar")

    # Seleção do tipo de atividade
    tipo_atividade = st.radio(
        "Selecione o tipo de registro:",
        ("Atividade Semanal", "Atividade Extra", "Reforma e Passagem", "Pós-Aplicação", "Auditoria")
    )

    # Formulário para Atividade Semanal
    if tipo_atividade == "Atividade Semanal":
        with st.form("form_atividade_semanal"):
            st.subheader("Atividade Semanal")
            Data = st.date_input("Data")
            Setor = st.number_input("Setor", min_value=0, step=1, format="%d")
            Colaborador = st.selectbox("Colaborador", ["", "Ana", "Camila", "Gustavo", "Maico", "Márcio", "Pedro", "Talita", "Washington", "Willian", "Iago"])
            Tipo = st.selectbox("Tipo", ["", "Projeto de Sistematização", "Mapa de Sistematização", "LOC", "Projeto de Transbordo", "Auditoria", "Projeto de Fertirrigação", "Projeto de Sulcação", "Mapa de Pré-Plantio", "Mapa de Pós-Plantio", "Projeto de Colheita", "Mapa de Cadastro"])
            Status = st.selectbox("Status", ["A fazer", "Em andamento", "A validar", "Concluído"])
            submit = st.form_submit_button("Registrar")

        if submit:
            try:
                cursor.execute('''
                    INSERT INTO tarefas (Data, Setor, Colaborador, Tipo, Status)
                    VALUES (?, ?, ?, ?, ?)
                ''', (str(Data), Setor, Colaborador, Tipo, Status))
                conn.commit()
                st.success("Atividade registrada com sucesso!")
            except Exception as e:
                st.error(f"Erro ao registrar: {e}")

    # Formulário para Atividade Extra
    elif tipo_atividade == "Atividade Extra":
        with st.form("form_atividade_extra"):
            st.subheader("Atividade Extra")
            Data = st.date_input("Data")
            Colaborador = st.selectbox("Colaborador", ["", "Ana", "Camila", "Gustavo", "Maico", "Márcio", "Pedro", "Talita", "Washington", "Willian", "Iago"])
            Solicitante = st.text_input("Nome do Solicitante")
            SetorSolicitante = st.text_input("Setor Solicitante")
            Atividade = st.selectbox("Atividade", ["", "Impressão de Mapa", "Voo com drone", "Mapa", "Tematização de mapa", "Processamento", "Projeto", "Outro"])
            Horas = st.time_input("Horas de trabalho")
            submit = st.form_submit_button("Registrar")

        if submit:
            nova_tarefa = pd.DataFrame({
                "Data": [Data],
                "Colaborador": [Colaborador],
                "Solicitante": [Solicitante],
                "SetorSolicitante": [SetorSolicitante],
                "Atividade": [Atividade],
                "Horas": [Horas]
            })
            
            if os.path.exists(EXTRAS_PATH):
                df_extras = pd.read_csv(EXTRAS_PATH)
            else:
                df_extras = pd.DataFrame(columns=["Data", "Descricao", "Colaborador", "Prioridade"])
            
            df_extras = pd.concat([df_extras, nova_tarefa], ignore_index=True)
            salvar_dados_csv(df_extras, EXTRAS_PATH)
            st.success("Atividade Extra registrada com sucesso!")

    # Formulário para Reforma e Passagem
    elif tipo_atividade == "Reforma e Passagem":

        # Carregar os dados das abas de Reforma e Passagem
        df_reforma = carregar_dados(REF_PAS_PATH, aba="Reforma")
        df_passagem = carregar_dados(REF_PAS_PATH, aba="Passagem")

        # Definir o df_editar antes de usá-lo
        df_editar = pd.DataFrame()  # Inicializando com um DataFrame vazio

        # Seleção da aba para edição
        opcao = st.radio("Selecione a planilha para editar:", ["Reforma", "Passagem"])

        # Atribuir df_editar corretamente com base na aba selecionada
        if opcao == "Reforma":
            df_editar = df_reforma
        elif opcao == "Passagem":
            df_editar = df_passagem

        # Exibir o editor de dados baseado na aba selecionada
        df_editado = st.data_editor(df_editar, num_rows="dynamic")

        # Botão para salvar alterações no Excel
        if st.button("Salvar Alterações"):
            if opcao == "Reforma":
                # Atualizar o df_reforma com os dados editados
                df_reforma = df_editado

                # Salvar as alterações de volta na aba "Reforma" do arquivo Excel
                with pd.ExcelWriter(REF_PAS_PATH, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
                    df_reforma.to_excel(writer, sheet_name="Reforma", index=False)
                st.success("Dados da aba Reforma atualizados com sucesso!")

            elif opcao == "Passagem":
                # Atualizar o df_passagem com os dados editados
                df_passagem = df_editado

                # Salvar as alterações de volta na aba "Passagem" do arquivo Excel
                with pd.ExcelWriter(REF_PAS_PATH, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
                    df_passagem.to_excel(writer, sheet_name="Passagem", index=False)
                st.success("Dados da aba Passagem atualizados com sucesso!")

    elif tipo_atividade == "Pós-Aplicação":
        st.header("Upload de Arquivo - Pós-Aplicação")

        # Lista de colunas padronizadas
        COLUNAS_PADRONIZADAS = ["DESC_OPERAÇÃO", "DATA", "SETOR", "TALHÃO", "AREA"]

        # Variável de controle para indicar se o arquivo foi salvo agora
        arquivo_salvo_agora = False 

        # Upload do arquivo
        arquivo = st.file_uploader("Carregue um arquivo Excel", type=["xls", "xlsx"])

        if arquivo:
            # Definir caminho do arquivo
            caminho_arquivo = os.path.join(PASTA_POS, arquivo.name)

            # Verificar se o arquivo já existe antes de salvar
            if os.path.exists(caminho_arquivo):
                st.error(f"O arquivo '{arquivo.name}' já existe na pasta.")
            else:
                # Salvar o arquivo na pasta
                with open(caminho_arquivo, "wb") as f:
                    f.write(arquivo.getbuffer())

                st.success(f"Arquivo salvo: {arquivo.name}")
                arquivo_salvo_agora = True  # Marca que um arquivo novo foi salvo

        # Listar arquivos na pasta (somente se não acabamos de salvar um novo arquivo)
        if not arquivo_salvo_agora:
            arquivos_excel = glob.glob(os.path.join(PASTA_POS, "*.xls*"))

            if arquivos_excel:
                dfs = []
                for arquivo in arquivos_excel:
                    df = pd.read_excel(arquivo)

                    # Verificar se as colunas estão padronizadas
                    if list(df.columns) != COLUNAS_PADRONIZADAS:
                        st.error(f"O arquivo {os.path.basename(arquivo)} não segue o padrão de colunas esperado.")
                        st.write(f"Colunas esperadas: {COLUNAS_PADRONIZADAS}")
                        st.write(f"Colunas encontradas: {list(df.columns)}")
                        continue  # Pula este arquivo

                    dfs.append(df)

                if dfs:
                    df_total = pd.concat(dfs, ignore_index=True)

                    # Exibir todas as operações disponíveis
                    operacoes_unicas = df_total["DESC_OPERAÇÃO"].unique().tolist()
                    operacoes_selecionadas = st.multiselect(
                        "Selecione as operações que deseja salvar:", operacoes_unicas
                    )

                    # Filtrar os dados
                    df_filtrado = df_total[df_total["DESC_OPERAÇÃO"].isin(operacoes_selecionadas)]

                    if not df_filtrado.empty:
                        st.write("Prévia dos dados filtrados:")
                        st.dataframe(df_filtrado)

                        # Botão para salvar os dados
                        if st.button("Salvar Dados no CSV"):
                            if os.path.exists(ARQUIVO_POS_CSV):
                                # Carregar dados existentes
                                df_existente = pd.read_csv(ARQUIVO_POS_CSV)

                                # Concatenar sem duplicar "DESC_OPERAÇÃO", "SETOR" e "TALHÃO"
                                df_final = pd.concat([df_existente, df_filtrado])
                                df_final = df_final.drop_duplicates(subset=["DESC_OPERAÇÃO", "SETOR", "TALHÃO"])

                                # Salvar no CSV
                                df_final.to_csv(ARQUIVO_POS_CSV, index=False)
                            else:
                                df_filtrado.to_csv(ARQUIVO_POS_CSV, index=False)

                            st.success("Os dados filtrados foram adicionados ao pos_aplicacao.csv sem duplicações.")
                    else:
                        st.warning("Nenhuma operação selecionada. O arquivo não será salvo.")

    # Formulário para Auditoria
    elif tipo_atividade == "Auditoria":
        with st.form("form_auditoria"):
            st.subheader("Auditoria")
            Data = st.date_input("Auditoria referente à")
            Auditores = st.multiselect("Auditores", ["Camila", "Guilherme", "Maico", "Sebastião", "Willian"])
            Unidade = st.selectbox("Unidade", ["", "Paraguaçu", "Narandiba"])
            Setor = st.number_input("Setor", min_value=0, step=1, format="%d")
            TipoPlantio_Planejado = st.selectbox("Tipo de Plantio Planejado", ["", "ESD", "Convencional", "ESD e Convencional"])
            TipoPlantio_Executado = st.selectbox("Tipo de Plantio Executado", ["", "ESD", "Convencional", "ESD e Convencional"])
            TipoTerraco_Planejado = st.selectbox("Tipo de Terraço Planejado", ["", "Base Larga", "Embutida", "ESD", "Base Large e ESD", "Base Larga e Embutida", "Embutida e ESD"])
            TipoTerraco_Executado = st.selectbox("Tipo de Terraço Executado", ["", "Base Larga", "Embutida", "ESD", "Base Large e ESD", "Base Larga e Embutida", "Embutida e ESD"])
            QuantidadeTerraco_Planejado = st.selectbox("Quantidade de Terraços Planejado", ["", "Ok", "Não"])
            QuantidadeTerraco_Executado = st.selectbox("Quantidade de Terraços Executado", ["", "Ok", "Não"])
            Levantes_Planejado = st.number_input("Levantes Planejado", min_value=0, step=1)
            Levantes_Executado = st.number_input("Levantes Executado", min_value=0, step=1)
            LevantesDesmanche_Planejado = st.number_input("Levantes Desmanche Planejado", min_value=0, step=1)
            LevantesDesmanche_Executado = st.number_input("Levantes Desmanche Executado", min_value=0, step=1)
            Bigodes_Planejado = st.number_input("Bigodes Planejado", min_value=0, step=1)
            Bigodes_Executado = st.number_input("Bigodes Executado", min_value=0, step=1)
            BigodesDesmanche_Planejado = st.number_input("Bigodes Desmanche Planejado", min_value=0, step=1)
            BigodesDesmanche_Executado = st.number_input("Bigodes Desmanche Executado", min_value=0, step=1)
            Carreadores_Planejado = st.selectbox("Carreadores Planejado", ["", "Ok", "Não"])
            Carreadores_Executado = st.selectbox("Carreadores Executado", ["", "Ok", "Não"])
            Patios_Projetado = st.number_input("Pátios Projetado", min_value=0, step=1)
            Patios_Executado = st.number_input("Pátios Executado", min_value=0, step=1)
            Observacao = st.text_area("Observação")
            submit = st.form_submit_button("Registrar")

        if submit:
            nova_auditoria = pd.DataFrame({
                "Data": [Data],
                "Auditores": [Auditores],
                "Unidade": [Unidade],
                "Setor": [Setor],
                "TipoPlantio_Planejado": [TipoPlantio_Planejado],
                "TipoPlantio_Executado": [TipoPlantio_Executado],
                "TipoTerraco_Planejado": [TipoTerraco_Planejado],
                "TipoTerraco_Executado": [TipoTerraco_Executado],
                "QuantidadeTerraco_Planejado": [QuantidadeTerraco_Planejado],
                "QuantidadeTerraco_Executado": [QuantidadeTerraco_Executado],
                "Levantes_Planejado": [Levantes_Planejado],
                "Levantes_Executado": [Levantes_Executado],
                "LevantesDesmanche_Planejado": [LevantesDesmanche_Planejado],
                "LevantesDesmanche_Executado": [LevantesDesmanche_Executado],
                "Bigodes_Planejado": [Bigodes_Planejado],
                "Bigodes_Executado": [Bigodes_Executado],
                "BigodesDesmanche_Planejado": [BigodesDesmanche_Planejado],
                "BigodesDesmanche_Executado": [BigodesDesmanche_Executado],
                "Carreadores_Planejado": [Carreadores_Planejado],
                "Carreadores_Executado": [Carreadores_Executado],
                "Patios_Projetado": [Patios_Projetado],
                "Patios_Executado": [Patios_Executado],
                "Observacao": [Observacao]
            })

            if os.path.exists(AUDITORIA_PATH):
                df_auditoria = pd.read_csv(AUDITORIA_PATH)
            else:
                df_auditoria = pd.DataFrame(columns=[
                    "Data", "Auditores", "Unidade", "Setor", "TipoPlantio_Planejado", "TipoPlantio_Executado", 
                    "TipoTerraco_Planejado", "TipoTerraco_Executado", "QuantidadeTerraco_Planejado", "QuantidadeTerraco_Executado", 
                    "Levantes_Planejado", "Levantes_Executado", "LevantesDesmanche_Planejado", "LevantesDesmanche_Executado", 
                    "Bigodes_Planejado", "Bigodes_Executado", "BigodesDesmanche_Planejado", "BigodesDesmanche_Executado", 
                    "Carreadores_Planejado", "Carreadores_Executado", "Patios_Projetado", "Patios_Executado", "Observacao"
                ])

            df_auditoria = pd.concat([df_auditoria, nova_auditoria], ignore_index=True)
            salvar_dados_csv(df_auditoria, AUDITORIA_PATH)
            st.success("Auditoria registrada com sucesso!")

########################################## ATIVIDADES ##########################################

# Função para exibir os projetos como cards clicáveis
def tarefas_semanais():
    st.title("📂 Atividades")

    # Garantir que os dados sejam carregados corretamente
    global df_tarefas  # Usa a variável global para evitar redefinição local errada
    # df_tarefas = carregar_dados(TAREFAS_PATH, ["Data", "Setor", "Colaborador", "Tipo", "Status"])
    df_tarefas = carregar_tarefas()

    # Aplicando os filtros e retornando o DataFrame filtrado
    df_tarefas = filtros_atividades(df_tarefas)
    
    filtro_dropdown = st.selectbox(
        "🔍 Selecione uma atividade",
        options=[""] + sorted(list(df_tarefas["Setor"].unique()), key=int),  # Dropdown inclui opção vazia
        index=0
    )

    # Filtrar os projetos
    if filtro_dropdown:
        df_tarefas = df_tarefas[df_tarefas["Tipo"] == filtro_dropdown]
    else:
        df_tarefas = df_tarefas

    # Divide a tela em 3 colunas
    col1, col2, col3 = st.columns(3)

    for i, row in df_tarefas.iterrows():
        # Criando um card HTML clicável com efeito hover
        card = f"""
        <div onclick="selectProject({i})" style="
            background-color: #ffffff;
            padding: 15px;
            border-radius: 10px;
            border: 1px solid #ddd;
            text-align: center;
            width: 220px;
            height: 160px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            box-shadow: 2px 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        "
        onmouseover="this.style.transform='scale(1.05)'; this.style.boxShadow='4px 4px 15px rgba(0,0,0,0.2)';"
        onmouseout="this.style.transform='scale(1)'; this.style.boxShadow='2px 2px 10px rgba(0,0,0,0.1)';">
            <strong>Setor {row['Setor']}</strong><br>
            👤 {row['Colaborador']}<br>
            🗂️ {row['Tipo']}<br>
            ⏳ {row['Status']}
        </div>
        """

        # Distribuir os cards nas colunas
        if i % 3 == 0:
            with col1:
                if st.button(f"Setor {row['Setor']}", key=f"proj_{i}") :
                    st.session_state["projeto_selecionado"] = row.to_dict()
                st.markdown(card, unsafe_allow_html=True)
        elif i % 3 == 1:
            with col2:
                if st.button(f"Setor {row['Setor']}", key=f"proj_{i}") :
                    st.session_state["projeto_selecionado"] = row.to_dict()
                st.markdown(card, unsafe_allow_html=True)
        else:
            with col3:
                if st.button(f"Setor {row['Setor']}", key=f"proj_{i}") :
                    st.session_state["projeto_selecionado"] = row.to_dict()
                st.markdown(card, unsafe_allow_html=True)

    # Verificar se um projeto foi selecionado
    if "projeto_selecionado" in st.session_state:
        tarefa = st.session_state["projeto_selecionado"]

        # Criar as abas para exibir detalhes ou editar
        tabs = st.radio("Escolha uma opção", ("Detalhes", "Editar"), key="aba_selecionada")

        if tabs == "Detalhes":
            # Exibir detalhes do projeto selecionado
            st.markdown(
                f"""
                <div style="
                    background-color: #f8f9fa;
                    padding: 20px;
                    border-radius: 10px;
                    border: 1px solid #ddd;
                    box-shadow: 2px 2px 10px rgba(0,0,0,0.1);
                    text-align: left;
                    margin-top: 20px;">
                    <h3 style="text-align: center;">📄 Detalhes da Atividade</h3>
                    <strong>Data:</strong> {tarefa['Data']}<br>
                    <strong>Setor:</strong> {tarefa['Setor']}<br>
                    <strong>Colaborador:</strong> {tarefa['Colaborador']}<br>
                    <strong>Tipo:</strong> {tarefa['Tipo']}<br>
                    <strong>Status:</strong> {tarefa['Status']}
                </div>
                """, 
                unsafe_allow_html=True
            )

        elif tabs == "Editar":
            # Formulário de edição do projeto
            st.subheader("Editar Atividade")

            with st.form(key="edit_form"):
                # Campos de edição
                # Data = st.date_input("Data", value=tarefa["Data"].date() if isinstance(tarefa["Data"], pd.Timestamp) else datetime.strptime(tarefa["Data"], "%Y-%m-%d").date())
                Data = st.date_input("Data", value=datetime.today().date())
                Setor = st.number_input("Setor", value=tarefa["Setor"], min_value=0, step=1, format="%d")
                Colaborador = st.selectbox("Colaborador", ["Ana", "Camila", "Gustavo", "Maico", "Márcio", "Pedro", "Talita", "Washington", "Willian", "Iago"], index=(["Ana", "Camila", "Gustavo", "Maico", "Márcio", "Pedro", "Talita", "Washington", "Willian", "Iago"].index(tarefa["Colaborador"]) if tarefa["Colaborador"] in ["Ana", "Camila", "Gustavo", "Maico", "Márcio", "Pedro", "Talita", "Washington", "Willian"] else 0))
                Tipo = st.selectbox("Tipo", ["Projeto de Sistematização", "Mapa de Sistematização", "LOC", "Projeto de Transbordo", "Auditoria", "Projeto de Fertirrigação", "Projeto de Sulcação", "Mapa de Pré-Plantio", "Mapa de Pós-Plantio", "Projeto de Colheita", "Mapa de Cadastro"], index=["Projeto de Sistematização", "Mapa de Sistematização", "LOC", "Projeto de Transbordo", "Auditoria", "Projeto de Fertirrigação", "Projeto de Sulcação", "Mapa de Pré-Plantio", "Mapa de Pós-Plantio", "Projeto de Colheita", "Mapa de Cadastro"].index(tarefa["Tipo"]))
                Status = st.selectbox("Status", ["A fazer", "Em andamento", "A validar", "Concluído"], index=["A fazer", "Em andamento", "A validar", "Concluído"].index(tarefa["Status"]))

                # Botões de salvar e cancelar
                col1, col2 = st.columns(2)

                with col1:
                    # if st.form_submit_button("Salvar Alterações"):
                    #     # Atualiza o projeto no DataFrame
                    #     index = df_tarefas[df_tarefas["Tipo"] == tarefa["Tipo"]].index[0]
                    #     df_tarefas.loc[index] = {
                    #         "Data": Data.strftime("%Y-%m-%d"),
                    #         "Setor": Setor,
                    #         "Colaborador": Colaborador,
                    #         "Tipo": Tipo,
                    #         "Status": Status
                    #     }
                        
                    if st.form_submit_button("Salvar Alterações"):
                        cursor.execute('''
                            UPDATE tarefas 
                            SET Data = ?, Setor = ?, Colaborador = ?, Tipo = ?, Status = ?
                            WHERE id = ?
                        ''', (str(Data), Setor, Colaborador, Tipo, Status, tarefa['id']))
                        conn.commit()

                        # salvar_dados_excel(df_tarefas, TAREFAS_PATH1)  # Salva no Excel
                        # st.session_state["projeto_selecionado"] = df_tarefas.loc[index].to_dict()
                        st.session_state["editando"] = False
                        st.success("Alterações salvas com sucesso!")
                        st.rerun()

                with col2:
                    if st.form_submit_button("Cancelar"):
                        st.session_state["editando"] = False
                        st.rerun()

########################################## REFORMA E PASSAGEM ##########################################

# Página de Acompanhamento Reforma e Passagem
def acompanhamento_reforma_passagem():

    st.title("🌱 Reforma e Passagem")

    # Lista d# Lista de categorias e colunas correspondentes no DataFrame
    categorias = ["Em andamento", "Realizado", "Aprovado", "Sistematização", "LOC", "Pré-Plantio"]
    colunas = ["Projeto", "Projeto", "APROVADO", "SISTEMATIZAÇÃO", "LOC", "PRE PLANTIO"]

    # Criar um dicionário para armazenar os valores
    data_reforma = {"Categoria": categorias}
    data_passagem = {"Categoria": categorias}
    data = {"Categoria": categorias}

######################## REFORMA ########################

    for unidade, nome in zip(["PPT", "NRD"], ["Paraguaçu", "Narandiba"]):
        unidade_area = df_reforma[(df_reforma["UNIDADE"] == unidade) & (df_reforma["PLANO"] == "REFORMA PLANO A")]["ÁREA"].sum()
        valores_reforma = []
        for coluna, categoria in zip(colunas, categorias):
            if categoria == "Em andamento":
                filtro = df_reforma["Projeto"] == "EM ANDAMENTO"
            else:
                filtro = df_reforma[coluna] == "OK"
            
            area_categoria = df_reforma[(df_reforma["UNIDADE"] == unidade) & (df_reforma["PLANO"] == "REFORMA PLANO A") & filtro]["ÁREA"].sum()
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
        unidade_area = df_passagem[(df_passagem["UNIDADE"] == unidade)]["ÁREA"].sum()
        valores_passagem = []
        for coluna, categoria in zip(colunas, categorias):
            if categoria == "Em andamento":
                filtro = df_passagem["Projeto"] == "EM ANDAMENTO"
            else:
                filtro = df_passagem[coluna] == "OK"
            
            area_categoria = df_passagem[(df_passagem["UNIDADE"] == unidade) & filtro]["ÁREA"].sum()
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

######################## GRÁFICO ########################

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

    fig.update_traces(marker_color="#76b82a", texttemplate="%{text:.0f}%", textposition="outside")

    fig.update_layout(
        showlegend=False,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(range=[0, 105], showgrid=True, showticklabels=True, title='Porcentagem (%)', showline=False, zeroline=False),
        yaxis=dict(showgrid=False, showticklabels=True, title='', showline=False, zeroline=False),
    )

    # Exibir o gráfico dinâmico no Streamlit
    st.subheader(f"Acompanhamento de {opcao_tipo} - {opcao_visualizacao}")
    st.plotly_chart(fig)

######################## TABELAS ########################

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
    try:
        # Converte para float
        planejado = float(planejado)
        executado = float(executado)

        # Se ambos forem 0, a aderência é 100%
        if planejado == 0 and executado == 0:
            return 100
        
        # Se apenas um for 0, aderência é 0%
        if planejado == 0 or executado == 0:
            return 0

        # Divide o menor pelo maior e multiplica por 100
        menor = min(planejado, executado)
        maior = max(planejado, executado)
        return (menor / maior) * 100
    
    except ValueError:
        # Se não forem numéricos, retorna 100% se forem iguais, senão 0%
        return 100 if str(planejado).strip().lower() == str(executado).strip().lower() else 0

# Página de Auditoria
def auditoria():
    st.title("🔍 Auditoria")
    global df_auditoria

    # Aplicando os filtros e retornando o DataFrame filtrado
    df_auditoria = filtros_auditoria(df_auditoria)

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
    colunas_aderencia = [col for col in df_auditoria.columns if "Aderência" in col]  # Obter todas as colunas de aderência

    # Calcular a média de cada item (linha a linha) e armazenar no formato desejado
    df_media_itens = df_auditoria[colunas_aderencia].mean().reset_index()
    df_media_itens.columns = ["Item", "Média Aderência (%)"]  # Renomear as colunas para facilitar a leitura

    # Dicionário para renomear os itens (exemplo, ajustando conforme necessário)
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
                        x="Item",                 # Eixo Y com os itens de aderência
                        y="Média Aderência (%)",  # Eixo X com as médias de aderência
                        text="Média Aderência (%)",
                        orientation="v",         # "h" para barras horizontais
                        color="Item",             # Cor única para cada barra
                        color_discrete_sequence=px.colors.qualitative.Set1,  # Lista de cores distintas
                        )  # Remover título do eixo X

    # Ajustar a posição do rótulo para fora da barra
    fig_aderencia.update_traces(textposition='outside')

    # Ajustar os valores no gráfico para mostrar sem casas decimais
    fig_aderencia.update_traces(texttemplate='%{text:.0f}%')

    fig_aderencia.update_layout(
        showlegend=False,  # Não mostrar a legenda
        xaxis=dict(showgrid=False, showticklabels=True, title='', showline=False, zeroline=False),
        yaxis=dict(showgrid=False, showticklabels=False, showline=False, zeroline=False))

    # Exibir gráfico
    st.write("### Aderência")
    st.plotly_chart(fig_aderencia)

    st.divider()

    # Exibir tabela formatada
    st.write("### Planejado x Executado")
    st.dataframe(df_tabela)

########################################## EXTRAS ##########################################

# Página de Atividades Extras
def atividades_extras():
    st.title("📌 Atividades Extras")
    global df_extras

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
        st.plotly_chart(fig_colab)
    
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
        st.plotly_chart(fig_setor)
    
    # Tabela
    df_extras["Data"] = pd.to_datetime(df_extras["Data"]).dt.strftime("%d/%m/%Y")
    st.write("### Detalhes das Atividades")
    atividades_realizadas = df_extras[["Data", "Colaborador", "Atividade", "Solicitante", "SetorSolicitante", "Horas"]]
    st.dataframe(atividades_realizadas, use_container_width=True, hide_index=True)

########################################## FILTROS ##########################################

# Função para filtros da aba Dashboard
def filtros_dashboard(df_tarefas):

    st.sidebar.title("Filtros")

    # Filtro de Data
    # Garantir que a coluna "Data" está em formato datetime
    df_tarefas["Data"] = pd.to_datetime(df_tarefas["Data"], errors='coerce')

    # Definindo o intervalo de datas
    data_min = df_tarefas["Data"].min().date()  # Convertendo para date
    data_max = df_tarefas["Data"].max().date()  # Convertendo para date

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
    df_tarefas = df_tarefas[(df_tarefas["Data"] >= data_inicio) & 
                            (df_tarefas["Data"] <= data_fim)]
    
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

# Função para filtros da aba Dashboard
def filtros_atividades(df_tarefas):

    st.sidebar.title("Filtros")

    # Filtro de Data
    # Garantir que a coluna "Data" está em formato datetime
    df_tarefas["Data"] = pd.to_datetime(df_tarefas["Data"], errors='coerce')

    # Definindo o intervalo de datas
    data_min = df_tarefas["Data"].min().date()  # Convertendo para date
    data_max = df_tarefas["Data"].max().date()  # Convertendo para date
    
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
    df_tarefas = df_tarefas[(df_tarefas["Data"] >= data_inicio) & 
                                   (df_tarefas["Data"] <= data_fim)]
    
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

# Função para filtros da aba Extras
def filtros_extras(df_extras):

    st.sidebar.title("Filtros")

    # Garantir que a coluna "Data" está em formato datetime
    df_extras["Data"] = pd.to_datetime(df_extras["Data"], errors='coerce')

    # Definindo o intervalo de datas
    data_min = df_extras["Data"].min().date()  # Convertendo para date
    data_max = df_extras["Data"].max().date()  # Convertendo para date
    
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
        st.session_state["logged_in"] = True  # Apenas inicializa na primeira execução

    # Sempre chama a main_app, mas a lógica de exibição pode depender de logged_in
    if st.session_state["logged_in"]:
        main_app()