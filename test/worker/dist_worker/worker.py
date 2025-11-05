# dist_worker/worker.py
import uuid
import time
from ..logs.logger import logger
from .client_actions import ClientActionsMixin
from .main_loop import LogicMixin

class Worker(ClientActionsMixin, LogicMixin):
    
    def __init__(self, config_path=None):
        """
        Inicializa o worker e seu estado.
        (config_path não é usado, mas está aqui para
         manter o padrão do Server)
        """
        logger.info("Inicializando worker...")
        
        # --- Estado do Worker (movido do script principal) ---
        self.home_host = "127.0.0.1" 
        self.home_port = 9002
        self.home_uuid = "SERVER_2"
        self.worker_id = f"WORKER_{uuid.uuid4().hex[:6]}"
        
        # O estado dinâmico que muda
        self.current_master_host = self.home_host
        self.current_master_port = self.home_port
        self.owner_id = self.home_uuid # O 'dono' original
        
        # Flag de controle
        self._running = True
        
        logger.success(f"Worker {self.worker_id} inicializado. DONO: {self.home_host}:{self.home_port} ({self.home_uuid})")

    def start(self):
        """Inicia o loop principal do worker."""
        # _run_loop() vem do LogicMixin e contém o "while self._running"
        self._run_loop()
        
    def stop(self):
        """Sinaliza para o loop parar na próxima iteração."""
        logger.warning("Sinal de encerramento recebido...")
        self._running = False