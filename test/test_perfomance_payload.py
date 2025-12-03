import unittest
# Import absoluto da raiz
from payload_models import server_performance_report

class TestPerformancePayload(unittest.TestCase):

    def test_server_performance_report_structure(self):
        """
        Testa se o payload de performance segue a estrutura hierárquica correta.
        """
        # 1. PREPARA (Dados fictícios)
        server_uuid = "SERVER_TEST_1"
        
        system_data = {
            "cpu": {"usage_percent": 50.0},
            "memory": {"percent_used": 30.0}
        }
        
        farm_data = {
            "workers": {"alive": 5, "total": 10},
            "tasks": {"pending": 0}
        }
        
        config_data = {"max_queue": 100}
        
        neighbors_data = [{"id": "S2", "status": "ok"}]

        # 2. AGE
        payload = server_performance_report(
            server_uuid=server_uuid,
            system_data=system_data,
            farm_data=farm_data,
            config_thresholds=config_data,
            neighbors_data=neighbors_data
        )

        # 3. VERIFICA (Assert)
        
        # Verifica campos da raiz
        self.assertEqual(payload["server_uuid"], server_uuid)
        self.assertEqual(payload["task"], "performance_report")
        self.assertIn("timestamp", payload)  # Verifica se gerou timestamp
        self.assertIn("mensage_id", payload) # Verifica se gerou UUID da mensagem
        
        # Verifica se 'system' está dentro de 'performance'
        self.assertEqual(payload["performance"]["system"], system_data)
        
        # Verifica se 'farm_state' está na raiz (conforme definimos no último passo)
        self.assertEqual(payload["performance"]["farm_state"], farm_data)
        
        # Verifica vizinhos e config
        self.assertEqual(payload["config_thresholds"], config_data)
        self.assertEqual(payload["neighbors"], neighbors_data)
