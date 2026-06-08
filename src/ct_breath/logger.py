import logging


class RespiraScopeFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        if record.levelno >= logging.WARNING:
            return f"[RespiraScope] {record.levelname}: {message}"
        return f"[RespiraScope] {message}"


def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(RespiraScopeFormatter("%(message)s"))
        logger.addHandler(handler)

    return logger


logger = setup_logger(__name__)
