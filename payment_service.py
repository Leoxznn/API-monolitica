import logging
import os
import socket

from flask import Flask, request, jsonify

logger = logging.getLogger("PaymentService")

INSTANCE_ID = os.environ.get("INSTANCE_ID", socket.gethostname())

app = Flask(__name__)


@app.route("/payment", methods=["POST"])
def payment():
    order = request.get_json()
    logger.info(f"[{INSTANCE_ID}] processando pagamento order_id={order.get('id')}")

    if order["price"] > 0:
        logger.info(f"[{INSTANCE_ID}] pagamento aprovado")
        status = "APPROVED"
    else:
        logger.warning(f"[{INSTANCE_ID}] pagamento recusado")
        status = "REJECTED"

    return jsonify({"status": status, "instance": INSTANCE_ID})


@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({"status": "ok", "instance": INSTANCE_ID}), 200


if __name__ == "__main__":
    app.run(port=5001)
