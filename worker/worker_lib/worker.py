# worker_lib/worker.py
import json # Importa json
from typing import Dict

# Importa os Mixins
from .connection_loop import ConnectionLoopMixin
from .task_processor import TaskProcessorMixin

# Importa o logger
from logs.logger import logger
# A linha 'from . import config' foi REMOVIDA

class Worker(ConnectionLoopMixin, TaskProcessorMixin):
    
    def __init__(self, config_path="config.json"):
        """Inicializa o Worker carregando configuração e estado."""
        
        # 1. Carrega configurações do arquivo JSON
        self._load_config(config_path)
        
        # 2. Define atributos a partir do config carregado
        try:
            self.worker_id = self.config['worker_id']
            self.owner_id = self.config['home_master']['id']
            self.reconnect_delay = self.config['timing']['reconnect_delay']
            
            self.home_master: Dict[str, any] = {
                'ip': self.config['home_master']['ip'],
                'port': self.config['home_master']['port']
            }
        except KeyError as e:
            logger.critical(f"Chave de configuração ausente em '{config_path}': {e}")
            raise # Impede o worker de iniciar sem config válida

        logger.info(f"Inicializando Worker ID: {self.worker_id}")

        # 3. Inicializa o estado (substitui o state.py)
        self.current_master: Dict[str, any] = self.home_master.copy()

        # 4. Controle de loop
        self._running = True

    def _load_config(self, config_path):
        """Carrega a configuração do arquivo JSON."""
        try:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
            logger.info(f"Configuração '{config_path}' carregada.")
        except FileNotFoundError:
            logger.critical(f"Arquivo de configuração '{config_path}' não encontrado!")
            raise
        except json.JSONDecodeError:
            logger.critical(f"Erro ao decodificar (formato inválido) o JSON em '{config_path}'!")
            raise

    def start(self):
        """Inicia o loop principal de conexão do Worker."""
        
        # Adiciona o worker_id ao contexto do logger 
        with logger.contextualize(worker_id=self.worker_id):
            logger.info("Worker iniciado. Entrando no loop de conexão...")
            self._running = True
            
            # Chama o método herdado do ConnectionLoopMixin
            self._connection_loop()

    def stop(self):
        """Sinaliza para o loop principal parar."""
        logger.warning("Recebendo sinal de parada...")
        self._running = False