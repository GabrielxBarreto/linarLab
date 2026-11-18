"""Executa os experimentos de Gauss, LU e QR e exporta resultados em CSV.

Uso padrão:
    python3 experimentos.py

Os parâmetros podem ser alterados na seção CONFIGURAÇÃO abaixo.
"""

from __future__ import annotations

import csv
import math
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Callable

import numpy as np

from matrizes import gerar_sistema
from metodos import eliminacao_gauss, resolver_lu, resolver_qr
from metricas import calcular_metricas


# ---------------------------------------------------------------------
# CONFIGURAÇÃO DOS EXPERIMENTOS
# ---------------------------------------------------------------------
DIMENSOES = [10, 30, 50, 100]
CONDICOES = [1, 10, 100, 1_000, 10_000, 100_000, 1_000_000]
NUM_SEMENTES = 5
REPETICOES_TEMPO = 5
SEED_BASE = 42

PASTA_RESULTADOS = Path(__file__).resolve().parent / "resultados"

METODOS = {
    "Gauss": eliminacao_gauss,
    "LU": resolver_lu,
    "QR_Householder": resolver_qr,
}

CAMPOS_DETALHADOS = [
    "dimensao",
    "condicao_alvo",
    "condicao_medida",
    "semente",
    "metodo",
    "tempo_mediano_s",
    "erro_absoluto",
    "erro_relativo",
    "residuo_absoluto",
    "residuo_relativo",
    "erro_retroativo",
    "status",
    "mensagem_erro",
]

CAMPOS_RESUMO = [
    "dimensao",
    "condicao_alvo",
    "metodo",
    "n_execucoes_sucesso",
    "n_falhas",
    "tempo_mediano_s",
    "erro_absoluto_mediano",
    "erro_relativo_mediano",
    "residuo_relativo_mediano",
    "erro_retroativo_mediano",
]


def _formatar_numero(valor: float) -> str:
    """Representação estável e legível de números nos arquivos CSV."""
    return f"{float(valor):.12g}"


def _mediana_valores(linhas: list[dict], campo: str) -> float:
    valores = [float(linha[campo]) for linha in linhas if linha[campo] not in (None, "")]
    valores = [v for v in valores if math.isfinite(v)]
    return float(statistics.median(valores)) if valores else float("nan")


def _salvar_csv(caminho: Path, campos: list[str], linhas: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", newline="", encoding="utf-8-sig") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos, extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(linhas)


def executar_experimentos(
    dimensoes: list[int] | None = None,
    condicoes: list[float] | None = None,
    num_sementes: int = NUM_SEMENTES,
    repeticoes_tempo: int = REPETICOES_TEMPO,
    seed_base: int = SEED_BASE,
    pasta_resultados: str | Path = PASTA_RESULTADOS,
    progress_callback: Callable[[dict], None] | None = None,
) -> tuple[Path, Path]:
    """Executa a bateria de testes e retorna os caminhos dos dois CSVs.

    O CSV detalhado possui uma linha por dimensão, condicionamento,
    semente e método. O CSV de resumo agrega as sementes pela mediana.
    """
    dimensoes = DIMENSOES if dimensoes is None else dimensoes
    condicoes = CONDICOES if condicoes is None else condicoes

    if not dimensoes or any(not isinstance(n, int) or n < 2 for n in dimensoes):
        raise ValueError("Informe dimensões inteiras maiores ou iguais a 2.")
    if not condicoes or any(not np.isfinite(c) or c < 1 for c in condicoes):
        raise ValueError("Informe números de condição finitos e maiores ou iguais a 1.")
    if num_sementes < 1 or repeticoes_tempo < 1:
        raise ValueError("num_sementes e repeticoes_tempo devem ser pelo menos 1.")

    linhas_detalhadas: list[dict] = []
    total_sistemas = len(dimensoes) * len(condicoes) * num_sementes
    sistema_atual = 0
    total_execucoes = total_sistemas * len(METODOS)
    execucoes_concluidas = 0

    print("Iniciando experimentos...")
    print(f"Dimensões: {dimensoes}")
    print(f"Números de condição: {condicoes}")
    print(f"Sementes por configuração: {num_sementes}")
    print(f"Repetições de tempo por método: {repeticoes_tempo}")
    print()

    for indice_n, n in enumerate(dimensoes):
        for indice_c, condicao in enumerate(condicoes):
            for repeticao in range(num_sementes):
                sistema_atual += 1
                # Para uma mesma dimensão e repetição, reutilizamos a semente
                # em todos os condicionamentos. Assim, U, V e x_real permanecem
                # iguais; o que muda essencialmente é a escala dos valores singulares.
                # Isso controla melhor a comparação do efeito do condicionamento.
                semente = seed_base + indice_n * 100_000 + repeticao

                A, b, x_real = gerar_sistema(n, float(condicao), semente)
                condicao_medida = float(np.linalg.cond(A, 2))

                print(
                    f"Sistema {sistema_atual}/{total_sistemas}: "
                    f"n={n}, cond_alvo={_formatar_numero(condicao)}, semente={semente}"
                )

                for nome_metodo, funcao in METODOS.items():
                    linha = {
                        "dimensao": n,
                        "condicao_alvo": _formatar_numero(condicao),
                        "condicao_medida": condicao_medida,
                        "semente": semente,
                        "metodo": nome_metodo,
                        "tempo_mediano_s": float("nan"),
                        "erro_absoluto": float("nan"),
                        "erro_relativo": float("nan"),
                        "residuo_absoluto": float("nan"),
                        "residuo_relativo": float("nan"),
                        "erro_retroativo": float("nan"),
                        "status": "OK",
                        "mensagem_erro": "",
                    }

                    try:
                        # Aquecimento fora da medição para reduzir o efeito da primeira chamada.
                        funcao(A, b)

                        tempos = []
                        x_calculado = None
                        for _ in range(repeticoes_tempo):
                            inicio = time.perf_counter()
                            x_calculado = funcao(A, b)
                            fim = time.perf_counter()
                            tempos.append(fim - inicio)

                        if x_calculado is None or not np.all(np.isfinite(x_calculado)):
                            raise FloatingPointError("O método retornou uma solução não finita.")

                        metricas = calcular_metricas(A, b, x_real, x_calculado)
                        linha["tempo_mediano_s"] = float(statistics.median(tempos))
                        linha.update(metricas)

                    except Exception as erro:
                        linha["status"] = "FALHA"
                        linha["mensagem_erro"] = f"{type(erro).__name__}: {erro}"

                    linhas_detalhadas.append(linha)
                    execucoes_concluidas += 1
                    if progress_callback is not None:
                        progress_callback({
                            "current": execucoes_concluidas,
                            "total": total_execucoes,
                            "dimensao": n,
                            "condicao": float(condicao),
                            "semente": semente,
                            "metodo": nome_metodo,
                            "status": linha["status"],
                            "message": (
                                f"{nome_metodo}: n={n}, cond={_formatar_numero(condicao)} "
                                f"({execucoes_concluidas}/{total_execucoes})"
                            ),
                        })

    # Agrupa as repetições para produzir uma tabela compacta para gráficos.
    grupos: dict[tuple, list[dict]] = defaultdict(list)
    for linha in linhas_detalhadas:
        chave = (linha["dimensao"], linha["condicao_alvo"], linha["metodo"])
        grupos[chave].append(linha)

    linhas_resumo = []
    for (n, condicao_alvo, metodo), linhas in sorted(grupos.items()):
        sucessos = [linha for linha in linhas if linha["status"] == "OK"]
        falhas = len(linhas) - len(sucessos)

        linhas_resumo.append({
            "dimensao": n,
            "condicao_alvo": condicao_alvo,
            "metodo": metodo,
            "n_execucoes_sucesso": len(sucessos),
            "n_falhas": falhas,
            "tempo_mediano_s": _mediana_valores(sucessos, "tempo_mediano_s"),
            "erro_absoluto_mediano": _mediana_valores(sucessos, "erro_absoluto"),
            "erro_relativo_mediano": _mediana_valores(sucessos, "erro_relativo"),
            "residuo_relativo_mediano": _mediana_valores(sucessos, "residuo_relativo"),
            "erro_retroativo_mediano": _mediana_valores(sucessos, "erro_retroativo"),
        })

    pasta = Path(pasta_resultados)
    arquivo_detalhado = pasta / "resultados_detalhados.csv"
    arquivo_resumo = pasta / "resumo_resultados.csv"

    _salvar_csv(arquivo_detalhado, CAMPOS_DETALHADOS, linhas_detalhadas)
    _salvar_csv(arquivo_resumo, CAMPOS_RESUMO, linhas_resumo)

    total_falhas = sum(linha["status"] != "OK" for linha in linhas_detalhadas)
    print("\nExperimentos concluídos.")
    print(f"Registros detalhados: {arquivo_detalhado}")
    print(f"Resumo: {arquivo_resumo}")
    print(f"Execuções com falha: {total_falhas} de {len(linhas_detalhadas)}")

    return arquivo_detalhado, arquivo_resumo


if __name__ == "__main__":
    executar_experimentos()
