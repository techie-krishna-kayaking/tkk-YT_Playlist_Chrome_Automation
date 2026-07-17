"""Telegram Bot API notifications (standard library only, no extra deps)."""

from __future__ import annotations

import ssl
import urllib.parse
import urllib.request

from loguru import logger

from .config import TelegramConfig


def _build_ssl_context() -> ssl.SSLContext:
    """Build an SSL context that trusts the OS certificate store.

    On networks with a TLS-inspecting proxy (common in corporate environments),
    Python's default OpenSSL trust store does not contain the proxy's root CA,
    causing ``CERTIFICATE_VERIFY_FAILED``. ``truststore`` bridges Python to the
    operating system trust store (macOS Keychain / Windows cert store), which
    already trusts that root - so verification stays ON and secure.
    """
    try:
        import truststore  # type: ignore

        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except Exception:  # noqa: BLE001 - fall back to the default trust store
        return ssl.create_default_context()


class TelegramNotifier:
    """Sends messages to a Telegram chat via the Bot API.

    Failures never raise: a notifier problem must not interrupt the playback
    cycle, so send() logs and returns False instead.
    """

    _API = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(self, cfg: TelegramConfig) -> None:
        self._cfg = cfg
        self._ssl_context = _build_ssl_context()

    @property
    def active(self) -> bool:
        """True when notifications are enabled and fully configured."""
        return bool(self._cfg.enabled and self._cfg.bot_token and self._cfg.chat_id)

    def send(self, text: str) -> bool:
        """Send a text message. Returns True on success.

        Args:
            text: The message body.
        """
        if not self.active:
            if self._cfg.enabled:
                logger.warning(
                    "Telegram enabled but bot_token/chat_id are missing; "
                    "skipping message. Set them in config.yaml or via the "
                    "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID env vars."
                )
            return False

        url = self._API.format(token=self._cfg.bot_token)
        payload = urllib.parse.urlencode(
            {
                "chat_id": self._cfg.chat_id,
                "text": text,
                "disable_web_page_preview": "true",
            }
        ).encode("utf-8")

        try:
            request = urllib.request.Request(url, data=payload, method="POST")
            with urllib.request.urlopen(  # noqa: S310
                request, timeout=15, context=self._ssl_context
            ) as response:
                ok = 200 <= response.status < 300
            if ok:
                logger.debug("Telegram message sent.")
            else:
                logger.warning("Telegram API returned status {}.", response.status)
            return ok
        except Exception as exc:  # noqa: BLE001 - never break the cycle
            logger.warning("Failed to send Telegram message: {}", exc)
            return False
