"""Script de activacion - se corre una vez con el provisioning_token del QR.

Uso:
    python -m cloud_agent.activate <provisioning_token>
    python -m cloud_agent.activate --api http://server:8000 <token>
"""
import argparse
import logging
import sys

from cloud_agent.client import CloudClient
from cloud_agent.config import AgentConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("activate")


def main() -> int:
    parser = argparse.ArgumentParser(description="Activa este dispositivo contra el backend SaaS")
    parser.add_argument("token", help="provisioning_token obtenido del dashboard / QR")
    parser.add_argument("--api", help="URL base del backend (default: desde env o config)")
    args = parser.parse_args()

    config = AgentConfig.load()
    if args.api:
        config.api_base_url = args.api.rstrip("/")

    if config.is_activated:
        logger.warning("Este dispositivo ya esta activado (device_id=%s)", config.device_id)
        logger.warning("Si querés reactivarlo, borra %s primero.", "~/.greenhouse-agent/agent.json")
        return 1

    client = CloudClient(config)
    try:
        logger.info("Activando contra %s...", config.api_base_url)
        result = client.activate(args.token)
    except Exception as e:
        logger.error("Fallo de activacion: %s", e)
        return 2

    config.device_id = result["device_id"]
    config.device_secret = result["device_secret"]
    config.save()
    logger.info("Activacion exitosa. device_id=%s", config.device_id)
    logger.info("Credenciales guardadas en ~/.greenhouse-agent/agent.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
