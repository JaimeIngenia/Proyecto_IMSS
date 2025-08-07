import logging
import os

def configurar_log():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def guardar_datos_csv(data, archivo):
    # Código para guardar datos en CSV
    pass

def generar_nombre_archivo(base_path):
    """
    Genera un nombre de archivo único añadiendo un número al final si el archivo ya existe.
    """
    if not os.path.exists(base_path):
        return base_path
    else:
        i = 1
        while True:
            nuevo_archivo = base_path.replace(".csv", f"_{i}.csv")
            if not os.path.exists(nuevo_archivo):
                return nuevo_archivo
            i += 1