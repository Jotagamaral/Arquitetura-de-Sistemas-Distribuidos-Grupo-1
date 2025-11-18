# payload_models.py
"""
Centraliza a criação de todos os payloads (contratos)
usados na comunicação entre Servidor e Worker.
"""
import uuid

# --- Payloads enviados pelo WORKER ---

# PADRÃO PAYLOAD OK
def get_task(worker_id: str, owner_id: tuple = None) -> dict:
    """Payload que o Worker envia para PEDIR uma tarefa."""
    payload = {
        "WORKER": "ALIVE", 
        "WORKER_UUID": worker_id
    }
    if owner_id:
        # Se eu sou emprestado, eu informo quem é meu dono
        payload["SERVER_UUID"] = owner_id 

    print(payload)
    return payload

# PADRÃO PAYLOAD OK
def task_status(worker_id: str, status: str, task: str) -> dict:
    """Payload que o Worker envia para REPORTAR o status de uma tarefa."""
    payload = {
        "STATUS": status, # "OK" ou "NOK"
        "TASK": task,
        "WORKER_UUID": worker_id,
    }

    print(payload)
    return payload

# --- Payloads criados pelo PRODUTOR (interno do Servidor) ---

# PADRÃO PAYLOAD OK
def new_task_payload(user: str, task_type: str = "QUERY") -> dict:
    """
    Este é o payload da TAREFA EM SI. 
    É o que é colocado na fila e depois enviado ao Worker.
    """
    payload = {
        "TASK": task_type, # Identifica que este JSON é uma tarefa
        "USER": user,
    }

    print(payload)
    return payload

# --- Payloads enviados pelo SERVIDOR (Apenas como referência) ---

def server_no_task() -> dict:
    """Payload que o Servidor envia quando a fila está vazia."""
    payload = {"TASK": "NO_TASK"}

    print(payload)
    return payload

def server_ack() -> dict:
    """Payload que o Servidor envia para confirmar o recebimento de um status."""
    payload = {"STATUS": "ACK"} # ACK = Acknowledged (Confirmado)

    print(payload)
    return payload

def server_heartbeat(server_id: str) -> dict:
    """
    Payload que um Servidor (self.id) envia para um peer
    para checar se ele está ativo.
    """
    payload = {
        "SERVER_UUID": server_id,
        "TASK": "HEARTBEAT"
    }

    print(payload)
    return payload

def server_request_worker(requestor_info: dict) -> dict:
    """
    Payload que um Servidor (MASTER) envia para um peer
    para solicitar workers (WORKER_REQUEST).
    """
    payload = {
        "TASK": "WORKER_REQUEST",
        "REQUESTOR_INFO": requestor_info # O dict {'ip':..., 'port':...}
    }

    print(payload)
    return payload

def server_command_release(master_id: str, worker_ids: list) -> dict:
    """
    Payload que um Servidor (MASTER) envia para um peer (o dono original)
    para notificar que está liberando (COMMAND_RELEASE) uma lista de workers.
    """
    payload = {
        "SERVER_UUID": master_id,
        "TASK": "COMMAND_RELEASE",
        "WORKERS_UUID": worker_ids # Lista de IDs dos workers
    }

    print(payload)
    return payload

def server_release_ack(master_id: str, workers_list: list) -> dict:
    """
    Payload que um Servidor (o dono original) envia de volta
    para confirmar (RELEASE_ACK) o recebimento de uma notificação
    COMMAND_RELEASE.
    """
    payload = {
        "SERVER_UUID": master_id,
        "RESPONSE": "RELEASE_ACK",
        "WORKERS_UUID": workers_list 
    }

    print(payload)
    return payload

def server_order_return(return_target_server: dict) -> dict:
    """
    Payload que um Servidor (MASTER) envia para um Worker
    ordenando que ele RETORNE ao seu dono original (MASTER_RETURN).
    """
    payload = {
        "TASK": "RETURN", 
        "SERVER_RETURN": return_target_server # O dict {'ip':..., 'port':...} do dono
    }

    print(payload)
    return payload

def server_order_redirect(redirect_target_server: dict) -> dict:
    """
    Payload que um Servidor envia para um Worker
    ordenando que ele seja REDIRECIONADO para um novo mestre (MASTER_REDIRECT).
    
    (Nota: Este payload não inclui 'MASTER' ID, seguindo seu original)
    """
    payload = {
        "TASK": "REDIRECT", 
        "SERVER_REDIRECT": redirect_target_server # O dict {'ip':..., 'port':...} do novo mestre
    }

    print(payload)
    return payload

def server_response_available(master_id: str, worker_uuid_list: list) -> dict:
    """
    Payload que um Servidor (MASTER) envia em resposta a um WORKER_REQUEST,
    indicando que workers (WORKER_UUID) estão disponíveis e sendo enviados.
    """
    payload = {
        "SERVER_UUID": master_id,
        "RESPONSE": "AVAILABLE",
        "WORKERS_UUID": worker_uuid_list
    }

    print(payload)
    return payload

def server_response_unavailable(master_id: str, include_empty_list: bool = False) -> dict:
    """
    Payload que um Servidor (MASTER) envia em resposta a um WORKER_REQUEST,
    indicando que NÃO há workers disponíveis.
    - Se 'include_empty_list' for True, adiciona "WORKER_UUID": [].
    """
    payload = {
        "SERVER_UUID": master_id,
        "RESPONSE": "UNAVAILABLE"
    }
    if include_empty_list:
        payload["WORKERS_UUID"] = []

    print(payload)
    return payload

def server_heartbeat_response(server_id: str) -> dict:
    """
    Payload que um Servidor (self.id) envia de volta
    em resposta a um HEARTBEAT de um peer, confirmando "ALIVE".
    """
    payload = {
        "SERVER_UUID": server_id,
        "TASK": "HEARTBEAT",
        "RESPONSE": "ALIVE"
    }

    print(payload)
    return payload

def server_release_completed(server_id: str, worker_uuids: list) -> dict:
    """
    Payload que o Servidor "Dono" (S2) envia ao Servidor "Emprestador" (S1)
    para confirmar que os workers chegaram em casa.
    """
    payload = {
        "SERVER_UUID": server_id,
        "RESPONSE": "RELEASE_COMPLETED", # É uma resposta, não uma TASK
        "WORKERS_UUID": worker_uuids
    }

    print(payload)
    return payload
