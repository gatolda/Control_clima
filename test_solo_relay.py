# test_solo_relay.py
from Actuadores.relay import RelayBoard
import time

print("⚡ Iniciando prueba de la placa de relés...")

try:
    # Ajusta los pines a los conectados físicamente
    relay_board = RelayBoard(relay_pins=[12, 38])  # Cambia si es necesario
    print("✅ Placa de relés inicializada correctamente.")

    for canal in range(len(relay_board.relay_pins)):
        print(f"🔛 Activando relé {canal} (pin {relay_board.relay_pins[canal]})")
        relay_board.activar(canal)
        time.sleep(2)
        print(f"🔌 Desactivando relé {canal}")
        relay_board.desactivar(canal)
        time.sleep(1)

    print("🔄 Encendiendo todos los relés durante 3 segundos...")
    for pin in relay_board.relay_pins:
        relay_board.activar(relay_board.relay_pins.index(pin))
    time.sleep(3)
    print("🔌 Apagando todos los relés...")
    relay_board.apagar_todos()

except Exception as e:
    print(f"❌ Error durante la prueba de relés: {e}")

finally:
    relay_board.cleanup()
    print("♻️ Pines GPIO liberados.")

print("✅ Prueba de la placa de relés finalizada.")
