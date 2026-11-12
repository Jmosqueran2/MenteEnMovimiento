# Mente en Movimiento

Sistema de estimulación cognitiva y neuromotora para adultos mayores, controlado
con gestos frente a la cámara web.

| Componente | Tecnología | Carpeta |
|---|---|---|
| API principal | Django + Django REST Framework + JWT | `backend/` |
| Microservicio de visión | FastAPI + OpenCV + MediaPipe + YOLOv8-Pose | `vision_service/` |
| Frontend | React + Vite | `frontend/` |
| Nube | AWS EC2 + RDS PostgreSQL + S3 (HTTPS con Caddy) | `deploy/` — ver [deploy/GUIA.md](deploy/GUIA.md) |

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

`cargar_datos --demo` crea el banco de 159 preguntas, el usuario **cuidador**
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
python descargar_modelos.py       # MediaPipe Hands + Face + YOLOv8n-pose (~18 MB)
copy .env.example .env
uvicorn app.main:app --port 8001 --env-file .env
```

Página de prueba con tu cámara: http://localhost:8001 · Pruebas: `python -m pytest`

### Qué hace cada librería
| Librería | Uso |
|---|---|
| **OpenCV** | Decodifica el JPEG, aplica espejo, mide luz (poca luz / contraluz) |
| **MediaPipe Hands** | 21 puntos de la mano → cursor (centro de la palma) y gesto (abierta, cerrada, apunta, pinza) |
| **MediaPipe Face Landmarker** | 478 puntos de la cara con iris → cursor con la mirada (cabeza + ojos) |
| **YOLOv8n-Pose** | 17 puntos del cuerpo → presencia, rostro visible, distancia, centrado, calibración y brazos estirados (Coordinación) |
| **Filtro One Euro** | Suaviza el cursor para que el temblor no provoque selecciones involuntarias |

### Protocolo WebSocket `/ws/vision?token=<access JWT>`
El navegador envía frames JPEG binarios (320×240) y uno nuevo solo al recibir
la respuesta del anterior. Mensajes de control en texto JSON:
`{"accion":"config","modo":"seleccion"|"coordinacion","espejo":true,"puntero":"mano"|"mirada","movilidad":"completa"|…}` y `{"accion":"calibrar"}`.

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

### Cursor con la mirada
Para quien se cansa de tener el brazo levantado: en **Configuración → Mover el
cursor con → La mirada** el cursor sigue hacia dónde mira la persona.

- Una cámara web común no ve el iris con precisión suficiente por sí solo, así
  que se combinan la orientación de la cabeza (estable) y la posición de los
  ojos (fina). Basta con mover solo los ojos, solo la cabeza o ambos.
- En la pantalla 03 la persona mira 9 puntos (~15 s). Una regresión lineal
  aprende su relación entre cabeza, ojos y pantalla; se ajusta dos veces para
  descartar los instantes en que miró a otro lado. Si se cae la conexión, el
  navegador reenvía la calibración y no hay que repetirla.
- Además del iris se usan los *blendshapes* de MediaPipe (`eyeLook*`), una
  estimación de la mirada más estable que el iris solo.
- En modo mirada la cámara se pide en 720p y se envían frames de 960 px de
  ancho con más calidad JPEG; con poca luz se realza el contraste (CLAHE) antes
  de buscar la cara.
- El parpadeo se detecta respecto de la apertura habitual de cada persona, así
  quien tiene los párpados caídos no queda como "ojos cerrados" todo el tiempo.
- Al parpadear el cursor se queda quieto, así no se pierde la permanencia.
- En **Coordinación** se sigue usando la mano: el ejercicio es estirar los brazos.
- Con la mirada se recomienda un tiempo de permanencia de 2 o 2,5 s.

Mensajes extra en modo mirada: `"rostro": {"detectado", "ojos_abiertos"}` y
`"calibracion_mirada": {"estado", "progreso", "indice", "punto", "modelo"}`;
`{"accion":"config","modelo_mirada":{...}}` restaura una calibración.

### Perfil de movilidad y voz
Se guardan en el perfil de la persona (`puntero`, `movilidad`, `comandos_voz`),
así la acompañan en cualquier equipo. Se editan en **Configuración → Cómo se mueve**.

| Movilidad | Selección y Coordinación |
|---|---|
| `completa` | Ambos brazos (comportamiento original) |
| `reducida` | Silla de ruedas u hombros rígidos: 20 % menos alcance y casi nada por encima de la cabeza |
| `brazo_izquierdo` / `brazo_derecho` | La zona activa se corre hacia ese lado para no cruzar el cuerpo |
| `cabeza` | En Coordinación el cursor sigue solo el giro de la cabeza (ejercicio de cuello); necesita `face_landmarker.task` |

**Mover el cursor con → La voz** (`puntero = "voz"`): la persona elige solo
hablando. La cámara no se enciende, no hay detección ni calibración, y la
actividad Coordinación no aparece en el menú porque es un ejercicio de movimiento.

**Elegir también con la voz** (apagado por defecto, con la mano o la mirada): la persona dice el nombre de la
opción ("cuchara", "comenzar", "pausa") y se pulsa el elemento `data-elegible`
cuyo texto coincide; `data-voz="sí, acepto"` agrega sinónimos. Si hay empate no
se elige nada. Lo que dice la narración se ignora para no elegir solo. Usa el
reconocimiento de voz del navegador (Chrome o Edge): salvo que Chrome pueda
procesarlo en el equipo, **el audio se envía a Google o Microsoft**, y así se le
advierte al cuidador antes de activarlo.

### Ajustes de la prueba de usabilidad incluidos
Actividades deshabilitadas ocultas en el menú · tiempo de permanencia
configurable · narración por voz · aviso de cambios sin guardar · "Actividades
de hoy: X de 2 completadas" · texto mínimo de 24 px en las pantallas del adulto
mayor · botón secundario más diferenciado.

## Juegos de cada actividad

Cada sesión tiene 8 ítems que mezclan los juegos de su actividad
(`backend/sesiones/juegos.py`). El nivel cambia cuántos hay de cada juego y
qué tan difícil es cada uno. El primer ítem siempre es de elegir una opción.

| Actividad | Juego | Fácil | Medio | Difícil |
|---|---|---|---|---|
| Memoria | ¿Qué objeto va con esto? | 2 | 2 | 2 |
| | Opuestos | 2 · 3 opciones sin relación | 2 · 4 del mismo tema | 2 · casi sinónimos |
| | Clasifica en su grupo | 2 · Cocina/Baño | 2 · + Dormitorio | 1 · + Jardín |
| | Secuencia de la vida diaria | 1 · 3 pasos | 1 · 4 pasos | 2 · 5 pasos |
| | Parejas de Memoria | 1 · 3 pares iguales | 1 · 4 pares relacionados | 1 · 6 pares relacionados |
| Atención | Encuentra la pareja igual | 3 | 2 | 2 · figuras muy parecidas |
| | ¿Cuál NO pertenece? | 2 · de otro mundo | 2 · mismo tema | 2 · hay que pensar |
| | Preguntas de categoría | 2 | 2 | 1 |
| | Sigue la figura | 1 · 3 cartas, 2 cruces | 2 · 4 cartas, 4 cruces | 3 · 4 cartas, 6 cruces rápidos |
| Coordinación | Preguntas en las esquinas | 5 | 4 | 4 |
| | Alcanza y recuerda | 3 · se ve 5 s | 4 · se ve 3 s | 4 · recordar su pareja |
| Mi Historia | ¿Qué momento es este? | 2 opciones | 3 | 4 |
| | ¿Quién es? (señalar la foto) | 2 fotos | 3 | 4 |
| | Encuentra la foto igual | 2 fotos | 3 | — |
| | Ordena los recuerdos | 3 | 3 | 4 |

- **Según cómo se mueve el cursor:** con *La voz* cada opción lleva un número
  verde («di el tres»); en Encuentra la pareja igual, la foto igual y ¿Quién es?
  el nombre se oculta y solo vale el número, porque decir «tortuga» resolvería
  el juego sin mirar. En Parejas y Sigue la figura siempre se dice el número de
  la carta. Con *La mirada*, Parejas usa como mucho 4 pares (cartas más grandes),
  porque ese cursor es menos preciso que la mano.
- **Cómo se responde:** la mayoría de los juegos son de elegir una opción.
  Secuencia y Ordena los recuerdos se responden señalando en orden (`orden` en
  `/responder/`), y Parejas informa cuántos errores hubo (`errores`).
- **Parejas** siempre termina resuelta: dentro de los errores tolerados (4, 6 o
  9) cuenta como acierto y, con más, como resuelta con ayuda. Es el único juego
  cuyas cartas viajan al navegador, porque hay que poder destaparlas.
- El tiempo de Parejas y de las secuencias se guarda por jugada, para que el
  modelo de dificultad no confunda una partida larga con lentitud.
- **Ordena los recuerdos** usa el año que el cuidador puede escribir al subir
  cada foto o audio (opcional); aparece cuando al menos 2 recuerdos tienen
  años distintos. Cada recuerdo sale como mucho dos veces por sesión.
- Parejas, Sigue la figura, Alcanza y recuerda y los juegos de Mi Historia se
  arman al vuelo con contenido que ya existe; Opuestos, Clasifica, ¿Cuál NO
  pertenece? y Secuencia están en el banco (`actividades/banco.py`), que con
  `cargar_datos` queda en 159 preguntas.

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
