import unittest
import threading
import time
import requests

class TestIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Sobe os servidores uma vez antes de todos os testes."""
        def start_payment_service():
            import payment_service
            payment_service.app.run(port=5001, use_reloader=False)

        def start_gateway():
            import gateway
            gateway.app.run(port=5000, use_reloader=False)

        threading.Thread(target=start_payment_service, daemon=True).start()
        threading.Thread(target=start_gateway, daemon=True).start()
        time.sleep(1)  # aguarda os servidores iniciarem

    def test_full_flow(self):
        response = requests.post(
            "http://localhost:5000/api/orders",
            json={"item": "Headset", "price": 200}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["payment_status"], "APPROVED")

    def test_payment_rejected(self):
        response = requests.post(
            "http://localhost:5000/api/orders",
            json={"item": "Headset", "price": 0}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["payment_status"], "REJECTED")

    def test_route_not_found(self):
        response = requests.get("http://localhost:5000/rota-inexistente")
        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.json())

if __name__ == "__main__":
    unittest.main()