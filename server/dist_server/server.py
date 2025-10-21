# dist_server/server.py
import socket
import threading
import json
import time
from typing import Dict, List

# Importa o logger do pacote (ou de onde ele estiver)
from logs.logger import logger
# Importa os Mixins
from .connection_handler import ConnectionHandlerMixin
from .background_tasks import BackgroundTasksMixin
from .client_actions import ClientActionsMixin
from .state_helpers import StateHelpersMixin

# A classe Server agora herda de todos os Mixins
class Server(ConnectionHandlerMixin, 
             BackgroundTasksMixin, 
             ClientActionsMixin, 
             StateHelpersMixin):
    
    def __init__(self, config_path="config.json"):
        """Inicializa o servidor carregando a configuração e o estado."""
        logger.info(f"Inicializando servidor com config: {config_path}")
        self._load_config(config_path)

        # Estado do Servidor
        self.id = f'SERVER_{self.id_number}'
        self.peer_status: Dict[str, Dict] = {}
        self.worker_status: Dict[str, Dict] = {}
        self.active_peers: List[Dict] = list(self.config['peers'])
        self.redirect_queue: List[Dict] = []
        self.completed_task_timestamps: List[float] = []
        self.lock = threading.Lock() # Lock único (como antes)

        # Controle de Threads
        self._threads: List[threading.Thread] = []
        self._running = True
        self.server_socket = None # Para o shutdown

        logger.success(f"Servidor {self.id} ({self.host}:{self.port}) inicializado.")

    def _load_config(self, config_path):
        """Carrega a configuração do arquivo JSON."""
        try:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
            self.host = self.config['server']['ip']
            self.port = self.config['server']['port']
            self.id_number = self.config['server']['id_number']
        except FileNotFoundError:
            logger.critical(f"Arquivo de configuração '{config_path}' não encontrado!")
            raise
        except KeyError as e:
            logger.critical(f"Chave de configuração ausente em '{config_path}': {e}")
            raise

    # --- MÉTODOS DE CONTROLE DO SERVIDOR ---
    def start(self):
        """Inicia todas as threads de fundo do servidor."""
        logger.info("Iniciando threads do servidor...")
        self._running = True

        # Métodos _loop (ex: _listen_loop) vêm dos Mixins!
        thread_targets = {
            "Listener": self._listen_loop,
            "Heartbeat": self._heartbeat_loop,
            "Monitor": self._monitor_loop,
            "LoadBalancer": self._load_balancer_loop
        }

        for name, target in thread_targets.items():
            # Usar daemon=False se você quiser que o .join() no stop() 
            # funcione de forma mais confiável.
            thread = threading.Thread(target=target, name=name, daemon=True)
            thread.start()
            self._threads.append(thread)
            logger.info(f"Thread '{name}' iniciada.")

        # Mantém a thread principal viva
        self._wait_for_shutdown()

    def _wait_for_shutdown(self):
        """Mantém o servidor rodando até receber um sinal de interrupção."""
        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        """Sinaliza para as threads pararem (implementação melhorada)."""
        if not self._running:
            return # Já está parando
            
        logger.warning("Recebido sinal de encerramento...")
        self._running = False

        # 1. Fecha o socket principal para desbloquear o .accept()
        try:
            if self.server_socket:
                self.server_socket.close()
                logger.info("Socket do listener fechado.")
        except Exception as e:
            logger.error(f"Erro ao fechar socket do listener: {e}")

        # 2. (Opcional, mas recomendado) Espera as threads terminarem
        # logger.info("Aguardando threads finalizarem...")
        # for thread in self._threads:
        #    thread.join(timeout=2.0) # Espera com timeout
        #    if thread.is_alive():
        #        logger.warning(f"Thread '{thread.name}' não finalizou a tempo.")
        
        logger.info("Servidor encerrado.")