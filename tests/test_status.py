from datetime import datetime, timezone
import json
import unittest
from unittest.mock import AsyncMock, Mock, call, patch

import requests

from src.commands.ctxstatus import (
    STATUSPAGE_SERVICES,
    estimated_uptime,
    parse_auth0_status,
    statusfunctx,
    supported_services,
    worst_auth0_uptime,
)


def auth0_html(regions):
    payload = {"props": {"pageProps": {"activeIncidents": regions}}}
    return f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(payload)}</script>'


def auth0_region(name, impact="none", incident="All Systems Operational"):
    return {
        "region": name,
        "environment": "Production",
        "response": {"incidents": [{"status": "operational", "impact": impact, "name": incident}]},
    }


class StatusTests(unittest.IsolatedAsyncioTestCase):
    def test_claude_is_supported(self):
        self.assertEqual(STATUSPAGE_SERVICES["claude"], ("Claude", "https://status.claude.com"))

    def test_donweb_is_supported(self):
        self.assertEqual(STATUSPAGE_SERVICES["donweb"], ("DonWeb", "https://status.donweb.com"))

    def test_uptime_merges_overlapping_incidents(self):
        now = datetime(2026, 8, 21, tzinfo=timezone.utc)
        incidents = [
            {"created_at": "2026-08-20T00:00:00Z", "resolved_at": "2026-08-20T02:00:00Z"},
            {"created_at": "2026-08-20T01:00:00Z", "resolved_at": "2026-08-20T03:00:00Z"},
        ]

        self.assertAlmostEqual(estimated_uptime(incidents, now), 99.583333, places=5)

    def test_ongoing_incident_counts_until_now(self):
        now = datetime(2026, 8, 21, tzinfo=timezone.utc)
        incidents = [{"created_at": "2026-08-20T12:00:00Z", "resolved_at": None}]

        self.assertAlmostEqual(estimated_uptime(incidents, now), 98.333333, places=5)

    async def test_unknown_service_lists_supported_services(self):
        ctx = unittest.mock.Mock()
        ctx.send = AsyncMock()

        await statusfunctx(ctx, "gitlab")

        ctx.send.assert_awaited_once_with(f"Servicio no soportado. Servicios disponibles: {supported_services()}")
        self.assertIn("auth0", supported_services())

    async def test_statuspage_service_uses_its_configured_endpoints(self):
        status_response = Mock()
        status_response.raise_for_status.return_value = None
        status_response.json.return_value = {"status": {"indicator": "none", "description": "All Systems Operational"}}
        incidents_response = Mock()
        incidents_response.raise_for_status.return_value = None
        incidents_response.json.return_value = {"incidents": []}
        ctx = unittest.mock.Mock()
        ctx.send = AsyncMock()

        with patch(
            "src.commands.ctxstatus.requests.get",
            side_effect=[status_response, incidents_response],
        ) as get:
            await statusfunctx(ctx, "Cloudflare")

        status_url = STATUSPAGE_SERVICES["cloudflare"][1]
        self.assertEqual(
            get.call_args_list,
            [
                call(f"{status_url}/api/v2/status.json", timeout=10),
                call(f"{status_url}/api/v2/incidents.json", timeout=10),
            ],
        )
        message = ctx.send.await_args.args[0]
        self.assertIn("Cloudflare: UP", message)
        self.assertIn("100.000%", message)

    def test_parse_auth0_status_picks_worst_region(self):
        html = auth0_html(
            [
                auth0_region("US-1"),
                auth0_region("EU-1", impact="major", incident="Elevated Error Rates"),
            ]
        )

        self.assertEqual(parse_auth0_status(html), ("EU-1", "major", "Elevated Error Rates"))

    def test_parse_auth0_status_all_operational(self):
        html = auth0_html([auth0_region("US-1"), auth0_region("AU")])

        self.assertEqual(parse_auth0_status(html), ("US-1", "none", "All Systems Operational"))

    def test_worst_auth0_uptime_handles_plus_suffix(self):
        data = {
            "US-1": {"uptime90days": "99.99%"},
            "AU": {"uptime90days": "99.999%+"},
            "EU-1": {"uptime90days": "99.94%"},
        }

        self.assertAlmostEqual(worst_auth0_uptime(data), 99.94, places=5)

    def test_worst_auth0_uptime_handles_numeric_values(self):
        data = {"US-1": {"uptime90days": 99.98}, "AU": {"uptime90days": "99.999%+"}}

        self.assertAlmostEqual(worst_auth0_uptime(data), 99.98, places=5)

    def test_parse_auth0_status_handles_region_without_incidents(self):
        html = auth0_html(
            [
                auth0_region("US-1", impact="major", incident="Outage"),
                {"region": "US-3", "environment": "Production", "response": {"incidents": []}},
            ]
        )

        self.assertEqual(parse_auth0_status(html), ("US-1", "major", "Outage"))

    def test_parse_auth0_status_ignores_non_production_regions(self):
        staging = auth0_region("EU-1", impact="critical", incident="Staging down")
        staging["environment"] = "Staging"
        html = auth0_html([auth0_region("US-1"), staging])

        self.assertEqual(parse_auth0_status(html), ("US-1", "none", "All Systems Operational"))

    def test_parse_auth0_status_requires_next_data(self):
        with self.assertRaises(ValueError):
            parse_auth0_status("<html>sin __NEXT_DATA__</html>")

    async def test_auth0_parse_failure_is_reported(self):
        home_response = Mock()
        home_response.raise_for_status.return_value = None
        home_response.text = "<html>sin __NEXT_DATA__</html>"
        uptime_response = Mock()
        uptime_response.raise_for_status.return_value = None
        uptime_response.json.return_value = {"US-1": {"uptime90days": "99.99%"}}
        ctx = unittest.mock.Mock()
        ctx.send = AsyncMock()

        with patch("src.commands.ctxstatus.requests.get", side_effect=[home_response, uptime_response]):
            await statusfunctx(ctx, "auth0")

        ctx.send.assert_awaited_once_with("No se pudo consultar el estado de Auth0. Intenta nuevamente mas tarde.")

    async def test_auth0_reports_worst_region_status_and_uptime(self):
        home_response = Mock()
        home_response.raise_for_status.return_value = None
        home_response.text = auth0_html([auth0_region("US-1"), auth0_region("EU-1", impact="minor", incident="Degraded")])
        uptime_response = Mock()
        uptime_response.raise_for_status.return_value = None
        uptime_response.json.return_value = {"US-1": {"uptime90days": "99.99%"}, "EU-1": {"uptime90days": "99.94%"}}
        ctx = unittest.mock.Mock()
        ctx.send = AsyncMock()

        with patch("src.commands.ctxstatus.requests.get", side_effect=[home_response, uptime_response]) as get:
            await statusfunctx(ctx, "auth0")

        self.assertEqual(
            get.call_args_list,
            [
                call("https://status.auth0.com", timeout=10),
                call("https://status.auth0.com/api/uptime", timeout=10),
            ],
        )
        message = ctx.send.await_args.args[0]
        self.assertIn("Auth0: DEGRADADO (Degraded, region EU-1)", message)
        self.assertIn("99.940%", message)

    async def test_auth0_reports_status_when_uptime_request_fails(self):
        home_response = Mock()
        home_response.raise_for_status.return_value = None
        home_response.text = auth0_html([auth0_region("US-1", impact="minor", incident="Degraded")])
        ctx = unittest.mock.Mock()
        ctx.send = AsyncMock()

        with patch(
            "src.commands.ctxstatus.requests.get",
            side_effect=[home_response, requests.RequestException("boom")],
        ):
            await statusfunctx(ctx, "auth0")

        message = ctx.send.await_args.args[0]
        self.assertIn("Auth0: DEGRADADO (Degraded, region US-1)", message)
        self.assertIn("no disponible", message)

    async def test_auth0_reports_status_when_uptime_payload_is_invalid(self):
        home_response = Mock()
        home_response.raise_for_status.return_value = None
        home_response.text = auth0_html([auth0_region("US-1")])
        uptime_response = Mock()
        uptime_response.raise_for_status.return_value = None
        uptime_response.json.return_value = {"US-1": None}
        ctx = unittest.mock.Mock()
        ctx.send = AsyncMock()

        with patch("src.commands.ctxstatus.requests.get", side_effect=[home_response, uptime_response]):
            await statusfunctx(ctx, "auth0")

        message = ctx.send.await_args.args[0]
        self.assertIn("Auth0: UP", message)
        self.assertIn("no disponible", message)

    async def test_auth0_failure_is_reported(self):
        ctx = unittest.mock.Mock()
        ctx.send = AsyncMock()

        with patch("src.commands.ctxstatus.requests.get", side_effect=requests.RequestException("boom")):
            await statusfunctx(ctx, "auth0")

        ctx.send.assert_awaited_once_with("No se pudo consultar el estado de Auth0. Intenta nuevamente mas tarde.")


if __name__ == "__main__":
    unittest.main()
