"""Modelo base y mixins reutilizables para todos los modelos del dominio.

`BaseModel` hereda de `db.Model` (Flask-SQLAlchemy) para que todas las tablas
se registren en el mismo metadata que `db.create_all()` y Flask-Migrate
inspeccionan. Soporta el estilo tipado de SQLAlchemy 2.0 (Mapped/mapped_column).

Proporciona:
    - TimestampMixin: campos created_at / updated_at con actualizacion
      automatica.
    - BaseModel: clase base con utilidades comunes (repr, to_dict, save).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class TimestampMixin:
    """Mixin que anade marcas de tiempo de creacion y actualizacion.

    Usa zona horaria UTC para evitar ambiguedades con horarios de verano
    en deployments multi-region (Dokploy puede correr en cualquier TZ).
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class BaseModel(db.Model, TimestampMixin):
    """Clase base abstracta con utilidades comunes a todos los modelos.

    Hereda de `db.Model` (Flask-SQLAlchemy) para registrarse en el metadata
    unico que gestiona `db.create_all()` y Alembic.

    Attributes:
        id: Llave primaria autoincremental.
        created_at: Fecha de creacion (UTC).
        updated_at: Fecha de ultima modificacion (UTC).
    """

    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ---- Representacion ----
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={getattr(self, 'id', None)}>"

    # ---- Serializacion ----
    def to_dict(self, exclude: set[str] | None = None) -> dict[str, Any]:
        """Serializa el modelo a un diccionario.

        Args:
            exclude: Conjunto de nombres de columna a omitir (ej: password_hash).

        Returns:
            dict con las columnas y sus valores serializables.
        """
        exclude = exclude or set()
        result: dict[str, Any] = {}
        for column in self.__table__.columns:
            if column.name in exclude:
                continue
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            elif hasattr(value, "value"):
                # Enums de Python
                value = value.value
            result[column.name] = value
        return result

    # ---- Persistencia ----
    def save(self, commit: bool = True) -> "BaseModel":
        """Guarda la instancia en la sesion y opcionalmente hace commit."""
        db.session.add(self)
        if commit:
            db.session.commit()
        return self

    def delete(self, commit: bool = True) -> None:
        """Elimina la instancia de la base de datos."""
        db.session.delete(self)
        if commit:
            db.session.commit()

    @classmethod
    def get_by_id(cls, item_id: int) -> "BaseModel | None":
        """Busca un registro por su llave primaria."""
        return db.session.get(cls, item_id)
