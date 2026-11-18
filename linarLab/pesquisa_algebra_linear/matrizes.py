"""Geração reproduzível de matrizes e sistemas lineares com condicionamento controlado."""

from __future__ import annotations
import numpy as np


def gerar_matriz(n: int, condicao: float, seed: int = 42) -> np.ndarray:
    """Gera A (n x n) com número de condição 2 aproximadamente igual a condicao.

    A construção usa A = U @ S @ V.T, onde U e V são ortogonais e
    S contém valores singulares em progressão geométrica entre 1 e 1/condicao.
    """
    if not isinstance(n, int) or n < 1:
        raise ValueError("n deve ser um inteiro positivo.")
    if not np.isfinite(condicao) or condicao < 1:
        raise ValueError("condicao deve ser um número finito maior ou igual a 1.")

    rng = np.random.default_rng(seed)
    M1 = rng.normal(size=(n, n))
    M2 = rng.normal(size=(n, n))

    U, _ = np.linalg.qr(M1)
    V, _ = np.linalg.qr(M2)

    valores_singulares = np.geomspace(1.0, 1.0 / condicao, n)
    S = np.diag(valores_singulares)

    return U @ S @ V.T


def gerar_sistema(n: int, condicao: float, seed: int = 42):
    """Gera A, b e uma solução verdadeira x_real, com b = A @ x_real."""
    A = gerar_matriz(n, condicao, seed)

    rng = np.random.default_rng(seed + 1)
    x_real = rng.normal(size=n)
    b = A @ x_real

    return A, b, x_real
