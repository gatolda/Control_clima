import serial
import time

def read():
    try:
        ser = serial.Serial("/dev/serial0",
                            baudrate=9600,
                            timeout=1.0)
        cmd = bytearray([0xFF, 0x01, 0x86] + [0x00]*5)
        checksum = 0xFF - (sum(cmd[1:8]) % 256) + 1
        cmd.append(checksum & 0xFF)

        ser.write(cmd)
        time.sleep(0.1)
        response = ser.read(9)

        if len(response) != 9:
            return None

        if response[0] != 0xFF or response[1] != 0x86:
            return None

        co2 = response[2]*256 + response[3]
        temperature = response[4] - 40

        return {"co2": co2, "temperature": temperature}

    except Exception as e:
        print(f"Error al leer el sensor MH-Z19: {e}")
        return None
