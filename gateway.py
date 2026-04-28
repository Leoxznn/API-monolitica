import logging
from flask import Flask, request, jsonify
from monolith import Monolith
 
logger = logging.getLogger("Gateway")
 
app = Flask(__name__)
monolith = Monolith()
 
@app.route("/api/orders", methods=["POST"])
def handle_orders():
    logger.info("Recebendo requisição: /api/orders")
 
    data = request.get_json()
    if not data:
        logger.error("Body inválido ou ausente")
        return jsonify({"error": "Body JSON inválido ou ausente"}), 400
 
    if "item" not in data or "price" not in data:
        logger.error("Campos obrigatórios ausentes")
        return jsonify({"error": "Campos 'item' e 'price' são obrigatórios"}), 400
 
    logger.info("Encaminhando para o monolito")
    result = monolith.create_order(data)
    return jsonify(result), 200
 
@app.errorhandler(404)
def not_found(e):
    logger.error("Rota não encontrada")
    return jsonify({"error": "Rota não encontrada"}), 404
 
@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "Método HTTP não permitido"}), 405
 
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)