# scraping/extractor_facebook.py
# -*- coding: utf-8 -*-

import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

FACEBOOK_LOGIN_URL = "https://www.facebook.com/login"

# Ajusta estos para balancear rapidez vs. estabilidad
TIMEOUT = 12          # espera máxima por campo/botón
POLL = 0.2            # frecuencia de polling en esperas
WAIT_AFTER_LOGIN = 25 # espera total para quedar logueado, sin CAPTCHA


def _resolver_cookies(driver):
    """Intenta cerrar/aceptar banner de cookies si aparece (rápido y no bloqueante)."""
    selectores = [
        "//button[contains(., 'Aceptar') or contains(., 'Accept') or contains(., 'Permitir')]",
        "//div[@role='button' and (contains(., 'Aceptar') or contains(., 'Accept'))]"
    ]
    for x in selectores:
        try:
            btn = WebDriverWait(driver, 2, poll_frequency=POLL).until(
                EC.element_to_be_clickable((By.XPATH, x))
            )
            btn.click()
            break
        except Exception:
            pass


def _esta_logueado(driver) -> bool:
    """Heurística simple: fuera de /login y /checkpoint y presencia de elementos típicos."""
    url = (driver.current_url or "")
    if "login" in url or "checkpoint" in url:
        return False
    try:
        if driver.find_elements(By.CSS_SELECTOR, "a[href*='notifications'], input[aria-label*='Buscar'], input[aria-label*='Search']"):
            return True
    except Exception:
        pass
    return False


def _find_recaptcha_iframes(driver):
    """Devuelve (iframe_anchor, iframe_challenge) si existen, sino (None, None)."""
    anchor = None
    challenge = None
    try:
        anchors = driver.find_elements(By.CSS_SELECTOR, "iframe[src*='api2/anchor'], iframe[title*='reCAPTCHA']")
        if anchors:
            anchor = anchors[0]
    except Exception:
        pass
    try:
        challenges = driver.find_elements(By.CSS_SELECTOR, "iframe[src*='api2/bframe']")
        if challenges:
            challenge = challenges[0]
    except Exception:
        pass
    return anchor, challenge


def _esperar_recaptcha_si_aparece(driver, tiempo_max=180) -> bool:
    """
    Si aparece reCAPTCHA:
      - Enfoca el checkbox dentro del iframe.
      - Espera a que LO RESUELVAS MANUALMENTE.
      - Sale cuando el checkbox queda marcado o desaparecen iframes/challenge.
    Devuelve True si quedó resuelto o no hubo reCAPTCHA; False si agotó tiempo.
    """
    inicio = time.time()
    informó = False

    while time.time() - inicio < tiempo_max:
        if _esta_logueado(driver):
            return True

        iframe_anchor, iframe_challenge = _find_recaptcha_iframes(driver)

        if iframe_anchor:
            # Cambiamos al iframe del checkbox
            driver.switch_to.default_content()
            try:
                WebDriverWait(driver, 3, poll_frequency=POLL).until(
                    EC.frame_to_be_available_and_switch_to_it(iframe_anchor)
                )
            except Exception:
                driver.switch_to.default_content()
                time.sleep(0.5)
                continue

            try:
                checkbox = WebDriverWait(driver, 4, poll_frequency=POLL).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#recaptcha-anchor"))
                )
                # Enfoca/centra el checkbox (no lo clickeamos)
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", checkbox)
                try:
                    checkbox.send_keys("")  # foco suave
                except Exception:
                    pass

                if not informó:
                    print("🛡️ reCAPTCHA detectado. Marca la casilla y resuelve el challenge si aparece.")
                    informó = True

                estado = (checkbox.get_attribute("aria-checked") or "").lower()
                driver.switch_to.default_content()
                if estado == "true":
                    return True

            except Exception:
                driver.switch_to.default_content()

        if iframe_challenge:
            # Hay challenge (imágenes/audio); esperamos a que desaparezca
            if not informó:
                print("🧩 Desafío reCAPTCHA en curso (imágenes/audio). Resuélvelo manualmente.")
                informó = True
            time.sleep(0.5)
            a, b = _find_recaptcha_iframes(driver)
            if not a and not b:
                return True

        # Si no hay iframes, puede que no exista reCAPTCHA; damos una vuelta rápida
        if not iframe_anchor and not iframe_challenge:
            # Pequeña espera y reintento
            time.sleep(0.5)

    print("⌛ Tiempo de reCAPTCHA agotado.")
    return False


def _esperar_logueado(driver, max_seg=WAIT_AFTER_LOGIN) -> bool:
    """Espera a que la sesión quede iniciada (sin CAPTCHA) hasta max_seg."""
    inicio = time.time()
    while time.time() - inicio < max_seg:
        if _esta_logueado(driver):
            return True
        time.sleep(0.4)
    return False


def iniciar_sesion(driver, user: str, pwd: str, espera_recaptcha=180) -> bool:
    """
    Inicia sesión en Facebook.
    - Es rápido: usa esperas explícitas cortas, sin sleeps largos.
    - Si aparece reCAPTCHA, espera a que LO RESUELVAS y continúa.
    """
    if not user or not pwd:
        print("❌ Faltan credenciales (user/pwd).")
        return False

    print("🌐 Abriendo login de Facebook…")
    driver.get(FACEBOOK_LOGIN_URL)
    _resolver_cookies(driver)

    try:
        email_input = WebDriverWait(driver, TIMEOUT, poll_frequency=POLL).until(
            EC.presence_of_element_located((By.ID, "email"))
        )
        pass_input = WebDriverWait(driver, TIMEOUT, poll_frequency=POLL).until(
            EC.presence_of_element_located((By.ID, "pass"))
        )
        email_input.clear(); email_input.send_keys(user)
        pass_input.clear(); pass_input.send_keys(pwd)
        print("✍️ Credenciales ingresadas.")

        login_btn = WebDriverWait(driver, TIMEOUT, poll_frequency=POLL).until(
            EC.element_to_be_clickable((By.NAME, "login"))
        )
        login_btn.click()
        print("👉 Click en 'Iniciar sesión'.")

    except TimeoutException:
        print("❌ No se encontraron los campos o el botón de login a tiempo.")
        return False
    except Exception as e:
        print(f"❌ Error durante el login: {e}")
        return False

    # Si hay reCAPTCHA, espera a que lo resuelvas; si no, esto sale rápido
    if not _esperar_recaptcha_si_aparece(driver, tiempo_max=espera_recaptcha):
        return False

    # Confirma que ya estás dentro
    if _esperar_logueado(driver):
        print(f"✅ Sesión iniciada. URL: {driver.current_url}")
        return True

    # Último intento
    if _esta_logueado(driver):
        print(f"✅ Sesión iniciada (verificación final). URL: {driver.current_url}")
        return True

    print("❌ No se pudo confirmar el inicio de sesión.")
    return False
