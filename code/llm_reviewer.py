"""
LLM Reviewer — reconciles two Whisper transcription hypotheses into one final
corrected transcript using a Databricks-served model.

Usage:
    reviewer = LLMReviewer(
        base_url="https://<workspace>.azuredatabricks.net/serving-endpoints",
        model="system.ai.claude-opus-4-8",
    )
    final = reviewer.review(hypothesis_a, hypothesis_b, glossary="Lina, Compensar, pignoración")
"""

import re
import os
from difflib import SequenceMatcher
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


# ─── Similarity helper ───────────────────────────────────────────────────────

def _similarity(a: str, b: str) -> float:
    """Return a 0–1 similarity ratio between two strings (Levenshtein-inspired)."""
    if not a and not b:
        return 1.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


# ─── Prompt builder ──────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """Eres un corrector especializado en transcripciones de llamadas de servicio al cliente en español colombiano.

Tu tarea es reconciliar dos transcripciones automáticas del mismo audio (generadas con parámetros distintos) y producir una única transcripción final corregida.

Reglas:
1. Prioriza los NOMBRES PROPIOS y TÉRMINOS TÉCNICOS que aparezcan en el glosario proporcionado.
2. Cuando las dos hipótesis difieran, elige la que tenga más sentido semántico en el contexto de una llamada de servicio al cliente.
3. Corrige errores fonéticos obvios (p. ej. "Sábanas" cuando claramente es un nombre de persona "Sandra").
4. NO inventes información que no esté en ninguna de las dos hipótesis.
5. NO agregues comentarios, encabezados ni explicaciones. Devuelve únicamente el texto de la transcripción corregida.
6. Mantén el formato de turnos si las hipótesis usan etiquetas AGENTE/CLIENTE."""


def _build_user_prompt(hypothesis_a: str, hypothesis_b: str, glossary: str) -> str:
    parts = []
    if glossary.strip():
        parts.append(f"GLOSARIO DEL DOMINIO:\n{glossary.strip()}\n")
    parts.append(f"HIPÓTESIS A:\n{hypothesis_a}\n")
    parts.append(f"HIPÓTESIS B:\n{hypothesis_b}\n")
    parts.append("TRANSCRIPCIÓN FINAL CORREGIDA:")
    return "\n".join(parts)


# ─── LLMReviewer ─────────────────────────────────────────────────────────────

class LLMReviewer:
    """
    Sends two transcription hypotheses to a Databricks-served model and returns
    a single reconciled transcript.

    Args:
        base_url: Databricks serving endpoint. Defaults to DATABRICKS_BASE_URL.
        model:    Databricks-served model name. Defaults to DATABRICKS_MODEL.
        api_key:  Databricks token. Defaults to DATABRICKS_TOKEN.
        similarity_threshold: If both hypotheses are this similar (0–1), skip
                  the LLM call and return hypothesis_a directly. Default 0.95.
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        similarity_threshold: float = 0.95,
    ):
        self.base_url = (base_url or os.environ.get(
            "DATABRICKS_BASE_URL",
            "https://adb-2549848299256377.17.azuredatabricks.net/serving-endpoints",
        )).rstrip("/")
        self.model = model or os.environ.get("DATABRICKS_MODEL", "system.ai.claude-opus-4-8")
        self.api_key = api_key or os.environ.get("DATABRICKS_TOKEN", "")
        self.similarity_threshold = similarity_threshold
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url or None)

    # ── Public API ───────────────────────────────────────────────────────────

    def review(
        self,
        hypothesis_a: str,
        hypothesis_b: str,
        glossary: str = "",
    ) -> str:
        """
        Reconcile two transcription hypotheses.

        Returns the corrected final transcription string.
        If hypotheses are very similar or if Databricks is unreachable, falls back
        to hypothesis_a with a descriptive note appended.
        """
        # Fast path: hypotheses are nearly identical — no LLM call needed.
        sim = _similarity(hypothesis_a, hypothesis_b)
        if sim >= self.similarity_threshold:
            return hypothesis_a

        user_prompt = _build_user_prompt(hypothesis_a, hypothesis_b, glossary)
        try:
            return self._call_databricks(user_prompt)
        except Exception as exc:
            # Degrade gracefully: return hypothesis_a and annotate the failure.
            return hypothesis_a + f"\n\n[Revisión LLM no disponible: {exc}]"

    def is_available(self) -> tuple[bool, str]:
        """
        Check whether the Databricks client is configured.

        Returns:
            (ok: bool, message: str)
        """
        if not self.api_key:
            return False, "Falta DATABRICKS_TOKEN. Configúralo como variable de entorno."
        if not self.base_url:
            return False, "Falta DATABRICKS_BASE_URL. Configura el endpoint de Databricks."
        if not self.model:
            return False, "Falta DATABRICKS_MODEL. Configura el nombre del modelo servido."
        return True, f"Databricks configurado — modelo '{self.model}' listo para consultar."

    # ── Internal ─────────────────────────────────────────────────────────────

    def _call_databricks(self, user_prompt: str) -> str:
        """Call Databricks' OpenAI-compatible chat completions endpoint."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=4096,
        )
        content = (response.choices[0].message.content or "").strip()
        if not content:
            raise ValueError("Databricks devolvió una respuesta vacía.")

        # Strip any accidental preamble the model may add before the transcript
        content = re.sub(r"^(TRANSCRIPCI[OÓ]N FINAL CORREGIDA\s*:?\s*)", "", content, flags=re.IGNORECASE)
        return content.strip()
