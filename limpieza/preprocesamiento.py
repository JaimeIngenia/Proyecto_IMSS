import pandas as pd
import re


def limpiar_comentario(texto: str) -> str:
    texto = texto.lower()
    texto = re.sub(r"http\S+", "", texto)  # eliminar URLs
    texto = re.sub(r"@\w+", "", texto)     # eliminar menciones
    texto = re.sub(r"#\w+", "", texto)     # eliminar hashtags
    texto = re.sub(r"[^a-záéíóúñü\s]", "", texto)  # eliminar caracteres especiales
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto

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


def limpiar_texto(df: pd.DataFrame) -> pd.DataFrame:
    """
    Renombra los valores de tweet_id por un número incremental y
    limpia la columna 'tweet_text' aplicando transformaciones comunes.
    Devuelve el DataFrame actualizado.
    """
    df = df.copy()
    df['tweet_id'] = range(1, len(df) + 1)

    if 'tweet_text' in df.columns:
        df['tweet_text'] = df['tweet_text'].apply(limpiar_un_texto)
    else:
        raise ValueError("La columna 'tweet_text' no se encuentra en el DataFrame.")
    
    return df



