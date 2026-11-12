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
| GET/POST | `/api/auth/registro/` | Sin token. GET → `{abierto}`; POST `{nombre, usuario, email?, clave}` crea la cuenta y devuelve los tokens (máx. 10 por hora e IP) |
| GET/POST/PATCH/DELETE | `/api/pacientes/` | Perfil, nivel, tiempo de permanencia, actividades habilitadas (11). DELETE borra también sus archivos de Mi Historia |
| GET | `/api/pacientes/{id}/resumen/` | Tarjetas del panel del cuidador (11) |
| POST | `/api/pacientes/{id}/preparar/` | «Preparar sesión»: guarda `{nivel, actividades_habilitadas, tiempo_permanencia_ms, inicio_autonomo, mostrar_bloqueadas}` y deja lista la sesión de hoy (11) |
| GET | `/api/pacientes/{id}/sesion-hoy/` | Estado de la sesión de hoy: `no_preparada` · `lista` · `en_curso` · `terminada`, actividades hechas, aciertos y pedido de ayuda pendiente (11, 03, 04, 08) |
| POST | `/api/pacientes/{id}/sesion-hoy/comenzar/` | El adulto mayor pulsa «Comenzar» (03) |
| POST | `/api/pacientes/{id}/sesion-hoy/terminar/` | Sale a mitad (despedida) o el cuidador la da por terminada (11) |
| POST | `/api/pacientes/{id}/ayuda/` | «Pedir ayuda a mi cuidador» `{motivo: luz · camara · conexion · actividad · otro}` (05, 09, 10) |
| POST | `/api/pacientes/{id}/ayuda/atendida/` | El cuidador pulsa «Entendido» (11) |
| GET | `/api/pacientes/{id}/seguimiento/?dias=7` | Indicadores y gráfica (15) |
| GET | `/api/pacientes/{id}/seguimiento-csv/` | Exportar CSV (15) |
| GET | `/api/pacientes/{id}/seguimiento-pdf/?dias=7` | Exportar informe PDF: resumen, gráfica y tabla de sesiones (15) |
| GET/POST/PATCH/DELETE | `/api/historia/?paciente={id}` | Fotos y audios de Mi Historia, multipart (12, 13, 14) |
| POST | `/api/sesiones/` | Iniciar actividad `{paciente, tipo}` → 8 preguntas (05) |
| POST | `/api/sesiones/{id}/responder/` | `{indice_pregunta, opcion, tiempo_ms}` → acierto o pista (06, 07) |
| POST | `/api/sesiones/{id}/finalizar/` | `{cancelada?}` → resumen y nivel siguiente (08) |

`tipo` ∈ `memoria`, `atencion`, `coordinacion`, `historia`.

### Cuentas y personas a cargo
- Cada cuidador tiene su cuenta y solo ve a las personas que agregó desde esa cuenta.
  La cuenta se crea en `/registro` (enlace en la pantalla de inicio) o desde `/admin`.
  Con `DJANGO_REGISTRO_ABIERTO=False` (o `REGISTRO_ABIERTO=false` en `deploy/aws.env`)
  solo se crean desde `/admin`.
- Un cuidador puede tener muchos pacientes. **Mis pacientes** (menú lateral) los
  muestra todos; desde ahí, o desde la tarjeta «Paciente activo», se elige con
  quién trabajar o se agrega un paciente nuevo. Mi Historia, el progreso,
  el nivel y la configuración son de cada persona y no se mezclan.
- El navegador recuerda la última persona elegida. La calibración de la mirada se
  descarta al cambiar de persona; la sensibilidad del cursor es del equipo.

### Reglas importantes
- La respuesta correcta nunca se envía al iniciar; se revela al responder.
- Acierto = pregunta resuelta en el primer intento. Máximo 3 intentos por pregunta.
- Al finalizar, el nivel se ajusta solo con el modelo de scikit-learn (ver abajo);
  si el modelo no está entrenado se usan reglas fijas (≥80 % y ≤6 s sube; <50 % baja).
- Mi Historia acepta solo JPG, PNG o MP3 de hasta 10 MB y revisa el contenido
  real del archivo (un PDF renombrado a .jpg se rechaza).
- Una actividad deshabilitada por el cuidador no se puede iniciar. Con una sesión
  preparada vigente, solo se pueden iniciar sus actividades.

### Sesión preparada (modelo híbrido)
Diseño completo en [docs/diseno-interfaces-y-sesion-hibrida.md](docs/diseno-interfaces-y-sesion-hibrida.md).
- El cuidador configura en el panel (11) y pulsa **«Preparar sesión de Rosa»**: se
  guarda todo y queda la sesión de hoy (vale hasta las 23:59). No hace falta que
  se quede; el panel muestra el estado y avisa al terminar o si pide ayuda.
- El adulto mayor se sienta frente a la cámara: la pantalla 03 lo saluda y, si hay
  sesión, muestra el resumen y **«Comenzar»**. El menú (04) muestra solo lo
  preparado, sin nivel. Sin sesión: «Aún no hay actividades listas» y «Salir».
- **Perfil de inicio:** «Puede iniciar sola» o «Requiere acompañamiento». Toda
  persona nueva empieza acompañada: el cuidador usa **«Iniciar ahora con Rosa»**.
  Tras una sesión con ≥ 75 % de aciertos y sin pedir ayuda, el panel sugiere
  pasar a «Puede iniciar sola» (nunca cambia solo).
- En la pantalla 10 (sin cámara) la persona no puede elegir con la mano, así que
  el pedido de ayuda se envía solo a los 30 s.

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
- **Adulto mayor:** sesión preparada (o «Iniciar ahora con Rosa») → consentimiento (01/02)
  → detección, aviso de sesión y calibración (03) → menú con lo preparado (04)
  → actividad (05–07) → resumen (08). Las pantallas 09 (poca luz) y 10
  (cámara o conexión perdida) aparecen como capa sobre cualquier pantalla.

### Calibración guiada a la postura
Con *La mano*, al empezar las actividades (pantalla 03) el sistema se ajusta al
cuerpo de la persona ese día: primero ubica los hombros y luego le pide llevar
la mano **arriba, a la derecha, abajo y a la izquierda**, hasta donde llegue sin
esfuerzo, y dejarla quieta ~1 s en cada lado (un anillo se llena). La zona activa
sale de ese alcance real, así sirve igual en silla de ruedas, con un solo brazo
o con hombros rígidos.

- En selección se usa el 80 % central del alcance (los bordes se alcanzan sin
  estirarse del todo); en Coordinación, el alcance entero.
- La mano en reposo no completa un paso: primero hay que moverla hacia ese lado.
  Si en 12 s no se logra, se toma lo más lejos que llegó.
- El cuidador puede omitirla con el mouse («Omitir»): se usa la estimación por hombros.
- «Volver a calibrar» la repite. Al reconectar, el navegador reenvía el alcance.
- Mensajes: `{"accion":"config","alcance_guiado":true}`, `{"accion":"omitir_alcance"}`,
  `{"accion":"config","alcance":{"arriba","derecha","abajo","izquierda"}}`. Mientras
  dura, `calibracion` trae `estado:"alcance"`, `paso`, `direccion`, `objetivo` y `quieto` (0–1).

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
- Todo se mide en los ejes de la cara: si la persona ladea la cabeza, mirar a un
  lado no se confunde con mirar hacia arriba.
- En cada punto se descartan las muestras sueltas (mediana y MAD) y luego se
  elige el modelo por validación cruzada dejando un punto afuera: por eje
  (original), cruzado (la cámara encima de la pantalla acopla los ejes) o con
  términos cuadráticos del iris, y la regularización. Solo se usa uno más
  complejo si predice mejor los lugares que no se usaron al calibrar. El
  `error` que se informa es ese error de validación, no el de entrenamiento.
- **Corrección de la deriva:** cada botón elegido con la mirada confirma dónde
  estaba mirando la persona. El navegador manda
  `{"accion":"objetivo_mirada","punto":[x,y],"tamano":[ancho,alto]}` y el servicio
  corrige de a poco el sesgo (40 % por elección, tope de 15 % de pantalla;
  ignora objetivos lejanos o muy grandes). Se reinicia al recalibrar.
- Al parpadear el cursor se queda quieto, así no se pierde la permanencia.
- En **Coordinación** se sigue usando la mano: el ejercicio es estirar los brazos.
- Con la mirada se recomienda un tiempo de permanencia de 2 o 2,5 s.

Mensajes extra en modo mirada: `"rostro": {"detectado", "ojos_abiertos"}` y
`"calibracion_mirada": {"estado", "progreso", "indice", "punto", "modelo"}`;
`{"accion":"config","modelo_mirada":{...}}` restaura una calibración.

### Postura al estar sentado
Desde que empiezan las actividades (pantalla 03) y durante cada una, la cámara
vigila cómo está sentada la persona. En la 03 se ve «Revisando tu postura…» →
«Postura: estás bien sentado» o «Endereza la espalda». Si se encorva o se ladea
unos segundos, aparece arriba un aviso («Endereza la espalda» / «Ponte derecho»)
que no tapa el ejercicio ni se puede elegir, y se va solo al enderezarse
(«¡Así está muy bien!»).

- Con la cámara de frente no se ve la espalda, pero encorvarse baja la cabeza:
  se mide la altura de la nariz sobre la línea de hombros, dividida por el
  ancho de hombros, y el ángulo de los hombros.
- **Referencia propia:** las primeras ~12 mediciones en la pantalla 03. Cada
  cámara está a otra altura, así que se compara con su postura, no con un valor fijo.
  Pero nunca se toma como referencia una postura curva (altura mínima 0,45) ni
  ladeada (como mucho 5°): si empieza encorvada, también se le avisa.
- Avisa si la cabeza baja de 75 % de su altura de referencia o los hombros se
  inclinan más de 12° durante **3 s seguidos** (mirar abajo un momento no
  cuenta). El aviso se quita al volver a 85 % / 7° durante 1 s.
- Con una mano levantada (apuntando con el cursor) solo se revisa si está
  encorvada. En Coordinación se pausa. La voz lo dice como máximo cada 45 s
  y nunca interrumpe la lectura de una pregunta.
- Mensajes: `{"accion":"config","vigilar_postura":true}`; cada estado trae
  `postura_sentado`: `midiendo` · `buena` · `encorvado` · `inclinado` · `pausa`.
- Con «La voz» la cámara también se enciende, **solo para la postura**: no hay
  cursor ni se busca la mano (`"puntero": "voz"`), y si la cámara falla no salen
  las pantallas 09/10, porque se puede seguir jugando con la voz. La pantalla 01
  pide micrófono y cámara y lo dice («La cámara, solo para revisar cómo estás
  sentado»). Si no se da permiso de cámara, se juega igual, sin vigilar la postura.
  Con «Mouse (pruebas)» la cámara no se enciende.

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
- **Pregunta propia:** al subir una foto o audio (pantalla 12), el cuidador puede
  escribir una pregunta con 2 a 4 opciones y marcar la correcta (`pregunta`,
  `opciones`, `respuesta_correcta`). En la actividad sale con la foto o el audio;
  según el nivel se muestran 2 (Fácil), 3 (Medio) o todas (Difícil), siempre con
  la correcta. Hasta 4 por sesión. Con preguntas propias alcanza un solo recuerdo.
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
