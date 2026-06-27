"""Paquete de schemas (marshmallow) para validacion y serializacion.

Centraliza la carga/descarga de cada recurso de la API garantizando:
    - Validacion estricta de tipos y formatos en el entrada.
    - Salidas JSON consistentes (sin datos sensibles).
    - Mensajes de error claros para el frontend.
"""

from __future__ import annotations
