import pytest
import azure.functions as func
from src.webhook_receiver import main
import json
import os
import hmac
import hashlib

class MockOut:
    def __init__(self):
        self.val = None
    def set(self, val):
        self.val = val
    def get(self):
        return self.val

def test_webhook_verify_success(monkeypatch):
    monkeypatch.setenv("META_VERIFY_TOKEN", "test_verify_token")
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
    msg_stickers = MockOut()
    msg_queries = MockOut()
    
    resp = main(req, msg_stickers, msg_queries)
    assert resp.status_code == 200
    assert resp.get_body() == b'112233'

def test_webhook_post_sticker(monkeypatch):
    monkeypatch.setenv("META_APP_SECRET", "secret123")
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
    body_bytes = json.dumps(payload).encode('utf-8')
    signature = "sha256=" + hmac.new(b"secret123", msg=body_bytes, digestmod=hashlib.sha256).hexdigest()
    
    req = func.HttpRequest(
        method='POST',
        body=body_bytes,
        url='/api/webhook',
        headers={'X-Hub-Signature-256': signature}
    )
    
    msg_stickers = MockOut()
    msg_queries = MockOut()
    
    resp = main(req, msg_stickers, msg_queries)
    assert resp.status_code == 200
    assert msg_stickers.val is not None
