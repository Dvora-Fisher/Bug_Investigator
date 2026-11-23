import logging

log = logging.getLogger(__name__)


class TransientError(Exception):
    """The mail provider asked us to retry later."""


class Mailer:
    def __init__(self, transport, retries: int = 3):
        self.transport = transport
        self.retries = retries

    def send(self, message: dict) -> bool:
        for attempt in range(1, self.retries + 1):
            try:
                self.transport(message)
                return True
            except TransientError:
                log.debug("retrying %s (attempt %d)", message["to"], attempt)
        return False
