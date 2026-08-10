"""Etapa 4 — bipagem → checa ZPL engatilhada → dry-run print."""
import sys
import unittest
from pathlib import Path

from starlette.testclient import TestClient

api_dir = Path(__file__).resolve().parent.parent.parent
if str(api_dir) not in sys.path:
    sys.path.insert(0, str(api_dir))

from src.main import app
from src.infrastructure.database import RealOrderDB, async_session, init_db
from src.infrastructure import zpl_printer


class TestExpeditionFlow(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    async def asyncSetUp(self):
        await init_db()
        async with async_session() as session:
            session.add(
                RealOrderDB(
                    id="TEST-SCAN-001",
                    external_id="ML-TEST-001",
                    customer_name="Cliente Teste Bipagem",
                    status_name="Em Separação - Geral",
                    shipping_id="SHIP-001",
                    zpl_armed=False,
                    zpl_content="",
                )
            )
            await session.commit()

    async def asyncTearDown(self):
        async with async_session() as session:
            row = await session.get(RealOrderDB, "TEST-SCAN-001")
            if row:
                await session.delete(row)
                await session.commit()

    def test_printer_status_dry_run(self):
        res = self.client.get("/api/v1/expedition/printer")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("ok"))
        self.assertIn(data.get("mode"), ("dry_run", "raw", "cups"))

    def test_scan_without_armed_label_returns_409(self):
        res = self.client.post(
            "/api/v1/expedition/scan",
            json={"barcode": "TEST-SCAN-001", "dry_run": True},
        )
        self.assertEqual(res.status_code, 409)
        self.assertIn("engatilhada", res.json()["detail"].lower())

    def test_arm_and_scan_dry_run(self):
        arm = self.client.post(
            "/api/v1/expedition/arm/TEST-SCAN-001",
            json={"mark_ready_status": True},
        )
        self.assertEqual(arm.status_code, 200, arm.text)
        self.assertTrue(arm.json().get("ok"))

        scan = self.client.post(
            "/api/v1/expedition/scan",
            json={"barcode": "SHIP-001", "dry_run": True},
        )
        self.assertEqual(scan.status_code, 200, scan.text)
        body = scan.json()
        self.assertTrue(body.get("ok"))
        self.assertIn("Dry-run", body.get("message", ""))
        self.assertEqual(body["order"]["id"], "TEST-SCAN-001")
        self.assertTrue(body["printer"].get("dry_run_path"))

    def test_zpl_printer_dry_run_writes_file(self):
        result = zpl_printer.send_zpl("^XA^FDTEST^XZ", order_id="unit-test", mode_override="dry_run")
        self.assertTrue(result.ok)
        self.assertIsNotNone(result.dry_run_path)
        self.assertTrue(Path(result.dry_run_path).is_file())


if __name__ == "__main__":
    unittest.main()
