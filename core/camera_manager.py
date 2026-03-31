"""
Gestion de camara y analisis de imagen con IA.
Captura fotos con Pi Camera y las analiza usando Claude Vision.
"""
import threading
import time
import os
import base64
from datetime import datetime

try:
    from picamera2 import Picamera2
except ImportError:
    Picamera2 = None

try:
    import anthropic
except ImportError:
    anthropic = None

CAPTURE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "captures")


class CameraManager:
    """
    Captura imagenes del invernadero y las analiza con Claude Vision.

    Funcionalidades:
    - Captura manual desde dashboard
    - Captura automatica programada
    - Analisis IA de salud de plantas
    - Historial de capturas y analisis
    """

    def __init__(self, config, database):
        self.config = config
        self.db = database
        self.enabled = config.obtener("camara.habilitada", False)
        self.resolution = config.obtener("camara.resolucion", [1920, 1080])
        self.interval_minutes = config.obtener("camara.intervalo_minutos", 60)
        self.api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self._camera = None
        self._running = False
        self._thread = None
        self._last_analysis = None

        os.makedirs(CAPTURE_DIR, exist_ok=True)

        if self.enabled:
            print(f"CameraManager: habilitada, intervalo={self.interval_minutes}min")
        else:
            print("CameraManager: deshabilitada en config")

    def start(self):
        """Inicia captura automatica."""
        if not self.enabled:
            return
        if Picamera2 is None:
            print("CameraManager: picamera2 no disponible")
            return

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        print("CameraManager: captura automatica iniciada")

    def stop(self):
        """Detiene captura automatica."""
        self._running = False
        if self._camera:
            try:
                self._camera.close()
            except Exception:
                pass

    def _init_camera(self):
        """Inicializa la camara."""
        if self._camera is not None:
            return True
        if Picamera2 is None:
            return False
        try:
            self._camera = Picamera2()
            config = self._camera.create_still_configuration(
                main={"size": tuple(self.resolution)}
            )
            self._camera.configure(config)
            self._camera.start()
            time.sleep(2)  # Warm-up
            return True
        except Exception as e:
            print(f"CameraManager: error inicializando camara: {e}")
            self._camera = None
            return False

    def _capture_loop(self):
        """Loop de captura automatica."""
        while self._running:
            try:
                result = self.capture_and_analyze()
                if result.get("ok"):
                    print(f"CameraManager: captura automatica OK")
            except Exception as e:
                print(f"CameraManager: error en captura automatica: {e}")

            time.sleep(self.interval_minutes * 60)

    def capture(self):
        """Captura una foto y la guarda."""
        if not self._init_camera():
            return {"ok": False, "error": "Camara no disponible"}

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"capture_{timestamp}.jpg"
        filepath = os.path.join(CAPTURE_DIR, filename)

        try:
            self._camera.capture_file(filepath)
            print(f"CameraManager: foto guardada en {filepath}")
            return {
                "ok": True,
                "filepath": filepath,
                "filename": filename,
                "timestamp": timestamp
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def analyze_image(self, filepath):
        """Analiza una imagen con Claude Vision."""
        if not anthropic:
            return {"ok": False, "error": "anthropic SDK no instalado"}
        if not self.api_key:
            return {"ok": False, "error": "ANTHROPIC_API_KEY no configurada"}

        try:
            with open(filepath, "rb") as f:
                image_data = base64.standard_b64encode(f.read()).decode("utf-8")

            client = anthropic.Anthropic(api_key=self.api_key)
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_data
                            }
                        },
                        {
                            "type": "text",
                            "text": (
                                "Analiza esta imagen de un invernadero de cultivo. "
                                "Evalua:\n"
                                "1. **Salud general de las plantas** (1-10)\n"
                                "2. **Color del follaje** - verde saludable, amarillamiento, manchas\n"
                                "3. **Signos de plagas o enfermedades** - insectos, hongos, moho\n"
                                "4. **Estado del sustrato** - humedad visible, sequedad\n"
                                "5. **Problemas detectados** - deficiencias nutricionales, estres\n"
                                "6. **Recomendaciones** - acciones sugeridas\n\n"
                                "Responde en formato JSON con estas claves: "
                                "salud_general (1-10), color_follaje, plagas, "
                                "estado_sustrato, problemas, recomendaciones"
                            )
                        }
                    ]
                }]
            )

            analysis_text = response.content[0].text
            self._last_analysis = {
                "timestamp": datetime.now().isoformat(),
                "filepath": filepath,
                "analysis": analysis_text
            }

            return {"ok": True, "analysis": analysis_text}

        except Exception as e:
            return {"ok": False, "error": str(e)}

    def capture_and_analyze(self):
        """Captura y analiza en un solo paso."""
        capture = self.capture()
        if not capture.get("ok"):
            return capture

        analysis = self.analyze_image(capture["filepath"])
        if analysis.get("ok"):
            # Guardar en DB
            self.db.save_camera_event(
                filename=capture["filename"],
                analysis=analysis["analysis"]
            )

        return {
            "ok": True,
            "capture": capture,
            "analysis": analysis.get("analysis", ""),
            "error": analysis.get("error")
        }

    def get_latest_analysis(self):
        """Retorna el ultimo analisis."""
        return self._last_analysis

    def get_captures(self, limit=20):
        """Lista las capturas guardadas."""
        try:
            files = sorted(os.listdir(CAPTURE_DIR), reverse=True)[:limit]
            return [
                {
                    "filename": f,
                    "path": os.path.join(CAPTURE_DIR, f),
                    "timestamp": f.replace("capture_", "").replace(".jpg", "")
                }
                for f in files if f.endswith(".jpg")
            ]
        except Exception:
            return []

    def get_status(self):
        """Estado de la camara."""
        return {
            "enabled": self.enabled,
            "camera_available": Picamera2 is not None,
            "api_configured": bool(self.api_key),
            "captures_count": len(self.get_captures(limit=1000)),
            "last_analysis": self._last_analysis
        }
