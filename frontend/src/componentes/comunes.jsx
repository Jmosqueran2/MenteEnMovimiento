import { Brain, Check } from "lucide-react";
import { useVision } from "../vision/ProveedorVision";

export function Marca() {
  return (
    <div className="marca">
      <span className="marca-icono" aria-hidden="true">
        <Brain size={26} />
      </span>
      Mente en Movimiento
    </div>
  );
}

/** Arcos decorativos del panel lateral. */
export function Arcos() {
  return (
    <svg className="arcos" viewBox="0 0 400 400" aria-hidden="true">
      {[120, 180, 240, 300, 360].map((r) => (
        <circle key={r} cx="0" cy="400" r={r} />
      ))}
    </svg>
  );
}

export function Boton({ variante = "principal", icono: Icono, children, elegible = true, ...props }) {
  return (
    <button type="button" className={`boton boton-${variante}`} data-elegible={elegible ? "" : undefined} {...props}>
      {Icono && <Icono size={26} aria-hidden="true" />}
      {children}
    </button>
  );
}

/** Ícono de línea dentro de un círculo menta (guía de estilo 5.3). */
export function IconoCirculo({ icono: Icono, tono = "menta", tamano = 64 }) {
  return (
    <span className={`icono-circulo icono-${tono}`} style={{ width: tamano, height: tamano }} aria-hidden="true">
      <Icono size={tamano * 0.5} />
    </span>
  );
}

const PASOS = ["Privacidad", "Detección", "Actividades"];

export function Pasos({ actual }) {
  return (
    <ol className="pasos">
      {PASOS.map((paso, i) => (
        <li key={paso} className={i < actual ? "hecho" : i === actual ? "actual" : ""}>
          <span className="paso-numero">{i < actual ? <Check size={18} /> : i + 1}</span>
          {paso}
        </li>
      ))}
    </ol>
  );
}

export function EstadoCamara() {
  const { control, puntero, camara, conexion } = useVision();
  let texto = "Cámara en espera";
  let tono = "gris";
  if (puntero === "voz") {
    // Con la voz la cámara, si está encendida, solo revisa la postura.
    texto = camara === "activa" ? "Elige con la voz · cámara: postura" : "Elige con la voz (cámara apagada)";
    tono = "verde";
  } else if (control === "mouse") {
    texto = "Control con mouse (pruebas)";
    tono = "amarillo";
  } else if (camara === "desconectada" || camara === "denegada") {
    texto = "Sin cámara";
    tono = "rojo";
  } else if (camara === "activa") {
    texto = conexion === "abierta" ? "Cámara activa" : "Conectando…";
    tono = conexion === "abierta" ? "verde" : "amarillo";
  }
  return (
    <p className="estado-camara">
      <span className={`punto punto-${tono}`} aria-hidden="true" />
      {texto}
    </p>
  );
}

/** Distribución fija en dos zonas: panel oscuro + área clara (guía 5.4). */
export function PantallaAdulto({ lateral, children, acciones, claseContenido = "" }) {
  return (
    <div className="pantalla">
      <aside className="lateral">
        <Arcos />
        <Marca />
        <div className="lateral-cuerpo">{lateral}</div>
        <EstadoCamara />
      </aside>
      <main className={`contenido ${claseContenido}`}>
        <div className="contenido-cuerpo">{children}</div>
        {acciones && <div className="acciones">{acciones}</div>}
      </main>
    </div>
  );
}

export function Cargando({ texto = "Cargando…" }) {
  return (
    <div className="cargando" role="status">
      <span className="spinner" aria-hidden="true" />
      {texto}
    </div>
  );
}
