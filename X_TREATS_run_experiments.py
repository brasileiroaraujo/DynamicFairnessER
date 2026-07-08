# xxx_runner.py
# Python 3.8+
import subprocess
import sys
import os
from datetime import datetime
from itertools import product
from typing import List, Sequence, Optional


class runner:
    """
    Executor de experimentos para a classe X_TREATS_run_gpu.py

    Exemplo base:
        data/er_magellan/Structured/ 20 Amazon-Google roberta 0.1 599 15 m-fair ditto 1

    Variações:
      - dataset ∈ [DBLP-GoogleScholar, DBLP-ACM, Amazon-Google, Walmart-Amazon]
      - n_registros ∈ [199, 399, 599]
      - thresholds específicos por base:
          Amazon-Google -> 0.1
          Walmart-Amazon -> 0.6
          DBLP-ACM -> 0.2
          DBLP-GoogleScholar -> 0.1
    """

    def __init__(
            self,
            script_path: str,
            workdir: Optional[str] = None,
            python_exec: Optional[str] = None,
            dry_run: bool = False,
            extra_env: Optional[dict] = None,
    ):
        self.script_path = script_path
        self.workdir = workdir or os.getcwd()
        self.python_exec = python_exec or sys.executable
        self.dry_run = dry_run
        self.env = os.environ.copy()
        if extra_env:
            self.env.update(extra_env)

        # parâmetros constantes
        self.data_root = "data/er_magellan/Structured/"
        self.k_value = "20"
        self.model = "roberta"
        self.max_candidates = "15"
        self.fair_mode = "m-fair"
        self.matcher = "ditto"
        self.explanation_mode = "1"

        # thresholds específicos por base
        self.thresholds = {
            "Amazon-Google": "0.1",
            "Walmart-Amazon": "0.6",
            "DBLP-ACM": "0.2",
            "DBLP-GoogleScholar": "0.1",
        }

        # variações
        self.datasets: List[str] = list(self.thresholds.keys())
        self.record_counts: List[int] = [199, 399, 599]

        # diretório de logs
        self.log_dir = os.path.join(self.workdir, "logs_treats")
        os.makedirs(self.log_dir, exist_ok=True)

    def _build_args(self, dataset: str, n_records: int) -> Sequence[str]:
        threshold = self.thresholds.get(dataset, "0.1")
        return [
            self.python_exec,
            self.script_path,
            self.data_root,
            self.k_value,
            dataset,
            self.model,
            threshold,
            str(n_records),
            self.max_candidates,
            self.fair_mode,
            self.matcher,
            self.explanation_mode,
        ]

    def _log_paths(self, dataset: str, n_records: int):
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        base = f"{dataset.replace('-', '')}_n{n_records}_{ts}"
        stdout_path = os.path.join(self.log_dir, f"{base}.out.log")
        stderr_path = os.path.join(self.log_dir, f"{base}.err.log")
        return stdout_path, stderr_path

    def run_all(self):
        combos = list(product(self.datasets, self.record_counts))
        print(f"[XXX] Executando {len(combos)} combinações...")
        print(f"[XXX] Script: {self.script_path}")
        print(f"[XXX] Logs: {self.log_dir}")
        if self.dry_run:
            print("[XXX] Modo DRY-RUN (somente imprime comandos)\n")

        for dataset, n_records in combos:
            args = self._build_args(dataset, n_records)
            stdout_path, stderr_path = self._log_paths(dataset, n_records)

            print(f"\n[XXX] -> dataset={dataset}, n={n_records}, threshold={self.thresholds[dataset]}")
            print("[XXX] Comando:", " ".join(args))

            if self.dry_run:
                continue

            with open(stdout_path, "w", encoding="utf-8") as f_out:
                result = subprocess.run(
                    args,
                    cwd=self.workdir,
                    env=self.env,
                    stdout=f_out,
                    check=True,
                    text=True,
                )
                print(f"[XXX] OK (rc={result.returncode}). Logs em {stdout_path}")

        print("\n[XXX] Execuções finalizadas.")


if __name__ == "__main__":
    # Caminho do script principal a ser executado
    SCRIPT_PATH = "X_TREATS_run_gpu.py"
    WORKDIR = os.getcwd()
    DRY_RUN = False  # True = só imprime comandos

    runner = runner(
        script_path=SCRIPT_PATH,
        workdir=WORKDIR,
        dry_run=DRY_RUN,
        extra_env=None,  # ex.: {"CUDA_VISIBLE_DEVICES": "0"}
    )
    runner.run_all()
