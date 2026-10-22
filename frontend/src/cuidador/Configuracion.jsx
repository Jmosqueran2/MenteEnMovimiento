import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { guardarAjuste, leerAjuste } from "../ajustes";
import { useSesion } from "../sesion";
import { useVision } from "../vision/ProveedorVision";
import { Encabezado, useAvisoFlotante } from "./LayoutCuidador";

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

/** Perfil de la persona a cargo y preferencias de este equipo. */
export default function Configuracion() {
  const navegar = useNavigate();
  const { paciente, setPaciente, recargar } = useSesion();
  const { control, setControl } = useVision();
  const [datos, setDatos] = useState({
    nombre: paciente?.nombre || "",
    apellido: paciente?.apellido || "",
    fecha_nacimiento: paciente?.fecha_nacimiento || "",
    tiempo_permanencia_ms: paciente?.tiempo_permanencia_ms || 1500,
  });
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
        await api("/api/pacientes/", { metodo: "POST", datos: cuerpo });
        await recargar();
        navegar("/cuidador");
      }
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <>
      <Encabezado etiqueta="Configuración" titulo={paciente ? "Configuración" : "Crea el perfil de la persona a tu cargo"} />
      <form className="columnas" onSubmit={guardar}>
        <div className="tarjeta bloque">
          <h2>Perfil</h2>
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

          <h2>Tiempo para elegir con la mano</h2>
          <p className="texto-apoyo" style={{ fontSize: 16 }}>
            Cuánto tiempo debe quedarse quieta la mano sobre una opción. Aumentarlo ayuda si hay temblor o
            movilidad reducida.
          </p>
          <div className="segmentado" role="group" aria-label="Tiempo de permanencia">
            {TIEMPOS.map(([ms, texto]) => (
              <button key={ms} type="button" aria-pressed={datos.tiempo_permanencia_ms === ms}
                      onClick={() => setDatos({ ...datos, tiempo_permanencia_ms: ms })}>
                {texto}
              </button>
            ))}
          </div>
          {error && <p className="error-texto">{error}</p>}
          <div>
            <button type="submit" className="boton boton-principal">{paciente ? "Guardar" : "Crear perfil"}</button>
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
      {aviso}
    </>
  );
}
