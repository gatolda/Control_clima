import RPi.GPIO as GPIO
import time


class ActuatorManager:
    """
    Gestiona los actuadores con validacion de conflictos,
    registro de eventos y proteccion contra oscilacion.
    """

    def __init__(self, config):
        self.relay_pins = config.obtener("actuadores.pines", {})
        self.relay_mode = config.obtener("actuadores.tipo_activacion", "activo_bajo")
        self.conflictos = config.obtener("actuadores.conflictos", [])
        self.ozono_exclusivo = config.obtener("actuadores.ozono_exclusivo", True)
        self.estado = {nombre: False for nombre in self.relay_pins}
        self._last_change = {nombre: 0 for nombre in self.relay_pins}

        print("Inicializando actuadores...")
        for nombre, pin in self.relay_pins.items():
            print(f"  {nombre} -> pin {pin}")
            GPIO.setup(pin, GPIO.OUT)
            # Apagar todo al inicio
            if self.relay_mode == "nc_invertido":
                # Equipos en NC: rele activado (LOW) = equipo apagado
                GPIO.output(pin, GPIO.LOW)
            elif self.relay_mode == "activo_bajo":
                GPIO.output(pin, GPIO.HIGH)
            else:
                GPIO.output(pin, GPIO.LOW)

    def _check_conflict(self, nombre, accion):
        """
        Verifica si activar un actuador genera conflicto.
        Retorna: (permitido, motivo)
        """
        if accion != "on":
            return True, ""

        # Verificar conflictos de pares
        for par in self.conflictos:
            if nombre in par:
                otro = par[0] if par[1] == nombre else par[1]
                if self.estado.get(otro, False):
                    return False, f"Conflicto: {nombre} no puede activarse mientras {otro} esta activo"

        # Verificar ozono exclusivo
        if nombre == "ozono" and self.ozono_exclusivo:
            activos = [n for n, s in self.estado.items() if s and n != "ozono" and n != "luz"]
            if activos:
                return False, f"Ozono requiere que todo este apagado. Activos: {activos}"

        # Si se enciende algo y ozono esta activo, apagar ozono
        if nombre != "ozono" and self.estado.get("ozono", False) and self.ozono_exclusivo:
            self._set_output("ozono", False)
            print(f"Ozono apagado automaticamente al activar {nombre}")

        return True, ""

    def _set_output(self, nombre, estado):
        """Establece el estado fisico de un rele."""
        pin = self.relay_pins[nombre]
        if self.relay_mode == "nc_invertido":
            # Equipos en NC: HIGH = rele desactivado = NC cerrado = equipo ON
            GPIO.output(pin, GPIO.HIGH if estado else GPIO.LOW)
        elif self.relay_mode == "activo_bajo":
            GPIO.output(pin, GPIO.LOW if estado else GPIO.HIGH)
        else:
            GPIO.output(pin, GPIO.HIGH if estado else GPIO.LOW)
        self.estado[nombre] = estado
        self._last_change[nombre] = time.time()

    def turn_on(self, nombre):
        """Enciende un actuador si no hay conflictos."""
        if nombre not in self.relay_pins:
            return {"ok": False, "error": f"Actuador '{nombre}' no existe"}

        permitido, motivo = self._check_conflict(nombre, "on")
        if not permitido:
            print(f"BLOQUEADO: {motivo}")
            return {"ok": False, "error": motivo}

        self._set_output(nombre, True)
        print(f"{nombre} ACTIVADO")
        return {"ok": True}

    def turn_off(self, nombre):
        """Apaga un actuador."""
        if nombre not in self.relay_pins:
            return {"ok": False, "error": f"Actuador '{nombre}' no existe"}

        self._set_output(nombre, False)
        print(f"{nombre} DESACTIVADO")
        return {"ok": True}

    def status(self):
        """Retorna el estado de todos los actuadores."""
        return dict(self.estado)

    def get_last_change(self, nombre):
        """Retorna el timestamp del ultimo cambio de un actuador."""
        return self._last_change.get(nombre, 0)

    def emergency_stop(self):
        """Apaga todos los actuadores inmediatamente."""
        print("PARADA DE EMERGENCIA - apagando todo")
        for nombre in self.relay_pins:
            self._set_output(nombre, False)

    def cleanup(self):
        """Libera GPIO."""
        self.emergency_stop()
        print("GPIO liberado")
