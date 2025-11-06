# Worker/dist_worker/worker.py
import uuid
import time
import json # <-- Importe JSON
from ..logs.logger import logger
from .client_actions import ClientActionsMixin
from .main_loop import LogicMixin

class Worker(ClientActionsMixin, LogicMixin):
    
    def __init__(self, config_path=None):
        """
        Inicializa o worker e seu estado, carregando
        a configuração de um arquivo JSON.
        """
        logger.info(f"Inicializando worker com config: {config_path}")
        
        if not config_path:
            raise ValueError("O caminho para o arquivo de configuração (config_path) é obrigatório.")
            
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Carrega os dados do JSON
            self.home_host = config['home_server']['host']
            self.home_port = config['home_server']['port']
            self.home_uuid = config['home_server']['uuid']
            
        except FileNotFoundError:
            logger.critical(f"ERRO: Arquivo de configuração '{config_path}' não encontrado!")
            raise
        except KeyError as e:
            logger.critical(f"ERRO: Chave '{e}' ausente no arquivo '{config_path}'!")
            raise
        except Exception as e:
            logger.critical(f"ERRO: Falha ao carregar ou processar o config '{config_path}': {e}")
            raise
        
        
        # --- Estado do Worker ---
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