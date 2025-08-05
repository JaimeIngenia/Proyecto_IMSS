import pandas as pd
import re
import json


def limpiar_comentario(texto: str) -> str:
    if not isinstance(texto, str):
        return ""
    
    # Pasar a minúsculas
    texto = texto.lower()

    # Eliminar URLs
    texto = re.sub(r"http\S+|www.\S+", "", texto)

    # Eliminar menciones (@usuario) y hashtags
    texto = re.sub(r"@\w+", "", texto)
    texto = re.sub(r"#\w+", "", texto)

    # Eliminar caracteres extraños pero mantener acentos, números y signos básicos
    texto = re.sub(r"[^\w\sáéíóúñü.,!?¿¡]", "", texto, flags=re.UNICODE)

    # Eliminar espacios múltiples
    texto = re.sub(r"\s+", " ", texto).strip()

    return texto

def normalizar_comillas(texto: str) -> str:
    if not isinstance(texto, str):
        return ""
    return texto.replace('"', '').replace("“", "").replace("”", "")


def limpiar_un_texto(texto: str) -> str:
    """
    Limpia un texto individual eliminando URLs, menciones, hashtags y espacios.
    """
    if not isinstance(texto, str):
        return ""
    texto = re.sub(r"http\S+", "", texto)  # elimina URLs
    texto = re.sub(r"@\w+", "", texto)     # elimina menciones
    texto = re.sub(r"#\w+", "", texto)     # elimina hashtags
    texto = texto.lower().strip()          # minúsculas y espacios
    return texto






def limpiar_respuesta_ollama(respuesta: str) -> dict:
    try:
        texto = re.sub(r"```[a-zA-Z]*", "", respuesta)
        texto = texto.replace("```", "")
        texto = re.sub(r"//.*", "", texto)
        texto = re.sub(r'"\s*([a-zA-Z_]+)\s*"\s*:', r'"\1":', texto)
        texto = re.sub(r",\s*}", "}", texto)
        texto = re.sub(r",\s*]", "]", texto)

        data = json.loads(texto.strip())

        # Aseguramos siempre las claves
        sentimiento = data.get("sentimiento", "error").lower().strip()
        categoria = data.get("categoria", "error").lower().strip()

        return {"sentimiento": sentimiento, "categoria": categoria}
    except Exception as e:
        print(f"[DEBUG] Error parseando JSON: {e} -> Respuesta cruda: {respuesta}")
        return {"sentimiento": "error", "categoria": "error"}