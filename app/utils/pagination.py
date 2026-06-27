"""Helpers de paginacion para endpoints de listado.

Centraliza el parseo de parametros `page` y `per_page` y la construccion
del cuerpo de respuesta paginada para mantener una API consistente.
"""

from __future__ import annotations

from typing import Any

from flask import request
from flask_sqlalchemy.pagination import Pagination

from app.config import BaseConfig


def parse_pagination() -> tuple[int, int]:
    """Lee `page` y `per_page` de la query string con saneamiento.

    Returns:
        Tupla (page, per_page) acotados a limites seguros.
    """
    try:
        page: int = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1

    try:
        per_page: int = int(request.args.get("per_page", BaseConfig.DEFAULT_PAGE_SIZE))
    except (TypeError, ValueError):
        per_page = BaseConfig.DEFAULT_PAGE_SIZE

    per_page = max(1, min(per_page, BaseConfig.MAX_PAGE_SIZE))
    return page, per_page


def paginate_to_dict(
    pagination: Pagination, items_serializer: Any
) -> dict[str, Any]:
    """Serializa un objeto Pagination de Flask-SQLAlchemy a un dict.

    Args:
        pagination: Resultado de `Model.query.paginate(...)`.
        items_serializer: Schema de marshmallow o callable que recibe la
            lista de items y retorna su representacion serializada.

    Returns:
        Estructura { items, meta } lista para responder como JSON.
    """
    if callable(items_serializer):
        items: Any = items_serializer(pagination.items)
    else:
        # marshmallow Schema con many=True
        items = items_serializer.dump(pagination.items)

    return {
        "items": items,
        "meta": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev,
        },
    }
