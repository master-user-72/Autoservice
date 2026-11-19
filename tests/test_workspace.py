import concurrent.futures
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import access, db, workspace as ws
from app.main import app
from app.suppliers.workspace_demo import DEMO_CAR
from app.workspace_db import migrate, transaction


class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        folder = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch.object(db, "DB_PATH", Path(folder) / "test.db"))
        self.enterContext(patch.object(db, "_conn", None))
        self.enterContext(patch("app.main.setup_logging"))
        self.enterContext(patch("app.main.start_scheduler"))
        self.enterContext(patch("app.main.stop_scheduler"))
        self.moment = datetime(2026, 11, 18, 10, tzinfo=timezone.utc)
        self.enterContext(patch.object(ws, "now", lambda: self.moment))
        self.addCleanup(self.close_db)
        self.client = self.enterContext(TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 1000)))

    def close_db(self):
        if db._conn is not None:
            db._conn.close()
            db._conn = None

    def request(self, method, path, data=None, status=200):
        response = self.client.request(method, "/api/workspace" + path, json=data)
        self.assertEqual(response.status_code, status, response.text)
        return response.json()

    def example(self):
        return self.request("POST", "/example")

    def scenario(self, supplier, name, enabled=True):
        return self.request("PATCH", f"/suppliers/{supplier}", {"scenario": name, "enabled": enabled})

    def edit(self, row, **changes):
        fields = {key: row[key] for key in ("revision", "description", "quantity", "article")}
        fields.update(urgent=bool(row["urgent"]), original_required=bool(row["original_required"]))
        fields.update(changes)
        return self.request("PATCH", f"/items/{row['id']}", fields)

    def search(self, row, query=None, suppliers=None, status=200):
        return self.request("POST", f"/items/{row['id']}/search", {
            "revision": row["revision"], "query": query or row["description"],
            "suppliers": suppliers or ["rossko", "partkom", "emex", "exist"],
        }, status=status)

    def choose(self, row, supplier, status=200):
        offer = next(offer for offer in row["search_result"]["offers"] if offer["supplier"] == supplier)
        return self.request("POST", f"/items/{row['id']}/choice",
                            {"revision": row["revision"], "offer": offer["id"]}, status=status)

    def get_item(self, row):
        return next(i for i in self.request("GET", f"/requests/{row['request_id']}")["items"] if i["id"] == row["id"])

    def place(self, rows, action, day=None, status=200):
        return self.request("POST", "/placement", {
            "items": [{"id": row["id"], "revision": row["revision"]} for row in rows],
            "action": action, "day": day,
        }, status=status)

    def review_urgent(self, row, status=200):
        return self.request("POST", "/review", {"kind": "urgent", "ids": [row["id"]]}, status=status)

    def confirm(self, review, allow=False, status=200):
        return self.request("POST", f"/review/{review['id']}/confirm", {"allow_unknown_delivery": allow}, status=status)

    def test_parse_named_parts_and_preserve_request_text(self):
        raw = "масляный фильтр 2 шт.\nпередний амортизатор срочно"
        result = self.request("POST", "/parse", {"text": raw})
        self.assertEqual([line["description"] for line in result["items"]], ["масляный фильтр", "передний амортизатор"])
        self.assertEqual([(line["quantity"], line["urgent"]) for line in result["items"]], [(2, False), (1, True)])
        draft = self.request("POST", "/requests", {})
        result["items"][0]["description"] = "Исправлено сотрудником"
        applied = self.request("POST", f"/requests/{draft['id']}/apply-text",
                               {"revision": draft["revision"], "text": raw, "items": result["items"]})
        self.assertEqual(applied["raw_text"], raw)
        self.assertEqual(applied["items"][0]["description"], "Исправлено сотрудником")
        self.search(applied["items"][0], status=422)

    def test_partial_search_stock_originals_and_late_request(self):
        row = self.example()["items"][0]
        self.scenario("partkom", "offline")
        self.scenario("rossko", "stock")
        row = self.edit(row, quantity=3, original_required=True)
        result = self.search(row)
        self.assertEqual(result["search_result"]["sources"]["partkom"], "TEMPORARY_ERROR")
        self.assertEqual({x["supplier"] for x in result["search_result"]["offers"]}, {"rossko", "exist"})
        self.choose(result, "rossko", status=422)
        self.search(row, status=409)
        result = self.edit(result, description="передний амортизатор")
        self.search(result, "FLT-OIL-118", status=422)
        result = self.search(result)
        self.assertTrue(all(o["catalogue"] == "SHK-F-90" for o in result["search_result"]["offers"]))

    def test_garage_validation_and_manual_applicability(self):
        draft = self.example()
        self.request("POST", "/vehicles", {**DEMO_CAR, "vin": "invalid"}, status=422)
        self.request("POST", "/vehicles", DEMO_CAR, status=409)
        new_car = self.request("POST", "/vehicles", {**DEMO_CAR, "vin": "JMBXGKH8WLF012746"})["vehicle"]
        draft = self.request("PATCH", f"/requests/{draft['id']}", {"vin": new_car["vin"], "revision": draft["revision"], "accept_reset": True})
        row = draft["items"][0]
        self.assertIsNone(row["selection"])
        row = self.search(row)
        self.choose(row, "rossko", status=422)
        row = self.request("POST", f"/items/{row['id']}/basis", {"revision": row["revision"], "comment": "Учебный OEM сверен вручную"})
        self.assertEqual(self.choose(row,"rossko")["selection"]["supplier"], "rossko")
        self.request("POST", "/vehicles", {**DEMO_CAR, "vin":new_car["vin"], "engine":"2.4 дизель",
                                          "revision":new_car["revision"]})
        self.assertIsNone(self.get_item(row)["search_result"])

    def test_lot_cutoff_grouping_and_partial_result(self):
        draft = self.example()
        first, second = draft["items"]
        third = self.request("POST", f"/requests/{draft['id']}/items", {"description": "передний амортизатор"})
        third = self.choose(self.search(third), "rossko")
        urgent = self.request("POST", f"/requests/{draft['id']}/items", {"description": "масляный фильтр", "urgent": True})
        urgent = self.choose(self.search(urgent), "rossko")
        day = self.request("GET", "/overview")["window"]["open"]
        self.place([first, second, third], "lot", day)
        lot = self.request("GET", f"/lots?day={day}")
        self.assertEqual(sorted(map(len, lot["groups"].values())), [1, 2])
        self.assertNotIn(urgent["id"], [i["id"] for group in lot["groups"].values() for i in group])
        group = next(key for key, rows in lot["groups"].items() if len(rows) == 2)
        payload = {"kind": "lot", "day": day, "group": group}
        self.request("POST", "/review", payload, status=409)
        self.moment += timedelta(hours=1, minutes=1)
        ws.tick()
        ws.tick()
        self.assertEqual(self.request("GET", f"/lots?day={day}")["status"], "closed")
        self.place([self.get_item(urgent)], "lot", day, status=409)
        self.scenario("partkom", "failure")
        review = self.request("POST", "/review", payload)
        result = self.confirm(review)
        self.assertEqual({o["status"] for o in result["orders"]}, {"accepted", "error"})
        self.assertEqual(self.request("GET", f"/lots?day={day}")["status"], "partial")
        self.assertEqual([o["id"] for o in self.confirm(review)["orders"]], [o["id"] for o in result["orders"]])
        self.assertEqual(self.request("GET", "/orders")["total"], 2)

    def test_concurrent_confirmation_and_lost_reply_reconcile_after_reopen(self):
        self.scenario("rossko", "lost")
        row = self.example()["items"][0]
        self.place([row], "urgent")
        review = self.review_urgent(row)
        other = self.review_urgent(row)
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda _: self.confirm(review), range(6)))
        ids = {reply["orders"][0]["id"] for reply in results}
        self.assertEqual(len(ids), 1)
        identifier = ids.pop()
        self.assertEqual(self.request("GET", f"/orders/{identifier}")["status"], "unknown")
        self.confirm(other, status=409)
        with transaction() as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM workspace_demo_receipts").fetchone()[0], 1)
        self.close_db()
        migrate()
        self.assertEqual(self.request("POST", f"/orders/{identifier}/reconcile")["status"], "accepted")
        self.assertEqual(self.request("GET", "/orders?q=FLT-OIL-118")["total"], 1)
        self.assertEqual(self.confirm(review)["orders"][0]["id"], identifier)

    def test_changed_terms_require_new_review_and_order_is_snapshot(self):
        draft = self.example()
        row = draft["items"][0]
        self.place([row], "urgent")
        review = self.review_urgent(row)
        self.scenario("rossko", "price")
        result = self.confirm(review)
        self.assertFalse(result["orders"])
        self.assertNotEqual(result["issues"][0]["changes"]["price"]["before"], result["issues"][0]["changes"]["price"]["after"])
        self.assertEqual(self.confirm(review), result)
        self.assertEqual(self.confirm(self.review_urgent(row))["orders"][0]["status"], "accepted")
        car = draft["vehicle"]
        self.request("POST", "/vehicles", {**DEMO_CAR, "engine":"Исправленный двигатель", "revision":car["revision"]})
        lines = self.request("GET", "/orders")["orders"][0]["items"]
        self.assertEqual(lines[0]["vehicle"]["engine"], DEMO_CAR["engine"])

    def test_manual_cabinet_and_unique_reference(self):
        draft = self.example()
        for row in draft["items"]:
            row = self.choose(row, "exist")
            self.place([row], "urgent")
            order = self.confirm(self.review_urgent(row))["orders"][0]
            self.assertEqual(order["status"], "manual")
            expected = 200 if row["id"] == draft["items"][0]["id"] else 409
            self.request("POST", f"/orders/{order['id']}/manual", {"number": "DEMO-ABC"}, status=expected)

    def test_unknown_delivery_needs_express_consent(self):
        self.scenario("rossko", "unknown_delivery")
        row = self.example()["items"][0]
        self.place([row], "urgent")
        review = self.review_urgent(row)
        self.confirm(review, status=422)
        self.assertEqual(self.confirm(review, allow=True)["orders"][0]["status"], "accepted")

    def test_known_failure_can_retry_with_same_operation(self):
        self.scenario("rossko", "failure")
        row = self.example()["items"][0]
        self.place([row], "urgent")
        failed = self.confirm(self.review_urgent(row))["orders"][0]
        self.assertEqual(failed["status"], "error")
        path = f"/orders/{failed['id']}/retry-review"
        self.scenario("rossko", "price")
        review = self.request("POST", path)
        self.assertTrue(self.confirm(review)["requires_new_request"])
        self.scenario("rossko", "normal")
        review = self.request("POST", path)
        another = self.request("POST", path)
        success = self.confirm(review)["orders"][0]
        self.assertEqual((success["id"], success["status"]), (failed["id"], "accepted"))
        self.confirm(another, status=409)
        self.assertEqual(self.request("GET", "/orders")["total"], 1)

    def test_expired_and_disabled_results_are_not_selectable(self):
        row = self.example()["items"][0]
        self.moment += timedelta(minutes=16)
        self.choose(row, "rossko", status=409)
        self.scenario("rossko", "normal", enabled=False)
        self.place([row], "urgent", status=409)
        updated = self.search(row)
        self.assertEqual(updated["search_result"]["sources"]["rossko"], "NO_ACCESS")
        self.assertIsNone(updated["selection"])
        self.assertTrue(updated["search_result"]["offers"])

    def test_interrupted_claim_is_recoverable_without_resend(self):
        row = self.example()["items"][0]
        self.place([row], "urgent")
        review = self.review_urgent(row)
        with patch.object(ws, "dispatch", return_value=None):
            claim = self.confirm(review)["orders"][0]
        self.assertEqual(claim["status"], "sending")
        self.close_db()
        self.moment += timedelta(seconds=31)
        ws.tick()
        order = self.request("POST", f"/orders/{claim['id']}/reconcile")
        self.assertEqual(order["status"], "unknown")
        self.assertEqual(self.confirm(review)["orders"][0]["status"], "unknown")
        with transaction() as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM workspace_demo_receipts").fetchone()[0], 0)

    def test_shared_role_and_cross_origin(self):
        self.assertEqual(self.client.post("/api/workspace/example", headers={"Origin": "https://elsewhere.invalid"}).status_code, 403)
        users = {"readonly": {"password": "test-password", "role": "employee"}}
        with patch.object(access, "USERS", users), patch.object(access, "SECRET", b"s" * 32):
            with TestClient(app, base_url="https://work.example", client=("127.0.0.1", 1001)) as browser:
                self.assertEqual(browser.get("/api/workspace/overview").status_code, 401)
                login = browser.post("/api/workspace/login", json={"name": "readonly", "password": "test-password"})
                self.assertEqual(login.status_code, 200)
                self.assertIn("HttpOnly", login.headers["set-cookie"])
                self.assertIn("Secure", login.headers["set-cookie"])
                self.assertEqual(browser.get("/api/workspace/overview").status_code, 200)
                self.assertEqual(browser.patch("/api/workspace/settings", json={"cutoff":"19:00"}).status_code, 403)
                self.assertEqual(browser.post("/api/workspace/review", json={"kind":"urgent","ids":[1]}).status_code, 403)
                self.assertEqual(browser.get("/api/state").status_code, 403)
                self.assertEqual(browser.patch("/api/workspace/settings", json={"sort":"date"}).status_code, 200)


if __name__ == "__main__":
    unittest.main()
