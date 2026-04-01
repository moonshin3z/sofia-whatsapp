from datetime import datetime, timedelta
from fastapi import APIRouter, Query
from models.activity_log import activity_log
from services import calcom_service

router = APIRouter(prefix="/api")

# Guatemala = UTC-6
_GT_OFFSET = timedelta(hours=-6)


def _gt_today() -> str:
    return (datetime.utcnow() + _GT_OFFSET).strftime("%Y-%m-%d")


# ── Health ─────────────────────────────────────────────────────────────────────

@router.get("/health")
async def api_health() -> dict:
    return {"status": "ok", "agent": "Sofía AI", "version": "1.0.0"}


# ── Stats ──────────────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_stats() -> dict:
    """KPI summary for the dashboard overview page.

    Matches the ``statsData`` shape in ``dashboardsofia/src/data/mockData.js``.
    """
    return activity_log.get_stats()


# ── Llamadas (call history) ────────────────────────────────────────────────────

@router.get("/llamadas")
async def get_llamadas(
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=10, ge=1, le=100),
    tipo: str = Query(default="all"),
    fecha: str = Query(default=""),
) -> dict:
    """Paginated WhatsApp conversation log.

    Matches the ``llamadas`` shape in ``mockData.js``.

    Query params:
    - ``page``: 0-indexed page number.
    - ``page_size``: items per page (1–100).
    - ``tipo``: filter by tipo field (``"all"`` skips filter).
    - ``fecha``: filter by exact date string ``YYYY-MM-DD``.
    """
    result = activity_log.get_llamadas(page=page, page_size=page_size)

    # Apply optional filters post-pagination for simplicity (in-memory dataset)
    if tipo and tipo != "all":
        result["items"] = [i for i in result["items"] if i["tipo"] == tipo]

    if fecha:
        result["items"] = [i for i in result["items"] if i["fecha"] == fecha]

    return result


# ── Citas (appointments from Cal.com) ─────────────────────────────────────────

@router.get("/citas")
async def get_citas(
    fecha_inicio: str = Query(default=""),
    fecha_fin: str = Query(default=""),
) -> list[dict]:
    """Fetch appointments from Cal.com and map them to the dashboard shape.

    Matches the ``citas`` shape in ``mockData.js``.

    If no date range is provided, defaults to current week (Mon–Sun Guatemala).
    """
    if not fecha_inicio or not fecha_fin:
        today = datetime.utcnow() + _GT_OFFSET
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        fecha_inicio = monday.strftime("%Y-%m-%d")
        fecha_fin = sunday.strftime("%Y-%m-%d")

    raw_bookings = await calcom_service.list_bookings_range(fecha_inicio, fecha_fin)

    _STATUS_MAP = {
        "ACCEPTED": "confirmada",
        "PENDING": "pendiente",
        "CANCELLED": "cancelada",
        "accepted": "confirmada",
        "pending": "pendiente",
        "cancelled": "cancelada",
    }

    citas = []
    for b in raw_bookings:
        attendees = b.get("attendees", [])
        patient_name = attendees[0].get("name", "Paciente") if attendees else "Paciente"

        start_str = b.get("start", "")
        if start_str:
            try:
                dt = datetime.fromisoformat(start_str.replace("Z", "+00:00")) + _GT_OFFSET
                fecha = dt.strftime("%Y-%m-%d")
                hora = dt.strftime("%H:%M")
            except ValueError:
                fecha = start_str[:10]
                hora = ""
        else:
            fecha = ""
            hora = ""

        citas.append(
            {
                "id": b.get("id") or b.get("uid"),
                "paciente": patient_name,
                "servicio": b.get("title", "Consulta dental"),
                "doctor": b.get("user", {}).get("name", "") if isinstance(b.get("user"), dict) else "",
                "fecha": fecha,
                "hora": hora,
                "estado": _STATUS_MAP.get(b.get("status", ""), "pendiente"),
            }
        )

    return citas


# ── Pacientes (patient list) ───────────────────────────────────────────────────

@router.get("/pacientes")
async def get_pacientes(
    q: str = Query(default=""),
) -> list[dict]:
    """Deduplicated patient list derived from the activity log.

    Matches the ``pacientes`` shape in ``mockData.js``.

    Query params:
    - ``q``: case-insensitive search by name or phone.
    """
    return activity_log.get_pacientes(q=q)
