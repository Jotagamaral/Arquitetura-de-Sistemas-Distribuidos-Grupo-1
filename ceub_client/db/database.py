import mysql.connector
from mysql.connector import Error
from datetime import datetime

def buscar_saldo(cpf):
    """
    Busca o nome do cliente e o saldo da conta no banco de dados MySQL com base no CPF.
    """
    connection = None
    try:
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password='ceub123456',
            database='sys'
        )
        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)
            sql_query = "SELECT c.NOME, a.SALDO FROM CONTA AS a JOIN USERS AS c ON a.fk_id_user = c.ID WHERE C.CPF = %s"
            cursor.execute(sql_query, (cpf,))
            usuario = cursor.fetchone()
            if usuario:
                return (usuario['NOME'], usuario['SALDO'], datetime.now().isoformat())
    except Error as e:
        print(f"Erro de DB na thread: {e}")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
    return None

def atualizar_saldo(cpf: str, novo_saldo: float) -> bool:
    """
    Atualiza o saldo de um usuário no banco de dados com base no seu CPF.
    """
    connection = None
    try:
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password='ceub123456',
            database='sys'
        )
        if connection.is_connected():
            cursor = connection.cursor()
            sql_query = "UPDATE CONTA AS a JOIN USERS AS c ON a.fk_id_user = c.ID SET a.SALDO = %s WHERE c.CPF = %s"
            cursor.execute(sql_query, (novo_saldo, cpf))
            connection.commit()
            if cursor.rowcount > 0:
                return True
    except Error as e:
        print(f"Erro de DB na thread: {e}")
        if connection:
            connection.rollback()
    finally:
        if connection and connection.is_connected():
            connection.close()
    return False
