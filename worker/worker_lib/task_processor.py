# worker_lib/task_processor.py
import time
from random import randint
from logs.logger import logger

class TaskProcessorMixin:
    
    def _process_task(self, task_data: dict) -> dict:
        """
        Simula o processamento de uma tarefa recebida (agora é um método).
        """
        user = task_data.get("USER")
        logger.info(f"Processando tarefa de consulta para o usuário: {user}")

        # Simulação: sucesso
        if user != 'Joao':
            time.sleep(2)  # Simula tempo de processamento
            
            # self.worker_id é herdado da classe Worker principal
            response = {
                "STATUS": "OK", 
                "SALDO": randint(50, 999), 
                "USER": user, 
                "WORKER_ID": self.worker_id
            }
            logger.success(f"Tarefa concluída com sucesso.")
            return response
        else:
            time.sleep(1)
            response = {
                "STATUS": "NOK", 
                "TASK": "QUERY", 
                "ERROR": f"User not found"
            }
            logger.warning(f"Tarefa para '{user}' falhou: Usuário não encontrado.")
            return response