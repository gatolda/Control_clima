"""
config_loader.py
Carga y gestiona la configuración desde el archivo config.yml
"""

import yaml
import os

class ConfigLoader:
    def __init__(self, config_file="config.yml"):
        self.config_file = config_file
        self.config = None

    def cargar_configuracion(self):
        """Carga el archivo YAML de configuración"""
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(f"⚠️ Archivo de configuración {self.config_file} no encontrado.")

        with open(self.config_file, "r") as f:
            try:
                self.config = yaml.safe_load(f)
                print(f"✅ Configuración cargada correctamente desde {self.config_file}")
            except yaml.YAMLError as e:
                raise Exception(f"❌ Error al analizar {self.config_file}: {e}")

    def obtener(self, clave, por_defecto=None):
        """
        Devuelve un valor de configuración usando clave anidada separada por puntos.
        Ejemplo: obtener("sensores.temperatura_humedad.pin")
        """
        if self.config is None:
            raise Exception("❌ La configuración no se ha cargado. Llama a cargar_configuracion() primero.")

        claves = clave.split(".")
        valor = self.config
        for k in claves:
            if k in valor:
                valor = valor[k]
            else:
                return por_defecto
        return valor


# Ejemplo de uso directo
if __name__ == "__main__":
    config = ConfigLoader()
    config.cargar_configuracion()
    print("🌡️ Pin del sensor Temp/Humedad:", config.obtener("sensores.temperatura_humedad.pin"))
    print("⚡ Pines de relés:", config.obtener("actuadores.rele_board.pines"))
