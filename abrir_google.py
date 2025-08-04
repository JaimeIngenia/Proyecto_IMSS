from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import logging

# Configuración de logs
logging.basicConfig(
    #filename='selenium_test.log',
    filename='/scripts/selenium_test.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s'
)

try:
    logging.info("Iniciando script Selenium...")

    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-extensions")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get("https://www.google.com")
    logging.info("Navegador abierto correctamente.")

    time.sleep(10)

    driver.quit()
    logging.info("Navegador cerrado exitosamente.")
except Exception as e:
    logging.error(f"Error en Selenium: {e}")
