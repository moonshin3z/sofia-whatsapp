from datetime import datetime, timedelta


class ConversationManager:
    """In-memory per-user conversation history.

    Keyed by the full WhatsApp number string (e.g. 'whatsapp:+50255551234').
    Entries expire after TIMEOUT_MINUTES of inactivity and are capped at
    MAX_MESSAGES to prevent unbounded memory growth.
    """

    TIMEOUT_MINUTES: int = 30
    MAX_MESSAGES: int = 20  # ~10 user/assistant turns

    def __init__(self) -> None:
        self._store: dict[str, dict] = {}

    def get_history(self, phone: str) -> list[dict]:
        """Return the conversation history for *phone*.

        Clears and returns [] if the session has been idle longer than
        TIMEOUT_MINUTES.  Updates last_updated on every successful access.
        """
        entry = self._store.get(phone)
        if entry is None:
            return []

        if datetime.now() - entry["last_updated"] > timedelta(minutes=self.TIMEOUT_MINUTES):
            self.clear_history(phone)
            return []

        entry["last_updated"] = datetime.now()
        return list(entry["messages"])  # return a shallow copy

    def add_message(self, phone: str, role: str, content: str) -> None:
        """Append a message to the history for *phone*.

        Creates the entry if it does not exist.  Enforces the MAX_MESSAGES cap
        by dropping the two oldest messages (one user + one assistant turn) when
        the limit is reached.
        """
        if phone not in self._store:
            self._store[phone] = {"messages": [], "last_updated": datetime.now()}

        self._store[phone]["messages"].append({"role": role, "content": content})
        self._store[phone]["last_updated"] = datetime.now()

        # Trim to cap: drop oldest pair
        msgs = self._store[phone]["messages"]
        if len(msgs) > self.MAX_MESSAGES:
            self._store[phone]["messages"] = msgs[2:]

    def clear_history(self, phone: str) -> None:
        """Delete the conversation history for *phone*."""
        self._store.pop(phone, None)


# Module-level singleton — import this in routers and services.
conversation_manager = ConversationManager()
