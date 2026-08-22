"""
Script para transcribir audios de llamadas de servicio al cliente.
Usa faster-whisper local con preprocesamiento de audio vía ffmpeg.

Instalación:
    pip install faster-whisper python-dotenv

El modelo Whisper se descarga en el primer uso y puede configurarse mediante variables de entorno.
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional

from audio_utils import format_transcription_output, transcribe_audio_file


def _configure_ffmpeg_path() -> None:
    """Make ffmpeg discoverable when Windows apps do not inherit the user PATH."""
    if os.name != "nt" or shutil.which("ffmpeg"):
        return

    candidates = []
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.extend(
            Path(local_app_data).glob(
                r"Microsoft\WinGet\Packages\Gyan.FFmpeg_*\ffmpeg-*\bin"
            )
        )

    program_files = [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")]
    for root in [p for p in program_files if p]:
        candidates.extend(Path(root).glob(r"ffmpeg*\bin"))

    for bin_dir in candidates:
        if (bin_dir / "ffmpeg.exe").exists():
            os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"
            return


_configure_ffmpeg_path()

# Carpeta de salida por defecto: records/ en la raíz del proyecto
DEFAULT_RECORDS_DIR = Path(__file__).resolve().parents[1] / "records"


def transcribir_audio(
    ruta_audio: str,
    guardar_txt: bool = True,
    carpeta_salida: Optional[str] = None,
    preprocesar: bool = True,
    initial_prompt: str = "",
) -> dict:
    """
    Transcribe un archivo de audio a texto.

    Args:
        ruta_audio:      Ruta al archivo de audio (.wav, .mp3, .m4a, .ogg, .flac).
        guardar_txt:     Si True, guarda la transcripción en archivo .txt.
        carpeta_salida:  Carpeta destino del .txt (default: records/ junto al script).
        preprocesar:     Aplica normalización de volumen, limpieza de silencio y
                         conversión a 16 kHz mono antes de transcribir.
        initial_prompt:  Vocabulario o contexto del dominio para mejorar el
                         reconocimiento de términos específicos.

    Returns:
        Diccionario con la transcripción y metadatos.
    """
    print(f"Transcribiendo: {ruta_audio}")
    resultado = transcribe_audio_file(
        ruta_audio,
        initial_prompt=initial_prompt,
        enable_preprocess=preprocesar,
    )

    transcripcion = {
        "archivo": os.path.basename(ruta_audio),
        "texto": format_transcription_output(
            os.path.basename(ruta_audio), resultado["text"]
        ),
        "segmentos": resultado["segments"],
        "idioma_detectado": resultado["language"],
        "fecha_transcripcion": datetime.now().isoformat(),
    }

    if guardar_txt:
        ruta_txt = guardar_transcripcion_txt(
            transcripcion["texto"],
            os.path.basename(ruta_audio),
            carpeta_salida=carpeta_salida,
        )
        transcripcion["archivo_txt"] = str(ruta_txt)

    return transcripcion


def guardar_transcripcion_txt(
    texto: str,
    nombre_audio: str,
    carpeta_salida: Optional[str] = None,
) -> Path:
    """
    Guarda el texto de una transcripción en un archivo .txt.

    Args:
        texto: Texto transcrito.
        nombre_audio: Nombre del archivo de audio original (solo basename).
        carpeta_salida: Carpeta destino. Si None, usa records/ junto al script.

    Returns:
        Path del archivo .txt generado.
    """
    salida = Path(carpeta_salida) if carpeta_salida else DEFAULT_RECORDS_DIR
    salida.mkdir(parents=True, exist_ok=True)

    nombre_stem = Path(nombre_audio).stem
    ruta_txt = salida / f"{nombre_stem}_transcript.txt"

    with open(ruta_txt, "w", encoding="utf-8") as f:
        f.write(texto)

    print(f"   [OK] Guardado en: {ruta_txt}")
    return ruta_txt


def generar_ruta_txt(ruta_audio: str, carpeta_salida: Optional[str] = None) -> Path:
    """
    Genera la ruta del archivo .txt de transcripción.
    audio.wav -> records/audio_transcript.txt  (o carpeta_salida si se especifica)
    """
    salida = Path(carpeta_salida) if carpeta_salida else DEFAULT_RECORDS_DIR
    salida.mkdir(parents=True, exist_ok=True)
    nombre_stem = Path(ruta_audio).stem
    return salida / f"{nombre_stem}_transcript.txt"


def transcribir_directorio(
    directorio: str,
    salida_json: str = None,
    preprocesar: bool = True,
    initial_prompt: str = "",
) -> list:
    """
    Transcribe todos los archivos WAV en un directorio.
    Cada transcripción se guarda como: nombre_transcript.txt

    Args:
        directorio:     Ruta al directorio con archivos .wav.
        salida_json:    Ruta para guardar resumen en JSON (opcional).
        preprocesar:    Preprocesar audio antes de transcribir (recomendado).
        initial_prompt: Vocabulario o contexto del dominio.

    Returns:
        Lista de transcripciones.
    """
    directorio = Path(directorio)
    archivos_wav = list(directorio.glob("*.wav")) + list(directorio.glob("*.WAV"))

    if not archivos_wav:
        print(f"No se encontraron archivos WAV en {directorio}")
        return []

    print(f"Encontrados {len(archivos_wav)} archivos WAV")

    transcripciones = []
    for i, archivo in enumerate(archivos_wav, 1):
        print(f"\n[{i}/{len(archivos_wav)}] Procesando: {archivo.name}")

        try:
            transcripcion = transcribir_audio(
                str(archivo),
                guardar_txt=True,
                preprocesar=preprocesar,
                initial_prompt=initial_prompt,
            )
            transcripciones.append(transcripcion)
            print(f"   [OK] Guardado en: {transcripcion.get('archivo_txt', 'N/A')}")

        except Exception as e:
            print(f"   [ERROR] {e}")
            transcripciones.append({
                "archivo": archivo.name,
                "error": str(e)
            })

    if salida_json:
        with open(salida_json, "w", encoding="utf-8") as f:
            json.dump(transcripciones, f, ensure_ascii=False, indent=2)
        print(f"\nResumen JSON guardado en: {salida_json}")

    print(f"\n{'='*50}")
    ok = len([t for t in transcripciones if "texto" in t])
    print(f"Transcripciones completadas: {ok}/{len(archivos_wav)}")
    print(f"Archivos .txt generados en: {directorio}")

    return transcripciones


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Transcribir audios de llamadas de servicio al cliente"
    )
    parser.add_argument(
        "entrada",
        help="Archivo de audio o directorio con archivos WAV"
    )
    parser.add_argument(
        "-o", "--salida-json",
        help="Archivo JSON para guardar resumen de resultados"
    )
    parser.add_argument(
        "--no-txt",
        action="store_true",
        help="No generar archivos .txt individuales"
    )
    parser.add_argument(
        "--no-preprocesar",
        action="store_true",
        help="Omitir el preprocesamiento de audio (normalización, limpieza de silencio)"
    )
    parser.add_argument(
        "--initial-prompt",
        default="",
        metavar="TEXTO",
        help="Vocabulario o contexto del dominio para mejorar el reconocimiento"
    )
    
    args = parser.parse_args()
    entrada = Path(args.entrada)
    preprocesar = not args.no_preprocesar
    
    if entrada.is_file():
        resultado = transcribir_audio(
            str(entrada),
            guardar_txt=not args.no_txt,
            preprocesar=preprocesar,
            initial_prompt=args.initial_prompt,
        )
        
        print("\n" + "="*50)
        print("TRANSCRIPCIÓN:")
        print("="*50)
        print(resultado["texto"])
            
        if args.salida_json:
            with open(args.salida_json, "w", encoding="utf-8") as f:
                json.dump(resultado, f, ensure_ascii=False, indent=2)
            print(f"\nResumen JSON guardado en: {args.salida_json}")
            
    elif entrada.is_dir():
        transcribir_directorio(
            str(entrada),
            args.salida_json,
            preprocesar=preprocesar,
            initial_prompt=args.initial_prompt,
        )
    else:
        print(f"Error: No se encontró '{entrada}'")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
