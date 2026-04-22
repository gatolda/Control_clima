"""Configuracion del agente cloud - lee de variables de entorno / archivo."""
import json
import os
from dataclasses import dataclass
from pathlib import Path

CONFIG_PATH = Path(os.environ.get("AGENT_CONFIG", "/etc/greenhouse-agent/agent.json"))
if not CONFIG_PATH.exists():
    # Fallback para desarrollo local
    CONFIG_PATH = Path.home() / ".greenhouse-agent" / "agent.json"


@dataclass
class AgentConfig:
    api_base_url: str
    device_id: str | None
    device_secret: str | None
    telemetry_interval_seconds: int = 30
    command_poll_interval_seconds: int = 10
    event_flush_interval_seconds: int = 15
    max_queue_size: int = 10_000

    @classmethod
    def load(cls) -> "AgentConfig":
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text())
        else:
            data = {}
        api = os.environ.get("GREENHOUSE_API_URL", data.get("api_base_url", "http://localhost:8000"))
        return cls(
            api_base_url=api.rstrip("/"),
            device_id=os.environ.get("DEVICE_ID", data.get("device_id")),
            device_secret=os.environ.get("DEVICE_SECRET", data.get("device_secret")),
            telemetry_interval_seconds=int(data.get("telemetry_interval_seconds", 30)),
            command_poll_interval_seconds=int(data.get("command_poll_interval_seconds", 10)),
            event_flush_interval_seconds=int(data.get("event_flush_interval_seconds", 15)),
            max_queue_size=int(data.get("max_queue_size", 10_000)),
        )

    def save(self) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(self.__dict__, indent=2))

    @property
    def is_activated(self) -> bool:
        return bool(self.device_id and self.device_secret)

    def headers(self) -> dict[str, str]:
        return {
            "X-Device-ID": self.device_id or "",
            "X-Device-Secret": self.device_secret or "",
        }
