import os
import tempfile
import unittest
from pathlib import Path


class PointsManagerApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.environ["DATA_DIR"] = cls.temp_dir.name
        os.environ["DATABASE_PATH"] = str(Path(cls.temp_dir.name) / "test.db")
        from app import app

        cls.app = app
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def setUp(self):
        self.client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        accounts = self.client.get("/api/accounts").get_json()["accounts"]
        for account in accounts:
            if account["role"] == "child" or account["username"] != "admin":
                self.client.delete(f"/api/accounts/{account['id']}")

    def create_child(self, username="child1", display_name="小明", password="child123"):
        response = self.client.post(
            "/api/accounts",
            json={"username": username, "display_name": display_name, "password": password, "role": "child"},
        )
        self.assertEqual(response.status_code, 201)
        return response.get_json()

    def state(self):
        response = self.client.get("/api/state")
        self.assertEqual(response.status_code, 200)
        return response.get_json()

    def test_starts_with_admin_only(self):
        response = self.client.get("/api/accounts")
        self.assertEqual(response.status_code, 200)
        accounts = response.get_json()["accounts"]
        self.assertEqual({account["username"] for account in accounts}, {"admin"})

        data = self.state()
        self.assertIsNone(data["active_child"])
        self.assertEqual(data["total_points"], 0)
        self.assertEqual(data["earn_items"], [])
        self.assertEqual(data["deduct_items"], [])
        self.assertEqual(data["rewards"], [])
        self.assertEqual(len(data["account_overview"]), 1)

    def test_login_roles_and_child_isolation(self):
        self.create_child(username="child", display_name="小朋友")
        earn_id = self.state()["earn_items"][0]["id"]
        response = self.client.post("/api/transactions", json={"kind": "earn", "item_id": earn_id})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["total_points"], 10)

        response = self.client.post(
            "/api/accounts",
            json={"username": "kid2", "display_name": "小明", "password": "kid12345", "role": "child"},
        )
        self.assertEqual(response.status_code, 201)
        kid2_id = response.get_json()["id"]
        response = self.client.post(
            "/api/accounts",
            json={"username": "manager2", "display_name": "家长二", "password": "manager123", "role": "admin"},
        )
        self.assertEqual(response.status_code, 201)
        actions = {log["action"] for log in self.state()["account_logs"]}
        self.assertIn("create_child", actions)
        self.assertIn("create_admin", actions)

        response = self.client.post("/api/auth/select-child", json={"child_id": kid2_id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["total_points"], 0)

        response = self.client.post("/api/transactions", json={"kind": "earn", "points": 6, "name": "测试"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["total_points"], 6)

        self.client.post("/api/auth/logout")
        response = self.client.post("/api/auth/login", json={"username": "child", "password": "child123"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["total_points"], 10)
        self.assertEqual(self.client.post("/api/system/reset").status_code, 403)

    def test_child_transactions_require_admin_approval(self):
        self.create_child(username="child", display_name="小朋友")
        self.client.post("/api/auth/logout")
        response = self.client.post("/api/auth/login", json={"username": "child", "password": "child123"})
        earn_id = response.get_json()["earn_items"][0]["id"]

        response = self.client.post("/api/transactions", json={"kind": "earn", "item_id": earn_id})
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.get_json()["request_submitted"])
        self.assertEqual(response.get_json()["total_points"], 0)
        request_id = response.get_json()["request_id"]
        self.assertEqual(self.client.post(f"/api/requests/{request_id}/approve").status_code, 403)

        self.client.post("/api/auth/logout")
        self.client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        requests = self.client.get("/api/state").get_json()["requests"]
        self.assertEqual(requests[0]["status"], "pending")
        response = self.client.post(f"/api/requests/{request_id}/approve")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["requests"][0]["status"], "approved")

        self.client.post("/api/auth/logout")
        response = self.client.post("/api/auth/login", json={"username": "child", "password": "child123"})
        self.assertEqual(response.get_json()["total_points"], 10)

    def test_v06_child_permissions_avatars_and_account_edit(self):
        self.create_child(username="child", display_name="小朋友")
        state = self.state()
        self.assertEqual(state["version"], "0.6.8")
        self.assertEqual(state["user"]["avatar"], "adult-male")
        self.assertEqual(state["active_child"]["avatar"], "boy")

        self.client.post("/api/auth/logout")
        child_login = self.client.post("/api/auth/login", json={"username": "child", "password": "child123"})
        self.assertEqual(child_login.status_code, 200)
        earn_id = child_login.get_json()["earn_items"][0]["id"]
        self.assertEqual(self.client.post("/api/transactions", json={"kind": "deduct", "item_id": earn_id}).status_code, 403)
        self.assertEqual(self.client.post("/api/transactions", json={"kind": "manual", "points": -1, "name": "负数"}).status_code, 403)

        response = self.client.post("/api/transactions", json={"kind": "earn", "item_id": earn_id})
        self.assertEqual(response.status_code, 202)
        earn_request_id = response.get_json()["request_id"]
        self.client.post("/api/auth/logout")
        self.client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        response = self.client.post(f"/api/requests/{earn_request_id}/approve")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["total_points"], 10)
        response = self.client.post("/api/items/reward", json={"name": "测试兑换", "points": 5})
        self.assertEqual(response.status_code, 201)
        reward_id = response.get_json()["id"]

        self.client.post("/api/auth/logout")
        child_login = self.client.post("/api/auth/login", json={"username": "child", "password": "child123"})
        response = self.client.post("/api/transactions", json={"kind": "exchange", "reward_id": reward_id})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.get_json()["total_points"], 10)
        exchange_request_id = response.get_json()["request_id"]
        self.client.post("/api/auth/logout")
        self.client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        response = self.client.post(f"/api/requests/{exchange_request_id}/approve")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["total_points"], 5)

        self.client.post("/api/auth/logout")
        self.client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        child_id = self.state()["active_child_id"]
        response = self.client.put(f"/api/accounts/{child_id}", json={"display_name": "新名字", "password": "newpass123", "avatar": "girl"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["display_name"], "新名字")
        self.assertEqual(response.get_json()["avatar"], "girl")
        self.assertIn("update_child", {log["action"] for log in self.state()["account_logs"]})

        self.client.post("/api/auth/logout")
        response = self.client.post("/api/auth/login", json={"username": "child", "password": "newpass123"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["user"]["display_name"], "新名字")
        self.assertEqual(response.get_json()["user"]["avatar"], "girl")

    def test_password_updates_and_last_child_can_be_deleted(self):
        child = self.create_child(username="child", display_name="小朋友")
        manager = self.client.post(
            "/api/accounts",
            json={"username": "manager2", "display_name": "家长二", "password": "manager123", "role": "admin"},
        ).get_json()

        response = self.client.put(
            f"/api/accounts/{manager['id']}",
            json={"display_name": "新家长", "password": "manager456", "avatar": "adult-female"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["avatar"], "adult-female")
        self.client.post("/api/auth/logout")
        self.assertEqual(
            self.client.post("/api/auth/login", json={"username": "manager2", "password": "manager123"}).status_code,
            401,
        )
        self.assertEqual(
            self.client.post("/api/auth/login", json={"username": "manager2", "password": "manager456"}).status_code,
            200,
        )
        self.client.post("/api/auth/logout")
        self.client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})

        response = self.client.put(
            f"/api/accounts/{child['id']}",
            json={"display_name": "新名字", "password": "newpass123", "avatar": "girl"},
        )
        self.assertEqual(response.status_code, 200)
        self.client.post("/api/auth/logout")
        self.assertEqual(
            self.client.post("/api/auth/login", json={"username": "child", "password": "child123"}).status_code,
            401,
        )
        self.assertEqual(
            self.client.post("/api/auth/login", json={"username": "child", "password": "newpass123"}).status_code,
            200,
        )
        self.client.post("/api/auth/logout")
        self.client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        self.assertEqual(self.client.delete(f"/api/accounts/{child['id']}").status_code, 200)
        self.assertIsNone(self.state()["active_child"])

    def test_earn_deduct_exchange_and_undo(self):
        self.create_child()
        state = self.state()
        earn_id = state["earn_items"][0]["id"]
        deduct_id = state["deduct_items"][1]["id"]
        self.assertEqual(self.client.post("/api/transactions", json={"kind": "earn", "item_id": earn_id}).status_code, 201)
        response = self.client.post("/api/transactions", json={"kind": "deduct", "item_id": deduct_id})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["total_points"], 5)

        reward_id = self.state()["rewards"][0]["id"]
        self.assertEqual(self.client.post("/api/transactions", json={"kind": "exchange", "reward_id": reward_id}).status_code, 409)

        record_id = self.state()["records"][0]["id"]
        response = self.client.post(f"/api/transactions/{record_id}/undo")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["total_points"], 10)

    def test_custom_items_and_manual_history(self):
        self.create_child()
        response = self.client.post("/api/items/earn", json={"name": "整理书桌", "points": 6, "icon": "television.svg"})
        self.assertEqual(response.status_code, 201)
        item_id = response.get_json()["id"]
        self.assertEqual(response.get_json()["icon"], "television.svg")

        response = self.client.put(f"/api/items/earn/{item_id}", json={"name": "整理书桌并复习", "points": 9, "icon": "game.svg"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["name"], "整理书桌并复习")
        self.assertEqual(response.get_json()["icon"], "game.svg")

        response = self.client.post("/api/transactions", json={"kind": "manual", "name": "历史补录", "points": 12, "date": "2026-01-02"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["records"][0]["date"], "2026-01-02")

        self.assertEqual(self.client.delete(f"/api/items/earn/{item_id}").status_code, 200)

    def test_clear_and_reset(self):
        self.create_child()
        self.client.post("/api/transactions", json={"kind": "earn", "points": 20, "name": "测试"})
        self.assertEqual(self.client.post("/api/system/clear").get_json()["total_points"], 0)
        self.client.post("/api/items/reward", json={"name": "临时奖励", "points": 1})
        data = self.client.post("/api/system/reset").get_json()
        self.assertEqual(data["total_points"], 0)
        self.assertEqual(len(data["rewards"]), 4)

    def test_custom_image_routes_find_uploaded_assets(self):
        for asset in ("child-boy", "child-girl", "adult-male", "adult-female", "account-log", "login-cover", "control-center"):
            response = self.client.get(f"/custom-assets/{asset}")
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.content_type.startswith("image/"))
            response.close()


if __name__ == "__main__":
    unittest.main()
