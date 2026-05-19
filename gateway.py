import logging

from flask import Flask, request, jsonify

from monolith import Monolith
from repository import Repository, init_db

logger = logging.getLogger("Gateway")

app = Flask(__name__)
init_db()
repository = Repository()
monolith = Monolith(repository=repository)


@app.route("/api/orders", methods=["POST"])
def handle_orders():
    logger.info("Recebendo requisição: /api/orders")

    data = request.get_json(silent=True)
    if not data:
        logger.error("Body inválido ou ausente")
        return jsonify({"error": "Body JSON inválido ou ausente"}), 400

    if "item" not in data or "price" not in data:
        logger.error("Campos obrigatórios ausentes")
        return jsonify({"error": "Campos 'item' e 'price' são obrigatórios"}), 400

    idempotency_key = request.headers.get("Idempotency-Key")
    if idempotency_key:
        cached = repository.get_idempotent_response(idempotency_key)
        if cached is not None:
            logger.info(f"retornando resposta idempotente para chave {idempotency_key}")
            return jsonify(cached), 200

    logger.info("Encaminhando para o monolito")
    result = monolith.create_order(data)

    if idempotency_key:
        result = repository.save_idempotent_response(idempotency_key, result)

    return jsonify(result), 200


@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({"status": "ok"}), 200


@app.errorhandler(404)
def not_found(e):
    logger.error("Rota não encontrada")
    return jsonify({"error": "Rota não encontrada"}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "Método HTTP não permitido"}), 405


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
