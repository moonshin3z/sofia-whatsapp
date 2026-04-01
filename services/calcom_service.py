import httpx
import logging
from datetime import datetime, timedelta
from config import CALCOM_API_KEY, CALCOM_EVENT_TYPE_ID

logger = logging.getLogger(__name__)

BASE_URL = "https://api.cal.com/v2"
_HEADERS = {
    "Authorization": f"Bearer {CALCOM_API_KEY}",
    "cal-api-version": "2024-09-04",
    "Content-Type": "application/json",
}

# Guatemala = UTC-6
_GT_OFFSET = timedelta(hours=-6)


def _to_guatemala(iso_str: str) -> datetime:
    """Parse an ISO-8601 UTC string and convert it to Guatemala time (UTC-6)."""
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return dt + _GT_OFFSET


async def get_available_slots(days_ahead: int = 7) -> dict:
    """Return available slots for the next *days_ahead* days.

    Slots are filtered to clinic hours: 08:00–18:00 Guatemala time.
    Returns a dict shaped like::

        {
            "2026-03-25": [
                {"iso": "2026-03-25T14:00:00Z", "hora_local": "08:00"},
                ...
            ],
            ...
        }

    Returns ``{"error": "<message>"}`` on failure.
    """
    now = datetime.utcnow()
    start = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    end = (now + timedelta(days=days_ahead)).strftime("%Y-%m-%dT23:59:59Z")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{BASE_URL}/slots",
                params={
                    "eventTypeId": CALCOM_EVENT_TYPE_ID,
                    "start": start,
                    "end": end,
                    "timeZone": "America/Guatemala",
                },
                headers=_HEADERS,
            )
            logger.warning("CALCOM status: %s body: %s", resp.status_code, resp.text)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.warning("CALCOM get_available_slots HTTP error: %s", exc)
        return {"error": str(exc)}
    except Exception as exc:
        logger.warning("CALCOM get_available_slots error: %s", exc)
        return {"error": str(exc)}

    # Cal.com v2: {"status":"success","data":{"2026-04-02":[{"start":"..."}],...}}
    raw_slots: dict = {}
    if isinstance(data, dict):
        inner = data.get("data", {})
        raw_slots = inner if isinstance(inner, dict) else {}

    filtered: dict = {}
    for date_str, slots in raw_slots.items():
        valid = []
        for slot in slots:
            iso = slot.get("start") or slot.get("time") or ""
            if not iso:
                continue
            # Slots already come in Guatemala time (offset -06:00), parse as-is
            dt = datetime.fromisoformat(iso)
            if 8 <= dt.hour < 18:
                valid.append({"iso": iso, "hora_local": dt.strftime("%H:%M")})
        if valid:
            filtered[date_str] = valid

    return filtered


async def create_booking(
    nombre: str,
    email: str,
    telefono: str,
    slot_iso: str,
) -> dict:
    """Create an appointment in Cal.com.

    Returns::

        {"booking_id": 42, "start": "2026-03-25T14:00:00Z", "status": "accepted"}

    or ``{"error": "<message>"}`` on failure.
    """
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{BASE_URL}/bookings",
                headers=_HEADERS,
                json={
                    "eventTypeId": CALCOM_EVENT_TYPE_ID,
                    "start": slot_iso,
                    "attendee": {
                        "name": nombre,
                        "email": email,
                        "timeZone": "America/Guatemala",
                        "phoneNumber": telefono,
                    },
                    "metadata": {"whatsapp": telefono},
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        return {"error": str(exc)}

    booking = data.get("data", data)  # unwrap if nested
    return {
        "booking_id": booking.get("id") or booking.get("uid"),
        "start": booking.get("start") or slot_iso,
        "status": booking.get("status", "accepted"),
    }


async def get_bookings_by_phone(telefono: str) -> list[dict]:
    """Return upcoming bookings for a patient identified by *telefono*.

    Returns a list of dicts::

        [{"booking_id": 42, "start": "...", "title": "...", "status": "accepted"}, ...]

    Returns ``[]`` on failure or when no bookings are found.
    """
    clean_phone = telefono.replace("-", "").replace(" ", "")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{BASE_URL}/bookings",
                headers=_HEADERS,
                params={"status": "upcoming"},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    bookings_raw = (
        data.get("data", {}).get("upcomingBookings", [])
        if isinstance(data.get("data"), dict)
        else data.get("data", [])
    )

    results = []
    for b in bookings_raw:
        attendees = b.get("attendees", [])
        attendee_phone = attendees[0].get("phoneNumber", "") if attendees else ""
        meta_phone = str(b.get("metadata", {}).get("whatsapp", ""))

        if clean_phone in attendee_phone.replace("-", "").replace(" ", "") or clean_phone in meta_phone:
            results.append(
                {
                    "booking_id": str(b.get("id") or b.get("uid")),
                    "start": b.get("start", ""),
                    "title": b.get("title", "Consulta dental"),
                    "status": b.get("status", ""),
                }
            )

    return results


async def cancel_booking(booking_id: str, reason: str = "Cancelado por paciente") -> dict:
    """Cancel a booking by its ID.

    Returns ``{"cancelled": True, "booking_id": "..."}`` or ``{"error": "..."}``.
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.delete(
                f"{BASE_URL}/bookings/{booking_id}/cancel",
                headers=_HEADERS,
                json={"cancellationReason": reason},
            )
            resp.raise_for_status()
    except Exception as exc:
        return {"error": str(exc)}

    return {"cancelled": True, "booking_id": booking_id}


async def list_bookings_range(start_date: str, end_date: str) -> list[dict]:
    """Fetch all bookings between *start_date* and *end_date* (YYYY-MM-DD).

    Used by the dashboard /api/citas endpoint.
    Returns list of raw booking dicts or [] on failure.
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{BASE_URL}/bookings",
                headers=_HEADERS,
                params={
                    "afterStart": f"{start_date}T00:00:00Z",
                    "beforeEnd": f"{end_date}T23:59:59Z",
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    raw = data.get("data", [])
    if isinstance(raw, dict):
        raw = raw.get("upcomingBookings", []) + raw.get("recurringBookings", [])

    return raw if isinstance(raw, list) else []
