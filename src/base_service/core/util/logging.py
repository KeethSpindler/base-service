import logging


def instantiate_logger(service_name: str, logging_level: str) -> logging.Logger:
    formatter = logging.Formatter(
        fmt="[%(name)s | %(levelname)s](%(asctime)s): %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    logger = logging.getLogger(service_name)
    logger.setLevel(logging_level)
    logger.addHandler(handler)
    logger.propagate = False
