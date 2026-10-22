from pathlib import Path

from PIL import Image
from rest_framework.exceptions import ValidationError

from .models import TipoContenido

EXTENSIONES = {
    ".jpg": TipoContenido.IMAGEN,
    ".jpeg": TipoContenido.IMAGEN,
    ".png": TipoContenido.IMAGEN,
    ".mp3": TipoContenido.AUDIO,
}
FORMATOS_IMAGEN = {"JPEG", "PNG"}
TAMANO_MAXIMO = 10 * 1024 * 1024  # 10 MB


def _formato_no_permitido(nombre):
    return ValidationError(
        f"«{nombre}» no se pudo subir. Este formato no está permitido. "
        "Usa una foto JPG o PNG, o un audio MP3.",
        code="formato_no_permitido",
    )


def _es_mp3(cabecera):
    # Etiqueta ID3 o, sin etiqueta, un encabezado de trama MPEG (11 bits en 1).
    return cabecera[:3] == b"ID3" or (
        len(cabecera) >= 2 and cabecera[0] == 0xFF and cabecera[1] & 0xE0 == 0xE0
    )


def validar_archivo(archivo):
    """Comprueba extensión, tamaño y contenido real. Devuelve el TipoContenido."""
    nombre = Path(archivo.name).name
    tipo = EXTENSIONES.get(Path(nombre).suffix.lower())
    if tipo is None:
        raise _formato_no_permitido(nombre)
    if archivo.size > TAMANO_MAXIMO:
        raise ValidationError(
            f"«{nombre}» pesa más de 10 MB. Elige un archivo más liviano.",
            code="archivo_muy_grande",
        )

    # No basta con la extensión: un PDF renombrado a .jpg también debe rechazarse.
    archivo.seek(0)
    if tipo == TipoContenido.IMAGEN:
        try:
            with Image.open(archivo) as imagen:
                formato = imagen.format
                imagen.verify()
        except Exception:
            raise _formato_no_permitido(nombre)
        if formato not in FORMATOS_IMAGEN:
            raise _formato_no_permitido(nombre)
    elif not _es_mp3(archivo.read(3)):
        raise _formato_no_permitido(nombre)
    archivo.seek(0)
    return tipo
