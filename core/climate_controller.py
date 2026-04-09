"""
Controlador climatico automatico para cultivo indoor.
Lee sensores, compara contra umbrales de la etapa actual,
y activa/desactiva actuadores siguiendo escalamiento energetico.

Logica principal:
1. Lee temperatura, humedad, CO2, VPD, humedad suelo
2. Compara contra STAGE_THRESHOLDS de la etapa configurada
3. Usa histeresis para evitar oscilacion
4. Respeta conflictos de actuadores
5. Controla fotoperiodo (luz on/off segun etapa)
6. Registra todas las acciones como "auto" en la base de datos
"""
import threading
import time
import math
from datetime import datetime
from data.models import STAGE_THRESHOLDS, STAGE_ORDER


class ClimateController:
    """
    Motor de control automatico. Corre en un thread que evalua
    condiciones cada N segundos y toma decisiones de actuacion.
    """

    def __init__(self, config, sensor_reader, actuator_manager, database):
        self.config = config
        self.sensor_reader = sensor_reader
        self.actuators = actuator_manager
        self.db = database

        # Histeresis desde config.yml
        histeresis = config.obtener("histeresis", {})
        self.hist_temp = histeresis.get("temperatura", 1.5)
        self.hist_hum = histeresis.get("humedad", 5.0)
        self.hist_co2 = histeresis.get("co2", 50)
        self.min_time = histeresis.get("tiempo_minimo", 180)

        # Escalamiento desde config.yml
        self.escalamiento = config.obtener("escalamiento", {})

        self._running = False
        self._thread = None
        self._eval_interval = 10  # segundos entre evaluaciones
        self._last_decisions = {}  # cache de ultimas decisiones para logging
        self._light_state = None  # tracking de estado de luz

    def start(self):
        """Inicia el controlador si el modo es 'auto'."""
        mode = self.db.get_config("mode", "manual")
        if mode != "auto":
            print("ClimateController: modo manual, no inicia")
            return

        self._running = True
        self._thread = threading.Thread(target=self._control_loop, daemon=True)
        self._thread.start()
        print("ClimateController: INICIADO en modo automatico")

    def stop(self):
        """Detiene el controlador."""
        self._running = False
        print("ClimateController: detenido")

    def set_mode(self, mode):
        """Cambia entre auto/manual. Retorna True si cambio exitoso."""
        self.db.set_config("mode", mode)
        if mode == "auto" and not self._running:
            self.start()
        elif mode == "manual" and self._running:
            self._running = False
            print("ClimateController: cambiado a manual, deteniendo control auto")
        return True

    def is_running(self):
        return self._running

    def get_current_stage(self):
        """Retorna la etapa actual y sus umbrales."""
        stage = self.db.get_config("stage", "vegetativo_temprano")
        thresholds = STAGE_THRESHOLDS.get(stage, STAGE_THRESHOLDS["vegetativo_temprano"])
        return stage, thresholds

    def set_stage(self, stage):
        """Cambia la etapa de cultivo."""
        if stage not in STAGE_THRESHOLDS:
            return {"ok": False, "error": f"Etapa '{stage}' no existe"}
        self.db.set_config("stage", stage)
        # Actualizar horario de luz segun etapa
        thresholds = STAGE_THRESHOLDS[stage]
        light_on = int(self.db.get_config("light_on_hour", "6"))
        light_off_hour = (light_on + thresholds["light_hours"]) % 24
        self.db.set_config("light_off_hour", str(light_off_hour))
        print(f"ClimateController: etapa cambiada a '{stage}'")
        return {"ok": True, "stage": stage, "thresholds": thresholds}

    def get_next_stage(self):
        """Retorna la siguiente etapa en la progresion."""
        current = self.db.get_config("stage", "vegetativo_temprano")
        if current in STAGE_ORDER:
            idx = STAGE_ORDER.index(current)
            if idx < len(STAGE_ORDER) - 1:
                return STAGE_ORDER[idx + 1]
        return None

    def get_status(self):
        """Estado completo del controlador para el dashboard."""
        stage, thresholds = self.get_current_stage()
        mode = self.db.get_config("mode", "manual")
        return {
            "mode": mode,
            "running": self._running,
            "stage": stage,
            "stage_info": thresholds.get("descripcion", ""),
            "thresholds": thresholds,
            "next_stage": self.get_next_stage(),
            "stages": list(STAGE_THRESHOLDS.keys()),
            "last_decisions": self._last_decisions,
            "light_on_hour": int(self.db.get_config("light_on_hour", "6")),
            "light_hours": thresholds.get("light_hours", 18),
        }

    # === LOOP PRINCIPAL ===

    def _control_loop(self):
        """Loop de control: lee sensores y toma decisiones."""
        print("ClimateController: loop de control iniciado")
        while self._running:
            try:
                # Verificar que seguimos en modo auto
                mode = self.db.get_config("mode", "manual")
                if mode != "auto":
                    self._running = False
                    print("ClimateController: modo cambiado a manual, deteniendo")
                    break

                stage, thresholds = self.get_current_stage()
                readings = self._read_all_sensors()

                if readings["temperature"] is not None:
                    decisions = self._evaluate(readings, thresholds)
                    self._execute(decisions)
                    self._last_decisions = decisions

                # Control de fotoperiodo
                self._control_light(thresholds)

                # Filtro de carbon: obligatorio desde pre-floracion hasta secado
                self._control_carbon_filter(stage)

            except Exception as e:
                print(f"ClimateController error: {e}")

            time.sleep(self._eval_interval)

    def _read_all_sensors(self):
        """Lee todos los sensores y retorna valores consolidados."""
        data = self.sensor_reader.read_all()
        temp = data.get("temperatura_humedad", {}).get("temperature")
        hum = data.get("temperatura_humedad", {}).get("humidity")
        co2 = data.get("co2", {}).get("co2")

        # Filtrar lecturas erraticas
        if temp is not None and (temp <= 0 or temp > 80):
            temp = None
        if hum is not None and (hum <= 0 or hum > 100):
            hum = None
        if co2 is not None and (co2 <= 0 or co2 > 5000):
            co2 = None

        vpd = self._calculate_vpd(temp, hum)

        # Humedad suelo
        soil_hum = None
        try:
            zone_data = self.sensor_reader.read_zone_data()
            for zone_id, readings in zone_data.items():
                if "humedad_suelo" in readings:
                    soil_hum = readings["humedad_suelo"]
                    break
        except Exception:
            pass

        return {
            "temperature": temp,
            "humidity": hum,
            "co2": co2,
            "vpd": vpd,
            "soil_humidity": soil_hum,
        }

    def _calculate_vpd(self, temp, hum):
        """Calcula VPD en kPa."""
        if temp is None or hum is None:
            return None
        try:
            svp = 0.6108 * math.exp((17.27 * temp) / (temp + 237.3))
            return round(svp * (1 - hum / 100.0), 2)
        except (ValueError, ZeroDivisionError):
            return None

    def _is_night(self):
        """Determina si es periodo nocturno segun fotoperiodo."""
        now = datetime.now().hour
        light_on = int(self.db.get_config("light_on_hour", "6"))
        stage, thresholds = self.get_current_stage()
        light_hours = thresholds.get("light_hours", 18)

        if light_hours == 0:
            return True  # secado/curado = siempre oscuro
        if light_hours == 24:
            return False

        light_off = (light_on + light_hours) % 24
        if light_on < light_off:
            return not (light_on <= now < light_off)
        else:  # cruza medianoche
            return light_off <= now < light_on

    # === EVALUACION ===

    def _evaluate(self, readings, thresholds):
        """
        Evalua las lecturas contra los umbrales y genera decisiones.
        Retorna dict con acciones recomendadas por cada variable.
        """
        decisions = {
            "temperature": {"action": "ok", "detail": ""},
            "humidity": {"action": "ok", "detail": ""},
            "co2": {"action": "ok", "detail": ""},
        }
        temp = readings["temperature"]
        hum = readings["humidity"]
        co2 = readings["co2"]
        is_night = self._is_night()

        # --- TEMPERATURA ---
        if temp is not None:
            if is_night:
                t_min = thresholds.get("temp_night_min", thresholds["temp_min"] - 4)
                t_max = thresholds.get("temp_night_max", thresholds["temp_max"] - 4)
            else:
                t_min = thresholds["temp_min"]
                t_max = thresholds["temp_max"]

            if temp > t_max + self.hist_temp:
                decisions["temperature"] = {
                    "action": "cool",
                    "detail": f"Temp {temp}°C > {t_max}°C (+hist {self.hist_temp})",
                    "severity": min((temp - t_max) / 5.0, 1.0),
                }
            elif temp < t_min - self.hist_temp:
                decisions["temperature"] = {
                    "action": "heat",
                    "detail": f"Temp {temp}°C < {t_min}°C (-hist {self.hist_temp})",
                    "severity": min((t_min - temp) / 5.0, 1.0),
                }
            elif t_min <= temp <= t_max:
                # Dentro de rango optimo - apagar climatizacion
                decisions["temperature"] = {
                    "action": "ok",
                    "detail": f"Temp {temp}°C OK [{t_min}-{t_max}]",
                }

        # --- HUMEDAD ---
        if hum is not None:
            h_min = thresholds["hum_min"]
            h_max = thresholds["hum_max"]

            if hum > h_max + self.hist_hum:
                decisions["humidity"] = {
                    "action": "dehumidify",
                    "detail": f"Hum {hum}% > {h_max}% (+hist {self.hist_hum})",
                    "severity": min((hum - h_max) / 20.0, 1.0),
                }
            elif hum < h_min - self.hist_hum:
                decisions["humidity"] = {
                    "action": "humidify",
                    "detail": f"Hum {hum}% < {h_min}% (-hist {self.hist_hum})",
                    "severity": min((h_min - hum) / 20.0, 1.0),
                }
            elif h_min <= hum <= h_max:
                decisions["humidity"] = {
                    "action": "ok",
                    "detail": f"Hum {hum}% OK [{h_min}-{h_max}]",
                }

        # --- CO2 ---
        # CO2 solo se controla con luces encendidas (plantas no fotosintetizan en oscuridad)
        if co2 is not None:
            c_min = thresholds["co2_min"]
            c_max = thresholds["co2_max"]

            if co2 > c_max + self.hist_co2:
                decisions["co2"] = {
                    "action": "ventilate",
                    "detail": f"CO2 {co2}ppm > {c_max}ppm (+hist {self.hist_co2})",
                    "severity": min((co2 - c_max) / 500.0, 1.0),
                }
            elif c_min <= co2 <= c_max:
                decisions["co2"] = {
                    "action": "ok",
                    "detail": f"CO2 {co2}ppm OK [{c_min}-{c_max}]",
                }

        return decisions

    # === EJECUCION ===

    def _execute(self, decisions):
        """
        Ejecuta las decisiones activando/desactivando actuadores
        siguiendo el escalamiento energetico de config.yml
        """
        temp_action = decisions["temperature"]["action"]
        hum_action = decisions["humidity"]["action"]
        co2_action = decisions["co2"]["action"]

        # --- Temperatura alta: ventiladores -> intractor -> AC ---
        if temp_action == "cool":
            self._escalate("temperatura_alta", decisions["temperature"])
        elif temp_action == "ok":
            self._deescalate("temperatura_alta")

        # --- Temperatura baja: calefactor ---
        if temp_action == "heat":
            self._escalate("temperatura_baja", decisions["temperature"])
        elif temp_action == "ok":
            self._deescalate("temperatura_baja")

        # --- Humedad alta: ventiladores -> intractor -> deshumidificador ---
        if hum_action == "dehumidify":
            self._escalate("humedad_alta", decisions["humidity"])
        elif hum_action == "ok":
            self._deescalate("humedad_alta")

        # --- Humedad baja: humidificador ---
        if hum_action == "humidify":
            self._escalate("humedad_baja", decisions["humidity"])
        elif hum_action == "ok":
            self._deescalate("humedad_baja")

        # --- CO2 alto: ventiladores -> intractor ---
        if co2_action == "ventilate":
            self._escalate("co2_alto", decisions["co2"])
        elif co2_action == "ok":
            self._deescalate("co2_alto")

    def _escalate(self, scenario, decision):
        """
        Activa actuadores en orden de escalamiento.
        La severidad determina cuantos escalar.
        """
        actuadores = self.escalamiento.get(scenario, [])
        if not actuadores:
            return

        severity = decision.get("severity", 0.5)

        # Cuantos actuadores activar segun severidad
        # severity 0-0.3 = solo el primero, 0.3-0.6 = dos, 0.6+ = todos
        if severity < 0.3:
            n_activate = 1
        elif severity < 0.6:
            n_activate = min(2, len(actuadores))
        else:
            n_activate = len(actuadores)

        for i, nombre in enumerate(actuadores):
            if i < n_activate:
                if not self.actuators.estado.get(nombre, False):
                    if self._check_min_time(nombre):
                        result = self.actuators.turn_on(nombre)
                        if result.get("ok"):
                            self.db.log_actuator_event(nombre, "on", triggered_by="auto")
                            print(f"AUTO: {nombre} ON ({scenario}, sev={severity:.1f})")
            else:
                # Los de menor prioridad se apagan si no necesarios
                if self.actuators.estado.get(nombre, False):
                    last_by = self._get_last_trigger(nombre)
                    if last_by == "auto" and self._check_min_time(nombre):
                        self.actuators.turn_off(nombre)
                        self.db.log_actuator_event(nombre, "off", triggered_by="auto")
                        print(f"AUTO: {nombre} OFF (desescalado {scenario})")

    def _deescalate(self, scenario):
        """Apaga actuadores de un escenario cuando ya no se necesitan."""
        actuadores = self.escalamiento.get(scenario, [])
        for nombre in actuadores:
            if self.actuators.estado.get(nombre, False):
                last_by = self._get_last_trigger(nombre)
                # Solo apagar los que fueron encendidos por auto
                if last_by == "auto" and self._check_min_time(nombre):
                    # Verificar que ningun otro escenario necesita este actuador
                    if not self._is_needed_elsewhere(nombre, scenario):
                        self.actuators.turn_off(nombre)
                        self.db.log_actuator_event(nombre, "off", triggered_by="auto")
                        print(f"AUTO: {nombre} OFF (ok en {scenario})")

    def _is_needed_elsewhere(self, nombre, current_scenario):
        """Verifica si un actuador es necesario por otro escenario activo."""
        for scenario, actuadores in self.escalamiento.items():
            if scenario == current_scenario:
                continue
            if nombre in actuadores:
                # Verificar si este escenario tiene una decision activa
                decision = self._last_decisions.get(self._scenario_to_var(scenario), {})
                if decision.get("action") not in ("ok", ""):
                    return True
        return False

    def _scenario_to_var(self, scenario):
        """Mapea nombre de escenario a variable de decision."""
        mapping = {
            "temperatura_alta": "temperature",
            "temperatura_baja": "temperature",
            "humedad_alta": "humidity",
            "humedad_baja": "humidity",
            "co2_alto": "co2",
        }
        return mapping.get(scenario, "")

    def _check_min_time(self, nombre):
        """Verifica que ha pasado el tiempo minimo desde ultimo cambio."""
        last = self.actuators.get_last_change(nombre)
        if last == 0:
            return True
        return (time.time() - last) >= self.min_time

    def _get_last_trigger(self, nombre):
        """Obtiene quien activo por ultima vez un actuador."""
        conn = self.db._get_conn()
        row = conn.execute(
            """SELECT triggered_by FROM actuator_events
               WHERE actuator = ? ORDER BY id DESC LIMIT 1""",
            (nombre,)
        ).fetchone()
        conn.close()
        return row["triggered_by"] if row else "manual"

    # === CONTROL DE LUZ ===

    def _control_carbon_filter(self, stage):
        """Activa filtro de carbon automaticamente en etapas con olor."""
        smell_stages = {"pre_floracion", "floracion", "floracion_tardia", "secado"}
        should_filter = stage in smell_stages
        current = self.actuators.estado.get("filtro_carbon", False)

        if should_filter and not current:
            result = self.actuators.turn_on("filtro_carbon")
            if result.get("ok"):
                self.db.log_actuator_event("filtro_carbon", "on", triggered_by="auto")
                print(f"AUTO: filtro_carbon ON (etapa {stage} - control de olor)")
        elif not should_filter and current:
            last_by = self._get_last_trigger("filtro_carbon")
            if last_by == "auto":
                self.actuators.turn_off("filtro_carbon")
                self.db.log_actuator_event("filtro_carbon", "off", triggered_by="auto")
                print(f"AUTO: filtro_carbon OFF (etapa {stage} - sin olor)")

    def _control_light(self, thresholds):
        """Controla el fotoperiodo segun la etapa."""
        light_hours = thresholds.get("light_hours", 18)
        should_be_on = not self._is_night()

        # Secado y curado: luz siempre apagada
        if light_hours == 0:
            should_be_on = False

        current_state = self.actuators.estado.get("luz", False)

        if should_be_on and not current_state:
            result = self.actuators.turn_on("luz")
            if result.get("ok"):
                self.db.log_actuator_event("luz", "on", triggered_by="auto")
                print(f"AUTO: luz ON (fotoperiodo {light_hours}h)")
                self._light_state = True
        elif not should_be_on and current_state:
            last_by = self._get_last_trigger("luz")
            if last_by == "auto":
                self.actuators.turn_off("luz")
                self.db.log_actuator_event("luz", "off", triggered_by="auto")
                print(f"AUTO: luz OFF (periodo oscuro)")
                self._light_state = False
