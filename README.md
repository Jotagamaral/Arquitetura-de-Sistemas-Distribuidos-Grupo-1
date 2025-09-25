## 🚀 Guia de Execução Rápida (Quick Start)

1.  **Clone o repositório:**
    ```bash
    git clone https://github.com/Jotagamaral/Arquitetura-de-Sistemas-Distribuidos-Grupo-1.git
    cd projeto
    ```

2.  **Instale as dependências:**
    ```bash
    pip install websockets mysql-connector-python
    ```

3.  **Configure o Banco de Dados:**
    * Certifique-se de que seu servidor MySQL está rodando.
    * Execute o script SQL para criar as tabelas (veja a seção `5. Como Executar o Projeto` para o código SQL).
    * Ajuste as credenciais do banco em `client.py`.

4.  **Inicie os Servidores:**
    * Abra um terminal para cada instância do servidor que deseja executar.
    * Ajuste `MY_ADDRESS` e `PEER_SERVERS` em cada arquivo.
    ```bash
    # Terminal 1
    python server_8765.py

    # Terminal 2
    python server_8766.py
    ```

5.  **Inicie o Cliente de Teste (Worker):**
    * Ajuste os parâmetros de teste em `client.py`.
    * Em um novo terminal, execute:
    ```bash
    python client.py
    ```
