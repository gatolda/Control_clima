# Test Cases - Control de Reles (TC-REL)

## TC-REL-001: Activar rele individual (P0)
**Prerequisitos:** App corriendo, todos los reles apagados
**Pasos:**
1. Desde dashboard, activar "ventiladores"
2. Verificar que el LED del rele 1 (pin 37) se enciende
3. Verificar que GPIO.LOW se establece en pin 37
4. Verificar que el dashboard muestra estado ON
**Resultado esperado:** Rele activado, dashboard sincronizado, evento registrado en DB

## TC-REL-002: Desactivar rele individual (P0)
**Prerequisitos:** Rele "ventiladores" activo
**Pasos:**
1. Desde dashboard, desactivar "ventiladores"
2. Verificar que el LED del rele 1 se apaga
3. Verificar que GPIO.HIGH se establece en pin 37
4. Verificar que el dashboard muestra estado OFF
**Resultado esperado:** Rele desactivado, dashboard sincronizado

## TC-REL-003: Verificar logica activo_bajo en todos los pines (P0)
**Prerequisitos:** App detenida
**Pasos:**
1. Ejecutar test_relay.py en modo secuencia
2. Para cada rele (1-8), verificar: LOW=ON, HIGH=OFF
3. Verificar que todos los pines responden correctamente
**Resultado esperado:** 8/8 reles responden con logica correcta

## TC-REL-004: Estado inicial al arranque (P0)
**Prerequisitos:** App detenida, todos los reles en estado desconocido
**Pasos:**
1. Iniciar app.py
2. Verificar GPIO de cada pin = HIGH (apagado)
3. Verificar dashboard muestra todos los actuadores OFF
**Resultado esperado:** Todos los reles apagados al inicio, dashboard consistente

## TC-REL-005: Activar multiples reles simultaneos (P1)
**Prerequisitos:** App corriendo, todo apagado
**Pasos:**
1. Activar ventiladores, intractor y luz en secuencia rapida
2. Verificar que los 3 estan ON en dashboard
3. Verificar que los 3 LEDs estan encendidos
**Resultado esperado:** Multiples reles activos sin interferencia

## TC-REL-006: Todos los reles ON/OFF (P1)
**Prerequisitos:** App corriendo
**Pasos:**
1. Activar los 8 actuadores (respetando conflictos - omitir pares)
2. Verificar que todos los activados responden
3. Desactivar todos
4. Verificar todos OFF
**Resultado esperado:** Maximo de reles sin conflicto activos, luego todos apagados

## TC-REL-007: Pin mapping correcto (P0)
**Prerequisitos:** Acceso fisico al modulo de reles
**Pasos:**
1. Activar cada actuador individualmente desde dashboard
2. Verificar que el rele fisico correcto se activa:
   - ventiladores = Rele 1 (pin 37)
   - filtro_carbon = Rele 2 (pin 35)
   - intractor = Rele 3 (pin 33)
   - humidificador = Rele 4 (pin 31)
   - deshumidificador = Rele 5 (pin 29)
   - luz = Rele 6 (pin 32)
   - calefactor = Rele 7 (pin 36)
   - aire_acondicionado = Rele 8 (pin 38)
**Resultado esperado:** 8/8 mapeos correctos

## TC-REL-008: Actuador inexistente (P2)
**Pasos:**
1. Enviar via SocketIO: toggle_actuador con nombre="noexiste"
**Resultado esperado:** Respuesta error sin crash

## TC-REL-009: Emergency stop (P0)
**Prerequisitos:** Varios reles activos
**Pasos:**
1. Llamar emergency_stop()
2. Verificar todos los reles = OFF
3. Verificar todos los pines GPIO = HIGH
**Resultado esperado:** Todo apagado inmediatamente

## TC-REL-010: Cleanup al cerrar app (P1)
**Prerequisitos:** Reles activos
**Pasos:**
1. Detener app.py (Ctrl+C)
2. Verificar que GPIO.cleanup() se ejecuta
3. Verificar que reles quedan apagados
**Resultado esperado:** GPIO limpio, reles apagados

## TC-REL-011: Persistencia de estado tras reconexion (P2)
**Prerequisitos:** Reles activos, cliente web conectado
**Pasos:**
1. Refrescar pagina del dashboard
2. Verificar que el estado de reles se refleja correctamente
**Resultado esperado:** Estado fisico real coincide con dashboard

## TC-REL-012: Toggle rapido sin oscilacion (P1)
**Prerequisitos:** App corriendo
**Pasos:**
1. Activar y desactivar el mismo rele 10 veces en 5 segundos
2. Verificar estado final correcto
3. Verificar que no hay daño al rele
**Resultado esperado:** Estado final consistente, sin oscilacion
