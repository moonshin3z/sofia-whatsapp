from datetime import datetime, timedelta
from collections import defaultdict

# Guatemala is UTC-6
_GT_OFFSET = timedelta(hours=-6)


def _gt_now() -> datetime:
    """Current datetime in Guatemala time (UTC-6)."""
    return datetime.utcnow() + _GT_OFFSET


class ActivityLog:
    """In-memory append-only log of WhatsApp conversation turns.

    Each entry represents one inbound message + bot response cycle.
    Provides aggregated views for the dashboard REST API.
    """

    def __init__(self) -> None:
        self._log: list[dict] = []
        self._counter: int = 0

    # ── Write ──────────────────────────────────────────────────────────────────

    def log_call(
        self,
        phone: str,
        patient_name: str | None,
        resultado: str,
        tools_called: list[str],
        mensajes_count: int,
    ) -> None:
        """Append one activity entry."""
        self._counter += 1
        now = _gt_now()
        # Heuristic duration: 1 min base + 1 min per tool call
        duracion_min = max(1, 1 + len(tools_called))

        self._log.append(
            {
                "id": self._counter,
                "phone": phone,
                "patient_name": patient_name,
                "tipo": "Entrante",
                "resultado": resultado,
                "fecha": now.strftime("%Y-%m-%d"),
                "hora": now.strftime("%H:%M"),
                "duracion_min": duracion_min,
                "mensajes_count": mensajes_count,
                "tools_called": list(tools_called),
            }
        )

    # ── Read ───────────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Return KPI dict for the /api/stats endpoint."""
        today = _gt_now().strftime("%Y-%m-%d")
        month = _gt_now().strftime("%Y-%m")

        today_entries = [e for e in self._log if e["fecha"] == today]
        month_entries = [e for e in self._log if e["fecha"].startswith(month)]

        citas_hoy = sum(1 for e in today_entries if e["resultado"] == "Cita agendada")
        citas_mes = sum(1 for e in month_entries if e["resultado"] == "Cita agendada")

        # Resolution = turns that didn't end in "Error" or "No contestó"
        non_resolved = {"Error", "No contestó"}
        resolved_today = sum(1 for e in today_entries if e["resultado"] not in non_resolved)
        tasa = int(resolved_today / len(today_entries) * 100) if today_entries else 100

        minutos = sum(e["duracion_min"] for e in self._log)

        return {
            "llamadasHoy": len(today_entries),
            "citasAgendadas": citas_hoy,
            "tasaResolucion": tasa,
            "noShows": 0,
            "llamadasMes": len(month_entries),
            "citasMes": citas_mes,
            "minutosAhorrados": minutos,
            "agentActivo": True,
        }

    def get_llamadas(self, page: int = 0, page_size: int = 10) -> dict:
        """Return a paginated, newest-first call list for /api/llamadas."""
        # Reverse so newest entries appear first
        reversed_log = list(reversed(self._log))
        total = len(reversed_log)
        pages = max(1, -(-total // page_size))  # ceiling division
        start = page * page_size
        slice_ = reversed_log[start : start + page_size]

        items = [
            {
                "id": e["id"],
                "paciente": e["patient_name"] or f"WhatsApp ...{e['phone'][-4:]}",
                "telefono": e["phone"],
                "duracion": f"{e['duracion_min']}:00",
                "tipo": e["tipo"],
                "resultado": e["resultado"],
                "fecha": e["fecha"],
                "hora": e["hora"],
            }
            for e in slice_
        ]

        return {"items": items, "total": total, "page": page, "pages": pages}

    def get_pacientes(self, q: str = "") -> list[dict]:
        """Return a deduplicated patient list grouped by phone number."""
        # Group entries by phone
        by_phone: dict[str, list[dict]] = defaultdict(list)
        for e in self._log:
            by_phone[e["phone"]].append(e)

        patients = []
        for idx, (phone, entries) in enumerate(by_phone.items(), start=1):
            # Use the most recent non-None patient name
            name = next(
                (e["patient_name"] for e in reversed(entries) if e["patient_name"]),
                f"WhatsApp ...{phone[-4:]}",
            )

            cita_entries = [e for e in entries if e["resultado"] == "Cita agendada"]
            ultima_cita = cita_entries[-1]["fecha"] if cita_entries else None

            patient = {
                "id": idx,
                "nombre": name,
                "telefono": phone,
                "email": None,
                "ultimaCita": ultima_cita,
                "proximaCita": None,
                "proximoServicio": None,
                "totalCitas": len(cita_entries),
            }
            patients.append(patient)

        if q:
            q_lower = q.lower()
            patients = [
                p
                for p in patients
                if q_lower in p["nombre"].lower() or q_lower in p["telefono"]
            ]

        return patients


# Module-level singleton
activity_log = ActivityLog()
