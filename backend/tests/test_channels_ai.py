"""اختبار مسار الذكاء الاصطناعي وقناة تيليجرام بردود وهمية (بدون إنترنت)."""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import ai, classifier, messaging, telegram_bot
from app.db import session_scope
from app.main import app
from app.models import Invoice, Item, Message, Staff
from app.seed import reset_database

SARA = "966500000014"


class FakeResp:
    def __init__(self, data, status=200):
        self._data, self.status_code = data, status

    def json(self):
        return self._data

    def raise_for_status(self):
        pass


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def fresh():
    reset_database()


def test_ai_path_reads_invoice(client, monkeypatch):
    with session_scope() as db:
        serum = db.scalar(select(Item).where(Item.name == "سيروم شعر")).id
        dye = db.scalar(select(Item).where(Item.name == "صبغة بنية")).id
    sent = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        sent["payload"] = json
        content = {
            "type": "invoice", "confidence": 0.95, "items": [], "device_id": None, "issue": "", "task_run_id": None,
            "invoice": {"supplier": "مؤسسة لمسة للتجميل", "invoice_no": "LM-2318", "total": 763.6, "date": "",
                        "lines": [{"item_id": serum, "name": "سيروم شعر", "qty": 4, "unit_price": 90},
                                  {"item_id": dye, "name": "صبغة بنية", "qty": 8, "unit_price": 38}]},
            "question": None,
        }
        return FakeResp({"choices": [{"message": {"content": "```json\n" + __import__("json").dumps(content, ensure_ascii=False) + "\n```"}}],
                         "usage": {"prompt_tokens": 900, "completion_tokens": 120}})

    monkeypatch.setattr(ai.settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(ai.httpx, "post", fake_post)
    r = client.post("/api/sim/send", data={"phone": SARA, "text": "", "sample": "invoice-lamsa.jpg"})
    assert r.json()["kind"] == "invoice"
    # الصورة انرسلت للنموذج كـ data URL
    parts = sent["payload"]["messages"][1]["content"]
    assert any(p["type"] == "image_url" and p["image_url"]["url"].startswith("data:image/jpeg;base64,") for p in parts)
    with session_scope() as db:
        inv = db.scalar(select(Invoice).order_by(Invoice.id.desc()))
        assert inv.invoice_no == "LM-2318" and float(inv.total) == 763.6 and inv.extraction == "ai"
        assert float(db.get(Item, serum).quantity) == 6  # 2 + 4


def test_ai_invalid_ids_become_question(client, monkeypatch):
    monkeypatch.setattr(ai.settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(
        ai.httpx, "post",
        lambda *a, **k: FakeResp({"choices": [{"message": {"content": json.dumps({"type": "shortage", "items": [{"item_id": 99999}]})}}]}),
    )
    r = client.post("/api/sim/send", data={"phone": SARA, "text": "خلص هذا"})
    assert r.json()["kind"] == "shortage"
    out = [m for m in client.get(f"/api/sim/thread/{SARA}").json() if m["direction"] == "out"][-1]
    assert out["kind"] == "question"


def test_ai_failure_falls_back_to_rules(client, monkeypatch):
    monkeypatch.setattr(ai.settings, "openrouter_api_key", "test-key")

    def boom(*a, **k):
        raise ai.httpx.ConnectError("offline")

    monkeypatch.setattr(ai.httpx, "post", boom)
    r = client.post("/api/sim/send", data={"phone": SARA, "text": "خلصت الصبغة البنية"})
    assert r.json()["kind"] == "shortage"
    assert r.json()["classification"]["source"] == "rules"


def test_telegram_link_and_message(client, monkeypatch):
    calls = []

    def fake_api(method, payload=None, timeout=20):
        calls.append((method, payload))
        if method == "sendMessage":
            return {"ok": True, "result": {"message_id": len(calls)}}
        return {"ok": True, "result": {}}

    monkeypatch.setattr(messaging.settings, "telegram_bot_token", "123:abc")
    monkeypatch.setattr(messaging, "telegram_api", fake_api)
    monkeypatch.setattr(telegram_bot, "telegram_api", fake_api)
    monkeypatch.setattr(telegram_bot, "telegram_send", messaging.telegram_send)

    with session_scope() as db:
        code = db.scalar(select(Staff).where(Staff.phone == SARA)).invite_code
    telegram_bot.process_update({"update_id": 1, "message": {"chat": {"id": 555}, "text": f"/start {code}"}})
    with session_scope() as db:
        assert db.scalar(select(Staff).where(Staff.phone == SARA)).telegram_chat_id == "555"
    assert "تم ربطك" in calls[-1][1]["text"]

    telegram_bot.process_update({"update_id": 2, "message": {"chat": {"id": 555}, "text": "خلصت الصبغة البنية"}})
    reply = [c for c in calls if c[0] == "sendMessage"][-1][1]
    assert reply["chat_id"] == "555" and "صبغة بنية" in reply["text"]
    with session_scope() as db:
        m = db.scalar(select(Message).where(Message.direction == "in").order_by(Message.id.desc()))
        assert m.channel == "telegram"

    # غريب بدون ربط
    telegram_bot.process_update({"update_id": 3, "message": {"chat": {"id": 777}, "text": "هلا"}})
    assert "رابط الدعوة" in calls[-1][1]["text"]
