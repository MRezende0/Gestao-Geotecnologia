import streamlit as st
import pandas as pd
import plotly.express as px
import os
from dateutil.relativedelta import relativedelta
from datetime import datetime
import openpyxl

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

########################################## DADOS ########################################## 

# Caminho dos arquivos CSV
BASE_PATH = "dados/base.csv"
TAREFAS_PATH = "dados/tarefas.csv"
EXTRAS_PATH = "dados/extras.csv"
POS_PATH = "dados/pos_aplicacao.xlsx"
REF_PAS_PATH = "dados/reforma_passagem.xlsx"

# Função para carregar dados de CSV ou Excel
def carregar_dados(caminho, colunas=None, aba=None):
    if os.path.exists(caminho):
        _, extensao = os.path.splitext(caminho)
        extensao = extensao.lower()
        if extensao == ".csv":
            return pd.read_csv(caminho)
        elif extensao in [".xls", ".xlsx"]:
            if aba is not None:
                return pd.read_excel(caminho, sheet_name=aba)
            else:
                return pd.read_excel(caminho)  # Carrega a primeira aba por padrão
        else:
            raise ValueError(f"Formato de arquivo {extensao} não suportado!")
    else:
        return pd.DataFrame(columns=colunas)
    
# Carrega as duas abas
df_passagem = carregar_dados(REF_PAS_PATH, aba=0)  # Carrega a primeira aba
df_reforma = carregar_dados(REF_PAS_PATH, aba=1)  # Carrega a segunda aba

# Carrega os dados iniciais
df_tarefas = carregar_dados(TAREFAS_PATH, ["Data", "Setor", "Colaborador", "Tipo", "Status"])
df_base = carregar_dados(BASE_PATH, ["Unidade", "Setor", "Area"])
df_pos = carregar_dados(POS_PATH, ["UNIDADE", "SETOR", "TALHÃO", "AREA", "DESC_OPERAÇÃO", "DATA"])
df_extras = carregar_dados(EXTRAS_PATH, ["Data", "Colaborador", "Solicitante", "SetorSolicitante", "Atividade", "Horas", "Descrição"])
df_ref_pas = carregar_dados(REF_PAS_PATH, [""])

# Mesclar bases de dados
df_tarefas = df_tarefas.merge(df_base, on="Setor", how="left")

########################################## DASHBOARD ##########################################

def dashboard():
    st.title("📊 Dashboard")
    global df_tarefas

    # Aplicando os filtros e retornando o DataFrame filtrado
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
        st.metric("Colaboradores", df_tarefas['Colaborador'].unique().size)

    st.divider()

    # Layout com 2 colunas e 3 linhas
    col1, linha, col2 = st.columns([4, 0.5, 4])

    # Linha 1 - Gráficos de Atividades por Colaborador e Projetos por Tipo
    with col1:

        # Gráfico de Atividades por Colaborador
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

        # Gráfico de Quantidade de Projetos por Tipo
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

        # Gráfico de Status dos Projetos
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

    with col2:

        # Gráfico de Projetos por Unidade
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
        st.plotly_chart(fig_pizza)

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

########################################## REGISTRAR ##########################################

# Função para salvar dados
def salvar_dados(df, caminho):
    df.to_csv(caminho, index=False)

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
            nova_tarefa = pd.DataFrame({
                "Data": [Data],
                "Setor": [Setor],
                "Colaborador": [Colaborador],
                "Tipo": [Tipo],
                "Status": [Status]
            })
            
            if os.path.exists(TAREFAS_PATH):
                df_tarefas = pd.read_csv(TAREFAS_PATH)
            else:
                df_tarefas = pd.DataFrame(columns=["Data", "Setor", "Colaborador", "Tipo", "Status"])
            
            df_tarefas = pd.concat([df_tarefas, nova_tarefa], ignore_index=True)
            salvar_dados(df_tarefas, TAREFAS_PATH)
            st.success("Atividade Semanal registrada com sucesso!")

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
            salvar_dados(df_extras, EXTRAS_PATH)
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

########################################## ATIVIDADES ##########################################

# Função para exibir os projetos como cards clicáveis
def tarefas_semanais():
    st.title("📂 Atividades")

    # Garantir que os dados sejam carregados corretamente
    global df_tarefas  # Usa a variável global para evitar redefinição local errada
    df_tarefas = carregar_dados(TAREFAS_PATH, ["Data", "Setor", "Colaborador", "Tipo", "Status"])

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
                Data = st.date_input("Data", value=datetime.strptime(tarefa["Data"], "%Y-%m-%d"))
                Setor = st.number_input("Setor", value=tarefa["Setor"], min_value=0, step=1, format="%d")
                Colaborador = st.selectbox("Colaborador", ["Ana", "Camila", "Gustavo", "Maico", "Márcio", "Pedro", "Talita", "Washington", "Willian", "Iago"], index=(["Ana", "Camila", "Gustavo", "Maico", "Márcio", "Pedro", "Talita", "Washington", "Willian", "Iago"].index(tarefa["Colaborador"]) if tarefa["Colaborador"] in ["Ana", "Camila", "Gustavo", "Maico", "Márcio", "Pedro", "Talita", "Washington", "Willian"] else 0))
                Tipo = st.selectbox("Tipo", ["Projeto de Sistematização", "Mapa de Sistematização", "LOC", "Projeto de Transbordo", "Auditoria", "Projeto de Fertirrigação", "Projeto de Sulcação", "Mapa de Pré-Plantio", "Mapa de Pós-Plantio", "Projeto de Colheita", "Mapa de Cadastro"], index=["Projeto de Sistematização", "Mapa de Sistematização", "LOC", "Projeto de Transbordo", "Auditoria", "Projeto de Fertirrigação", "Projeto de Sulcação", "Mapa de Pré-Plantio", "Mapa de Pós-Plantio", "Projeto de Colheita", "Mapa de Cadastro"].index(tarefa["Tipo"]))
                Status = st.selectbox("Status", ["A fazer", "Em andamento", "A validar", "Concluído"], index=["A fazer", "Em andamento", "A validar", "Concluído"].index(tarefa["Status"]))

                # Botões de salvar e cancelar
                col1, col2 = st.columns(2)

                with col1:
                    if st.form_submit_button("Salvar Alterações"):
                        # Atualiza o projeto no DataFrame
                        index = df_tarefas[df_tarefas["Tipo"] == tarefa["Tipo"]].index[0]
                        df_tarefas.loc[index] = {
                            "Data": Data.strftime("%Y-%m-%d"),
                            "Setor": Setor,
                            "Colaborador": Colaborador,
                            "Tipo": Tipo,
                            "Status": Status
                        }

                        salvar_dados(df_tarefas, TAREFAS_PATH)  # Salva no CSV
                        st.session_state["projeto_selecionado"] = df_tarefas.loc[index].to_dict()
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

    # Métricas de Reforma
    st.write("### Métricas de Reforma")

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

    # Exibir tabela no Streamlit
    st.dataframe(df_metrica_reforma, use_container_width=True, hide_index=True)

    st.divider()

    # Métricas de Passagem
    st.write("### Métricas de Passagem")

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

    # Exibir tabela no Streamlit
    st.dataframe(df_metrica_passagem, use_container_width=True, hide_index=True)

    st.divider()

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

########################################## AUDITORIA ##########################################

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