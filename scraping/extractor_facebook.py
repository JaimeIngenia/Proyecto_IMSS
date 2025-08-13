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


def recolectar_links_publicaciones(driver, max_links=3, max_scrolls=20):
    """
    Hace scroll en la página y devuelve hasta max_links permalinks únicos de publicaciones.
    Usa la función existente recolectar_publicaciones_pagina.
    """
    links = []
    vistos = set()

    # Levanta más posts de los que necesitamos para tener margen
    publicaciones = recolectar_publicaciones_pagina(driver, max_posts=max_links*5, max_scrolls=max_scrolls)
    for p in publicaciones:
        pl = (p.get("permalink") or "").strip()
        if pl and pl not in vistos:
            vistos.add(pl)
            links.append({
                "permalink": pl,
                "autor": p.get("autor", ""),
                "texto": (p.get("texto", "") or "")[:140]  # preview corto opcional
            })
            if len(links) >= max_links:
                break
    return links


def guardar_links_csv(links, ruta_csv, pagina_url="https://www.facebook.com/IMSSmx"):
    import csv, os, time
    os.makedirs(os.path.dirname(ruta_csv), exist_ok=True)
    now = time.strftime('%Y-%m-%d %H:%M:%S')

    # Modificamos el nombre de la columna texto_preview a text_publicacion
    with open(ruta_csv, "w", newline="", encoding="utf-8") as f:
        campos = ["fecha_extraccion", "pagina_url", "permalink", "autor", "text_publicacion"]
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()

        for item in links:
            w.writerow({
                "fecha_extraccion": now,
                "pagina_url": pagina_url,
                "permalink": item.get("permalink", ""),
                "autor": item.get("autor", ""),
                "text_publicacion": (item.get("texto", "") or "").replace("\r", " ").replace("\n", " ").strip(),
            })
    print(f"💾 Guardado: {ruta_csv} ({len(links)} links)")
    return ruta_csv



def _esperar_y_enfocar_recaptcha(driver, timeout=30, poll=0.2):
    driver.switch_to.default_content()
    # 1) Espera iframe visible (no solo presente)
    iframe = WebDriverWait(driver, timeout, poll_frequency=poll).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, "iframe[src*='api2/anchor'], iframe[title*='reCAPTCHA']"))
    )
    # 2) Cambia al iframe
    WebDriverWait(driver, timeout, poll_frequency=poll).until(
        EC.frame_to_be_available_and_switch_to_it(iframe)
    )
    # 3) Espera el checkbox visible
    checkbox = WebDriverWait(driver, timeout, poll_frequency=poll).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, "#recaptcha-anchor"))
    )
    # 4) Centra y enfoca (NO clic)
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", checkbox)
    try:
        checkbox.send_keys("")  # foco suave
    except Exception:
        pass
    driver.switch_to.default_content()
    return True


########################################################
# --- Navegar a una página concreta (ej. IMSSmx) ---
def navegar_a_pagina(driver, url_pagina: str, timeout=12, poll=0.2):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    print(f"🧭 Navegando a la página: {url_pagina}")
    driver.get(url_pagina)

    # Asegura que estamos en la página (role=main presente)
    WebDriverWait(driver, timeout, poll_frequency=poll).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='main']"))
    )

    # A veces Facebook abre la pestaña "Información"; intentamos ver contenido tipo publicaciones
    # Si existe una pestaña "Publicaciones"/"Posts", haz click (no bloqueante si no aparece):
    posibles_tabs = [
        "//a[contains(., 'Publicaciones')]",
        "//a[contains(., 'Posts')]",
    ]
    for xp in posibles_tabs:
        try:
            el = WebDriverWait(driver, 2, poll_frequency=poll).until(
                EC.element_to_be_clickable((By.XPATH, xp))
            )
            el.click()
            break
        except Exception:
            pass

    return True


# --- Extraer datos básicos desde un artículo ---
def _extraer_info_articulo(driver, article):
    """Intenta extraer texto, autor y link permanente de un 'div[role=article]'."""
    from selenium.webdriver.common.by import By

    texto = ""
    # Prioriza contenedores de mensaje; si no, usa texto visible del article
    try:
        msg = article.find_elements(By.CSS_SELECTOR, "div[data-ad-preview='message']")
        if msg:
            texto = "\n".join([m.text for m in msg]).strip()
    except Exception:
        pass
    if not texto:
        try:
            spans = article.find_elements(By.CSS_SELECTOR, "div[dir='auto'], span[dir='auto']")
            cand = []
            for s in spans[:30]:
                t = (s.text or "").strip()
                if t and len(t) > 3:
                    cand.append(t)
            texto = "\n".join(cand).strip()
        except Exception:
            pass

    # Autor (heurístico: primer link prominente en cabecera)
    autor = ""
    try:
        # Muchas páginas muestran el nombre en h3/strong -> a
        a_nodes = article.find_elements(By.CSS_SELECTOR, "h3 a, strong a, a[role='link']")
        for a in a_nodes[:10]:
            name = (a.text or "").strip()
            href = (a.get_attribute("href") or "")
            if name and len(name) > 2 and "facebook.com" in href:
                autor = name
                break
    except Exception:
        pass

    # Link permanente (post / photos / videos)
    permalink = ""
    try:
        links = article.find_elements(By.CSS_SELECTOR, "a[role='link'], a[href]")
        candidatos = []
        for a in links:
            href = (a.get_attribute("href") or "")
            if any(p in href for p in ["/posts/", "/photos/", "/videos/"]):
                candidatos.append(href)
        # Elige el más largo (suele ser el canónico)
        if candidatos:
            permalink = sorted(candidatos, key=len, reverse=True)[0]
    except Exception:
        pass

    return {
        "autor": autor or "",
        "texto": (texto or "").strip(),
        "permalink": permalink or "",
    }

# --- Scroll y recolección de publicaciones ---
def recolectar_publicaciones_pagina(driver, max_posts=15, max_scrolls=20):
    """
    Hace scroll en la página y colecta hasta max_posts artículos.
    Devuelve lista de dicts: {autor, texto, permalink}
    """
    from selenium.webdriver.common.by import By
    import time

    vistos = set()
    resultados = []

    last_height = driver.execute_script("return document.body.scrollHeight;")
    scrolls = 0

    while len(resultados) < max_posts and scrolls < max_scrolls:
        # Buscar artículos en el role=main
        try:
            main = driver.find_element(By.CSS_SELECTOR, "div[role='main']")
            articles = main.find_elements(By.CSS_SELECTOR, "div[role='article']")
        except Exception:
            articles = driver.find_elements(By.CSS_SELECTOR, "div[role='article']")

        for art in articles:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", art)
            except Exception:
                pass

            info = _extraer_info_articulo(driver, art)
            key = (info.get("texto", "")[:60], info.get("permalink", ""))
            if not info.get("texto") and not info.get("permalink"):
                continue
            if key in vistos:
                continue
            vistos.add(key)

            # Filtro simple: evita capturar la caja de "No hay más publicaciones..."
            if "No hay más publicaciones" in info.get("texto", ""):
                continue

            resultados.append(info)
            if len(resultados) >= max_posts:
                break

        # Scroll
        driver.execute_script("window.scrollBy(0, Math.floor(window.innerHeight*0.9));")
        time.sleep(0.6)
        scrolls += 1

        # Rompe si ya no crece el documento (tope)
        new_height = driver.execute_script("return document.body.scrollHeight;")
        if new_height <= last_height:
            # Intenta un pequeño nudge adicional
            driver.execute_script("window.scrollBy(0, 800);")
            time.sleep(0.6)
            newer_height = driver.execute_script("return document.body.scrollHeight;")
            if newer_height <= last_height:
                break
            last_height = newer_height
        else:
            last_height = new_height

    return resultados

# --- Guardar CSV ---
def guardar_publicaciones_csv(publicaciones, ruta_csv):
    import csv, os, time
    os.makedirs(os.path.dirname(ruta_csv), exist_ok=True)
    now = time.strftime('%Y-%m-%d %H:%M:%S')

    with open(ruta_csv, "w", newline="", encoding="utf-8") as f:
        campos = ["fecha_extraccion", "pagina_url", "autor", "permalink", "texto"]
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for p in publicaciones:
            w.writerow({
                "fecha_extraccion": now,
                "pagina_url": "https://www.facebook.com/IMSSmx",
                "autor": p.get("autor", ""),
                "permalink": p.get("permalink", ""),
                "texto": (p.get("texto", "") or "").replace("\r", " ").replace("\n", " ").strip(),
            })
    print(f"💾 Guardado: {ruta_csv} ({len(publicaciones)} filas)")
    return ruta_csv

########################################################


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
            driver.switch_to.default_content()
            try:
                # Esperar visibilidad del iframe antes de cambiar a él
                WebDriverWait(driver, 3, poll_frequency=POLL).until(
                    EC.visibility_of(iframe_anchor)
                )
                driver.switch_to.frame(iframe_anchor)
            except Exception:
                driver.switch_to.default_content()
                time.sleep(0.5)
                continue

            try:
                # Asegura que el checkbox sea visible y clickeable
                checkbox = WebDriverWait(driver, 4, poll_frequency=POLL).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "#recaptcha-anchor"))
                )
                # Enfoca el checkbox y realiza el scroll
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", checkbox)
                checkbox.send_keys("")  # Simple foco

                if not informó:
                    print("🛡️ reCAPTCHA detectado. Marca la casilla y resuelve el challenge si aparece.")
                    informó = True

                # Verifica si la casilla está marcada
                estado = (checkbox.get_attribute("aria-checked") or "").lower()
                driver.switch_to.default_content()
                if estado == "true":
                    return True

            except Exception:
                driver.switch_to.default_content()

        if iframe_challenge:
            if not informó:
                print("🧩 Desafío reCAPTCHA en curso (imágenes/audio). Resuélvelo manualmente.")
                informó = True
            time.sleep(0.5)
            a, b = _find_recaptcha_iframes(driver)
            if not a and not b:
                return True

        # Si no hay iframes, puede que no exista reCAPTCHA; damos una vuelta rápida
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

        # Tras login_btn.click(), espera el reCAPTCHA (solo si aparece)
        _esperar_recaptcha_si_aparece(driver, tiempo_max=espera_recaptcha)

    except TimeoutException:
        print("❌ No se encontraron los campos o el botón de login a tiempo.")
        return False
    except Exception as e:
        print(f"❌ Error durante el login: {e}")
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

