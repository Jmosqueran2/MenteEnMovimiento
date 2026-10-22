# Mente en Movimiento

Sistema de estimulación cognitiva y neuromotora para adultos mayores, controlado
con gestos frente a la cámara web.

| Componente | Tecnología | Carpeta |
|---|---|---|
| API principal | Django + Django REST Framework + JWT | `backend/` |
| Microservicio de visión | FastAPI + OpenCV + MediaPipe + YOLOv8-Pose | `vision_service/` |
| Frontend | React + Vite | `frontend/` |
| Nube | AWS EC2 + RDS PostgreSQL + S3 | `deploy/` *(fase 5)* |

## Backend: puesta en marcha local

Requisitos: Python 3.11 o superior.

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env            # Linux/Mac: cp
python manage.py migrate
python manage.py cargar_datos --demo
python manage.py entrenar_modelo  # modelo de dificultad adaptativa (~10 s)
python manage.py createsuperuser  # opcional, para entrar a /admin
python manage.py runserver
```

`cargar_datos --demo` crea el banco de 72 preguntas, el usuario **cuidador**
(clave `MenteEnMovimiento2026`), a Rosa Pérez, 4 fotos de ejemplo de Mi Historia
y 5 sesiones de ejemplo de la última semana.

Pruebas: `python manage.py test`

## API

Todas las rutas (salvo el token) requieren `Authorization: Bearer <access>`.

| Método | Ruta | Uso (pantalla del prototipo) |
|---|---|---|
| POST | `/api/auth/token/` | Inicio de sesión del cuidador `{username, password}` |
| POST | `/api/auth/token/refresh/` | Renovar token |
| GET | `/api/auth/yo/` | Cuidador y personas a su cargo |
| GET/POST/PATCH | `/api/pacientes/` | Perfil, nivel, tiempo de permanencia, actividades habilitadas (11) |
| GET | `/api/pacientes/{id}/resumen/` | Tarjetas del panel del cuidador (11) |
| GET | `/api/pacientes/{id}/seguimiento/?dias=7` | Indicadores y gráfica (15) |
| GET | `/api/pacientes/{id}/seguimiento-csv/` | Exportar CSV (15) |
| GET/POST/PATCH/DELETE | `/api/historia/?paciente={id}` | Fotos y audios de Mi Historia, multipart (12, 13, 14) |
| POST | `/api/sesiones/` | Iniciar actividad `{paciente, tipo}` → 8 preguntas (05) |
| POST | `/api/sesiones/{id}/responder/` | `{indice_pregunta, opcion, tiempo_ms}` → acierto o pista (06, 07) |
| POST | `/api/sesiones/{id}/finalizar/` | `{cancelada?}` → resumen y nivel siguiente (08) |

`tipo` ∈ `memoria`, `atencion`, `coordinacion`, `historia`.

### Reglas importantes
- La respuesta correcta nunca se envía al iniciar; se revela al responder.
- Acierto = pregunta resuelta en el primer intento. Máximo 3 intentos por pregunta.
- Al finalizar, el nivel se ajusta solo con el modelo de scikit-learn (ver abajo);
  si el modelo no está entrenado se usan reglas fijas (≥80 % y ≤6 s sube; <50 % baja).
- Mi Historia acepta solo JPG, PNG o MP3 de hasta 10 MB y revisa el contenido
  real del archivo (un PDF renombrado a .jpg se rechaza).
- Una actividad deshabilitada por el cuidador no se puede iniciar.

## Microservicio de visión: puesta en marcha local

```bash
cd vision_service
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
python arreglar_opencv.py         # deja un solo paquete de OpenCV
python descargar_modelos.py       # MediaPipe Hands + YOLOv8n-pose (~14 MB)
copy .env.example .env
uvicorn app.main:app --port 8001 --env-file .env
```

Página de prueba con tu cámara: http://localhost:8001 · Pruebas: `python -m pytest`

### Qué hace cada librería
| Librería | Uso |
|---|---|
| **OpenCV** | Decodifica el JPEG, aplica espejo, mide luz (poca luz / contraluz) |
| **MediaPipe Hands** | 21 puntos de la mano → cursor (centro de la palma) y gesto (abierta, cerrada, apunta, pinza) |
| **YOLOv8n-Pose** | 17 puntos del cuerpo → presencia, rostro visible, distancia, centrado, calibración y brazos estirados (Coordinación) |
| **Filtro One Euro** | Suaviza el cursor para que el temblor no provoque selecciones involuntarias |

### Protocolo WebSocket `/ws/vision?token=<access JWT>`
El navegador envía frames JPEG binarios (320×240) y uno nuevo solo al recibir
la respuesta del anterior. Mensajes de control en texto JSON:
`{"accion":"config","modo":"seleccion"|"coordinacion","espejo":true}` y `{"accion":"calibrar"}`.

Respuesta por frame:
```json
{
  "tipo": "estado", "frame": 42, "ms": 33,
  "cursor": {"x": 0.41, "y": 0.63},
  "mano": {"detectada": true, "gesto": "abierta", "lado": "derecha"},
  "luz": {"nivel": 112, "estado": "ok"},
  "postura": {"persona": true, "rostro_visible": true, "distancia": "ok", "centrado": true,
              "hombros_nivelados": true,
              "brazos": {"izquierdo": {"angulo_codo": 168, "extendido": true, "levantado": false}}},
  "calibracion": {"estado": "completa", "progreso": 1.0, "zona": {"x0": 0.2, "x1": 0.8, "y0": 0.1, "y1": 0.7}},
  "alertas": []
}
```
`alertas` ⊂ `poca_luz`, `contraluz`, `sin_persona`, `rostro_no_visible`, `muy_lejos`,
`muy_cerca`, `descentrado`. La desconexión de la cámara la detecta el navegador.

**Privacidad:** cada frame se analiza en memoria y se descarta; nada se guarda
ni se reenvía. Solo vuelven números al navegador.

**Autenticación:** con `VISION_JWT_SECRETO` igual a `DJANGO_SECRET_KEY`, el
servicio acepta los mismos tokens que emite el backend.

## Frontend: puesta en marcha local

Requisitos: Node.js 20 o superior. Con el backend (puerto 8000) y la visión
(puerto 8001) encendidos:

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

Vite reenvía `/api` y `/media` a Django y `/ws` al microservicio, así que todo
funciona desde un solo origen, igual que en producción.

### Recorridos
- **Cuidador:** `/login` → panel (11) → Mi Historia (12–14) → Seguimiento (15) → Configuración.
- **Adulto mayor:** "Ver como Rosa" → consentimiento (01/02) → detección y calibración (03)
  → menú (04) → actividad (05–07) → resumen (08). Las pantallas 09 (poca luz) y 10
  (cámara o conexión perdida) aparecen como capa sobre cualquier pantalla.

### Selección por permanencia
Todo elemento con `data-elegible` se pulsa al dejar el cursor encima el tiempo
configurado (1,5 / 2 / 2,5 s). Después de elegir hay que mover la mano para
volver a elegir, así un botón que aparece debajo de la mano no se pulsa solo.

En **Configuración → Control → Mouse (pruebas)** el cursor sigue al mouse en vez
de a la mano, útil para probar sin cámara.

### Ajustes de la prueba de usabilidad incluidos
Actividades deshabilitadas ocultas en el menú · tiempo de permanencia
configurable · narración por voz · aviso de cambios sin guardar · "Actividades
de hoy: X de 2 completadas" · texto mínimo de 24 px en las pantallas del adulto
mayor · botón secundario más diferenciado.

## Dificultad adaptativa con scikit-learn

Al terminar cada sesión, un `RandomForestClassifier` decide si en la próxima
sesión se **sube, mantiene o baja** el nivel (`backend/adaptacion/`).

| Variable | Qué mide |
|---|---|
| `tasa_aciertos` | Preguntas resueltas al primer intento |
| `tasa_reintentos` | Resueltas después de equivocarse (con pista) |
| `tasa_agotadas` | Sin resolver tras 3 intentos |
| `tiempo_promedio_s` | Velocidad de respuesta (componente motor) |
| `media_reciente` | Aciertos promedio de las 3 sesiones anteriores |
| `sesiones_previas` | Cuánto historial hay |
| `nivel` | Nivel en el que se jugó |

**Datos de entrenamiento.** Aún no hay sesiones reales suficientes, así que
`adaptacion/simulacion.py` simula 6000 sesiones de adultos mayores con distinta
capacidad y velocidad, y las etiqueta con una política experta (desempeño actual
+ historial + reintentos + velocidad), con un 5 % de ruido que imita
desacuerdos entre terapeutas. Cuando existan sesiones reales revisadas por un
profesional, se reentrena con ellas sin cambiar el resto del sistema.

**Resultados** (`python manage.py entrenar_modelo`): exactitud 94,3 %, F1 macro
0,933 en validación cruzada de 5 pliegues. Variables más influyentes: aciertos,
tiempo de respuesta e historial reciente.

**Seguridad.** El modelo nunca salta más de un nivel, nunca sube con menos de
60 % de aciertos y nunca baja con 85 % o más. Si el archivo del modelo falta o
falla, se usan las reglas fijas. Cada sesión guarda la decisión, el método
(modelo/reglas) y la confianza; el cuidador la ve en su panel y puede cambiar
el nivel a mano. `GET /api/adaptacion/modelo/` devuelve métricas e importancias.
