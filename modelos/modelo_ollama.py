# modelos/modelo_ollama.py
from limpieza.preprocesamiento import limpiar_respuesta_ollama
import json
import subprocess
import subprocess


def probar_ollama_simple(texto="Hola, esto es una prueba"):
    """
    Envía un texto fijo a Ollama para probar la clasificación.
    """
    prompt = f"""
    Analiza el siguiente comentario:
    "{texto}"
    Devuelve únicamente un JSON válido con esta estructura:
    {{
      "sentimiento": "positivo | negativo | neutro",
      "categoria": "queja | elogio | otro"
    }}
    No incluyas explicaciones, comentarios ni bloques de código.
    """
    print("🤖 [TEST] Enviando prompt a Ollama...")
    
    try:
        proceso = subprocess.Popen(
            ["ollama", "run", "gemma:2b"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        salida, error = proceso.communicate(prompt, timeout=60)
        print("[DEBUG] STDOUT:", salida.strip())
        print("[DEBUG] STDERR:", error.strip() if error else "VACÍO")

        # Intentar limpiar la respuesta
        return limpiar_respuesta_ollama(salida)
    except Exception as e:
        print(f"❌ [ERROR] {e}")
        return {"sentimiento": "error", "categoria": "error"}

if __name__ == "__main__":
    resultado = probar_ollama_simple("cómo destruyen las instituciones")
    print("✅ [RESULTADO FINAL]:", resultado)
    
    
    
    
    
    


def consultar_ollama(prompt: str, modelo: str = "gemma:2b") -> str:
    print(f"[DEBUG] Llamando a Ollama con prompt: {prompt[:100]}...")
    try:
        proceso = subprocess.Popen(
            ["ollama", "run", modelo],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",   # Forzar UTF-8
            errors="replace"    # Reemplazar caracteres no soportados
        )
        salida, error = proceso.communicate(prompt, timeout=60)
        print("[DEBUG] STDOUT:", salida[:200] if salida else "VACÍO")
        print("[DEBUG] STDERR:", error[:200] if error else "VACÍO")
        if error:
            raise Exception(f"Error en Ollama: {error}")
        return salida.strip()
    except subprocess.TimeoutExpired:
        proceso.kill()
        return ""


def analizar_comentario_ollama(comentario: str) -> dict:
    """
    Clasifica el comentario usando Gemma (Ollama).
    Devuelve un diccionario con 'sentimiento' y 'categoria'.
    """
    prompt = f"""
    Analiza el siguiente comentario:
    "{comentario}"
    Devuelve únicamente un JSON válido con esta estructura:
    {{
      "sentimiento": "positivo | negativo | neutro",
      "categoria": "queja | elogio | otro"
    }}
    No incluyas explicaciones, comentarios ni bloques de código.
    """
    respuesta = consultar_ollama(prompt)
    return limpiar_respuesta_ollama(respuesta)



