import unittest
# Use imports absolutos a partir da raiz do projeto ('test/' está na raiz)
from payload_models import get_task, server_command_release

class TestPayloadModels(unittest.TestCase):

    def test_get_task_simple(self):
        """
        Testa se o payload 'get_task' é criado corretamente
        sem um 'owner_id'.
        """
        # 1. Prepara & 2. Age
        worker_id = "w-123"
        payload = get_task(worker_id=worker_id, owner_id=None)
        
        # 3. Verifica (Assert)
        # O payload esperado
        expected = {
            "WORKER": "ALIVE",
            "WORKER_UUID": "w-123"
        }
        self.assertEqual(payload, expected)
        self.assertNotIn("SERVER_UUID", payload) # Garante que a chave extra não está lá

    def test_get_task_with_owner(self):
        """
        Testa se o payload 'get_task' é criado corretamente
        COM um 'owner_id'.
        """
        # 1. Prepara & 2. Age
        payload = get_task(worker_id="w-123", owner_id="SERVER_2")
        
        # 3. Verifica (Assert)
        expected = {
            "WORKER": "ALIVE",
            "WORKER_UUID": "w-123",
            "SERVER_UUID": "SERVER_2" # Agora esperamos esta chave
        }
        self.assertEqual(payload, expected)

    def test_server_command_release(self):
        """Testa a lista de workers no command_release."""
        # 1. Prepara & 2. Age
        payload = server_command_release(master_id="S1", worker_ids=["w1", "w2"])
        
        # 3. Verifica (Assert)
        self.assertEqual(payload['SERVER_UUID'], "S1")
        self.assertEqual(len(payload['WORKERS_UUID']), 2)
        self.assertEqual(payload['WORKERS_UUID'], ["w1", "w2"])
