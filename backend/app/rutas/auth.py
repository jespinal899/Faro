"""Inicio y cierre de sesión."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from backend.app.seguridad import (
    CuentaBloqueada,
    Usuario,
    UsuarioActual,
    abrir_sesion,
    autenticar,
    cerrar_sesion,
)

router = APIRouter(prefix="/auth", tags=["Autenticación"])


class Credenciales(BaseModel):
    usuario: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=1, max_length=200)


@router.post("/login", response_model=Usuario, summary="Iniciar sesión")
def login(credenciales: Credenciales, respuesta: Response) -> Usuario:
    try:
        u = autenticar(credenciales.usuario.strip().lower(), credenciales.password)
    except CuentaBloqueada:
        raise HTTPException(
            status.HTTP_423_LOCKED,
            "Cuenta bloqueada por intentos fallidos. Intenta de nuevo en 15 minutos.",
        ) from None
    if u is None:
        # Mismo mensaje exista o no el usuario
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario o contraseña incorrectos")
    abrir_sesion(respuesta, u)
    return u


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Cerrar sesión")
def logout(respuesta: Response) -> None:
    cerrar_sesion(respuesta)


@router.get("/me", response_model=Usuario, summary="Usuario de la sesión actual")
def me(usuario: UsuarioActual) -> Usuario:
    return usuario
