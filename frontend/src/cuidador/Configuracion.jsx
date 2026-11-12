import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { guardarAjuste, leerAjuste } from "../ajustes";
import { useSesion } from "../sesion";
import { useVision } from "../vision/ProveedorVision";
import { vozDisponible } from "../vision/voz";
import { Encabezado, useAvisoFlotante } from "./LayoutCuidador";
import DialogoEliminarPaciente from "./EliminarPaciente";

const VARIABLES = {
  tasa_aciertos: "Aciertos al primer intento",
  tiempo_promedio_s: "Tiempo de respuesta",
  media_reciente: "Desempeño de sesiones anteriores",
  tasa_reintentos: "Respuestas con reintento",
  tasa_agotadas: "Preguntas sin resolver",
  nivel: "Nivel actual",
  sesiones_previas: "Cantidad de sesiones previas",
};

/** Tarjeta informativa del modelo de dificultad adaptativa (scikit-learn). */
function TarjetaModelo() {
  const [info, setInfo] = useState(null);
  useEffect(() => {
    api("/api/adaptacion/modelo/").then(setInfo).catch(() => {});
  }, []);
  if (!info) return null;
  if (!info.entrenado) {
    return (
      <div className="tarjeta bloque">
        <h2>Dificultad adaptativa</h2>
        <p className="texto-apoyo">El modelo de IA no está entrenado; se usan reglas fijas.</p>
      </div>
    );
  }
  const m = info.metricas;
  return (
    <div className="tarjeta bloque">
      <h2>Dificultad adaptativa (IA)</h2>
      <p className="texto-apoyo" style={{ fontSize: 16 }}>
        {info.algoritmo} · entrenado con {info.muestras.toLocaleString("es-EC")} sesiones simuladas ·{" "}
        {new Date(info.entrenado).toLocaleDateString("es-EC")}
      </p>
      <div className="cifras">
        <div className="cifra"><strong>{Math.round(m.exactitud * 100)} %</strong><span>Exactitud</span></div>
        <div className="cifra"><strong>{m.f1_macro_validacion_cruzada.toFixed(2)}</strong><span>F1 (validación cruzada)</span></div>
      </div>
      <strong>Qué pesa más en la decisión</strong>
      <div className="importancias">
        {Object.entries(info.importancias).map(([nombre, valor]) => (
          <div key={nombre} className="importancia">
            <span>{VARIABLES[nombre] || nombre}</span>
            <span className="barra"><span style={{ width: `${Math.round(valor * 100 / 0.3)}%` }} /></span>
            <span>{Math.round(valor * 100)} %</span>
          </div>
        ))}
      </div>
    </div>
  );
}

const TIEMPOS = [
  [1500, "1,5 s"],
  [2000, "2 s"],
  [2500, "2,5 s"],
];

const SENSIBILIDADES = [
  [1, "Normal"],
  [1.3, "Alta"],
  [1.6, "Muy alta"],
  [2, "Máxima"],
];

const MOVILIDADES = [
  ["completa", "Ambos brazos", "Coordinación pide estirar los dos brazos."],
  ["reducida", "Movimiento limitado", "Para silla de ruedas u hombros rígidos: hay que estirarse menos y casi nada por encima de la cabeza."],
  ["brazo_izquierdo", "Solo el brazo izquierdo", "Las opciones quedan al alcance del brazo izquierdo, sin cruzar el cuerpo."],
  ["brazo_derecho", "Solo el brazo derecho", "Las opciones quedan al alcance del brazo derecho, sin cruzar el cuerpo."],
  ["cabeza", "Sin usar los brazos", "En Coordinación se responde girando e inclinando la cabeza: es un ejercicio de cuello."],
];

/** Eliminar el perfil de la persona y todo lo suyo. */
function EliminarPerfil({ paciente }) {
  const navegar = useNavigate();
  const [confirmando, setConfirmando] = useState(false);

  return (
    <div className="tarjeta bloque">
      <h2>Eliminar perfil</h2>
      <p className="texto-apoyo" style={{ fontSize: 16 }}>
        Borra a {paciente.nombre} de tu cuenta junto con sus fotos y audios de Mi Historia y todo su progreso.
        No se puede deshacer.
      </p>
      <div>
        <button type="button" className="boton boton-peligro" onClick={() => setConfirmando(true)}>
          Eliminar a {paciente.nombre}
        </button>
      </div>
      {confirmando && (
        <DialogoEliminarPaciente
          paciente={paciente}
          onCerrar={() => setConfirmando(false)}
          onEliminado={() => navegar("/cuidador/pacientes", { replace: true })}
        />
      )}
    </div>
  );
}

/**
 * Perfil de la persona a cargo y preferencias de este equipo.
 * Con `nueva` el formulario empieza vacío y crea otra persona en la cuenta.
 */
export default function Configuracion({ nueva = false }) {
  const navegar = useNavigate();
  const { paciente: activo, setPaciente } = useSesion();
  const paciente = nueva ? null : activo;
  const { control, setControl, sensibilidad, setSensibilidad } = useVision();
  const [datos, setDatos] = useState({
    nombre: paciente?.nombre || "",
    apellido: paciente?.apellido || "",
    fecha_nacimiento: paciente?.fecha_nacimiento || "",
    tiempo_permanencia_ms: paciente?.tiempo_permanencia_ms || 1500,
    puntero: paciente?.puntero || "mano",
    movilidad: paciente?.movilidad || "completa",
    comandos_voz: paciente?.comandos_voz || false,
    rol_cuidador: paciente?.rol_cuidador || "cuidador",
  });
  const elegir = (campo, valor) => setDatos({ ...datos, [campo]: valor });
  // Cambiar cómo se mueve el cursor apaga la voz extra: el micrófono solo se
  // usa si el cuidador lo vuelve a activar a propósito (o si elige «La voz»).
  const elegirPuntero = (valor) => {
    if (valor !== datos.puntero) setDatos({ ...datos, puntero: valor, comandos_voz: false });
  };
  const [voz, setVoz] = useState(() => leerAjuste("voz"));
  const [error, setError] = useState(null);
  const [aviso, mostrarAviso] = useAvisoFlotante();

  const cambiar = (campo) => (e) => setDatos({ ...datos, [campo]: e.target.value });

  const guardar = async (e) => {
    e.preventDefault();
    if (!datos.nombre.trim()) return setError("Escribe el nombre.");
    setError(null);
    const cuerpo = { ...datos, fecha_nacimiento: datos.fecha_nacimiento || null };
    try {
      if (paciente) {
        setPaciente(await api(`/api/pacientes/${paciente.id}/`, { metodo: "PATCH", datos: cuerpo }));
        mostrarAviso("Configuración guardada");
      } else {
        // El paciente nuevo queda como el activo; se muestra la lista completa
        // para que se vea que se sumó a los demás.
        setPaciente(await api("/api/pacientes/", { metodo: "POST", datos: cuerpo }));
        navegar("/cuidador/pacientes");
      }
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <>
      <Encabezado
        etiqueta="Configuración"
        titulo={paciente ? "Configuración" : activo ? "Agregar un paciente nuevo" : "Crea el perfil de tu primer paciente"}
      />
      {!paciente && activo && (
        <p className="texto-apoyo" style={{ fontSize: 17 }}>
          El paciente nuevo se suma a tu lista; {activo.nombre} y los demás siguen en «Mis pacientes» con sus datos.
        </p>
      )}
      <form className="columnas" onSubmit={guardar}>
        <div className="tarjeta bloque">
          <h2>{paciente ? "Perfil del paciente" : "Datos del paciente nuevo"}</h2>
          <div className="campo">
            <label htmlFor="nombre">Nombre</label>
            <input id="nombre" value={datos.nombre} onChange={cambiar("nombre")} maxLength={80} />
          </div>
          <div className="campo">
            <label htmlFor="apellido">Apellido</label>
            <input id="apellido" value={datos.apellido} onChange={cambiar("apellido")} maxLength={80} />
          </div>
          <div className="campo">
            <label htmlFor="nacimiento">Fecha de nacimiento</label>
            <input id="nacimiento" type="date" value={datos.fecha_nacimiento} onChange={cambiar("fecha_nacimiento")} />
          </div>

          <h2>Cómo te nombra en los mensajes</h2>
          <p className="texto-apoyo" style={{ fontSize: 16 }}>
            Se usa en avisos como «Pídele a tu cuidadora que las prepare».
          </p>
          <div className="segmentado" role="group" aria-label="Cómo te nombra en los mensajes">
            {[["cuidador", "Mi cuidador"], ["cuidadora", "Mi cuidadora"]].map(([valor, texto]) => (
              <button key={valor} type="button" aria-pressed={datos.rol_cuidador === valor}
                      onClick={() => elegir("rol_cuidador", valor)}>
                {texto}
              </button>
            ))}
          </div>

          <h2>Tiempo para elegir</h2>
          <p className="texto-apoyo" style={{ fontSize: 16 }}>
            Cuánto tiempo debe quedarse quieto el cursor sobre una opción. Aumentarlo ayuda si hay temblor o
            movilidad reducida. Con la mirada conviene 2 o 2,5 s, para que no se elija algo solo por leerlo.
          </p>
          <div className="segmentado" role="group" aria-label="Tiempo de permanencia">
            {TIEMPOS.map(([ms, texto]) => (
              <button key={ms} type="button" aria-pressed={datos.tiempo_permanencia_ms === ms}
                      onClick={() => setDatos({ ...datos, tiempo_permanencia_ms: ms })}>
                {texto}
              </button>
            ))}
          </div>

          <h2>Cómo se mueve</h2>
          <strong>Mover el cursor con</strong>
          <div className="segmentado" role="group" aria-label="Mover el cursor con">
            <button type="button" aria-pressed={datos.puntero === "mano"} onClick={() => elegirPuntero("mano")}>La mano</button>
            <button type="button" aria-pressed={datos.puntero === "mirada"} onClick={() => elegirPuntero("mirada")}>La mirada</button>
            <button type="button" aria-pressed={datos.puntero === "voz"} disabled={!vozDisponible()}
                    onClick={() => elegirPuntero("voz")}>La voz</button>
          </div>
          <p className="texto-apoyo" style={{ fontSize: 16 }}>
            {datos.puntero === "voz"
              ? "La persona elige diciendo en voz alta la opción que quiere («memoria», «cuchara», «comenzar»). La cámara no se enciende y la actividad Coordinación no aparece, porque es un ejercicio de movimiento. Ojo: según el navegador, el audio puede procesarse en servidores de Google o Microsoft."
              : datos.puntero === "mirada"
                ? "El cursor sigue hacia dónde mira la persona (cabeza y ojos), sin levantar las manos. Al empezar se le pide mirar 9 puntos."
                : "El cursor sigue la palma de la mano. Si la persona se cansa de levantar el brazo, elige «La mirada» o «La voz»."}
            {!vozDisponible() && " «La voz» necesita Google Chrome o Microsoft Edge."}
          </p>

          <div className="campo">
            <label htmlFor="movilidad">Movilidad</label>
            <select id="movilidad" value={datos.movilidad} onChange={cambiar("movilidad")}>
              {MOVILIDADES.map(([valor, texto]) => <option key={valor} value={valor}>{texto}</option>)}
            </select>
          </div>
          <p className="texto-apoyo" style={{ fontSize: 16 }}>
            {MOVILIDADES.find(([valor]) => valor === datos.movilidad)?.[2]}
          </p>

          {datos.puntero !== "voz" && (<>
          <strong>Elegir también con la voz</strong>
          <div className="segmentado" role="group" aria-label="Elegir también con la voz">
            {[true, false].map((valor) => (
              <button key={String(valor)} type="button" aria-pressed={datos.comandos_voz === valor}
                      disabled={valor && !vozDisponible()} onClick={() => elegir("comandos_voz", valor)}>
                {valor ? "Activado" : "Desactivado"}
              </button>
            ))}
          </div>
          <p className="texto-apoyo" style={{ fontSize: 16 }}>
            {vozDisponible()
              ? "La persona puede decir en voz alta la opción que quiere («cuchara», «comenzar», «pausa»). Ojo: según el navegador, el audio puede procesarse en servidores de Google o Microsoft; en ese caso ya no queda solo en este equipo."
              : "Este navegador no reconoce la voz. Usa Google Chrome o Microsoft Edge."}
          </p>
          </>)}

          {error && <p className="error-texto">{error}</p>}
          <div>
            <button type="submit" className="boton boton-principal">{paciente ? "Guardar" : "Agregar paciente"}</button>
          </div>
        </div>

        <div className="tarjeta bloque">
          <h2>En este equipo</h2>
          <p className="texto-apoyo" style={{ fontSize: 16 }}>Estas opciones se guardan solo en este navegador.</p>
          <strong>Control</strong>
          <div className="segmentado" role="group" aria-label="Control">
            <button type="button" aria-pressed={control === "camara"} onClick={() => setControl("camara")}>Cámara</button>
            <button type="button" aria-pressed={control === "mouse"} onClick={() => setControl("mouse")}>Mouse (pruebas)</button>
          </div>

          <strong>Sensibilidad del cursor con la mano</strong>
          <div className="segmentado" role="group" aria-label="Sensibilidad del cursor con la mano">
            {SENSIBILIDADES.map(([valor, texto]) => (
              <button key={valor} type="button" aria-pressed={sensibilidad === valor}
                      onClick={() => setSensibilidad(valor)}>
                {texto}
              </button>
            ))}
          </div>
          <p className="texto-apoyo" style={{ fontSize: 16 }}>
            Súbela si con esta cámara no se alcanzan los bordes de la pantalla (cámaras que ven poco espacio o de
            baja resolución): el cursor llega más lejos con menos movimiento de la mano. Si el cursor se mueve
            demasiado rápido o tiembla, bájala.
          </p>

          <strong>Narración por voz</strong>
          <div className="segmentado" role="group" aria-label="Narración por voz">
            {[true, false].map((valor) => (
              <button key={String(valor)} type="button" aria-pressed={voz === valor}
                      onClick={() => { setVoz(valor); guardarAjuste("voz", valor); }}>
                {valor ? "Activada" : "Desactivada"}
              </button>
            ))}
          </div>
        </div>
      </form>
      {paciente && <TarjetaModelo />}
      {paciente && <EliminarPerfil paciente={paciente} />}
      {aviso}
    </>
  );
}
