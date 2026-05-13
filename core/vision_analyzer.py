"""
Analisis de imagenes del cultivo via Claude Vision (Opus 4.7).

Toma una foto del invernadero (path local) y devuelve un analisis estructurado
en JSON: salud, color, plagas, deficiencias, sustrato, vigor, recomendaciones.

Usa:
  - claude-opus-4-7 (top-tier vision, alta resolucion automatica)
  - adaptive thinking, effort=medium (balance cost/quality)
  - prompt caching sobre el system prompt (~90% ahorro tras la 1a llamada)
  - structured outputs via output_config.format (respuesta validada por schema)

Costos aproximados por imagen (Opus 4.7, ~5MP@2576px):
  ~$0.02-0.04 con caching activo, ~$0.05 sin caching.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path

try:
    import anthropic
except ImportError:
    anthropic = None


MODEL = "claude-opus-4-7"

# System prompt — estable, cacheable. Cualquier byte que cambie aca invalida el cache.
SYSTEM_PROMPT = """Sos un experto en horticultura indoor y diagnostico visual de cultivos de cannabis y plantas similares. Tu tarea es analizar fotos del interior de una carpa/invernadero y devolver un diagnostico breve y accionable.

Tene en cuenta:
- Las plantas estan bajo luz LED de cultivo (puede dar tinte purpura/rosado a la foto, eso es normal).
- El sustrato suele ser tierra, coco o hidroponico.
- Si la imagen esta muy oscura, borrosa, o no se ven plantas, indicalo en `observaciones` y bajá `confianza` a 1-3.
- Sé conciso pero util. Cada item de `recomendaciones` debe ser una accion concreta que el cultivador pueda hacer.
- `salud_general` 8-10 = plantas vigorosas y sin issues. 5-7 = leves problemas. 3-4 = problemas claros. 1-2 = critico.
- En `signos_plagas` y `signos_deficiencias`: si no detectas nada, usá `detectado: false` y `descripcion: null`.

Respondé SIEMPRE en JSON valido conforme al schema dado. No agregues texto fuera del JSON."""

# Schema de salida — Claude se asegura de que la respuesta lo cumpla.
ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "salud_general":    {"type": "integer",
                             "description": "Salud global, entero entre 1 y 10. 8-10 vigorosa, 5-7 leves problemas, 3-4 problemas claros, 1-2 critico."},
        "color_follaje":    {"type": "string",
                             "description": "Descripcion breve del color de las hojas (ej: 'verde intenso uniforme', 'amarillamiento leve en hojas bajas')."},
        "vigor":            {"type": "string", "enum": ["alto", "medio", "bajo", "indeterminable"],
                             "description": "Vigor general visible."},
        "estado_sustrato":  {"type": "string",
                             "description": "Que se ve del sustrato (humedo/seco/no_visible y comentarios)."},
        "signos_plagas":    {
            "type": "object",
            "properties": {
                "detectado":  {"type": "boolean"},
                "descripcion": {"type": ["string", "null"]}
            },
            "required": ["detectado", "descripcion"],
            "additionalProperties": False
        },
        "signos_deficiencias": {
            "type": "object",
            "properties": {
                "detectado":  {"type": "boolean"},
                "descripcion": {"type": ["string", "null"]}
            },
            "required": ["detectado", "descripcion"],
            "additionalProperties": False
        },
        "etapa_estimada":   {"type": "string", "enum": ["plantula", "vegetativo", "prefloracion", "floracion", "indeterminable"],
                             "description": "Etapa de cultivo aparente."},
        "recomendaciones":  {"type": "array", "items": {"type": "string"},
                             "description": "Lista de 0-5 acciones concretas. Vacio si todo OK."},
        "observaciones":    {"type": "string",
                             "description": "Cualquier nota adicional (calidad de foto, contexto, dudas)."},
        "confianza":        {"type": "integer",
                             "description": "Que tan seguro estas del diagnostico, entero entre 1 y 10. Bajo si foto borrosa/oscura/sin plantas."}
    },
    "required": [
        "salud_general", "color_follaje", "vigor", "estado_sustrato",
        "signos_plagas", "signos_deficiencias", "etapa_estimada",
        "recomendaciones", "observaciones", "confianza"
    ],
    "additionalProperties": False
}


_client: "anthropic.Anthropic | None" = None


def _get_client() -> "anthropic.Anthropic":
    """Cliente lazy, usa ANTHROPIC_API_KEY del env."""
    global _client
    if _client is None:
        if anthropic is None:
            raise RuntimeError("anthropic SDK no instalado. `pip install anthropic`")
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY no esta en el entorno (.env)")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def analyze_image(image_path: str | Path, extra_context: str | None = None) -> dict:
    """Analiza una imagen del invernadero y devuelve dict estructurado.

    Args:
        image_path: path local a la imagen .jpg/.png
        extra_context: contexto opcional ("etapa: floracion semana 3", "alerta:
                       el sistema reporto humedad baja hace 2h"...). Va al user
                       turn — NO al system prompt — para no romper el cache.

    Returns:
        dict con el shape de ANALYSIS_SCHEMA + metadata `_usage` y `_cached`.

    Raises:
        FileNotFoundError, RuntimeError (config), anthropic.APIError (API).
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Imagen no existe: {path}")

    media_type = "image/jpeg" if path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    with open(path, "rb") as f:
        image_b64 = base64.standard_b64encode(f.read()).decode("utf-8")

    client = _get_client()

    user_text = "Analiza esta foto del cultivo y devolveme el diagnostico en JSON conforme al schema."
    if extra_context:
        user_text += f"\n\nContexto adicional:\n{extra_context}"

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        # Adaptive thinking + effort=medium: balance cost/quality. Para fotos
        # rutinarias del cultivo no necesitamos "max"; las fotos no son ambiguas.
        thinking={"type": "adaptive"},
        output_config={
            "effort": "medium",
            "format": {"type": "json_schema", "schema": ANALYSIS_SCHEMA},
        },
        # Cache el system prompt — se repite identico en cada llamada.
        # ~90% ahorro a partir de la 2a llamada dentro de la ventana de 5min.
        system=[{
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": image_b64,
                }},
                {"type": "text", "text": user_text},
            ],
        }],
    )

    # output_config.format garantiza que el primer block de texto es JSON valido.
    text = next((b.text for b in response.content if b.type == "text"), None)
    if not text:
        raise RuntimeError(f"Respuesta sin bloque de texto. stop_reason={response.stop_reason}")

    analysis = json.loads(text)
    analysis["_usage"] = {
        "input_tokens":              response.usage.input_tokens,
        "output_tokens":             response.usage.output_tokens,
        "cache_read_input_tokens":   getattr(response.usage, "cache_read_input_tokens", 0),
        "cache_creation_input_tokens": getattr(response.usage, "cache_creation_input_tokens", 0),
    }
    analysis["_model"] = response.model
    analysis["_stop_reason"] = response.stop_reason
    return analysis
