# Gestão Geotecnologia

Sistema de gestão para a equipe de Geotecnologia, desenvolvido com Streamlit e integrado ao Google Sheets.

## Funcionalidades

- **Dashboard**: Visualização geral das atividades e métricas
- **Registrar**: Registro de diferentes tipos de atividades
  - Atividade Semanal
  - Atividade Extra
  - Reforma e Passagem
  - Pós-Aplicação
  - Auditoria
- **Atividades**: Acompanhamento de tarefas semanais
- **Reforma e Passagem**: Acompanhamento de projetos de reforma e passagem
- **Auditoria**: Gestão de auditorias
- **Extras**: Controle de atividades extras

## Requisitos

- Python 3.8+
- Dependências listadas em `requirements.txt`
- Credenciais do Google Sheets configuradas no Streamlit Secrets

## Instalação

1. Clone o repositório
2. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure as credenciais do Google Sheets no Streamlit Secrets
4. Execute a aplicação:
   ```bash
   streamlit run app.py
   ```

## Estrutura do Projeto

```
.
├── app.py              # Aplicação principal
├── dados/             # Diretório de dados
│   └── pos-aplicacao/ # Dados de pós-aplicação
├── imagens/           # Imagens e ícones
└── requirements.txt   # Dependências do projeto
```

## Google Sheets

A aplicação utiliza o Google Sheets como banco de dados, com as seguintes abas:
- Tarefas
- AtividadesExtras
- Auditoria
- Base
- Reforma
- Passagem

## Desenvolvimento

Para contribuir com o projeto:

1. Faça um fork do repositório
2. Crie uma branch para sua feature
3. Faça commit das suas alterações
4. Envie um pull request

## Suporte

Em caso de dúvidas ou problemas, entre em contato com a equipe de desenvolvimento.
