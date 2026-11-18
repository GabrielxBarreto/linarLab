"""Métodos numéricos para resolver sistemas lineares A x = b.

Implementações:
- Eliminação de Gauss com pivoteamento parcial;
- Decomposição LU com pivoteamento parcial (P A = L U);
- Decomposição QR por reflexões de Householder.

As funções de resolução recebem uma matriz quadrada A e um vetor b,
e retornam a solução x como um vetor NumPy de uma dimensão.
"""

from __future__ import annotations

import numpy as np


Array = np.ndarray


def _validar_matriz(A: Array) -> Array:
    """Converte A para float e verifica se é quadrada e finita."""
    A = np.asarray(A, dtype=float)

    if A.ndim != 2:
        raise ValueError("A matriz A precisa ser bidimensional.")
    if A.shape[0] != A.shape[1]:
        raise ValueError("A matriz A precisa ser quadrada.")
    if A.shape[0] == 0:
        raise ValueError("A matriz A não pode ser vazia.")
    if not np.all(np.isfinite(A)):
        raise ValueError("A matriz A contém valores NaN ou infinitos.")

    return A.copy()


def _validar_vetor(b: Array, n: int) -> Array:
    """Converte b para vetor e verifica compatibilidade com A."""
    b = np.asarray(b, dtype=float)

    # Aceita tanto formato (n,) quanto (n, 1).
    if b.ndim == 2 and b.shape == (n, 1):
        b = b[:, 0]

    if b.ndim != 1 or b.size != n:
        raise ValueError(f"O vetor b precisa ter {n} elementos.")
    if not np.all(np.isfinite(b)):
        raise ValueError("O vetor b contém valores NaN ou infinitos.")

    return b.copy()


def _tolerancia_pivo(A: Array) -> float:
    """Tolerância para detectar pivôs numericamente nulos."""
    n = A.shape[0]
    escala = np.linalg.norm(A, ord=np.inf)
    return np.finfo(float).eps * n * escala


def _substituicao_retroativa(U: Array, y: Array, tol: float) -> Array:
    """Resolve U x = y, onde U é triangular superior."""
    n = U.shape[0]
    x = np.zeros(n, dtype=float)

    for i in range(n - 1, -1, -1):
        pivo = U[i, i]
        if abs(pivo) <= tol:
            raise np.linalg.LinAlgError(
                "Sistema singular ou numericamente singular: pivô nulo na substituição retroativa."
            )

        soma = np.dot(U[i, i + 1 :], x[i + 1 :])
        x[i] = (y[i] - soma) / pivo

    return x


def _substituicao_progressiva(L: Array, b: Array, tol: float) -> Array:
    """Resolve L y = b, onde L é triangular inferior."""
    n = L.shape[0]
    y = np.zeros(n, dtype=float)

    for i in range(n):
        pivo = L[i, i]
        if abs(pivo) <= tol:
            raise np.linalg.LinAlgError(
                "Sistema singular ou fator L inválido: diagonal numericamente nula."
            )

        soma = np.dot(L[i, :i], y[:i])
        y[i] = (b[i] - soma) / pivo

    return y


# ---------------------------------------------------------------------
# 1. ELIMINAÇÃO DE GAUSS COM PIVOTEAMENTO PARCIAL
# ---------------------------------------------------------------------

def eliminacao_gauss(A: Array, b: Array) -> Array:
    """Resolve A x = b por eliminação de Gauss com pivoteamento parcial.

    Em cada coluna, escolhe como pivô o elemento de maior módulo entre
    a linha atual e as linhas abaixo dela. Isso reduz problemas causados
    por pivôs muito pequenos.

    Retorna:
        x: vetor solução.
    """
    A = _validar_matriz(A)
    n = A.shape[0]
    b = _validar_vetor(b, n)
    tol = _tolerancia_pivo(A)

    U = A.copy()
    c = b.copy()

    # Eliminação: transforma A em uma matriz triangular superior U.
    for k in range(n - 1):
        linha_pivo = k + np.argmax(np.abs(U[k:, k]))

        if abs(U[linha_pivo, k]) <= tol:
            raise np.linalg.LinAlgError(
                "A matriz é singular ou numericamente singular."
            )

        # Troca as linhas da matriz e do vetor independente.
        if linha_pivo != k:
            U[[k, linha_pivo], :] = U[[linha_pivo, k], :]
            c[[k, linha_pivo]] = c[[linha_pivo, k]]

        # Zera os elementos abaixo do pivô.
        for i in range(k + 1, n):
            multiplicador = U[i, k] / U[k, k]
            U[i, k:] -= multiplicador * U[k, k:]
            c[i] -= multiplicador * c[k]
            U[i, k] = 0.0

    if abs(U[n - 1, n - 1]) <= tol:
        raise np.linalg.LinAlgError(
            "A matriz é singular ou numericamente singular."
        )

    # Resolve o sistema triangular U x = c.
    return _substituicao_retroativa(U, c, tol)


# ---------------------------------------------------------------------
# 2. DECOMPOSIÇÃO LU COM PIVOTEAMENTO PARCIAL
# ---------------------------------------------------------------------

def decomposicao_lu(A: Array) -> tuple[Array, Array, Array]:
    """Fatora A como P A = L U usando pivoteamento parcial.

    P é uma matriz de permutação, L é triangular inferior com diagonal
    unitária e U é triangular superior.

    Retorna:
        P, L, U
    """
    U = _validar_matriz(A)
    n = U.shape[0]
    tol = _tolerancia_pivo(U)

    L = np.eye(n, dtype=float)
    P = np.eye(n, dtype=float)

    for k in range(n - 1):
        linha_pivo = k + np.argmax(np.abs(U[k:, k]))

        if abs(U[linha_pivo, k]) <= tol:
            raise np.linalg.LinAlgError(
                "A matriz é singular ou numericamente singular; não foi possível fatorar em LU."
            )

        if linha_pivo != k:
            # Permuta as linhas de U e P.
            U[[k, linha_pivo], :] = U[[linha_pivo, k], :]
            P[[k, linha_pivo], :] = P[[linha_pivo, k], :]

            # Também permuta os multiplicadores já calculados em L.
            if k > 0:
                L[[k, linha_pivo], :k] = L[[linha_pivo, k], :k]

        for i in range(k + 1, n):
            multiplicador = U[i, k] / U[k, k]
            L[i, k] = multiplicador
            U[i, k:] -= multiplicador * U[k, k:]
            U[i, k] = 0.0

    if abs(U[n - 1, n - 1]) <= tol:
        raise np.linalg.LinAlgError(
            "A matriz é singular ou numericamente singular; não foi possível fatorar em LU."
        )

    return P, L, U


def resolver_lu(A: Array, b: Array) -> Array:
    """Resolve A x = b usando P A = L U.

    Primeiro resolve L y = P b por substituição progressiva; depois,
    resolve U x = y por substituição retroativa.
    """
    A = _validar_matriz(A)
    n = A.shape[0]
    b = _validar_vetor(b, n)
    tol = _tolerancia_pivo(A)

    P, L, U = decomposicao_lu(A)
    y = _substituicao_progressiva(L, P @ b, tol)
    x = _substituicao_retroativa(U, y, tol)

    return x


# ---------------------------------------------------------------------
# 3. DECOMPOSIÇÃO QR POR REFLEXÕES DE HOUSEHOLDER
# ---------------------------------------------------------------------

def decomposicao_qr(A: Array) -> tuple[Array, Array]:
    """Fatora A como A = Q R usando reflexões de Householder.

    Q é ortogonal (Q.T @ Q = I) e R é triangular superior.
    Esta implementação é para matrizes quadradas, como as geradas
    pelo gerador da pesquisa.

    Retorna:
        Q, R
    """
    R = _validar_matriz(A)
    n = R.shape[0]
    Q = np.eye(n, dtype=float)
    tol = _tolerancia_pivo(R)

    for k in range(n - 1):
        x = R[k:, k].copy()
        norma_x = np.linalg.norm(x, 2)

        if norma_x <= tol:
            continue

        # Escolha do sinal para evitar cancelamento numérico.
        sinal = 1.0 if x[0] >= 0.0 else -1.0
        alpha = -sinal * norma_x

        v = x
        v[0] -= alpha
        norma_v = np.linalg.norm(v, 2)

        if norma_v <= tol:
            continue

        v /= norma_v

        # Aplica H pela esquerda: R <- H R.
        R[k:, :] -= 2.0 * np.outer(v, v @ R[k:, :])

        # Acumula Q pela direita: Q <- Q H.
        Q[:, k:] -= 2.0 * np.outer(Q[:, k:] @ v, v)

    # Limpa apenas resíduos de arredondamento abaixo da diagonal.
    # Não altera os valores significativos da fatoração.
    for i in range(n):
        for j in range(i):
            if abs(R[i, j]) <= 10.0 * tol:
                R[i, j] = 0.0

    if np.any(np.abs(np.diag(R)) <= tol):
        raise np.linalg.LinAlgError(
            "A matriz é singular ou numericamente singular; não foi possível resolver por QR."
        )

    return Q, R


def resolver_qr(A: Array, b: Array) -> Array:
    """Resolve A x = b usando QR de Householder."""
    A = _validar_matriz(A)
    n = A.shape[0]
    b = _validar_vetor(b, n)
    tol = _tolerancia_pivo(A)

    Q, R = decomposicao_qr(A)
    y = Q.T @ b
    x = _substituicao_retroativa(R, y, tol)

    return x


# ---------------------------------------------------------------------
# TESTE RÁPIDO: execute `python3 metodos.py` para verificar as rotinas.
# ---------------------------------------------------------------------

if __name__ == "__main__":
    A_teste = np.array(
        [
            [2.0, 1.0, 1.0],
            [4.0, 5.0, 2.0],
            [2.0, 1.0, 3.0],
        ]
    )
    x_esperado = np.array([13.0 / 6.0, 2.0 / 3.0, 2.0])
    b_teste = A_teste @ x_esperado

    solucoes = {
        "Gauss": eliminacao_gauss(A_teste, b_teste),
        "LU": resolver_lu(A_teste, b_teste),
        "QR": resolver_qr(A_teste, b_teste),
    }

    print("Solução esperada:", x_esperado)
    for nome, x in solucoes.items():
        erro = np.linalg.norm(x - x_esperado, 2)
        residuo = np.linalg.norm(A_teste @ x - b_teste, 2)
        print(f"{nome:6s} -> x = {x}; erro = {erro:.3e}; resíduo = {residuo:.3e}")

    P, L, U = decomposicao_lu(A_teste)
    print("\nVerificação da fatoração LU (P @ A deve ser igual a L @ U):")
    print("||P A - L U||_2 =", np.linalg.norm(P @ A_teste - L @ U, 2))

    Q, R = decomposicao_qr(A_teste)
    print("\nVerificação da fatoração QR (A deve ser igual a Q @ R):")
    print("||A - Q R||_2 =", np.linalg.norm(A_teste - Q @ R, 2))
    print("||Q.T Q - I||_2 =", np.linalg.norm(Q.T @ Q - np.eye(3), 2))
