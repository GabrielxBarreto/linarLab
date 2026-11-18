"""Interface web local para executar os experimentos de Álgebra Linear."""

from __future__ import annotations

import csv
import math
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request, send_file

from experimentos import executar_experimentos

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "resultados_web"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

JOBS: dict[str, dict[str, Any]] = {}
ACTIVE_JOB_ID: str | None = None
JOBS_LOCK = threading.Lock()

MAX_DIMENSION = 500
MAX_CONFIGURATIONS = 5000


def _parse_csv_ints(value: Any, field_name: str) -> list[int]:
    if isinstance(value, list):
        raw_values = value
    elif isinstance(value, str):
        raw_values = [part.strip() for part in value.split(",") if part.strip()]
    else:
        raise ValueError(f"O campo {field_name} deve ser uma lista ou texto separado por vírgulas.")

    try:
        values = [int(item) for item in raw_values]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"O campo {field_name} deve conter números inteiros.") from exc

    if not values:
        raise ValueError(f"Informe ao menos um valor em {field_name}.")
    if len(values) != len(set(values)):
        raise ValueError(f"Remova valores repetidos de {field_name}.")
    return values


def _parse_csv_floats(value: Any, field_name: str) -> list[float]:
    if isinstance(value, list):
        raw_values = value
    elif isinstance(value, str):
        raw_values = [part.strip() for part in value.split(",") if part.strip()]
    else:
        raise ValueError(f"O campo {field_name} deve ser uma lista ou texto separado por vírgulas.")

    try:
        values = [float(item) for item in raw_values]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"O campo {field_name} deve conter números válidos.") from exc

    if not values:
        raise ValueError(f"Informe ao menos um valor em {field_name}.")
    if len(values) != len(set(values)):
        raise ValueError(f"Remova valores repetidos de {field_name}.")
    if any(not math.isfinite(v) or v < 1 for v in values):
        raise ValueError("Os números de condição devem ser finitos e maiores ou iguais a 1.")
    return values


def _validar_configuracao(data: dict[str, Any]) -> dict[str, Any]:
    dimensoes = _parse_csv_ints(data.get("dimensoes", "10,30,50,100"), "dimensões")
    condicoes = _parse_csv_floats(
        data.get("condicoes", "1,10,100,1000,10000,100000,1000000"),
        "números de condição",
    )

    if any(n < 2 or n > MAX_DIMENSION for n in dimensoes):
        raise ValueError(f"Cada dimensão deve estar entre 2 e {MAX_DIMENSION}.")

    try:
        num_sementes = int(data.get("num_sementes", 5))
        repeticoes_tempo = int(data.get("repeticoes_tempo", 5))
        seed_base = int(data.get("seed_base", 42))
    except (TypeError, ValueError) as exc:
        raise ValueError("Sementes, repetições e semente inicial devem ser inteiros.") from exc

    if not 1 <= num_sementes <= 50:
        raise ValueError("O número de sementes deve estar entre 1 e 50.")
    if not 1 <= repeticoes_tempo <= 50:
        raise ValueError("As repetições de tempo devem estar entre 1 e 50.")
    if seed_base < 0:
        raise ValueError("A semente inicial não pode ser negativa.")

    total_execucoes = len(dimensoes) * len(condicoes) * num_sementes * 3
    if total_execucoes > MAX_CONFIGURATIONS:
        raise ValueError(
            f"A configuração gera {total_execucoes} execuções. "
            f"Reduza os parâmetros para no máximo {MAX_CONFIGURATIONS}."
        )

    return {
        "dimensoes": dimensoes,
        "condicoes": condicoes,
        "num_sementes": num_sementes,
        "repeticoes_tempo": repeticoes_tempo,
        "seed_base": seed_base,
        "total_execucoes": total_execucoes,
    }


def _atualizar_job(job_id: str, **updates: Any) -> None:
    with JOBS_LOCK:
        if job_id in JOBS:
            JOBS[job_id].update(updates)


def _executar_em_background(job_id: str, config: dict[str, Any]) -> None:
    pasta_execucao = RESULTS_DIR / job_id
    pasta_execucao.mkdir(parents=True, exist_ok=True)

    _atualizar_job(
        job_id,
        status="running",
        started_at=datetime.now(timezone.utc).isoformat(),
        message="Preparando os sistemas e iniciando os métodos.",
    )

    def atualizar_progresso(info: dict[str, Any]) -> None:
        _atualizar_job(
            job_id,
            progress=info.get("current", 0),
            total=info.get("total", config["total_execucoes"]),
            current_case={
                "dimensao": info.get("dimensao"),
                "condicao": info.get("condicao"),
                "semente": info.get("semente"),
                "metodo": info.get("metodo"),
                "status": info.get("status"),
            },
            message=info.get("message", "Executando experimento..."),
        )

    try:
        detalhado, resumo = executar_experimentos(
            dimensoes=config["dimensoes"],
            condicoes=config["condicoes"],
            num_sementes=config["num_sementes"],
            repeticoes_tempo=config["repeticoes_tempo"],
            seed_base=config["seed_base"],
            pasta_resultados=pasta_execucao,
            progress_callback=atualizar_progresso,
        )
        _atualizar_job(
            job_id,
            status="completed",
            progress=config["total_execucoes"],
            total=config["total_execucoes"],
            message="Experimentos concluídos. Os arquivos CSV estão disponíveis.",
            completed_at=datetime.now(timezone.utc).isoformat(),
            files={
                "detalhado": str(detalhado),
                "resumo": str(resumo),
            },
        )
    except Exception as exc:  # a falha fica registrada para a interface informar ao usuário
        _atualizar_job(
            job_id,
            status="failed",
            message=f"Não foi possível concluir os experimentos: {type(exc).__name__}: {exc}",
            error=f"{type(exc).__name__}: {exc}",
            completed_at=datetime.now(timezone.utc).isoformat(),
        )


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "application": "Experimentos de Álgebra Linear"})


@app.post("/api/experimentos")
def iniciar_experimentos():
    global ACTIVE_JOB_ID

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Envie os parâmetros como JSON."}), 400
    try:
        config = _validar_configuracao(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    with JOBS_LOCK:
        if ACTIVE_JOB_ID and JOBS.get(ACTIVE_JOB_ID, {}).get("status") == "running":
            return jsonify({
                "error": "Já existe um experimento em execução. Aguarde sua conclusão."
            }), 409

        job_id = uuid.uuid4().hex
        JOBS[job_id] = {
            "id": job_id,
            "status": "queued",
            "progress": 0,
            "total": config["total_execucoes"],
            "message": "Experimento colocado na fila.",
            "config": config,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "current_case": None,
            "files": None,
            "error": None,
        }
        ACTIVE_JOB_ID = job_id

    worker = threading.Thread(
        target=_executar_em_background,
        args=(job_id, config),
        daemon=True,
        name=f"experimento-{job_id[:8]}",
    )
    worker.start()

    return jsonify({"job_id": job_id, "status": "queued", "config": config}), 202


@app.get("/api/status/<job_id>")
def status_experimento(job_id: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return jsonify({"error": "Experimento não encontrado nesta sessão."}), 404
        # Devolve uma cópia para não expor o dicionário compartilhado entre threads.
        payload = dict(job)
    payload.pop("files", None)
    payload.pop("error", None)
    return jsonify(payload)


@app.get("/api/resultados/<job_id>")
def obter_resultados(job_id: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return jsonify({"error": "Experimento não encontrado nesta sessão."}), 404
        if job.get("status") != "completed" or not job.get("files"):
            return jsonify({"error": "Os resultados ainda não estão disponíveis."}), 409
        resumo_path = Path(job["files"]["resumo"])
        detalhado_path = Path(job["files"]["detalhado"])
        config = job["config"]

    try:
        with resumo_path.open("r", newline="", encoding="utf-8-sig") as arquivo:
            resumo = list(csv.DictReader(arquivo))
        with detalhado_path.open("r", newline="", encoding="utf-8-sig") as arquivo:
            detalhado = list(csv.DictReader(arquivo))
    except OSError as exc:
        return jsonify({"error": f"Não foi possível ler os CSVs: {exc}"}), 500

    def convert_value(row: dict[str, str]) -> dict[str, Any]:
        converted: dict[str, Any] = {}
        for key, value in row.items():
            if value == "":
                converted[key] = None
                continue
            try:
                number = float(value)
                converted[key] = number if math.isfinite(number) else None
            except (TypeError, ValueError):
                converted[key] = value
        return converted

    return jsonify({
        "config": config,
        "summary": [convert_value(row) for row in resumo],
        "detailed": [convert_value(row) for row in detalhado],
        "files": {
            "summary": f"/download/{job_id}/resumo",
            "detailed": f"/download/{job_id}/detalhado",
        },
    })


@app.get("/download/<job_id>/<file_type>")
def baixar_csv(job_id: str, file_type: str):
    key_by_type = {"resumo": "resumo", "detalhado": "detalhado"}
    if file_type not in key_by_type:
        return jsonify({"error": "Tipo de arquivo inválido."}), 404

    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None or job.get("status") != "completed" or not job.get("files"):
            return jsonify({"error": "Arquivo não disponível."}), 404
        caminho = Path(job["files"][key_by_type[file_type]]).resolve()

    # Garante que o download permaneça dentro do diretório de resultados da aplicação.
    try:
        caminho.relative_to(RESULTS_DIR.resolve())
    except ValueError:
        return jsonify({"error": "Caminho de arquivo inválido."}), 400

    if not caminho.is_file():
        return jsonify({"error": "Arquivo não encontrado."}), 404

    nome = "resumo_resultados.csv" if file_type == "resumo" else "resultados_detalhados.csv"
    return send_file(caminho, as_attachment=True, download_name=nome, mimetype="text/csv")


if __name__ == "__main__":
    # A aplicação é local por padrão; não exponha publicamente sem autenticação e proteção adequadas.
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
