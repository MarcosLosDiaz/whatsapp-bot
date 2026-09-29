
class MockOut:
    def __init__(self):
        self.val = None
    def set(self, val):
        self.val = val
    def get(self):
        return self.val
import pytest
import azure.functions as func
from src.webhook_receiver import main
import json

def test_webhook_verify_success():
    req = func.HttpRequest(
        method='GET',
        body=b'',
        url='/api/webhook',
        params={
            'hub.mode': 'subscribe',
            'hub.verify_token': 'test_verify_token',
            'hub.challenge': '112233'
        }
    )
    # We will mock the queue output
    msg_stickers = MockOut()
    msg_queries = MockOut()
    
    resp = main(req, msg_stickers, msg_queries)
    assert resp.status_code == 200
    assert resp.get_body() == b'112233'

def test_webhook_verify_fail():
    req = func.HttpRequest(
        method='GET',
        body=b'',
        url='/api/webhook',
        params={
            'hub.mode': 'subscribe',
            'hub.verify_token': 'wrong_token',
            'hub.challenge': '112233'
        }
    )
    msg_stickers = MockOut()
    msg_queries = MockOut()
    
    resp = main(req, msg_stickers, msg_queries)
    assert resp.status_code == 403

def test_webhook_post_sticker():
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "type": "sticker",
                        "sticker": {"id": "sticker123"},
                        "from": "15551234567"
                    }]
                }
            }]
        }]
    }
    req = func.HttpRequest(
        method='POST',
        body=json.dumps(payload).encode('utf-8'),
        url='/api/webhook'
    )
    
    

    msg_stickers = MockOut()
    msg_queries = MockOut()
    
    resp = main(req, msg_stickers, msg_queries)
    assert resp.status_code == 200
    assert msg_stickers.val is not None
    assert "sticker123" in msg_stickers.val
    assert msg_queries.val is None
