# dist_server/state_helpers.py
import time
from typing import Dict, List

class StateHelpersMixin:

    def _record_task_completion(self, ts: float = None):
        """Registra a conclusão de uma tarefa (agora é um método)."""
        if ts is None:
            ts = time.time()
        with self.lock:
            self.completed_task_timestamps.append(ts)

    def _tasks_completed_in_window(self, window_seconds: int) -> int:
        """Calcula tarefas na janela (agora é um método)."""
        cutoff = time.time() - window_seconds
        with self.lock:
            # Limpa timestamps antigos para não consumir memória
            while self.completed_task_timestamps and self.completed_task_timestamps[0] < cutoff:
                self.completed_task_timestamps.pop(0)
            return len(self.completed_task_timestamps)

    def _find_idle_workers(self) -> List[Dict]:
         """Encontra workers ociosos (novo método helper)."""
         idle_candidates = []
         now = time.time()
         idle_threshold = self.config['load_balancing']['idle_worker_threshold']
         with self.lock:
             for wid, winfo in self.worker_status.items():
                 if (now - winfo.get('last_seen', 0)) >= idle_threshold:
                     idle_candidates.append({'id': wid})
         return idle_candidates