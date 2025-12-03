import unittest
import time
from unittest.mock import Mock, patch, MagicMock

# Importa o Mixin que contém a thread
from server.dist_server.background_tasks import BackgroundTasksMixin

# Classe Dummy para simular o Server
class DummyServer(BackgroundTasksMixin):
    def __init__(self):
        self.id = "SERVER_TEST"
        self.start_time = time.time()
        self._running = True
        self.lock = unittest.mock.MagicMock()
        self._send_to_supervisor = unittest.mock.MagicMock()
        
        # Estado interno simulado
        self.task_queue = []
        self.worker_status = {}
        self.peer_status = {}
        
        # Configuração simulada
        self.config = {
            'load_balancing': {'max_queue_threshold': 50},
            'timing': {'heartbeat_timeout': 30},
            'server': {'id_number': '1'},

            'supervisor': {
                'supervisor_interval': 1,  
                'supervisor_info': {"ip":'127.0.0.1','port': 8000}               
            }
        }

class TestPerformanceThread(unittest.TestCase):

    def setUp(self):
        self.server = DummyServer()

    @patch('server.dist_server.background_tasks.psutil')
    @patch('server.dist_server.background_tasks.server_performance_report')
    @patch('time.sleep')

    def test_performance_reporter_loop(self, mock_sleep, mock_payload_gen, mock_psutil):
        """
        Testa uma iteração do loop de performance.
        """
        
        # --- 1. CONFIGURA OS MOCKS (Simulando o Hardware) ---
        # Agora mock_psutil é de fato o psutil
        mock_psutil.cpu_percent.return_value = 15.5
        mock_psutil.cpu_count.return_value = 4
        
        # Simula Memória
        mock_mem = MagicMock()
        mock_mem.total = 16 * 1024 * 1024 * 1024 
        mock_mem.available = 8 * 1024 * 1024 * 1024
        mock_mem.percent = 50.0
        mock_mem.used = 8 * 1024 * 1024 * 1024
        mock_psutil.virtual_memory.return_value = mock_mem
        
        # Simula Disco
        mock_disk = MagicMock()
        mock_disk.total = 500 * 1024**3
        mock_disk.free = 250 * 1024**3
        mock_disk.percent = 50.0
        mock_psutil.disk_usage.return_value = mock_disk

        # Simula Load Avg
        mock_psutil.getloadavg.return_value = (1.5, 1.2, 1.0)

        # --- 2. CONFIGURA O ESTADO DA "FAZENDA" ---
        self.server.task_queue = ["task1", "task2"]
        self.server.worker_status = {
            "w1": {"last_seen": time.time(), "OWNER_ID": "1"},
            "w2": {"last_seen": time.time() - 1000, "OWNER_ID": "1"}
        }

        # --- 3. CONTROLE DO LOOP ---
        
        mock_sleep.return_value = None 

        def stop_server_after_report(*args, **kwargs):
            self.server._running = False
            return {"mock": "payload"}

        mock_payload_gen.side_effect = stop_server_after_report

        # --- 4. EXECUTA (Act) ---
        self.server._performance_reporter_loop()

        # --- 5. VERIFICA (Assert) ---
        
        # Verifica se psutil foi chamado
        mock_psutil.cpu_percent.assert_called()
        mock_psutil.virtual_memory.assert_called()
        
        # Verifica se gerou o payload
        self.assertTrue(mock_payload_gen.called)
        
        # Valida os argumentos passados
        args, kwargs = mock_payload_gen.call_args
        passed_system = kwargs['system_data']
        passed_farm = kwargs['farm_data']

        self.assertEqual(passed_system['cpu']['usage_percent'], 15.5)
        self.assertEqual(passed_system['memory']['total_mb'], 16384) 
        
        self.assertEqual(passed_farm['workers']['total_registered'], 2)
        self.assertEqual(passed_farm['workers']['workers_alive'], 1) 
        self.assertEqual(passed_farm['workers']['workers_failed'], 1)
        self.assertEqual(passed_farm['tasks']['tasks_pending'], 2)

        print(kwargs)
