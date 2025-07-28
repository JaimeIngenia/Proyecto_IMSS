# modelos/modelo_huggingface.py

from transformers import pipeline
''' 
classifier = pipeline("text-classification", model="distilbert-base-uncased")

def clasificar_texto(texto):
    resultado = classifier(texto)[0]
    return resultado['label']
'''

# Implementar funciones como analizar_sentimiento(texto) y extraer_temas(texto).


# Cargar modelo de análisis de sentimientos en español
sentiment_model = pipeline("sentiment-analysis", model="pysentimiento/robertuito-sentiment-analysis")

def analizar_comentario(texto: str) -> dict:
    resultado = sentiment_model(texto[:512])[0]  # Truncar si es muy largo
    sentimiento = resultado["label"]

    # Extraer temas de forma simplificada (mejorable con LLMs)
    temas = []
    texto_bajo = texto.lower()
    if "medicamento" in texto_bajo or "farmacia" in texto_bajo:
        temas.append("medicamentos")
    if "espera" in texto_bajo or "cita" in texto_bajo:
        temas.append("tiempos de atención")
    if "trato" in texto_bajo or "personal" in texto_bajo:
        temas.append("trato del personal")
    if "instalación" in texto_bajo or "infraestructura" in texto_bajo:
        temas.append("infraestructura")

    return {
        "sentimiento": sentimiento,
        "temas": temas or ["otros"]
    }
