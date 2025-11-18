import unittest
import time
from unittest.mock import Mock, patch, call # Ferramentas de Mock

from server.dist_server.background_tasks import BackgroundTasksMixin

# 1. Classe Falsa
# Precisamos de um objeto 'self' para o Mixin.
# Criamos uma classe de teste que "usa" o Mixin.
class DummyServerForTest(BackgroundTasksMixin):
    # O Mixin precisa de 'self.lock', 'self.pending_release_attempts', etc.
    # Nós os "simulamos" (Mock) no próprio teste.
    pass


class TestBackoffLogic(unittest.TestCase):

    def setUp(self):
        """
        'setUp' roda ANTES de cada teste. Perfeito para
        criar nosso 'servidor' falso.
        """
        self.server = DummyServerForTest()
        
        # Simula os atributos de estado que o método precisa
        self.server.lock = unittest.mock.MagicMock() # Finge ser um lock
        self.server.pending_release_attempts = {}
        self.server.worker_status = {'w1': {}, 'w2': {}} # Adiciona workers
        self.server.redirect_queue = []
        
        # MOCK (Dublê) para a função de rede.
        # Nós controlamos o que ela faz.
        self.server._send_command_release = Mock(name="_send_command_release")


    @patch('time.sleep') # <-- Mágica: "Duble" a função 'time.sleep'
    def test_backoff_path_failure(self, mock_sleep):
        """
        Testa o "caminho triste":
        _send_command_release falha 5x e o backoff é chamado.
        """
        # 1. Prepara (Arrange)
        # Dizemos ao nosso dublê de rede para SEMPRE retornar False
        self.server._send_command_release.return_value = False 
        
        peer = {'id': 'S2', 'ip': '1.2.3.4', 'port': 9002}
        worker_list = [{'id': 'w1'}, {'id': 'w2'}]
        
        # 2. Age (Act)
        # Chamamos a função que queremos testar
        self.server._handle_release_with_backoff(peer, worker_list)
        
        # 3. Verifica (Assert)
        
        # Verificamos se a rede foi chamada 5 vezes (max_retries)
        self.assertEqual(self.server._send_command_release.call_count, 5)
        
        # Verificamos se o 'time.sleep' foi chamado com os delays certos
        # (5s, 10s, 20s, 40s)
        expected_sleeps = [
            call(5),  # (2**0) * 5
            call(10), # (2**1) * 5
            call(20), # (2**2) * 5
            call(30)  # Atinge o máximo de 30
        ]
        self.assertEqual(mock_sleep.call_args_list, expected_sleeps)
        
        # Verificamos se o estado foi limpo no final
        self.assertEqual(self.server.pending_release_attempts, {})


    @patch('time.sleep') # O Mock é necessário mesmo que não o usemos
    def test_backoff_path_success(self, mock_sleep):
        """
        Testa o "caminho feliz":
        _send_command_release funciona na primeira tentativa.
        """
        # 1. Prepara (Arrange)
        # Dizemos ao nosso dublê de rede para retornar True
        self.server._send_command_release.return_value = True 
        
        peer = {'id': 'S2', 'ip': '1.2.3.4', 'port': 9002}
        worker_list = [{'id': 'w1'}] # Apenas 1 worker
        self.server.pending_release_attempts['S2'] = time.time() # Simula o estado inicial

        # 2. Age (Act)
        self.server._handle_release_with_backoff(peer, worker_list)
        
        # 3. Verifica (Assert)
        
        # Verificamos se a rede foi chamada apenas 1 vez
        self.server._send_command_release.assert_called_once()
        
        # Verificamos se o time.sleep NÃO foi chamado
        mock_sleep.assert_not_called()
        
        # Verificamos se a devolução foi agendada
        self.assertEqual(len(self.server.redirect_queue), 1)
        self.assertEqual(self.server.redirect_queue[0]['worker_id'], 'w1')
        
        # Verificamos se o estado foi limpo
        self.assertEqual(self.server.pending_release_attempts, {})

