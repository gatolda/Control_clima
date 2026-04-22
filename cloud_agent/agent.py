"""Agente principal - orquesta telemetria, eventos y comandos.

Thread model:
- telemetry_loop: lee sensores y encola cada N seg
- flush_loop: drena la cola contra el backend
- command_loop: polling de comandos y los ejecuta

Diseño clave: el control climatico local NO depende del agente. Si el agente
muere, el ActuatorManager/ClimateController siguen funcionando.
"""
import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable

from cloud_agent.client import CloudClient
from cloud_agent.config import AgentConfig
from cloud_agent.queue import PersistentQueue

logger = logging.getLogger("cloud_agent.agent")

# Tipos de callbacks que el agente recibe del sistema local
SensorReadCallback = Callable[[], list[dict[str, Any]]]
ActuatorToggleCallback = Callable[[str, str], dict[str, Any]]
StageSetCallback = Callable[[str], dict[str, Any]]


class CloudAgent:
    """
    Orquesta la comunicacion con el backend SaaS.
    No conoce el hardware - recibe callbacks desde app.py.
    """

    def __init__(
        self,
        config: AgentConfig,
        read_sensors: SensorReadCallback,
        toggle_actuator: ActuatorToggleCallback,
        set_stage: StageSetCallback | None = None,
        queue_db_path: str | None = None,
    ):
        self.config = config
        self.client = CloudClient(config)
        self.read_sensors = read_sensors
        self.toggle_actuator = toggle_actuator
        self.set_stage = set_stage

        queue_path = queue_db_path or str(Path.home() / ".greenhouse-agent" / "outbox.db")
        self.queue = PersistentQueue(queue_path)

        self._running = False
        self._threads: list[threading.Thread] = []

    # --- Eventos publicos (los invoca app.py cuando pasa algo local) ---

    def record_actuator_event(self, actuator: str, action: str, triggered_by: str = "auto") -> None:
        """Encola un evento de actuador para publicar."""
        self.queue.enqueue("actuator", {
            "actuator": actuator,
            "action": action,
            "triggered_by": triggered_by,
        })

    def record_irrigation_event(
        self,
        zone_id: str | None,
        action: str,
        duration_seconds: int | None = None,
        soil_humidity: float | None = None,
        reason: str | None = None,
        triggered_by: str = "scheduler",
    ) -> None:
        self.queue.enqueue("irrigation", {
            "zone_id": zone_id,
            "action": action,
            "duration_seconds": duration_seconds,
            "soil_humidity": soil_humidity,
            "reason": reason,
            "triggered_by": triggered_by,
        })

    # --- Lifecycle ---

    def start(self) -> None:
        if not self.config.is_activated:
            logger.warning("Agente NO activado - saltando arranque. Ejecutar activate.py primero.")
            return

        self._running = True
        for target in (self._telemetry_loop, self._flush_loop, self._command_loop):
            t = threading.Thread(target=target, daemon=True, name=f"cloud-{target.__name__}")
            t.start()
            self._threads.append(t)
        logger.info("CloudAgent iniciado (device_id=%s)", self.config.device_id)

    def stop(self) -> None:
        self._running = False
        logger.info("CloudAgent detenido")

    # --- Loops internos ---

    def _telemetry_loop(self) -> None:
        """Lee sensores cada N seg y encola."""
        while self._running:
            try:
                readings = self.read_sensors()
                for r in readings:
                    self.queue.enqueue("telemetry", r)
                trimmed = self.queue.trim(self.config.max_queue_size)
                if trimmed:
                    logger.warning("Cola llena, descartados %d items viejos", trimmed)
            except Exception as e:
                logger.exception("telemetry_loop error: %s", e)
            time.sleep(self.config.telemetry_interval_seconds)

    def _flush_loop(self) -> None:
        """Drena la cola contra el backend."""
        while self._running:
            try:
                self._flush_kind("telemetry", self.client.publish_telemetry)
                self._flush_kind("actuator", self.client.publish_actuator_events)
                self._flush_kind("irrigation", self.client.publish_irrigation_events)
            except Exception as e:
                logger.exception("flush_loop error: %s", e)
            time.sleep(self.config.event_flush_interval_seconds)

    def _flush_kind(self, kind: str, publish_fn: Callable[[list[dict[str, Any]]], bool]) -> None:
        items = self.queue.peek(kind, limit=200)
        if not items:
            return
        ids = [i[0] for i in items]
        payloads = [i[1] for i in items]
        if publish_fn(payloads):
            self.queue.delete(ids)
            logger.info("Publicados %d items de %s", len(ids), kind)
        # Si falla, quedan en la cola y reintentamos en la proxima iteracion

    def _command_loop(self) -> None:
        """Polling de comandos + ejecucion + ack."""
        while self._running:
            try:
                commands = self.client.poll_commands()
                for cmd in commands:
                    self._execute_command(cmd)
            except Exception as e:
                logger.exception("command_loop error: %s", e)
            time.sleep(self.config.command_poll_interval_seconds)

    def _execute_command(self, cmd: dict[str, Any]) -> None:
        """Dispatcher de comandos."""
        cmd_id = cmd["id"]
        cmd_name = cmd["command"]
        payload = cmd.get("payload") or {}

        logger.info("Ejecutando comando %s (%s)", cmd_name, cmd_id)
        try:
            if cmd_name == "turn_on":
                actuator = payload["actuator"]
                result = self.toggle_actuator(actuator, "on")
                self.client.ack_command(cmd_id, success=result.get("ok", False),
                                        error_message=result.get("error"))
            elif cmd_name == "turn_off":
                actuator = payload["actuator"]
                result = self.toggle_actuator(actuator, "off")
                self.client.ack_command(cmd_id, success=result.get("ok", False),
                                        error_message=result.get("error"))
            elif cmd_name == "set_stage" and self.set_stage:
                stage = payload["stage"]
                result = self.set_stage(stage)
                self.client.ack_command(cmd_id, success=True, result=result)
            else:
                self.client.ack_command(
                    cmd_id, success=False,
                    error_message=f"Comando desconocido: {cmd_name}",
                )
        except Exception as e:
            logger.exception("Error ejecutando %s: %s", cmd_name, e)
            self.client.ack_command(cmd_id, success=False, error_message=str(e))
