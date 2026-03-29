import yaml
import os


class ConfigLoader:
    def __init__(self, config_file="config.yml"):
        self.config_file = config_file
        self.config = None

    def cargar_configuracion(self):
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(f"Archivo de configuracion {self.config_file} no encontrado.")

        with open(self.config_file, "r") as f:
            self.config = yaml.safe_load(f)
            print(f"Configuracion cargada desde {self.config_file}")

    def obtener(self, clave, por_defecto=None):
        """
        Devuelve un valor usando clave anidada separada por puntos.
        Ejemplo: obtener("actuadores.pines")
        """
        if self.config is None:
            raise Exception("La configuracion no se ha cargado.")

        claves = clave.split(".")
        valor = self.config
        for k in claves:
            if isinstance(valor, dict) and k in valor:
                valor = valor[k]
            else:
                return por_defecto
        return valor
