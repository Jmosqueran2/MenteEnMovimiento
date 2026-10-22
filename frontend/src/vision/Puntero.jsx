import { useEffect, useRef, useState } from "react";
import { sonarSeleccion } from "../sonidos";
import { useVision } from "./ProveedorVision";

// Tras elegir, hay que mover la mano esta distancia antes de poder elegir otra
// cosa. Evita selecciones en cadena cuando la pantalla siguiente tiene un botón
// justo debajo de la mano (p. ej. "Volver al menú" → "Salir" en el menú).
const MOVIMIENTO_MINIMO_PX = 70;

/*
 * Cursor virtual y selección por permanencia (RF-07).
 *
 * Cualquier elemento con el atributo data-elegible se "pulsa" cuando el
 * cursor se queda sobre él el tiempo configurado. Durante la espera recibe la
 * clase .eligiendo y la variable CSS --progreso (0 a 1) para dibujar el anillo.
 */
export default function Puntero({ permanenciaMs = 1500 }) {
  const { control, estado } = useVision();
  const posicion = useRef(null);
  const anillo = useRef(null);
  const [visible, setVisible] = useState(null);

  // Control con mouse (pruebas sin cámara).
  useEffect(() => {
    if (control !== "mouse") return undefined;
    const mover = (e) => {
      posicion.current = { x: e.clientX, y: e.clientY };
      setVisible(posicion.current);
    };
    const salir = () => {
      posicion.current = null;
      setVisible(null);
    };
    window.addEventListener("mousemove", mover);
    document.documentElement.addEventListener("mouseleave", salir);
    return () => {
      window.removeEventListener("mousemove", mover);
      document.documentElement.removeEventListener("mouseleave", salir);
    };
  }, [control]);

  // Control con la mano: el servicio entrega x, y normalizados (0–1).
  useEffect(() => {
    if (control !== "camara") return;
    const cursor = estado?.cursor;
    posicion.current = cursor ? { x: cursor.x * window.innerWidth, y: cursor.y * window.innerHeight } : null;
    setVisible(posicion.current);
  }, [control, estado]);

  // Bucle de permanencia a 60 fps para que el anillo avance suave entre frames.
  useEffect(() => {
    let cuadro;
    let actual = null;
    let desde = 0;
    let ancla = null; // dónde se hizo la última selección

    const soltar = (elemento) => {
      if (!elemento) return;
      elemento.classList.remove("eligiendo");
      elemento.style.removeProperty("--progreso");
    };

    const paso = (ahora) => {
      const p = posicion.current;
      if (p && ancla && Math.hypot(p.x - ancla.x, p.y - ancla.y) > MOVIMIENTO_MINIMO_PX) ancla = null;

      let bajo = null;
      if (p && !ancla) {
        bajo = document.elementFromPoint(p.x, p.y)?.closest?.("[data-elegible]") || null;
        if (bajo && (bajo.disabled || bajo.getAttribute("aria-disabled") === "true")) bajo = null;
      }
      if (bajo !== actual) {
        soltar(actual);
        actual = bajo;
        desde = ahora;
        actual?.classList.add("eligiendo");
      }

      const progreso = actual ? Math.min((ahora - desde) / permanenciaMs, 1) : 0;
      actual?.style.setProperty("--progreso", progreso.toFixed(3));
      anillo.current?.setAttribute("stroke-dasharray", `${progreso * 100} 100`);

      if (actual && progreso >= 1) {
        const elegido = actual;
        soltar(elegido);
        actual = null;
        ancla = { ...p };
        sonarSeleccion();
        elegido.click();
      }
      cuadro = requestAnimationFrame(paso);
    };

    cuadro = requestAnimationFrame(paso);
    return () => {
      cancelAnimationFrame(cuadro);
      soltar(actual);
    };
  }, [permanenciaMs]);

  if (!visible) return null;
  return (
    <svg
      className={`puntero ${control === "camara" ? "puntero-camara" : ""}`}
      style={{ transform: `translate(${visible.x}px, ${visible.y}px)` }}
      viewBox="0 0 80 80"
      aria-hidden="true"
    >
      <circle className="puntero-fondo" cx="40" cy="40" r="24" />
      <circle className="puntero-centro" cx="40" cy="40" r="7" />
      <circle ref={anillo} className="puntero-anillo" cx="40" cy="40" r="34" pathLength="100" strokeDasharray="0 100" />
    </svg>
  );
}
