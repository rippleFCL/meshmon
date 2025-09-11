import logging
from distmon.config import NetworkConfigLoader

# Set up basic logging for testing
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s|%(name)s|%(levelname)s|%(message)s")
logger = logging.getLogger("test")

logger.info("Starting configuration test")
config = NetworkConfigLoader()
logger.info(f"Loaded {len(config.networks)} networks")

print()
