import logging
import sys
import os


logging.basicConfig(
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"hermes_{os.getpid()}.log", mode="w"),
    ],
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger("main_logger")
