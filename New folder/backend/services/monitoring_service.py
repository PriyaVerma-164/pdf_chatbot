import logging
import time
import psutil

from ..config import settings

logger = logging.getLogger("backend.monitoring")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


def log_metric(name: str, value, extra: str = None) -> None:
    message = f"metric={name} value={value}"
    if extra:
        message = f"{message} {extra}"
    logger.info(message)


def throttle_cpu() -> None:
    usage = psutil.cpu_percent(interval=0.1)
    if usage >= settings.CPU_THRESHOLD:
        logger.info("CPU usage %.1f%% detected, yielding to keep load low", usage)
        time.sleep(0.5)
