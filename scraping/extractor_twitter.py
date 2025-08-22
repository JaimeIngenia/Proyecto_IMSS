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

def visible_text_with_entities(div):
    """
    Devuelve el texto visible tal cual se muestra en X:
    - Sustituye emojis <img alt="…"> por su alt (el propio emoji).
    - Normaliza hashtags: <a href="/hashtag/TAG?..."> → "#TAG"
    - Normaliza menciones: <a href="/Usuario?..."> → "@Usuario"
    - Limpia espacios y 'zero-width' invisibles.
    """
    if not div:
        return ""

    # Trabaja sobre una copia para no alterar el árbol original
    clone = BeautifulSoup(str(div), "html.parser")

    # 1) Emojis: <img alt="🙂"> → "🙂"
    for img in clone.find_all("img"):
        alt = img.get("alt")
        if alt:
            img.replace_with(alt)

    # 2) Hashtags y menciones
    for a in clone.find_all("a", href=True):
        href = a["href"]
        txt = a.get_text("", strip=True)
        replacement = None

        # Hashtag: /hashtag/TAG
        if "/hashtag/" in href:
            tag = href.split("/hashtag/", 1)[1].split("?", 1)[0]
            if tag:
                replacement = "#" + tag

        # Mención: /Usuario  (evita rutas del sistema)
        elif href.startswith("/") and not href.startswith(("/hashtag/", "/search", "/i/")):
            user = href.split("?", 1)[0].strip("/").split("/", 1)[0]
            # si el texto no empieza con @, prefija
            if user and not txt.startswith("@"):
                replacement = "@" + user

        if replacement:
            a.replace_with(replacement)
        else:
            # Conserva el texto visible del enlace
            a.replace_with(txt)

    # 3) Texto plano + limpieza de separadores invisibles
    text = clone.get_text(" ", strip=True)
    text = re.sub(r"[\u200B\u200C\u200D\u2060\uFEFF]", "", text)  # zero-width
    text = re.sub(r"\s+", " ", text).strip()
    return text




def extraer_entidades(div_text):
    if not div_text:
        return [], [], [], []

    def uniq(seq): return list(dict.fromkeys(seq))

    hashtags, menciones, urls, cashtags = [], [], [], []

    # 1) Por enlaces (cuando los hay)
    for a in div_text.find_all("a", href=True):
        href = a["href"]
        txt = a.get_text(strip=True)
        if "/hashtag/" in href:
            tag = href.split("/hashtag/")[1].split("?")[0]
            hashtags.append("#" + tag)
        elif txt.startswith("@"):
            menciones.append(txt)
        elif txt.startswith("$"):
            cashtags.append(txt)
        elif href.startswith("http"):
            urls.append(a.get("title") or href)

    # 2) Fallback por texto plano (por si no hay <a>)
    text_plain = div_text.get_text(" ", strip=True)
    hashtags += re.findall(r"#\w+", text_plain, flags=re.UNICODE)

    return uniq(hashtags), uniq(menciones), uniq(urls), uniq(cashtags)




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
    fieldnames = [
        "tweet_id", "tweet_text", "comentario", "comentario_autor",
        "fecha_publicacion", "timestamp_extraccion","replies",
        "reposts", "likes", "views",
        "hashtags_tweet", "hashtags_comentario"  # ← columnas nuevas
    ]

    archivo_nuevo = not os.path.exists(archivo_csv)
    f = open(archivo_csv, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(f, fieldnames=fieldnames)

    if archivo_nuevo:
        writer.writeheader()

    # DEBUG útil: confirma columnas y ruta
    print(f"📄 Escribiendo en: {archivo_csv}")
    print(f"🧾 Columnas CSV: {writer.fieldnames}")

    return f, writer

def extraer_datos_tweet(soup):
    """Devuelve (tweet_id, tweet_text, fecha, replies, reposts, likes, views, hashtags_tweet)."""
    elem = soup.find("article", {"data-testid": "tweet"})
    text_tag = elem.find("div", {"data-testid": "tweetText"}) if elem else None
    #raw_text = text_tag.get_text(" ", strip=True) if text_tag else ""
    #text = re.sub(r"\s+", " ", raw_text).strip()
    text = visible_text_with_entities(text_tag)
    tweet_id = "id_" + text[:30].replace(" ", "_")

    time_tag = elem.find("time") if elem else None
    fecha = time_tag["datetime"] if (time_tag and time_tag.has_attr("datetime")) else ""

    replies = "0"
    group = elem.find("div", {"role": "group", "aria-label": True}) if elem else None
    if group:
        aria = group["aria-label"]
        m = re.search(r"(\d+)\s+repl(?:y|ies)", aria, re.IGNORECASE)
        if m: replies = m.group(1)

    reposts_tag = elem.find("button", {"data-testid": "retweet"}) if elem else None
    raw_reposts = reposts_tag.text.strip() if reposts_tag else ""
    reposts = raw_reposts if raw_reposts.isdigit() else "0"

    likes_tag = elem.find("button", {"data-testid": "like"}) if elem else None
    raw_likes = likes_tag.text.strip() if likes_tag else ""
    likes = raw_likes if raw_likes.isdigit() else "0"

    views = "0"
    label = elem.find(lambda t: t.name == "span" and "view" in t.get_text(strip=True).lower()) if elem else None
    if label:
        pt = label.parent.get_text(" ", strip=True)
        v = re.search(r"([\d,]+)\s+view", pt, re.IGNORECASE)
        if v: views = v.group(1).replace(",", "")

    # ← Hashtags del TWEET PRINCIPAL (por <a> y por texto)
    ht_tweet, _, _, _ = extraer_entidades(text_tag)
    hashtags_tweet = "|".join(ht_tweet) if ht_tweet else ""

    return tweet_id, text, fecha, replies, reposts, likes, views, hashtags_tweet



def limpiar_para_csv(texto: str) -> str:
    if not isinstance(texto, str):
        return ""
    # Reemplazar comas por punto y coma o espacio
    texto = texto.replace(",", ";")
    # Reemplazar comillas dobles por comillas simples
    texto = texto.replace('"', "'")
    # Eliminar saltos de línea
    texto = texto.replace("\n", " ").replace("\r", " ")
    # Quitar espacios dobles
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()



def guardar_comentarios(
    tweet_id, tweet_text, soup, writer,
    fecha_pub, replies, reposts, likes, views,
    tweet_owner_raw,hashtags_tweet=""
):

    '''
def guardar_comentarios(
    tweet_id, tweet_text, soup, writer,
    fecha_pub, replies, reposts, views,
    tweet_owner_raw
):
    '''
    print(f"↪️ [guardar_comentarios] para tweet_id={tweet_id}")
    tweet_owner = tweet_owner_raw.split("·")[0].strip()
    
    # === Hashtags del tweet principal ===
    orig_article = soup.find("article", {"data-testid": "tweet"})
    orig_text_div = orig_article.find("div", {"data-testid": "tweetText"}) if orig_article else None
    ht_tweet, _, _, _ = extraer_entidades(orig_text_div)
    hashtags_tweet = "|".join(ht_tweet) if ht_tweet else ""

    # 1) Replies oficiales
    conv = soup.find(
        "div",
        {"role": "region", "aria-label": re.compile(r"(Timeline|Cronolog[ií]a):\s*(Conversation|Conversaci[oó]n)", re.I)
}
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
    autenticas = filt
    print(f"→ auténticas tras filtrar: {len(autenticas)}")

    timestamp = datetime.now().isoformat()
    def clean(txt):
        return re.sub(r"\s+", " ", txt.replace("\n"," ")).strip()

    # 5) Si no hay, guardamos genérica
    if not autenticas:
        print("⚠️ Sin respuestas auténticas: grabo genérica.")
        
        writer.writerow({
            "tweet_id": tweet_id,
            "tweet_text": limpiar_para_csv(tweet_text),
            "replies": replies,
            "comentario": "**VERIFIQUÉ Y NO HAY NINGÚN COMENTARIO**",
            "comentario_autor": "**VERIFIQUÉ Y NO HAY NINGÚN COMENTARIO**",
            "fecha_publicacion": fecha_pub,
            "timestamp_extraccion": timestamp,
            "reposts": reposts,
            "likes": likes,
            "views": views,
            #"hashtags_tweet": limpiar_para_csv(hashtags_tweet),
            "hashtags_tweet": hashtags_tweet,
            "hashtags_comentario": hashtags_comentario
        })
        
        
        '''
        writer.writerow({
            "tweet_id": tweet_id,
            "tweet_text": limpiar_para_csv(tweet_text),
            "replies": replies,
            "comentario": 'null',
            "comentario_autor": 'null',
            "fecha_publicacion": fecha_pub,
            "timestamp_extraccion": timestamp,
            "reposts": reposts,
            "views": views
        })
        '''
        return

    # 6) Guardar cada reply auténtica
    for idx, com in enumerate(autenticas, start=1):
        print(f"🔄 Guardando respuesta auténtica #{idx}")
        # texto
        text_div = com.find("div", {"data-testid": "tweetText"})
        comentario_raw = text_div.get_text(" ", strip=True) if text_div else "Comentario no encontrado"
        # Hashtags del comentario
        ht_com, _, _, _ = extraer_entidades(text_div)
        hashtags_comentario = "|".join(ht_com) if ht_com else ""
        # autor
        autor_div = com.find("div", {"data-testid": "User-Name"})
        autor_raw = autor_div.get_text(" ", strip=True) if autor_div else "Autor desconocido"
        # fecha reply
        time_div = com.find("time")
        fecha_com = time_div["datetime"] if (time_div and time_div.has_attr("datetime")) else fecha_pub

        
        writer.writerow({
            "tweet_id": tweet_id,
            "tweet_text": limpiar_para_csv(tweet_text),
            "replies": replies,
            "comentario": limpiar_para_csv(comentario_raw),
            "comentario_autor": limpiar_para_csv(autor_raw),
            "fecha_publicacion": fecha_com,
            "timestamp_extraccion": timestamp,
            "reposts": reposts,
            "likes": likes,
            "views": views,
            "hashtags_tweet": limpiar_para_csv(hashtags_tweet),
            #"hashtags_comentario": limpiar_para_csv(hashtags_comentario)
            "hashtags_comentario": hashtags_comentario
        })
        
        '''
        
        writer.writerow({
            "tweet_id": tweet_id,
            "tweet_text": limpiar_para_csv(tweet_text),
            "replies": replies,
            "comentario": limpiar_para_csv(comentario_raw),
            "comentario_autor": limpiar_para_csv(autor_raw),
            "fecha_publicacion": fecha_com,
            "timestamp_extraccion": timestamp,
            "reposts": reposts,
            "views": views
        })
        '''

# Verificar 

def procesar_tweet_por_url(driver, url, tweets_procesados, writer):
    print(f"\n▶️  Abriendo tweet en nueva pestaña: {url}")
    driver.execute_script("window.open(arguments[0], '_blank');", url)
    driver.switch_to.window(driver.window_handles[-1])

    # Espera a que aparezca el artículo del tweet (no al URL)
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'article[data-testid="tweet"]'))
        )
    except TimeoutException:
        print("  ⏱️ Timeout esperando el tweet. Cierro esta pestaña y continúo con el siguiente.")
        driver.close()
        if driver.window_handles:
            driver.switch_to.window(driver.window_handles[0])
        return

    sleep(1)

    # Scroll inicial
    for i in range(3):
        driver.execute_script("window.scrollBy(0, 800);")
        sleep(0.7)

    # Botón de “spam probable” en ES/EN (si aparece)
    try:
        spam_btn = None
        for xp in [
            "//span[normalize-space(.)='Show probable spam']",
            "//span[normalize-space(.)='Mostrar spam probable']",
            "//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'spam')]"
        ]:
            els = driver.find_elements(By.XPATH, xp)
            if els:
                spam_btn = els[0]
                break
        if spam_btn:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", spam_btn)
            sleep(0.5)
            spam_btn.click()
            sleep(1)
    except Exception:
        pass

    # Bucle de carga de replies
    prev_count = -1
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        sleep(1)

        html = driver.page_source
        soup_tmp = BeautifulSoup(html, "html.parser")
        conv = soup_tmp.find("div", {
            "role": "region",
            "aria-label": re.compile(r"(Timeline|Cronolog[ií]a):\s*(Conversation|Conversaci[oó]n)", re.I)
        })
        loaded = (len(conv.find_all("article", {"data-testid": "tweet"})) - 1) if conv else 0


        print(f"    🔄 Replies cargados: {loaded}")
        if loaded == prev_count:
            break
        prev_count = loaded

    print(f"  🔍 Tamaño de page_source tras spam: {len(driver.page_source)}")
    soup = BeautifulSoup(driver.page_source, "html.parser")

    # 5) Extraemos datos del tweet principal
    #tweet_id, tweet_text, fecha_pub, replies, reposts, likes, views = extraer_datos_tweet(soup)
    tweet_id, tweet_text, fecha_pub, replies, reposts, likes, views, hashtags_tweet = extraer_datos_tweet(soup)

    print(f"  💡 Extraído: id={tweet_id} replies={replies}")

    # 6) Evitar duplicados
    if tweet_id in tweets_procesados:
        print("  ⚠️ ya procesado, cierro y regreso.")
        driver.close()
        if driver.window_handles:
            driver.switch_to.window(driver.window_handles[0])
        return
    tweets_procesados.add(tweet_id)

    # 7) Capturar autor original (con guardas)
    art = soup.find("article", {"data-testid": "tweet"})
    owner_tag = art.find("div", {"data-testid": "User-Name"}) if art else None
    tweet_owner_raw = owner_tag.get_text(" ", strip=True) if owner_tag else ""
    print(f"  👤 Autor original: {tweet_owner_raw}")

    # 8) Guardar comentarios
    '''
    guardar_comentarios(
        tweet_id, tweet_text, soup, writer,
        fecha_pub, replies, reposts, likes, views,
        tweet_owner_raw
    )
    '''
    guardar_comentarios(
        tweet_id, tweet_text, soup, writer,
        fecha_pub, replies, reposts, likes, views,
        tweet_owner_raw,
        hashtags_tweet        # ← nuevo arg
    )
    
    

    # 9) Cerrar y volver
    print("  🔙 Cerrando pestaña y volviendo…")
    driver.close()
    if driver.window_handles:
        driver.switch_to.window(driver.window_handles[0])
 
        
def extraer_y_guardar_comentarios(
    driver,
    archivo_csv="comentarios_imss.csv",
    max_tweets=20,
    #max_tweets=30,
    n_scrolls=1,
    #n_scrolls=10,
    scroll_pause=2
    #scroll_pause=4
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
    print(f"🔍 Se encontraron {len(elems)} elementos tipo tweet antes de extraer los enlaces. Jaime!")
    
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
            try:
                procesar_tweet_por_url(driver, url, tweets_procesados, writer)
            except Exception as e:
                print(f"  ⚠️ Error procesando {url}: {repr(e)}")
                # Intenta recuperar el foco de la ventana principal
                try:
                    if len(driver.window_handles) > 1:
                        driver.close()
                except Exception:
                    pass
                if driver.window_handles:
                    driver.switch_to.window(driver.window_handles[0])
                continue

    finally:
        f.close()