import serial
import time

print("📡 Probar lectura del sensor MH-Z19...")

try:
    # Abrimos el puerto serial
    ser = serial.Serial("/dev/serial0", baudrate=9600, timeout=1)

    while True:
        # Comando de lectura del sensor MH-Z19
        command = bytearray([0xFF, 0x01, 0x86] + [0x00]*5 + [0x79])
        ser.write(command)

        response = ser.read(9)
        if len(response) == 9:
            co2 = response[2]*256 + response[3]
            temp = response[4] - 40
            print(f"🌿 CO₂: {co2} ppm | 🌡️ Temp: {temp}°C")
        else:
            print("❌ No se recibió una respuesta válida")

        time.sleep(2)

except Exception as e:
    print(f"⚠️ Error: {e}")
