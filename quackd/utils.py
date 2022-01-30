from datetime import datetime, timezone
import json

from qiskit import IBMQ
from quantuminspire.qiskit import QI


def set_qi_auth(path):
    with open(path) as f:
        auth = json.load(f)
    QI.set_authentication_details(*auth.values())


def get_ibm_provider(path):
    IBMQ.load_account()
    with open(path) as f:
        return IBMQ.get_provider(**json.load(f))


def load_slack_tokens(path):
    with open(path) as f:
        auth = json.load(f)
    return auth['SLACK_APP_TOKEN'], auth['SLACK_BOT_TOKEN']


def timestamp():
    return datetime.now(timezone.utc)
