import json
from quantuminspire.qiskit import QI

def set_auth(path='credentials/auth.json'):
    with open(path) as f:
        auth = json.load(f)
    QI.set_authentication_details(*auth.values())
