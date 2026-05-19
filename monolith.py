import itertools
import logging
import os
import threading

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger("Monolith")


def _parse_payment_urls():
    multi = os.environ.get("PAYMENT_SERVICE_URLS")
    if multi:
        return [u.strip() for u in multi.split(",") if u.strip()]
    return [os.environ.get("PAYMENT_SERVICE_URL", "http://localhost:5001/payment")]


PAYMENT_SERVICE_URLS = _parse_payment_urls()
PAYMENT_TIMEOUT_SECONDS = float(os.environ.get("PAYMENT_TIMEOUT_SECONDS", "3"))

_rr_lock = threading.Lock()
_rr_cycle = itertools.cycle(PAYMENT_SERVICE_URLS)


def _next_payment_url():
    with _rr_lock:
        return next(_rr_cycle)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.2, max=2),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    reraise=True,
)
def _call_payment(order):
    url = _next_payment_url()
    logger.info(f"load balancer -> {url}")
    response = requests.post(url, json=order, timeout=PAYMENT_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


class Monolith:
    def __init__(self, repository=None):
        self.repository = repository

    def create_order(self, data):
        logger.info("criando pedido")

        order = {
            "item": data.get("item"),
            "price": data.get("price"),
        }

        if self.repository is not None:
            order["id"] = self.repository.save_order(order)
        else:
            order["id"] = 1

        logger.info(f"pedido criado: {order}")
        logger.info("chamando microserviço de pagamento")

        payment_instance = None
        try:
            payment_response = _call_payment(order)
            payment_status = payment_response["status"]
            payment_instance = payment_response.get("instance")
        except requests.RequestException as exc:
            logger.error(f"falha ao chamar pagamento: {exc}")
            payment_status = "UNKNOWN"

        logger.info(f"status do pagamento: {payment_status} (instância: {payment_instance})")

        return {
            "order": order,
            "payment_status": payment_status,
            "payment_instance": payment_instance,
        }
