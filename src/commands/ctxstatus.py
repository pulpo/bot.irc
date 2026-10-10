from datetime import datetime, timedelta, timezone

import asyncio
import json
import re
import requests

WINDOW_DAYS = 30

AUTH0_STATUS_URL = "https://status.auth0.com"
AUTH0_IMPACT_ORDER = {"none": 0, "minor": 1, "major": 2, "critical": 3}
AUTH0_ERRORS = (requests.RequestException, KeyError, TypeError, ValueError, AttributeError, IndexError)

STATUSPAGE_SERVICES = {
    "atlassian": ("Atlassian", "https://status.atlassian.com"),
    "claude": ("Claude", "https://status.claude.com"),
    "cloudflare": ("Cloudflare", "https://www.cloudflarestatus.com"),
    "datadog": ("Datadog US1", "https://status.datadoghq.com"),
    "digitalocean": ("DigitalOcean", "https://status.digitalocean.com"),
    "discord": ("Discord", "https://discordstatus.com"),
    "donweb": ("DonWeb", "https://status.donweb.com"),
    "github": ("GitHub", "https://www.githubstatus.com"),
    "npm": ("npm", "https://status.npmjs.org"),
    "openai": ("OpenAI", "https://status.openai.com"),
}


def supported_services() -> str:
    return ", ".join(sorted([*STATUSPAGE_SERVICES, "auth0"]))


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def estimated_uptime(incidents: list[dict], now: datetime) -> float:
    """Estimate uptime as time without a published incident in the last 30 days."""
    now = now.astimezone(timezone.utc)
    window_start = now - timedelta(days=WINDOW_DAYS)
    intervals = []

    for incident in incidents:
        created_at = incident.get("created_at")
        if not created_at:
            continue
        start = max(parse_timestamp(created_at), window_start)
        resolved_at = incident.get("resolved_at")
        end = min(parse_timestamp(resolved_at), now) if resolved_at else now
        if start < end and end > window_start:
            intervals.append((start, end))

    intervals.sort()
    merged = []
    for start, end in intervals:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)

    downtime = sum((end - start).total_seconds() for start, end in merged)
    window_seconds = timedelta(days=WINDOW_DAYS).total_seconds()
    return max(0.0, 100.0 * (window_seconds - downtime) / window_seconds)


def auth0_region_impact(region: dict) -> int:
    """Return the worst impact level among a region's active incidents."""
    incidents = region.get("response", {}).get("incidents") or []
    return max((AUTH0_IMPACT_ORDER.get(incident.get("impact", "none"), 0) for incident in incidents), default=0)


def parse_auth0_status(html: str) -> tuple[str, str, str]:
    """Return (region, impact, name) for the worst production region of Auth0."""
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    if not match:
        raise ValueError("No se encontro __NEXT_DATA__ en la pagina de Auth0")

    data = json.loads(match.group(1))
    active = data["props"]["pageProps"]["activeIncidents"]
    regions = [region for region in active if region.get("environment") == "Production"]
    if not regions:
        raise ValueError("Sin regiones de produccion de Auth0")

    worst = max(regions, key=auth0_region_impact)
    incidents = worst.get("response", {}).get("incidents") or [{}]
    incident = max(incidents, key=lambda item: AUTH0_IMPACT_ORDER.get(item.get("impact", "none"), 0))
    return worst["region"], incident.get("impact", "none"), incident.get("name", "estado desconocido")


def worst_auth0_uptime(data: dict) -> float:
    """Return the lowest 90-day uptime across Auth0 regions as a percentage."""
    values = []
    for region in data.values():
        raw = region.get("uptime90days")
        if not raw:
            continue
        values.append(float(str(raw).rstrip("%+")))
    if not values:
        raise ValueError("Sin datos de uptime de Auth0")
    return min(values)


async def auth0_statusfunctx(ctx):
    try:
        home_response = await asyncio.to_thread(requests.get, AUTH0_STATUS_URL, timeout=10)
        home_response.raise_for_status()
        region, impact, name = parse_auth0_status(home_response.text)
    except AUTH0_ERRORS:
        await ctx.send("No se pudo consultar el estado de Auth0. Intenta nuevamente mas tarde.")
        return

    try:
        uptime_response = await asyncio.to_thread(requests.get, f"{AUTH0_STATUS_URL}/api/uptime", timeout=10)
        uptime_response.raise_for_status()
        uptime = worst_auth0_uptime(uptime_response.json())
    except AUTH0_ERRORS:
        uptime = None

    state = "UP" if impact == "none" else f"DEGRADADO ({name}, region {region})"
    uptime_text = f"{uptime:.3f}%" if uptime is not None else "no disponible"
    await ctx.send(
        f"Auth0: {state} - Uptime reportado (90 dias, peor region): {uptime_text} "
        f"- Fuente: {AUTH0_STATUS_URL}"
    )


async def statusfunctx(ctx, service: str):
    service = service.strip().lower()
    if service == "auth0":
        await auth0_statusfunctx(ctx)
        return
    definition = STATUSPAGE_SERVICES.get(service)
    if not definition:
        await ctx.send(f"Servicio no soportado. Servicios disponibles: {supported_services()}")
        return

    display_name, status_url = definition
    try:
        status_response = await asyncio.to_thread(requests.get, f"{status_url}/api/v2/status.json", timeout=10)
        status_response.raise_for_status()
        incidents_response = await asyncio.to_thread(requests.get, f"{status_url}/api/v2/incidents.json", timeout=10)
        incidents_response.raise_for_status()

        status = status_response.json()["status"]
        incidents = incidents_response.json().get("incidents", [])
        uptime = estimated_uptime(incidents, datetime.now(timezone.utc))
        indicator = status.get("indicator", "unknown")
        state = "UP" if indicator == "none" else f"DEGRADADO ({status.get('description', 'estado desconocido')})"
        await ctx.send(f"{display_name}: {state} - Uptime estimado ultimos 30 dias: {uptime:.3f}% " f"- Fuente: {status_url}")
    except (requests.RequestException, KeyError, TypeError, ValueError):
        await ctx.send(f"No se pudo consultar el estado de {display_name}. Intenta nuevamente mas tarde.")
