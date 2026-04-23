"""Cliente HTTP hacia el backend SaaS con reintentos y timeouts."""
from __future__ import annotations

import logging
from typing import Any

import requests

from cloud_agent.config import AgentConfig

logger = logging.getLogger("cloud_agent.client")


class CloudClient:
    """Cliente sincrono (threading) con reintentos basicos."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "greenhouse-agent/0.1"})

    def _url(self, path: str) -> str:
        return f"{self.config.api_base_url}{path}"

    def _headers(self) -> dict[str, str]:
        return self.config.headers()

    def activate(self, provisioning_token: str) -> dict[str, str]:
        """Intercambia un provisioning_token por device_id + device_secret."""
        r = self.session.post(
            self._url("/api/v1/devices/activate"),
            json={"provisioning_token": provisioning_token},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()

    def publish_telemetry(self, readings: list[dict[str, Any]]) -> bool:
        """Publica un batch de lecturas. Retorna True si el server acepto."""
        try:
            r = self.session.post(
                self._url("/api/v1/telemetry"),
                json={"readings": readings},
                headers=self._headers(),
                timeout=10,
            )
            r.raise_for_status()
            return True
        except requests.RequestException as e:
            logger.warning("publish_telemetry fallo: %s", e)
            return False

    def publish_actuator_events(self, events: list[dict[str, Any]]) -> bool:
        try:
            r = self.session.post(
                self._url("/api/v1/events/actuators"),
                json={"events": events},
                headers=self._headers(),
                timeout=10,
            )
            r.raise_for_status()
            return True
        except requests.RequestException as e:
            logger.warning("publish_actuator_events fallo: %s", e)
            return False

    def publish_irrigation_events(self, events: list[dict[str, Any]]) -> bool:
        try:
            r = self.session.post(
                self._url("/api/v1/events/irrigation"),
                json={"events": events},
                headers=self._headers(),
                timeout=10,
            )
            r.raise_for_status()
            return True
        except requests.RequestException as e:
            logger.warning("publish_irrigation_events fallo: %s", e)
            return False

    def poll_commands(self) -> list[dict[str, Any]]:
        """Obtiene comandos pendientes. El server los marca como DELIVERED."""
        try:
            r = self.session.get(
                self._url("/api/v1/device/commands/pending"),
                headers=self._headers(),
                timeout=10,
            )
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            logger.warning("poll_commands fallo: %s", e)
            return []

    def ack_command(
        self,
        command_id: str,
        success: bool,
        error_message: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> bool:
        try:
            r = self.session.post(
                self._url(f"/api/v1/device/commands/{command_id}/ack"),
                json={
                    "success": success,
                    "error_message": error_message,
                    "result": result,
                },
                headers=self._headers(),
                timeout=10,
            )
            r.raise_for_status()
            return True
        except requests.RequestException as e:
            logger.warning("ack_command fallo: %s", e)
            return False
