"""
ai_controller.py — Modo Auto IA del greenhouse.

Cuando el sistema esta en modo "auto_ia", este modulo decide cada 30 min
que actuadores prender/apagar usando Claude Sonnet 4.6.

Flow:
    1. Tomar snapshot del estado (sensores + actuadores + etapa + hora + ultimo
       analisis visual + tendencia ultimas 6h + ultimas decisiones IA)
    2. Llamar Claude con structured output: list of {actuador, estado, razon}
    3. Validar acciones contra constraints (whitelist + conflictos + frecuencia)
    4. Aplicar via actuator_manager
    5. Guardar todo en tabla ai_decisions (auditoria)

Safety:
    - Solo actuadores en la whitelist (config.ai_control.allowed_actuators)
    - Solo "on" o "off"
    - Respeta conflictos del actuator_manager (humidificador <> deshumidificador, etc.)
    - Si confianza < min_confidence → solo loguea sin aplicar
    - Si Claude da error → no toca nada, registra el error
    - Failsafe: si el sistema esta en failsafe_active, el modo IA NO actua
"""
from __future__ import annotations
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import anthropic
except ImportError:
    anthropic = None

MODEL = "claude-sonnet-4-6"

# El JSON schema valida la respuesta de Claude antes de tocar relés.
# Si Claude devuelve algo que no matchea, output_config.format lanza error.
DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "acciones": {
            "type": "array",
            "description": "Lista de acciones a aplicar. Vacia si todo esta OK y no hay que cambiar nada.",
            "items": {
                "type": "object",
                "properties": {
                    "actuador": {"type": "string", "description": "Nombre exacto del actuador (ej. 'ventiladores')"},
                    "estado":   {"type": "string", "enum": ["on", "off"]},
                    "razon":    {"type": "string", "description": "Por que esta accion ahora (1-2 oraciones)"}
                },
                "required": ["actuador", "estado", "razon"],
                "additionalProperties": False
            }
        },
        "razonamiento_general": {
            "type": "string",
            "description": "Resumen del estado del sistema y por que las acciones propuestas (3-5 oraciones)."
        },
        "confianza": {
            "type": "integer",
            "description": "Confianza en las decisiones, 1-10. <5 indica que algo es ambiguo, mejor no actuar."
        },
        "alerta_humana": {
            "type": ["string", "null"],
            "description": "Si detectas algo que requiere intervencion humana urgente (sensor caido, condicion critica, etc.), describilo aca. null si todo OK."
        }
    },
    "required": ["acciones", "razonamiento_general", "confianza", "alerta_humana"],
    "additionalProperties": False
}


SYSTEM_PROMPT = """Sos el controlador climatico AUTONOMO de un invernadero indoor de cultivo (cannabis u otras plantas similares). Tu trabajo es decidir cada 30 minutos que actuadores prender o apagar para mantener el ambiente optimo segun la etapa de cultivo.

ACTUADORES DISPONIBLES (whitelist — usar SOLO estos nombres exactos):
- ventiladores       — circulacion interna de aire
- filtro_carbon      — filtra olor del aire
- intractor          — extractor de aire (saca aire caliente/humedo)
- humidificador      — sube humedad
- deshumidificador   — baja humedad
- calefactor         — sube temperatura
- aire_acondicionado — baja temperatura

NO PODES tocar: luz (la maneja el fotoperiodo automatico).

REGLAS HARD (nunca violar — el sistema te va a rechazar si lo intentas):
- humidificador y deshumidificador no pueden estar juntos en "on"
- calefactor y aire_acondicionado no pueden estar juntos en "on"

CRITERIOS DE DECISION:
- Compara cada sensor con los umbrales optimos de la etapa actual (te los paso en el contexto)
- Considera la TENDENCIA: si humedad esta bajando pero todavia en rango, no necesitas activar humidificador ya
- Considera las ULTIMAS DECISIONES: no estes prendiendo y apagando el mismo actuador cada ciclo (hysteresis)
- Hora del dia importa: durante el fotoperiodo de luz, la temp tiende a subir; durante oscuridad, baja
- Si todo esta dentro de rango y estable, no actues (acciones: [])

CRITERIOS DE CONFIANZA:
- 8-10: estado claro, accion obvia (sensor X fuera de rango, accion Y resuelve)
- 5-7: situacion ambigua pero accion razonable
- 1-4: muy incierto (sensor reportando raro, datos inconsistentes) — NO ACTUES, mejor alertar humano via alerta_humana

ALERTAS HUMANAS (usar alerta_humana):
- Sensor crítico no reporta hace mucho
- Combinacion peligrosa de variables que no se resuelve con actuadores (ej. CO2 disparado + temp alta + alta humedad simultaneamente)
- Patron inusual que no entendes

Sé conservador. Es mejor no actuar que actuar mal. El sistema corre cada 30 min, hay tiempo para correcciones."""


_client: "anthropic.Anthropic | None" = None


def _get_client() -> "anthropic.Anthropic":
    global _client
    if _client is None:
        if anthropic is None:
            raise RuntimeError("anthropic SDK no instalado")
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY no esta en el entorno")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def build_context(db, sensor_reader, actuator_manager, climate_controller) -> dict:
    """Snapshot del sistema. Se pasa a Claude como user message."""
    ctx: dict[str, Any] = {"timestamp": datetime.now().isoformat()}

    # Etapa + umbrales
    try:
        stage, thresholds = climate_controller.get_current_stage()
        ctx["etapa"] = stage
        ctx["umbrales_optimos"] = thresholds
    except Exception as e:
        ctx["etapa"] = "?"
        ctx["umbrales_optimos"] = {}
        ctx["_warn_stage"] = str(e)

    # Hora actual + fotoperiodo
    try:
        now = datetime.now()
        ctx["hora"] = now.strftime("%H:%M")
        light_on  = int(db.get_config("light_on_hour", "6") or "6")
        light_off = int(db.get_config("light_off_hour", "0") or "0")
        ctx["fotoperiodo"] = {"luz_on_hora": light_on, "luz_off_hora": light_off}
        ctx["en_fotoperiodo_luz"] = (light_on <= now.hour < (light_off if light_off > light_on else light_off + 24))
    except Exception:
        pass

    # Lecturas actuales
    try:
        row = db.get_latest_reading() if hasattr(db, "get_latest_reading") else None
        if row:
            ctx["sensores_actuales"] = {
                "temperatura_c": row.get("temperature"),
                "humedad_pct":   row.get("humidity"),
                "co2_ppm":       row.get("co2"),
                "vpd_kpa":       row.get("vpd"),
                "timestamp":     row.get("timestamp"),
            }
    except Exception as e:
        ctx["_warn_sensors"] = str(e)

    # Tendencia: agregada por hora ultimas 6h
    try:
        readings = db.get_readings(hours=6) if hasattr(db, "get_readings") else []
        if readings:
            # Agregar por hora: avg de cada variable
            from collections import defaultdict
            buckets: dict[str, list] = defaultdict(list)
            for r in readings:
                ts = r.get("timestamp", "")
                if not ts: continue
                hour_key = ts[:13]  # "YYYY-MM-DD HH"
                if r.get("temperature") is not None:
                    buckets[hour_key].append(r)
            tend = []
            for hkey in sorted(buckets.keys()):
                rows = buckets[hkey]
                def avg(field):
                    vals = [x[field] for x in rows if x.get(field) is not None]
                    return round(sum(vals) / len(vals), 1) if vals else None
                tend.append({
                    "hora": hkey,
                    "temp_avg":  avg("temperature"),
                    "hum_avg":   avg("humidity"),
                    "co2_avg":   avg("co2"),
                })
            ctx["tendencia_6h"] = tend
    except Exception as e:
        ctx["_warn_trend"] = str(e)

    # Estado de actuadores
    try:
        if actuator_manager:
            status = actuator_manager.status() if hasattr(actuator_manager, "status") else {}
            ctx["actuadores_estado_actual"] = status
    except Exception:
        pass

    # Failsafe activo?
    try:
        fs = climate_controller.failsafe_active if hasattr(climate_controller, "failsafe_active") else False
        ctx["failsafe_activo"] = bool(fs)
    except Exception:
        ctx["failsafe_activo"] = False

    # Ultimo analisis visual IA
    try:
        last = db.get_latest_analysis() if hasattr(db, "get_latest_analysis") else None
        if last and last.get("analysis"):
            a = last["analysis"]
            ctx["ultimo_analisis_visual"] = {
                "cuando": last.get("analyzed_at"),
                "salud_general": a.get("salud_general"),
                "plagas_detectadas": a.get("signos_plagas", {}).get("detectado"),
                "deficiencias_detectadas": a.get("signos_deficiencias", {}).get("detectado"),
                "recomendaciones": a.get("recomendaciones", [])[:3],
            }
    except Exception:
        pass

    # Ultimas decisiones IA (anti-flapping)
    try:
        if hasattr(db, "get_recent_ai_decisions"):
            recent = db.get_recent_ai_decisions(limit=5)
            ctx["ultimas_decisiones_ia"] = recent
    except Exception:
        pass

    return ctx


def decide(context: dict) -> dict:
    """Llama Claude con el contexto + system prompt cacheable. Devuelve dict
    matcheando DECISION_SCHEMA + metadata _usage / _model.
    """
    client = _get_client()

    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        # System cacheable — se repite identico en cada llamada (~90% ahorro)
        system=[{
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        output_config={
            "format": {"type": "json_schema", "schema": DECISION_SCHEMA},
        },
        messages=[{
            "role": "user",
            "content": "Estado actual del invernadero (JSON):\n\n" + json.dumps(context, indent=2, ensure_ascii=False, default=str),
        }],
    )

    text = next((b.text for b in response.content if b.type == "text"), None)
    if not text:
        raise RuntimeError(f"Respuesta sin bloque de texto. stop={response.stop_reason}")
    decision = json.loads(text)
    decision["_usage"] = {
        "input_tokens":  response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cache_read_input_tokens":     getattr(response.usage, "cache_read_input_tokens", 0),
        "cache_creation_input_tokens": getattr(response.usage, "cache_creation_input_tokens", 0),
    }
    decision["_model"] = response.model
    return decision


# Lista whitelist de actuadores que IA puede tocar (sin la luz)
ALLOWED_ACTUATORS = {
    "ventiladores", "filtro_carbon", "intractor",
    "humidificador", "deshumidificador",
    "calefactor", "aire_acondicionado",
}


def validate_and_apply(decision: dict, actuator_manager, min_confidence: int = 5) -> dict:
    """Valida las acciones de Claude y las aplica via actuator_manager.
    Devuelve dict con resultado por accion.
    """
    result = {
        "applied":  [],
        "skipped":  [],
        "errors":   [],
        "confidence_too_low": False,
    }

    confidence = decision.get("confianza", 0)
    if confidence < min_confidence:
        result["confidence_too_low"] = True
        for a in decision.get("acciones", []):
            result["skipped"].append({**a, "motivo_skip": f"confianza {confidence}<{min_confidence}"})
        return result

    for a in decision.get("acciones", []):
        name  = a.get("actuador", "")
        state = a.get("estado", "")
        if name not in ALLOWED_ACTUATORS:
            result["skipped"].append({**a, "motivo_skip": f"actuador no permitido"})
            continue
        if state not in ("on", "off"):
            result["skipped"].append({**a, "motivo_skip": f"estado invalido: {state}"})
            continue

        # actuator_manager devuelve dict {ok, error} con conflict handling
        try:
            if state == "on":
                res = actuator_manager.turn_on(name)
            else:
                res = actuator_manager.turn_off(name)
            if res and res.get("ok"):
                result["applied"].append(a)
            else:
                result["errors"].append({**a, "error": (res or {}).get("error", "unknown")})
        except Exception as e:
            result["errors"].append({**a, "error": str(e)})

    return result
