"""اختبار السيناريوهات الخمسة من البداية للنهاية عبر المحاكي (بدون ذكاء اصطناعي = مسار القواعد).

التشغيل: DATABASE_URL=... pytest -q
"""
import os

os.environ.setdefault("ENABLE_SCHEDULER", "false")
os.environ["OPENROUTER_API_KEY"] = ""
os.environ["TELEGRAM_BOT_TOKEN"] = ""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import DeviceIssue, Invoice, Item, Order, TaskRun
from app.seed import reset_database

OWNER, SARA, MARIAM, RIM, HAYA = "966500000001", "966500000014", "966500000015", "966500000012", "966500000013"
LAMSA_REP, NAQAA_REP = "966500000021", "966500000023"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def fresh_db():
    reset_database()


def say(client, phone, text="", sample=""):
    r = client.post("/api/sim/send", data={"phone": phone, "text": text, "sample": sample})
    assert r.status_code == 200, r.text
    thread = client.get(f"/api/sim/thread/{phone}").json()
    return r.json(), [m for m in thread if m["direction"] == "out"][-1]["body"]


def last_out(client, phone):
    return [m for m in client.get(f"/api/sim/thread/{phone}").json() if m["direction"] == "out"][-1]["body"]


def item(name):
    with session_scope() as db:
        return db.scalar(select(Item).where(Item.name == name))


def test_overview_and_seed(client):
    o = client.get("/api/overview").json()
    assert o["salon"]["name"] == "صالون التجميل"
    names = {i["name"] for i in o["low_items"]}
    assert {"سيروم شعر", "مطهر أدوات"} <= names
    assert len(o["spend_series"]) == 14


def test_scenario1_shortage_to_supplier(client):
    msg, reply = say(client, SARA, "خلصت الصبغة البنية")
    assert msg["kind"] == "shortage"
    assert "صبغة بنية" in reply and "طلبية الليلة" in reply
    assert float(item("صبغة بنية").quantity) == 0

    client.post("/api/demo/run/summary")
    summary = last_out(client, OWNER)
    assert "صبغة بنية" in summary and "سيروم شعر" in summary and "موافقة" in summary

    _, r = say(client, OWNER, "شيل مطهر الادوات")
    assert "شلت مطهر أدوات" in r
    _, r = say(client, OWNER, "الصبغة البنية 8")
    assert "8" in r

    _, r = say(client, OWNER, "موافقة")
    assert "أرسلت الطلبية" in r and "أبو فهد" in r
    rep_msg = last_out(client, LAMSA_REP)
    assert "صبغة بنية × 8" in rep_msg

    # بدون رد: تذكير ثم تنبيه لصاحبة الصالون
    client.post("/api/demo/run/supplier_followup")
    assert "تذكير" in last_out(client, LAMSA_REP)
    client.post("/api/demo/run/supplier_followup")
    assert "ما رد" in last_out(client, OWNER)

    _, r = say(client, LAMSA_REP, "تم يوصل بكرة العصر")
    assert "تم تسجيل ردك" in r
    with session_scope() as db:
        o = db.scalar(select(Order).where(Order.status == "confirmed"))
        assert o and o.supplier.rep_name == "أبو فهد"


def test_scenario2_cleaning(client):
    client.post("/api/demo/run/tasks")
    # زر العرض: أول ضغطة تذكير، الثانية تنبيه لصاحبة الصالون (يشتغل في أي وقت)
    client.post("/api/demo/run/cleaning_check")
    assert "تذكير" in last_out(client, MARIAM)
    client.post("/api/demo/run/cleaning_check")
    assert "ما تقفلت" in last_out(client, OWNER)
    msg, r = say(client, MARIAM, "", sample="proof-sterilize.jpg")
    assert msg["kind"] == "task_proof" and "قفلت مهمة" in r


def test_scenario3_device_issue(client):
    msg, r = say(client, SARA, "الاستشوار الثاني ما يسخن")
    assert msg["kind"] == "issue" and "استشوار 2" in r
    assert item("استشوار 2").status == "broken"
    assert "بلاغ عطل" in last_out(client, OWNER)
    _, r = say(client, SARA, "الاستشوار الثاني ما يسخن")
    assert "مسجل من قبل" in r
    _, r = say(client, OWNER, "انصلح استشوار 2")
    assert "رجع شغال" in r
    assert item("استشوار 2").status == "ok"


def test_ambiguous_device_asks_once(client):
    msg, r = say(client, SARA, "الاستشوار خربان")
    assert "أي واحد" in r
    _, r = say(client, SARA, "الثالث")
    assert "استشوار 3" in r
    assert item("استشوار 3").status == "broken"


def test_scenario4_invoice_matches_open_order(client):
    say(client, SARA, "خلصت الصبغة البنية")
    client.post("/api/demo/run/summary")
    say(client, OWNER, "موافقة")
    before = float(item("سيروم شعر").quantity)
    msg, r = say(client, SARA, "وصلت الطلبية هذي الفاتورة", sample="invoice-lamsa.jpg")
    assert msg["kind"] == "invoice" and "سجلت فاتورة" in r
    assert float(item("سيروم شعر").quantity) > before
    with session_scope() as db:
        inv = db.scalar(select(Invoice).order_by(Invoice.id.desc()))
        assert inv.order_id and inv.total > 0
        assert db.get(Order, inv.order_id).status == "received"


def test_scenario5_morning_report(client):
    client.post("/api/demo/run/morning")
    rep = last_out(client, OWNER)
    assert "تقرير" in rep and "النواقص" in rep and "مصاريف أمس" in rep


def test_shortage_with_remaining_qty_and_unknown(client):
    _, r = say(client, HAYA, "زيت المساج باقي علبتين")
    assert "زيت مساج: باقي 2" in r
    _, r = say(client, RIM, "خلص الشي اللي نستخدمه")
    assert "ما عرفت" in r


def test_unknown_number(client):
    _, r = say(client, "966511112222", "السلام عليكم")
    assert "غير مسجل" in r


def test_photo_without_caption_then_invoice_word(client):
    say(client, SARA, "خلصت الصبغة البنية")
    client.post("/api/demo/run/summary")
    say(client, OWNER, "موافقة")
    _, r = say(client, SARA, "", sample="invoice-lamsa.jpg")
    assert "فاتورة" in r
    msg, r = say(client, SARA, "فاتورة")
    assert msg["kind"] == "invoice" and "سجلت فاتورة" in r


def test_new_topic_after_question_is_not_merged(client):
    _, r = say(client, SARA, "", sample="shelf-dye.jpg")
    assert "وش هذي الصورة" in r
    msg, r = say(client, SARA, "الاستشوار الثاني ما يسخن")
    assert msg["kind"] == "issue" and "استشوار 2" in r


def test_cleaning_check_waits_for_check_time(client):
    """بدون زر العرض: ما فيه تذكير قبل وقت المراجعة."""
    from app import cleaning
    from app.db import session_scope
    from app.models import Salon
    from datetime import time as dtime

    with session_scope() as db:
        db.query(Salon).one().tasks_check_time = dtime(23, 59)
    with session_scope() as db:
        res = cleaning.check_overdue(db)
    assert res == {"reminded": 0, "escalated": 0}


def test_new_task_joins_today_list(client):
    r = client.post("/api/tasks", json={"title": "تعقيم أحواض الغسيل", "days": "0123456", "staff_id": None})
    assert r.status_code == 200
    titles = [x["title"] for x in client.get("/api/tasks").json()["runs"]]
    assert titles[-1] == "تعقيم أحواض الغسيل"
