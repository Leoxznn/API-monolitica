import threading
from logger_config import setup_logging
 
setup_logging()
 
def start_payment_service():
    import payment_service
    payment_service.app.run(host="0.0.0.0", port=5001, use_reloader=False)
 
def start_gateway():
    import gateway
    gateway.app.run(host="0.0.0.0", port=5000, use_reloader=False)
 
t1 = threading.Thread(target=start_payment_service, daemon=True)
t2 = threading.Thread(target=start_gateway, daemon=True)
 
t1.start()
t2.start()
 
print("Gateway      → http://0.0.0.0:5000")
print("PaymentSvc   → http://0.0.0.0:5001")
print("Pressione Ctrl+C para encerrar.")
 
t1.join()
t2.join()