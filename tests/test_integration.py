import unittest
import requests
 
BASE_URL = "http://localhost:5000"
 
class TestIntegration(unittest.TestCase):
 
    def test_full_flow(self):
        response = requests.post(
            f"{BASE_URL}/api/orders",
            json={"item": "Headset", "price": 200}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["payment_status"], "APPROVED")
 
    def test_payment_rejected(self):
        response = requests.post(
            f"{BASE_URL}/api/orders",
            json={"item": "Headset", "price": 0}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["payment_status"], "REJECTED")
 
    def test_missing_fields(self):
        response = requests.post(
            f"{BASE_URL}/api/orders",
            json={"item": "Teclado"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())
 
    def test_empty_body(self):
        response = requests.post(
            f"{BASE_URL}/api/orders",
            json={}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())
 
    def test_route_not_found(self):
        response = requests.get(f"{BASE_URL}/rota-inexistente")
        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.json())
 
    def test_method_not_allowed(self):
        response = requests.get(f"{BASE_URL}/api/orders")
        self.assertEqual(response.status_code, 405)
        self.assertIn("error", response.json())
 
if __name__ == "__main__":
    unittest.main()