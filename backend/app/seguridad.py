"""Autenticación: contraseñas con Argon2, sesión con JWT en cookie httpOnly.

- La cookie es httpOnly (JavaScript no puede leerla), SameSite=Lax y Secure en producción.
- Tras 5 intentos fallidos la cuenta se bloquea 15 minutos.
- Los mensajes de error no revelan si el usuario existe.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from .config import config
from .db import escritura

COOKIE = "faro_sesion"
ALGORITMO = "HS256"
MAX_INTENTOS = 5
BLOQUEO = timedelta(minutes=15)

_hasher = PasswordHasher()
# Hash fijo para comparar cuando el usuario no existe: el tiempo de respuesta es el mismo
# exista o no el usuario (evita adivinar usuarios midiendo tiempos).
_HASH_FICTICIO = _hasher.hash("contraseña-ficticia-para-igualar-tiempos")


class Usuario(BaseModel):
    usuario: str
    nombre: str
    rol: str


class CuentaBloqueada(Exception):
    """La cuenta superó el máximo de intentos fallidos."""


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def _verificar(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def autenticar(usuario: str, password: str) -> Usuario | None:
    """Devuelve el usuario si las credenciales son correctas. Lleva el control de intentos."""
    with escritura() as conn:
        fila = conn.execute(
            "SELECT usuario, nombre, rol, password_hash, activo, bloqueado_hasta "
            "FROM app.usuario WHERE usuario = %s FOR UPDATE",
            (usuario,),
        ).fetchone()
        if fila is None or not fila["activo"]:
            _verificar(_HASH_FICTICIO, password)
            return None
        if fila["bloqueado_hasta"] and fila["bloqueado_hasta"] > datetime.now(UTC):
            raise CuentaBloqueada
        if not _verificar(fila["password_hash"], password):
            conn.execute(
                "UPDATE app.usuario SET intentos_fallidos = intentos_fallidos + 1, "
                "bloqueado_hasta = CASE WHEN intentos_fallidos + 1 >= %s "
                "  THEN now() + %s ELSE NULL END WHERE usuario = %s",
                (MAX_INTENTOS, BLOQUEO, usuario),
            )
            return None
        conn.execute(
            "UPDATE app.usuario SET intentos_fallidos = 0, bloqueado_hasta = NULL, "
            "ultimo_acceso = now() WHERE usuario = %s",
            (usuario,),
        )
        return Usuario(usuario=fila["usuario"], nombre=fila["nombre"], rol=fila["rol"])


def abrir_sesion(respuesta: Response, u: Usuario) -> None:
    cfg = config()
    ahora = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": u.usuario,
            "nombre": u.nombre,
            "rol": u.rol,
            "iat": ahora,
            "exp": ahora + timedelta(minutes=cfg.jwt_minutos),
        },
        cfg.jwt_secret,
        algorithm=ALGORITMO,
    )
    respuesta.set_cookie(
        COOKIE,
        token,
        max_age=cfg.jwt_minutos * 60,
        httponly=True,
        secure=cfg.cookie_segura,
        samesite="lax",
        path="/",
    )


def cerrar_sesion(respuesta: Response) -> None:
    respuesta.delete_cookie(COOKIE, path="/")


def usuario_actual(request: Request) -> Usuario:
    """Dependencia: exige una sesión válida (cookie o encabezado Authorization: Bearer)."""
    token = request.cookies.get(COOKIE)
    encabezado = request.headers.get("authorization", "")
    if not token and encabezado.lower().startswith("bearer "):
        token = encabezado[7:]
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Inicia sesión para continuar")
    try:
        datos = jwt.decode(token, config().jwt_secret, algorithms=[ALGORITMO])
    except jwt.PyJWTError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "La sesión expiró o no es válida"
        ) from None
    return Usuario(usuario=datos["sub"], nombre=datos["nombre"], rol=datos["rol"])


UsuarioActual = Annotated[Usuario, Depends(usuario_actual)]
