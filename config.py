from dotenv import load_dotenv
import os

load_dotenv()

# ── Anthropic ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

# ── Twilio ─────────────────────────────────────────────────────────────────────
TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_NUMBER: str = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

# ── Cal.com ────────────────────────────────────────────────────────────────────
CALCOM_API_KEY: str = os.getenv("CALCOM_API_KEY", "")
CALCOM_EVENT_TYPE_ID: int = int(os.getenv("CALCOM_EVENT_TYPE_ID", "0"))

# ── App ────────────────────────────────────────────────────────────────────────
SKIP_TWILIO_VALIDATION: bool = True

# ── Clinic configuration ───────────────────────────────────────────────────────
# Edit this dict to adapt the bot to any clinic — all other files read from here.
clinic_config: dict = {
    "name": "Clínica Dental San Rafael",
    "address": "15 calle 5-22 Zona 10, frente al Parque Berlín, Ciudad de Guatemala",
    "phone": "2345-6789",
    "whatsapp": "este número",
    "emergency_phone": "5678-9012",
    "hours": {
        "lunes_viernes": "8:00 AM – 12:00 PM y 2:00 PM – 6:00 PM",
        "sabado": "8:00 AM – 12:00 PM",
        "domingo": "Cerrado",
    },
    "doctors": [
        {
            "name": "Dr. Carlos Mendoza",
            "specialty": "Odontología General",
        },
        {
            "name": "Dra. Andrea López",
            "specialty": "Ortodoncia y Estética Dental",
        },
    ],
    "prices": {
        "Consulta general": "Q150",
        "Limpieza dental": "Q250",
        "Extracción simple": "Q300",
        "Extracción muela del juicio": "Q600",
        "Calza / resina": "Q350",
        "Blanqueamiento dental": "Q800",
        "Consulta de ortodoncia": "Q200",
        "Brackets metálicos": "desde Q6,500",
        "Brackets estéticos": "desde Q8,500",
        "Corona dental": "Q1,200",
        "Endodoncia (tratamiento de conducto)": "Q1,500",
    },
}
