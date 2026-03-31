"""
Sistema de riego inteligente.
Combina programacion horaria con lectura de sensores de suelo.
"""
import threading
import time
from datetime import datetime, timedelta


class IrrigationManager:
    """
    Gestiona el riego por zonas con logica:
    1. Programacion horaria (ej: 08:00, 14:00, 20:00)
    2. Verificacion de humedad del suelo antes de regar
    3. Si humedad >= umbral_skip -> salta el riego
    4. Si humedad < umbral_minima -> riega duracion configurada
    5. Limite de seguridad de duracion maxima
    """

    def __init__(self, config, sensor_reader, actuator_manager, database):
        self.config = config
        self.sensor_reader = sensor_reader
        self.actuator_manager = actuator_manager
        self.db = database

        self.enabled = config.obtener("riego.habilitado", False)
        self.zones = config.obtener("riego.zonas", [])
        self._active = {}         # zone_id -> {"start": datetime, "end": datetime}
        self._last_check = {}     # zone_id -> {hora -> datetime del ultimo chequeo}
        self._lock = threading.Lock()
        self._running = False
        self._thread = None

        if self.zones:
            print(f"IrrigationManager: {len(self.zones)} zonas configuradas")
        else:
            print("IrrigationManager: sin zonas configuradas")

    def start(self):
        """Inicia el scheduler de riego."""
        if not self.enabled:
            print("IrrigationManager: deshabilitado en config")
            return
        if not self.zones:
            print("IrrigationManager: sin zonas, no inicia scheduler")
            return

        self._running = True
        self._thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._thread.start()
        print("IrrigationManager: scheduler iniciado")

    def stop(self):
        """Detiene el scheduler y cierra todas las valvulas."""
        self._running = False
        self.emergency_stop()

    def _scheduler_loop(self):
        """Loop principal: revisa cada 30 segundos si hay riego programado."""
        while self._running:
            try:
                now = datetime.now()
                self._check_schedules(now)
                self._check_active_irrigations(now)
            except Exception as e:
                print(f"IrrigationManager error: {e}")
            time.sleep(30)

    def _check_schedules(self, now):
        """Verifica si alguna zona necesita riego segun su programacion."""
        current_time = now.strftime("%H:%M")

        for zone in self.zones:
            zone_id = zone["id"]
            programacion = zone.get("programacion", [])

            for schedule in programacion:
                hora = schedule["hora"]
                # Solo activar si estamos en el minuto correcto
                if current_time != hora:
                    continue
                # Evitar activar mas de una vez por horario
                key = f"{zone_id}_{hora}"
                last = self._last_check.get(key)
                if last and (now - last).total_seconds() < 120:
                    continue
                self._last_check[key] = now

                # Ya esta regando esta zona?
                with self._lock:
                    if zone_id in self._active:
                        continue

                duracion = schedule.get("duracion_minutos", 5)
                self._evaluate_and_irrigate(zone, duracion)

    def _check_active_irrigations(self, now):
        """Verifica si alguna irrigacion activa debe terminar."""
        with self._lock:
            finished = []
            for zone_id, info in self._active.items():
                if now >= info["end"]:
                    finished.append(zone_id)

        for zone_id in finished:
            self.close_valve(zone_id, reason="completed")

    def _evaluate_and_irrigate(self, zone, duracion_minutos):
        """
        Logica de decision:
        1. Leer humedad del suelo
        2. Si humedad >= skip_threshold -> saltar
        3. Si no -> regar
        """
        zone_id = zone["id"]
        umbrales = zone.get("umbrales", {})
        skip_threshold = umbrales.get("humedad_skip", 65)
        duracion_max = umbrales.get("duracion_maxima_minutos", 15)

        # Limitar duracion al maximo de seguridad
        duracion_minutos = min(duracion_minutos, duracion_max)

        # Leer humedad del suelo
        soil_humidity = self._read_zone_humidity(zone)
        soil_ph = self._read_zone_ph(zone)

        # Decision
        if soil_humidity is not None and soil_humidity >= skip_threshold:
            print(f"Riego SALTADO zona {zone_id}: humedad={soil_humidity}% >= {skip_threshold}%")
            self.db.log_irrigation_event(
                zone_id=zone_id,
                action="skipped",
                soil_humidity=soil_humidity,
                soil_ph=soil_ph,
                reason=f"humedad {soil_humidity}% >= umbral {skip_threshold}%",
                triggered_by="scheduler"
            )
            return

        # Regar
        self.open_valve(zone_id, duracion_minutos, soil_humidity, soil_ph, "scheduler")

    def _read_zone_humidity(self, zone):
        """Lee la humedad del suelo para una zona."""
        sensor_ids = zone.get("sensores_humedad", [])
        if not sensor_ids:
            sensor_id = zone.get("sensor_humedad")
            if sensor_id:
                sensor_ids = [sensor_id]

        if not sensor_ids:
            return None

        # Leer desde el sensor_reader (Arduino hub)
        values = []
        for sid in sensor_ids:
            try:
                zone_data = self.sensor_reader.read_zone_data()
                for z, readings in zone_data.items():
                    for var, val in readings.items():
                        if var == "humedad_suelo" and val is not None:
                            values.append(val)
            except Exception:
                pass

        if not values:
            # Intentar leer directo del Arduino hub
            hub = self.sensor_reader.get_arduino_hub()
            if hub:
                for sid in sensor_ids:
                    val = hub.get_reading(sid)
                    if val is not None:
                        values.append(val)

        if not values:
            return None

        import statistics
        return round(statistics.median(values), 1)

    def _read_zone_ph(self, zone):
        """Lee el pH del suelo para una zona."""
        sensor_id = zone.get("sensor_ph")
        if not sensor_id:
            return None

        hub = self.sensor_reader.get_arduino_hub()
        if hub:
            return hub.get_reading(sensor_id)
        return None

    def open_valve(self, zone_id, duracion_minutos=5, soil_humidity=None,
                   soil_ph=None, triggered_by="manual"):
        """Abre la valvula de una zona."""
        zone = self._get_zone(zone_id)
        if not zone:
            return {"ok": False, "error": f"Zona '{zone_id}' no existe"}

        valvula = zone.get("valvula")
        if not valvula:
            return {"ok": False, "error": f"Zona '{zone_id}' sin valvula configurada"}

        # Limitar duracion maxima
        duracion_max = zone.get("umbrales", {}).get("duracion_maxima_minutos", 15)
        duracion_minutos = min(duracion_minutos, duracion_max)

        result = self.actuator_manager.turn_on(valvula)
        if not result.get("ok"):
            return result

        now = datetime.now()
        end = now + timedelta(minutes=duracion_minutos)

        with self._lock:
            self._active[zone_id] = {
                "start": now,
                "end": end,
                "valvula": valvula,
                "duracion_minutos": duracion_minutos
            }

        print(f"Riego INICIADO zona {zone_id}: {duracion_minutos} min (hasta {end.strftime('%H:%M')})")

        self.db.log_irrigation_event(
            zone_id=zone_id,
            action="started",
            duration_seconds=duracion_minutos * 60,
            soil_humidity=soil_humidity,
            soil_ph=soil_ph,
            reason="scheduled" if triggered_by == "scheduler" else "manual",
            triggered_by=triggered_by
        )
        return {"ok": True, "end": end.isoformat()}

    def close_valve(self, zone_id, reason="manual"):
        """Cierra la valvula de una zona."""
        with self._lock:
            info = self._active.pop(zone_id, None)

        if info:
            self.actuator_manager.turn_off(info["valvula"])
            duration = (datetime.now() - info["start"]).total_seconds()
            print(f"Riego FINALIZADO zona {zone_id}: {reason} ({int(duration)}s)")
            self.db.log_irrigation_event(
                zone_id=zone_id,
                action=reason,
                duration_seconds=int(duration),
                triggered_by="system"
            )
        return {"ok": True}

    def emergency_stop(self):
        """Cierra todas las valvulas inmediatamente."""
        with self._lock:
            active_zones = list(self._active.keys())
        for zone_id in active_zones:
            self.close_valve(zone_id, reason="emergency_stop")
        print("IrrigationManager: emergency stop")

    def manual_irrigate(self, zone_id, duracion_minutos=5):
        """Riego manual desde dashboard."""
        zone = self._get_zone(zone_id)
        if not zone:
            return {"ok": False, "error": f"Zona '{zone_id}' no existe"}

        soil_humidity = self._read_zone_humidity(zone)
        soil_ph = self._read_zone_ph(zone)
        return self.open_valve(zone_id, duracion_minutos, soil_humidity, soil_ph, "manual")

    def get_status(self):
        """Estado actual de todas las zonas."""
        with self._lock:
            active_copy = dict(self._active)

        status = {}
        for zone in self.zones:
            zid = zone["id"]
            if zid in active_copy:
                info = active_copy[zid]
                remaining = (info["end"] - datetime.now()).total_seconds()
                status[zid] = {
                    "state": "irrigating",
                    "remaining_seconds": max(0, int(remaining)),
                    "started": info["start"].isoformat(),
                    "ends": info["end"].isoformat()
                }
            else:
                status[zid] = {
                    "state": "idle",
                    "next": self._next_schedule(zone)
                }
        return status

    def _next_schedule(self, zone):
        """Calcula el proximo riego programado para una zona."""
        now = datetime.now()
        current_minutes = now.hour * 60 + now.minute
        schedules = zone.get("programacion", [])

        next_time = None
        for s in schedules:
            h, m = map(int, s["hora"].split(":"))
            sched_minutes = h * 60 + m
            if sched_minutes > current_minutes:
                next_time = s["hora"]
                break

        if next_time is None and schedules:
            next_time = schedules[0]["hora"] + " (manana)"

        return next_time

    def get_zones(self):
        """Retorna info de zonas para el dashboard."""
        return [
            {
                "id": z["id"],
                "nombre": z.get("nombre", z["id"]),
                "valvula": z.get("valvula", ""),
                "plantas": z.get("plantas", []),
                "programacion": z.get("programacion", []),
                "umbrales": z.get("umbrales", {})
            }
            for z in self.zones
        ]

    def _get_zone(self, zone_id):
        """Busca una zona por ID."""
        for z in self.zones:
            if z["id"] == zone_id:
                return z
        return None
