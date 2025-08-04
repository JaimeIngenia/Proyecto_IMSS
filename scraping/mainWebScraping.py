from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from extractor_twitter import iniciar_sesion, navegar_a_perfil, extraer_y_guardar_comentarios
from datetime import datetime
import os

# 📁 Función para evitar colisiones de nombre
def generar_nombre_archivo(base_dir, nombre_base):
    nombre_completo = os.path.join(base_dir, nombre_base)
    if not os.path.exists(nombre_completo):
        return nombre_completo

    # Si existe, añade sufijo incremental
    contador = 1
    while True:
        nuevo_nombre = os.path.join(base_dir, f"{nombre_base[:-4]}_{contador}.csv")
        if not os.path.exists(nuevo_nombre):
            return nuevo_nombre
        contador += 1

# Configurar opciones de Chrome para entorno sin interfaz gráfica (Docker)
options = Options()
options.binary_location = "/usr/bin/chromium"  # Usamos el que viene con Alpine
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

# Usamos el chromedriver instalado en el sistema
service = Service("/usr/bin/chromedriver")

# Crear instancia del navegador
driver = webdriver.Chrome(service=service, options=options)

try:
    # Paso 1: Iniciar sesión
    iniciar_sesion(driver, user='jamoncayop@gmail.com', pwd='Adaptiv3@*', username='@Jaime1807816689')

    # Paso 2: Navegar al perfil
    navegar_a_perfil(driver, "https://x.com/Tu_IMSS?f=live")
    print("✅ ¡Has iniciado sesión y estás en el perfil de @Tu_IMSS!")
    
    # Ruta base y nombre inicial
    fecha_actual = datetime.now().strftime("%Y-%m-%d")
    base_dir = "/app/db"
    os.makedirs(base_dir, exist_ok=True)
    nombre_base = f"cmts_extraidos_{fecha_actual}_jaime.csv"
    
    # Generar nombre final único
    nombre_archivo = generar_nombre_archivo(base_dir, nombre_base)

    # Guardar comentarios
    extraer_y_guardar_comentarios(driver, nombre_archivo)

except Exception as e:
    print("❌ Error en la ejecución:", e)

finally:
    if driver:
        driver.quit()

'''

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.binary_location = "/usr/bin/chromium-browser"

service = Service("/usr/bin/chromedriver")
driver = webdriver.Chrome(service=service, options=options)

driver.get("https://www.google.com")
print("✅ Navegador abierto correctamente:", driver.title)
driver.quit()
'''