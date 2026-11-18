"""Métricas para avaliar soluções aproximadas de sistemas lineares."""

from __future__ import annotations
import numpy as np


def calcular_metricas(A, b, x_real, x_calculado) -> dict[str, float]:
    """Calcula erros, resíduo e erro retroativo normwise na norma 2.

    erro_absoluto:       ||x_real - x_calculado||_2
    erro_relativo:       ||x_real - x_calculado||_2 / ||x_real||_2
    residuo_absoluto:    ||A x_calculado - b||_2
    residuo_relativo:    ||A x_calculado - b||_2 / ||b||_2
    erro_retroativo:     ||A x_calculado - b||_2 /
                         (||A||_2 ||x_calculado||_2 + ||b||_2)
    """
    A = np.asarray(A, dtype=float)
    b = np.asarray(b, dtype=float).reshape(-1)
    x_real = np.asarray(x_real, dtype=float).reshape(-1)
    x_calculado = np.asarray(x_calculado, dtype=float).reshape(-1)

    if A.ndim != 2 or A.shape[0] != A.shape[1]:
        raise ValueError("A deve ser uma matriz quadrada.")
    n = A.shape[0]
    if b.size != n or x_real.size != n or x_calculado.size != n:
        raise ValueError("A, b, x_real e x_calculado possuem dimensões incompatíveis.")
    if not all(np.all(np.isfinite(v)) for v in (A, b, x_real, x_calculado)):
        raise ValueError("Os dados das métricas devem conter apenas valores finitos.")

    erro_absoluto = float(np.linalg.norm(x_real - x_calculado, ord=2))
    norma_x_real = float(np.linalg.norm(x_real, ord=2))
    erro_relativo = erro_absoluto / norma_x_real if norma_x_real != 0.0 else float("nan")

    residuo = A @ x_calculado - b
    residuo_absoluto = float(np.linalg.norm(residuo, ord=2))
    norma_b = float(np.linalg.norm(b, ord=2))
    residuo_relativo = residuo_absoluto / norma_b if norma_b != 0.0 else float("nan")

    denominador_retroativo = (
        float(np.linalg.norm(A, ord=2))
        * float(np.linalg.norm(x_calculado, ord=2))
        + norma_b
    )
    erro_retroativo = (
        residuo_absoluto / denominador_retroativo
        if denominador_retroativo != 0.0
        else float("nan")
    )

    return {
        "erro_absoluto": erro_absoluto,
        "erro_relativo": float(erro_relativo),
        "residuo_absoluto": residuo_absoluto,
        "residuo_relativo": float(residuo_relativo),
        "erro_retroativo": float(erro_retroativo),
    }
