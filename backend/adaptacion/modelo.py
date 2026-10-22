"""Modelo de scikit-learn que decide si subir, mantener o bajar la dificultad."""

import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from django.conf import settings
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split

from . import simulacion
from .caracteristicas import NOMBRES

log = logging.getLogger(__name__)
ETIQUETAS = {-1: "bajar", 0: "mantener", 1: "subir"}


def _nuevo_clasificador(semilla):
    # Bosque poco profundo: suficiente para 7 variables y estable ante el ruido.
    return RandomForestClassifier(
        n_estimators=150,
        max_depth=8,
        min_samples_leaf=5,
        class_weight="balanced",
        random_state=semilla,
        n_jobs=-1,
    )


def entrenar(muestras=6000, semilla=42):
    X, y = simulacion.generar(muestras, semilla)
    X_entr, X_prueba, y_entr, y_prueba = train_test_split(
        X, y, test_size=0.2, random_state=semilla, stratify=y
    )
    modelo = _nuevo_clasificador(semilla).fit(X_entr, y_entr)
    predicho = modelo.predict(X_prueba)
    validacion = cross_val_score(
        _nuevo_clasificador(semilla), X, y,
        cv=StratifiedKFold(5, shuffle=True, random_state=semilla), scoring="f1_macro",
    )
    modelo.n_jobs = 1  # en producción predice una sesión a la vez

    clases = [ETIQUETAS[c] for c in modelo.classes_]
    info = {
        "entrenado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "algoritmo": "RandomForestClassifier (scikit-learn)",
        "datos": "sintéticos (simulador de sesiones)",
        "muestras": int(len(y)),
        "distribucion": {ETIQUETAS[c]: int((y == c).sum()) for c in modelo.classes_},
        "metricas": {
            "exactitud": round(float(accuracy_score(y_prueba, predicho)), 3),
            "f1_macro": round(float(f1_score(y_prueba, predicho, average="macro")), 3),
            "f1_macro_validacion_cruzada": round(float(validacion.mean()), 3),
        },
        "matriz_confusion": {"clases": clases, "valores": confusion_matrix(y_prueba, predicho).tolist()},
        "reporte": classification_report(y_prueba, predicho, target_names=clases, zero_division=0),
        "importancias": {
            nombre: round(float(valor), 3)
            for nombre, valor in sorted(zip(NOMBRES, modelo.feature_importances_), key=lambda par: -par[1])
        },
    }
    return modelo, info


def ruta_modelo():
    return Path(settings.ADAPTACION_MODELO)


def guardar(modelo, info, destino=None):
    destino = Path(destino or ruta_modelo())
    destino.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"modelo": modelo, "info": info}, destino)
    return destino


_cache = {"clave": None, "paquete": None}
_candado = threading.Lock()


def cargar():
    """Carga el modelo una vez y lo recarga solo si el archivo cambió."""
    ruta = ruta_modelo()
    if not ruta.exists():
        return None
    clave = (str(ruta), ruta.stat().st_mtime)
    with _candado:
        if _cache["clave"] != clave:
            _cache["paquete"] = joblib.load(ruta)
            _cache["clave"] = clave
        return _cache["paquete"]


def info_modelo():
    paquete = cargar()
    return paquete["info"] if paquete else None


def predecir(caracteristicas):
    """Devuelve (ajuste, confianza) o None si no hay modelo entrenado."""
    paquete = cargar()
    if paquete is None:
        return None
    modelo = paquete["modelo"]
    probabilidades = modelo.predict_proba(np.array([caracteristicas]))[0]
    mejor = int(probabilidades.argmax())
    return int(modelo.classes_[mejor]), float(probabilidades[mejor])
