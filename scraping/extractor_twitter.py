import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from time import sleep
import csv
import os
from datetime import datetime
from random import randint
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import StaleElementReferenceException
import re

from selenium.common.exceptions import NoSuchElementException
from bs4 import BeautifulSoup, NavigableString

def iniciar_sesion(driver,user='', pwd='', username=''):
    driver.get('https://twitter.com/login')

    try:
        # Ingresar correo electrónico
        email_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, 'text'))
        )
        email_input.send_keys(user)
        print("✔ Correo ingresado")

        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '//span[normalize-space(text())="Siguiente"]'))
        ).click()

        sleep(2)

        # Verificar si se solicita "nombre de usuario o teléfono"
        try:
            # Espera de máximo 3 segundos a que aparezca otro campo de texto
            username_field = WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.NAME, 'text'))
            )

            # Verifica que el texto del label indique "Teléfono o nombre de usuario"
            username_label = driver.find_element(By.XPATH, '//span[contains(text(), "Teléfono o nombre de usuario")]')
            if username_label and username:
                username_field.send_keys(username)
                WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, '//span[normalize-space(text())="Siguiente"]'))
                ).click()
                print("✔ Nombre de usuario confirmado")
            else:
                print("ℹ Apareció otro campo de texto, pero no se llenó porque no se identificó como campo de usuario.")
        except TimeoutException:
            print("ℹ No se pidió confirmación adicional de nombre de usuario.")

        # Ingresar contraseña
        password_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, 'password'))
        )
        password_input.send_keys(pwd)
        print("✔ Contraseña ingresada")

        # Click en "Iniciar sesión"
        login_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="LoginForm_Login_Button"]'))
        )
        login_button.click()
        print("✔ Se hizo clic en 'Iniciar sesión'")

        sleep(5)

    except TimeoutException as e:
        print(" Error de tiempo de espera durante el login:", e)

def navegar_a_perfil(driver,profile_url):
    """Navega al perfil especificado."""
    driver.get(profile_url)
    sleep(5)  # Espera a que el perfil cargue

def cargar_tweets_procesados(archivo_csv):
    """Carga los IDs de tweets ya procesados desde un archivo CSV."""
    if not os.path.exists(archivo_csv):
        return set()
    with open(archivo_csv, "r", encoding="utf-8") as f:
        return set(row["tweet_id"] for row in csv.DictReader(f))

def preparar_archivo_csv(archivo_csv):
    """Prepara el archivo CSV para escritura, añadiendo encabezados si es necesario."""
    archivo_nuevo = not os.path.exists(archivo_csv)
    f = open(archivo_csv, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(f, fieldnames=[
        "tweet_id", "tweet_text", "comentario", "comentario_autor",
        "fecha_publicacion", "timestamp_extraccion","replies",  
        "reposts", "likes", "views" 
    ])
    if archivo_nuevo:
        writer.writeheader()
    return f, writer

# Refactor

def extraer_datos_tweet(soup):
    """
    Devuelve (tweet_id, tweet_text, fecha, replies, reposts, likes, views).
    Ahora el regex de replies reconoce tanto '1 reply' como '4 replies'.
    """
    elem = soup.find("article", {"data-testid": "tweet"})
    
    # --- 1) Texto y ID ---
    text_tag = elem.find("div", {"data-testid": "tweetText"})
    raw_text = text_tag.get_text(" ", strip=True) if text_tag else ""
    text = re.sub(r"\s+", " ", raw_text).strip()
    tweet_id = "id_" + text[:30].replace(" ", "_")
    
    # --- 2) Fecha ---
    time_tag = elem.find("time")
    fecha = time_tag["datetime"] if (time_tag and time_tag.has_attr("datetime")) else ""
    
    # --- 3) Replies (comentarios) ---
    replies = "0"
    group = elem.find("div", {"role": "group", "aria-label": True})
    if group:
        aria = group["aria-label"]  # ej. "4 replies, 7 reposts, 29 likes, 2760 views"
        m = re.search(r"(\d+)\s+repl(?:y|ies)", aria, re.IGNORECASE)
        if m:
            replies = m.group(1)
    
    # --- 4) Reposts y Likes ---
    reposts_tag = elem.find("button", {"data-testid": "retweet"})
    raw_reposts = reposts_tag.text.strip() if reposts_tag else ""
    reposts = raw_reposts if raw_reposts.isdigit() else "0"
    
    likes_tag = elem.find("button", {"data-testid": "like"})
    raw_likes = likes_tag.text.strip() if likes_tag else ""
    likes = raw_likes if raw_likes.isdigit() else "0"
    
    # --- 5) Views ---
    views = "0"
    # Busca un span que contenga la palabra "view" o "views"
    label = elem.find(lambda t: t.name == "span" and "view" in t.get_text(strip=True).lower())
    if label:
        pt = label.parent.get_text(" ", strip=True)
        v = re.search(r"([\d,]+)\s+view", pt, re.IGNORECASE)
        if v:
            views = v.group(1).replace(",", "")
    
    return tweet_id, f'"{text}"', fecha, replies, reposts, likes, views



def guardar_comentarios(
    tweet_id, tweet_text, soup, writer,
    fecha_pub, replies, reposts, likes, views,
    tweet_owner_raw
):
    print(f"↪️ [guardar_comentarios] para tweet_id={tweet_id}")
    tweet_owner = tweet_owner_raw.split("·")[0].strip()

    # 1) Replies oficiales
    conv = soup.find(
        "div",
        {"role": "region", "aria-label": re.compile(r"Timeline: Conversation")}
    )
    oficiales = conv.find_all("article", {"data-testid": "tweet"}) if conv else []

    # 2) Replies ocultos bajo "spam"
    spam_cells = soup.find_all("div", {"data-testid": "cellInnerDiv"})
    spam_replies = []
    for cell in spam_cells:
        spam_replies += cell.find_all("article", {"data-testid": "tweet"})

    # 3) Todos los candidatos (sacando el original si aparece)
    candidatos = oficiales + spam_replies
    if candidatos and candidatos[0].find("time"):
        candidatos = candidatos[1:]

    print(f"🔎 oficiales: {len(oficiales)}")
    print(f"🔎 spam_cells encontradas: {len(spam_cells)}, total spam artículos: {len(spam_replies)}")
    print(f"🔎 total candidatos tras unir: {len(candidatos)}")

    # 4) Filtrar por botón reply y autor distinto
    filt = []
    for com in candidatos:
        if not com.find("button", {"data-testid": "reply"}):
            continue
        autor_tag = com.find("div", {"data-testid": "User-Name"})
        autor_norm = autor_tag.get_text(" ", strip=True).split("·")[0].strip() if autor_tag else ""
        if autor_norm != tweet_owner:
            filt.append(com)

    # ——— [4bis] Recortar a 'replies' máximo ———
    max_rep = int(replies or 0)
    auténticas = filt
    #auténticas = filt[:max_rep]
    print(f"→ auténticas tras filtrar y recortar a {len(auténticas)}/{max_rep}")

    timestamp = datetime.now().isoformat()
    def clean(txt):
        return re.sub(r"\s+", " ", txt.replace("\n"," ")).strip()

    # 5) Si no hay, guardamos genérica
    if not auténticas:
        print("⚠️ Sin respuestas auténticas: grabo genérica.")
        writer.writerow({
            "tweet_id": tweet_id,
            "tweet_text": tweet_text,
            "replies": replies,
            "comentario": '"**VERIFIQUÉ Y NO HAY NINGÚN COMENTARIO**"',
            "comentario_autor": '"**VERIFIQUÉ Y NO HAY NINGÚN COMENTARIO**"',
            "fecha_publicacion": fecha_pub,
            "timestamp_extraccion": timestamp,
            "reposts": reposts,
            "likes": likes,
            "views": views
        })
        return

    # 6) Guardar cada reply auténtica
    for idx, com in enumerate(auténticas, start=1):
        print(f"🔄 Guardando respuesta auténtica #{idx}")
        # texto
        text_div = com.find("div", {"data-testid": "tweetText"})
        comentario_raw = text_div.get_text(" ", strip=True) if text_div else "Comentario no encontrado"
        # autor
        autor_div = com.find("div", {"data-testid": "User-Name"})
        autor_raw = autor_div.get_text(" ", strip=True) if autor_div else "Autor desconocido"
        # fecha reply
        time_div = com.find("time")
        fecha_com = time_div["datetime"] if (time_div and time_div.has_attr("datetime")) else fecha_pub

        writer.writerow({
            "tweet_id": tweet_id,
            "tweet_text": tweet_text,
            "replies": replies,
            "comentario": f'"{clean(comentario_raw)}"',
            "comentario_autor": f'"{clean(autor_raw)}"',
            "fecha_publicacion": fecha_com,
            "timestamp_extraccion": timestamp,
            "reposts": reposts,
            "likes": likes,
            "views": views
        })

# Verificar 

def procesar_tweet_por_url(driver, url, tweets_procesados, writer):
    print(f"\n▶️  Abriendo tweet en nueva pestaña: {url}")
    # 1) Abrir en pestaña nueva y cambiar contexto
    driver.execute_script("window.open(arguments[0], '_blank');", url)
    driver.switch_to.window(driver.window_handles[-1])
    WebDriverWait(driver, 15).until(lambda d: "/status/" in d.current_url)
    sleep(1)

    # 2) Reveal inicial de replies y posible spam
    for i in range(3):
        driver.execute_script("window.scrollBy(0, 800);")
        sleep(0.7)
    try:
        spam_btn = driver.find_element(
            By.XPATH, "//span[normalize-space(text())='Show probable spam']"
        )
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", spam_btn)
        sleep(0.5)
        spam_btn.click()
        sleep(1)
    except NoSuchElementException:
        pass

    # 3) Bucle hasta que ya no cargue más replies
    prev_count = -1
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        sleep(1)

        # Capturamos el HTML y contamos replies (artículos menos el original)
        html = driver.page_source
        soup_tmp = BeautifulSoup(html, "html.parser")
        conv = soup_tmp.find("div", {
            "role": "region",
            "aria-label": re.compile(r"Timeline: Conversation")
        })
        loaded = (len(conv.find_all("article", {"data-testid": "tweet"})) - 1) if conv else 0

        print(f"    🔄 Replies cargados: {loaded}")
        if loaded == prev_count:
            break
        prev_count = loaded

    # 4) Ya con todo cargado, parseamos el resultado final
    print(f"  🔍 Tamaño de page_source tras spam: {len(driver.page_source)}")
    soup = BeautifulSoup(driver.page_source, "html.parser")

    # 5) Extraemos datos del tweet principal
    tweet_id, tweet_text, fecha_pub, replies, reposts, likes, views = extraer_datos_tweet(soup)
    print(f"  💡 Extraído: id={tweet_id} replies={replies}")

    # 6) Evitamos duplicados
    if tweet_id in tweets_procesados:
        print("  ⚠️ ya procesado, cierro y regreso.")
        driver.close()
        driver.switch_to.window(driver.window_handles[0])
        return
    tweets_procesados.add(tweet_id)

    # 7) Capturamos autor original
    owner_tag = soup.find("article", {"data-testid": "tweet"}) \
                    .find("div", {"data-testid": "User-Name"})
    tweet_owner_raw = owner_tag.get_text(" ", strip=True) if owner_tag else ""
    print(f"  👤 Autor original: {tweet_owner_raw}")

    # 8) Guardamos todos los comentarios ya cargados
    guardar_comentarios(
        tweet_id, tweet_text, soup, writer,
        fecha_pub, replies, reposts, likes, views,
        tweet_owner_raw
    )

    # 9) Cerramos pestaña y volvemos
    print("  🔙 Cerrando pestaña y volviendo…")
    driver.close()
    driver.switch_to.window(driver.window_handles[0])
    
        
def extraer_y_guardar_comentarios(
    driver,
    archivo_csv="comentarios_imss.csv",
    max_tweets=20,
    n_scrolls=1,       # fija aquí cuántos scrolls quieres
    scroll_pause=2
):
    wait = WebDriverWait(driver, 10)
    # entrar ya en modo “Latest”
    driver.get("https://x.com/Tu_IMSS?f=live")
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'article[data-testid="tweet"]')))

    # 1) Hacer n_scrolls scrolls sencillos
    for i in range(n_scrolls):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        print(f"🔄 Scroll fijo #{i+1}/{n_scrolls}")
        sleep(scroll_pause)

    # 2) Recolectar TODOS los enlaces (sin duplicados)
    seen = set()
    tweet_links = []
    elems = driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="tweet"]')
    for t in elems:
        try:
            href = t.find_element(By.CSS_SELECTOR, 'time')\
                    .find_element(By.XPATH, '..')\
                    .get_attribute('href')
        except:
            continue
        if href and href not in seen:
            seen.add(href)
            tweet_links.append(href)
        if len(tweet_links) >= max_tweets:
            break

    print(f"🔗 Capturadas {len(tweet_links)} URLs de tweets (queríamos {max_tweets})")

    # 3) Abrir CSV y procesar cada enlace
    tweets_procesados = cargar_tweets_procesados(archivo_csv)
    f, writer = preparar_archivo_csv(archivo_csv)
    try:
        for idx, url in enumerate(tweet_links, 1):
            print(f"\n🔹 Procesando URL #{idx}/{len(tweet_links)}: {url}")
            procesar_tweet_por_url(driver, url, tweets_procesados, writer)
    finally:
        f.close()


