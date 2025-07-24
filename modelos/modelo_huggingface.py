# modelos/modelo_huggingface.py

from transformers import pipeline

classifier = pipeline("text-classification", model="distilbert-base-uncased")

def clasificar_texto(texto):
    resultado = classifier(texto)[0]
    return resultado['label']
