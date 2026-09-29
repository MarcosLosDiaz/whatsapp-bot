import pytest
import azure.functions as func
from src.webhook_receiver import main
import json
import os
import hmac
import hashlib
from unittest.mock import patch

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
    
    resp = main(req)
    assert resp.status_code == 200
    assert resp.get_body() == b'112233'

@patch('src.webhook_receiver.send_to_queue')
def test_webhook_post_sticker(mock_send, monkeypatch):
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
    
    resp = main(req)
    assert resp.status_code == 200
    mock_send.assert_called_once()
