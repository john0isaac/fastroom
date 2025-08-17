from logging.config import dictConfig

from fast_room_api.models.config import settings

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        },
    },
    "handlers": {
        "default": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
    },
    "root": {
        "level": settings.log_level,
        "handlers": ["default"],
    },
}


def setup_logging():
    dictConfig(LOGGING_CONFIG)
