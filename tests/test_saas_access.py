import os
import tempfile
import unittest
from urllib.parse import parse_qs, urlparse

from app import create_app


class SaasAccessTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app({
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "DATABASE": os.path.join(self.tmp.name, "test.sqlite"),
            "SEED_DEMO_DATA": False,
            "PLATFORM_ADMIN_PASSWORD": "123456",
        })
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def db(self):
        from app.database import get_db
        return get_db()

    def admin_session(self):
        with self.client.session_transaction() as session:
            session["platform_admin_id"] = 1
            session["platform_admin_role"] = "Super Admin"

    def client_payload(self, **overrides):
        data = {
            "trade_name": "Cliente Teste",
            "legal_name": "Cliente Teste Ltda",
            "document": "12345678901",
            "segment": "Restaurante",
            "email": "comercial@cliente.com",
            "phone": "11999990000",
            "cep": "01001000",
            "address": "Rua A",
            "address_number": "10",
            "neighborhood": "Centro",
            "city": "Sao Paulo",
            "state": "SP",
            "responsible_name": "Ana Cliente",
            "responsible_email": "ana@cliente.com",
            "responsible_phone": "11888880000",
            "responsible_role": "Administrador",
            "plan_id": "1",
            "starts_at": "2026-07-15",
            "expires_at": "2026-08-15",
            "license_status": "trial",
        }
        data.update(overrides)
        return data

    def create_client_company(self, **overrides):
        self.admin_session()
        response = self.client.post("/apex-admin/clients/new", data=self.client_payload(**overrides), follow_redirects=False)
        token = parse_qs(urlparse(response.location).query).get("invite", [""])[0]
        return response, token

    def test_public_register_is_blocked(self):
        self.assertEqual(self.client.get("/auth/register").status_code, 404)
        self.assertEqual(self.client.post("/auth/register", data=self.client_payload()).status_code, 404)
        with self.app.app_context():
            self.assertEqual(self.db().execute("SELECT COUNT(*) value FROM companies").fetchone()["value"], 0)

    def test_client_cannot_access_apex_admin(self):
        response, token = self.create_client_company()
        self.client.post(f"/auth/invite/{token}", data={"password": "abcdef", "password_confirm": "abcdef"})
        self.client.post("/auth/login", data={"email": "ana@cliente.com", "password": "abcdef"})
        self.assertEqual(self.client.get("/apex-admin/").status_code, 302)

    def test_platform_admin_goes_to_admin_area(self):
        self.admin_session()
        self.assertIn("/apex-admin/", self.client.get("/", follow_redirects=False).location)

    def test_admin_creates_company_user_license_and_invite(self):
        response, _ = self.create_client_company()
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            db = self.db()
            self.assertEqual(db.execute("SELECT COUNT(*) value FROM companies").fetchone()["value"], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) value FROM users WHERE active=0").fetchone()["value"], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) value FROM company_licenses").fetchone()["value"], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) value FROM client_invites").fetchone()["value"], 1)

    def test_failed_admin_create_rolls_back(self):
        self.create_client_company()
        self.admin_session()
        response = self.client.post("/apex-admin/clients/new", data=self.client_payload(email="outra@empresa.com"), follow_redirects=False)
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertEqual(self.db().execute("SELECT COUNT(*) value FROM companies").fetchone()["value"], 1)

    def test_invite_expires_and_is_single_use(self):
        _, token = self.create_client_company()
        with self.app.app_context():
            db = self.db()
            db.execute("UPDATE client_invites SET expires_at='2000-01-01T00:00:00'")
            db.commit()
        self.assertEqual(self.client.get(f"/auth/invite/{token}", follow_redirects=False).status_code, 302)

        _, token = self.create_client_company(email="novo@empresa.com", responsible_email="novo@cliente.com")
        self.assertEqual(self.client.post(f"/auth/invite/{token}", data={"password": "abcdef", "password_confirm": "abcdef"}, follow_redirects=False).status_code, 302)
        self.assertEqual(self.client.post(f"/auth/invite/{token}", data={"password": "abcdef", "password_confirm": "abcdef"}, follow_redirects=False).status_code, 302)

    def test_login_and_license_blocks(self):
        _, token = self.create_client_company()
        self.client.post(f"/auth/invite/{token}", data={"password": "abcdef", "password_confirm": "abcdef"})
        self.assertEqual(self.client.post("/auth/login", data={"email": "ana@cliente.com", "password": "abcdef"}, follow_redirects=False).status_code, 302)
        with self.app.app_context():
            db = self.db()
            db.execute("UPDATE company_licenses SET status='blocked'")
            db.commit()
        self.assertIn("/subscription", self.client.get("/pos/", follow_redirects=False).location)

    def test_disabled_user_does_not_login(self):
        _, token = self.create_client_company()
        self.client.post(f"/auth/invite/{token}", data={"password": "abcdef", "password_confirm": "abcdef"})
        with self.app.app_context():
            db = self.db()
            db.execute("UPDATE users SET active=0 WHERE email='ana@cliente.com'")
            db.commit()
        response = self.client.post("/auth/login", data={"email": "ana@cliente.com", "password": "abcdef"}, follow_redirects=False)
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
