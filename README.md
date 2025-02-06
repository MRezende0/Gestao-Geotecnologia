# ERP de Gestão Financeira

Este é um **ERP de Gestão Financeira** desenvolvido com **Python** e **Streamlit**, projetado para auxiliar no controle financeiro de empresas. Ele oferece uma interface moderna e intuitiva, permitindo a gestão de receitas, despesas e relatórios financeiros, além de buscar informações de empresas por meio de consultas de CNPJ.

## **Funcionalidades**

- **Login Seguro**:
  - Acesso restrito com autenticação por e-mail e senha.
  - Use para fazer login: 20242025" senha: 123

- **Dashboard Financeiro**:
  - Visualização consolidada de receitas, despesas e saldo.
  - Gráficos interativos para análise de categorias de receitas e despesas.

- **Registro de Transações**:
  - Cadastro de receitas e despesas com informações detalhadas, como:
    - Data.
    - Descrição.
    - Categoria.
    - Valor.
    - Tipo (Receita ou Despesa).

- **Relatórios Financeiros**:
  - Tabela detalhada das transações realizadas.
  - Gráficos interativos (pizza) para análise de distribuição por categorias.

- **Consulta de CNPJ**:
  - Busca informações de empresas a partir do número do CNPJ:
    - Nome da empresa.
    - Situação cadastral.
    - UF.
    - Atividade principal.

## **Pré-requisitos**

Antes de executar o projeto, certifique-se de que as seguintes bibliotecas estão instaladas no seu ambiente Python:

```bash
pip install streamlit pandas plotly requests
```

## **Como Executar**

1. **Clone o Repositório**:
   ```bash
   git clone https://github.com/seu-usuario/seu-repositorio.git
   cd seu-repositorio
   ```

2. **Execute o Sistema**:
   No terminal, digite:
   ```bash
   streamlit run app.py
   ```

3. **Acesse no Navegador**:
   O Streamlit abrirá automaticamente no navegador, mas caso não abra, acesse:
   ```
   http://localhost:8501
   ```

4. **Login**:
   Use as seguintes credenciais para acessar o sistema:
   - **E-mail**: `marketing@odoscontabilidade.com.br`
   - **Senha**: `odos123`

## **Tecnologias Utilizadas**

- **Python**: Linguagem principal do sistema.
- **Streamlit**: Framework para criação de interfaces web interativas.
- **Pandas**: Manipulação e análise de dados financeiros.
- **Plotly**: Criação de gráficos interativos.
- **Requests**: Consulta de APIs (usada para buscar informações de CNPJ).

## **Exemplo de Uso**

### **Dashboard Financeiro**
O dashboard exibe as métricas financeiras consolidadas:
- Total de receitas.
- Total de despesas.
- Saldo atual.
Além disso, inclui gráficos para análise detalhada de categorias.

### **Registro de Transações**
Permite o cadastro de receitas e despesas com informações como data, descrição e valor, ajudando a organizar e controlar o fluxo financeiro.

### **Consulta de CNPJ**
Busca informações de uma empresa através do CNPJ, integrando dados úteis como nome, situação cadastral e atividade principal.

## **Contribuições**

Contribuições são bem-vindas! Se você tiver sugestões, problemas ou melhorias, fique à vontade para abrir uma issue ou um pull request neste repositório.

## **Licença**

Este projeto está licenciado sob a licença MIT. Consulte o arquivo `LICENSE` para mais detalhes.
