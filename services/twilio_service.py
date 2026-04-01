from twilio.rest import Client
from twilio.request_validator import RequestValidator
from config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER

_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
_validator = RequestValidator(TWILIO_AUTH_TOKEN)

_MAX_BODY_LENGTH = 1600
_TRUNCATION_SUFFIX = "\n\n_(Mensaje truncado)_"


def send_message(to: str, body: str) -> str:
    """Send a WhatsApp message via Twilio.

    Ensures *to* has the ``whatsapp:`` prefix.  Truncates *body* if it exceeds
    Twilio's 1600-character limit.

    Returns the Twilio message SID.
    """
    if not to.startswith("whatsapp:"):
        to = f"whatsapp:{to}"

    if len(body) > _MAX_BODY_LENGTH:
        cutoff = _MAX_BODY_LENGTH - len(_TRUNCATION_SUFFIX)
        body = body[:cutoff] + _TRUNCATION_SUFFIX

    message = _client.messages.create(
        from_=TWILIO_WHATSAPP_NUMBER,
        to=to,
        body=body,
    )
    return message.sid


def validate_signature(url: str, params: dict, signature: str) -> bool:
    """Verify that a request came from Twilio using HMAC-SHA1.

    *url* must be the exact URL Twilio posted to (including scheme).
    *params* is the raw POST form body as a dict.
    *signature* is the value of the ``X-Twilio-Signature`` header.

    Returns True if valid, False otherwise.
    """
    return _validator.validate(url, params, signature)
