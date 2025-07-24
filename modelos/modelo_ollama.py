# modelos/modelo_ollama.py

import subprocess

def clasificar_texto(texto):
    prompt = f"Clasifica este texto: '{texto}' como positivo, negativo o neutro."
    resultado = subprocess.run(
        ["ollama", "run", "gemma"],
        input=prompt.encode('utf-8'),
        capture_output=True
    )
    return resultado.stdout.decode('utf-8').strip()
