"""Pruebas unitarias del pronóstico (sin base de datos).

Lo que la guía exige verificar del ML: sin fuga de información futura, separación temporal
correcta, métricas bien calculadas, sin fabricar resultados para grupos sin historia.
"""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("sklearn", reason="requiere el grupo ml: uv sync --group ml")

from datos_ml import filas_sinteticas  # noqa: E402

from machine_learning.config import HISTORIA_MINIMA, PLIEGUES, SEMANAS_PLIEGUE  # noqa: E402
from machine_learning.datos import huella, preparar  # noqa: E402
from machine_learning.evaluacion import cortes, metricas, pliegue, separar  # noqa: E402
from machine_learning.modelos import ModeloPronostico  # noqa: E402
from machine_learning.variables import VARIABLES_NUMERICAS, muestras  # noqa: E402

BASES = ["base_ingenuo", "base_media_movil_4", "base_media_movil_13", "base_estacional"]


@pytest.fixture(scope="module")
def serie():
    return preparar(filas_sinteticas(), solo_reales=True)


def test_las_variables_no_usan_semanas_posteriores_al_origen(serie):
    ventas = serie.ventas
    origen = ventas.index[100]
    antes = muestras(ventas, origenes=[origen])
    # Se altera TODO lo posterior al origen: ninguna variable ni línea base puede cambiar
    alterada = ventas.copy()
    alterada.loc[alterada.index > origen] *= 3.7
    despues = muestras(alterada, origenes=[origen])

    columnas = VARIABLES_NUMERICAS + BASES
    pd.testing.assert_frame_equal(antes[columnas], despues[columnas])
    # El objetivo sí cambia (es la semana futura): la prueba detecta el futuro cuando se usa
    assert not np.allclose(antes["real"], despues["real"])


def test_lineas_base(serie):
    ventas = serie.ventas
    origen = ventas.index[100]
    m = muestras(ventas, origenes=[origen], horizontes=[2])
    fila = m[m["grupo"] == "Grande"].iloc[0]
    y = ventas["Grande"]
    assert fila["base_ingenuo"] == pytest.approx(y.iloc[100])
    assert fila["base_media_movil_4"] == pytest.approx(y.iloc[97:101].mean())
    assert fila["base_media_movil_13"] == pytest.approx(y.iloc[88:101].mean())
    assert fila["base_estacional"] == pytest.approx(y.iloc[100 + 2 - 52])
    assert fila["semana"] == origen + pd.Timedelta(weeks=2)


def test_separacion_temporal_sin_solape(serie):
    todas = muestras(serie.ventas)
    c = cortes(todas)
    desarrollo, prueba = separar(todas, c)

    assert desarrollo["semana"].max() < c.prueba <= prueba["semana"].min()
    assert len(c.pliegues) == PLIEGUES
    for (inicio, fin), siguiente in zip(
        c.pliegues, c.pliegues[1:] + ((c.prueba, None),), strict=True
    ):
        entrenamiento, validacion = pliegue(desarrollo, inicio, fin)
        # El modelo de cada pliegue no ve ninguna semana del pliegue ni posterior
        assert entrenamiento["semana"].max() < inicio
        assert entrenamiento["origen"].max() < inicio
        assert validacion["semana"].between(inicio, fin - pd.Timedelta(days=1)).all()
        assert fin == siguiente[0]  # pliegues contiguos que terminan donde empieza la prueba
    assert (c.prueba - c.validacion).days == 7 * PLIEGUES * SEMANAS_PLIEGUE


def test_metricas():
    m = metricas([100, 200], [110, 180])
    assert m["mae"] == pytest.approx(15)
    assert m["rmse"] == pytest.approx(np.sqrt((100 + 400) / 2))
    assert m["wape"] == pytest.approx(10)  # 30 / 300
    assert m["sesgo"] == pytest.approx(-10 / 3)  # se queda corto
    assert m["smape"] == pytest.approx(100 * (20 / 210 + 40 / 380) / 2)


def test_grupos_sin_historia_suficiente_se_excluyen_con_motivo(serie):
    assert list(serie.ventas.columns) == ["Chico", "Grande", "Mediano"]
    assert "Nuevo" in serie.excluidos
    assert f"mínimo {HISTORIA_MINIMA}" in serie.excluidos["Nuevo"]


def test_solo_semanas_completas_y_huecos_como_cero():
    filas = filas_sinteticas(semanas=120, grupo_corto=None)
    # Última semana a medias (termina el miércoles) y una semana sin ventas de "Chico"
    ultima = filas["semana"].max()
    filas.loc[filas["semana"] == ultima, ["ultima_fecha", "ultima_fecha_real"]] = (
        ultima + pd.Timedelta(days=2)
    )
    hueco = filas["semana"].unique()[50]
    filas = filas[~((filas["grupo"] == "Chico") & (filas["semana"] == hueco))]

    s = preparar(filas, solo_reales=True)
    assert s.hasta == ultima - pd.Timedelta(weeks=1)
    assert s.ventas.loc[hueco, "Chico"] == 0.0
    assert not s.ventas.isna().any().any()


def test_entrenar_solo_con_reales_y_predecir_con_todo():
    filas = filas_sinteticas(semanas=130, semanas_simuladas=4)
    reales = preparar(filas, solo_reales=True)
    todo = preparar(filas, solo_reales=False)
    assert reales.hasta == todo.hasta - pd.Timedelta(weeks=4)
    assert not reales.incluye_simulados and todo.incluye_simulados
    assert huella(reales.ventas) != huella(todo.ventas)


def test_modelo_serializado_predice_igual_y_el_rango_contiene_al_pronostico(serie):
    todas = muestras(serie.ventas)
    config = {"algoritmo": "ridge", "variables": "rezagos", "alpha": 10.0}
    modelo = ModeloPronostico.entrenar(config, todas)
    modelo.calibrar(todas, modelo.predecir(todas))
    copia = ModeloPronostico.desde_bytes(modelo.a_bytes())

    futuro = muestras(serie.ventas, origenes=[serie.hasta], con_objetivo=False)
    pronostico = modelo.predecir(futuro)
    np.testing.assert_allclose(copia.predecir(futuro), pronostico)
    inferior, superior = copia.rango(futuro, pronostico)
    assert (pronostico >= 0).all()
    assert (inferior <= pronostico).all() and (pronostico <= superior).all()
    assert len(futuro) == 4 * len(serie.ventas.columns)  # 4 semanas por grupo


def test_con_historia_insuficiente_falla_con_un_mensaje_claro(monkeypatch):
    import machine_learning.entrenar as modulo

    corta = filas_sinteticas(semanas=130, grupo_corto=None)
    monkeypatch.setattr(modulo, "leer", lambda conn: corta)
    with pytest.raises(ValueError, match="Historia insuficiente"):
        modulo.entrenar(None, guardar=False)
