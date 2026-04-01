from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import Response

from config import SKIP_TWILIO_VALIDATION, clinic_config
from models.conversation import conversation_manager
from models.activity_log import activity_log
from services import claude_service, twilio_service

router = APIRouter()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _derive_resultado(tools_called: list[str], response_text: str) -> str:
    """Map tool names (and response text hints) to a dashboard resultado label."""
    if "create_booking" in tools_called:
        return "Cita agendada"
    if "cancel_booking" in tools_called:
        return "Cancelación"
    if "get_patient_bookings" in tools_called and "get_available_slots" not in tools_called:
        return "Consulta de citas"
    if "get_available_slots" in tools_called:
        return "Consulta de disponibilidad"

    price_keywords = ("precio", "costo", "cuánto", "cuanto", "vale", "q150", "q250", "q300")
    if any(kw in response_text.lower() for kw in price_keywords):
        return "Información de precios"

    return "Consulta general"


def _reconstruct_url(request: Request) -> str:
    """Reconstruct the public HTTPS URL that Twilio actually called.

    Behind Railway/Render the internal URL uses http://, but Twilio signs
    against the original https:// URL.  We use X-Forwarded-Proto when present.
    """
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("host", request.url.netloc)
    path = request.url.path
    query = f"?{request.url.query}" if request.url.query else ""
    return f"{proto}://{host}{path}{query}"


# ── Background task ────────────────────────────────────────────────────────────

async def process_message(phone: str, body: str) -> None:
    """Process one inbound WhatsApp message and send a reply.

    Runs as a FastAPI BackgroundTask so Twilio receives a 200 OK immediately.
    """
    if not body or not body.strip():
        return

    try:
        history = conversation_manager.get_history(phone)

        response_text, tools_called, tool_inputs = await claude_service.get_response(
            history=history,
            user_message=body,
            patient_phone=phone,
        )

        # Persist turns in history AFTER getting the response so the
        # history passed to Claude is the state *before* this turn.
        conversation_manager.add_message(phone, "user", body)
        conversation_manager.add_message(phone, "assistant", response_text)

        # Send reply via Twilio
        twilio_service.send_message(to=phone, body=response_text)

        # Derive logging metadata
        patient_name: str | None = (
            tool_inputs.get("create_booking", {}).get("nombre")
            or tool_inputs.get("get_patient_bookings", {}).get("telefono")
        )
        resultado = _derive_resultado(tools_called, response_text)
        mensajes_count = len(conversation_manager.get_history(phone))

        activity_log.log_call(
            phone=phone.replace("whatsapp:", ""),
            patient_name=patient_name,
            resultado=resultado,
            tools_called=tools_called,
            mensajes_count=mensajes_count,
        )

    except Exception as exc:
        print(f"[ERROR] process_message({phone}): {exc}")
        # Best-effort error reply — don't crash the background task
        try:
            twilio_service.send_message(
                to=phone,
                body=(
                    f"Lo siento, ocurrió un error inesperado. "
                    f"Por favor llámenos al {clinic_config['phone']}."
                ),
            )
        except Exception:
            pass


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/webhook")
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> Response:
    """Receive inbound WhatsApp messages from Twilio.

    1. Validates the Twilio HMAC-SHA1 signature (unless SKIP_TWILIO_VALIDATION).
    2. Dispatches message processing to a background task.
    3. Returns an empty TwiML response immediately so Twilio doesn't time out.
    """
    form_data = await request.form()
    params = dict(form_data)

    # ── Signature validation ───────────────────────────────────────────────────
    if not SKIP_TWILIO_VALIDATION:
        signature = request.headers.get("x-twilio-signature", "")
        url = _reconstruct_url(request)
        if not twilio_service.validate_signature(url, params, signature):
            raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    # ── Extract message fields ─────────────────────────────────────────────────
    from_number: str = params.get("From", "")
    body: str = params.get("Body", "").strip()
    num_media: int = int(params.get("NumMedia", "0"))
    media_type: str = params.get("MediaContentType0", "")

    # Ignore completely empty messages (no text and no media)
    if not from_number or (not body and num_media == 0):
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
            media_type="text/xml",
        )

    # Media received — reply directly without going through Claude
    if num_media > 0 and not body:
        background_tasks.add_task(
            twilio_service.send_message,
            from_number,
            "¡Hola! Lamentablemente no puedo ver imágenes, stickers, videos ni audios 😊 "
            "¿En qué le puedo ayudar? Escríbame su consulta.",
        )
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
            media_type="text/xml",
        )

    # ── Dispatch text message ──────────────────────────────────────────────────
    background_tasks.add_task(process_message, from_number, body)

    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
        media_type="text/xml",
    )


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "agent": "Sofía AI", "version": "1.0.0"}
