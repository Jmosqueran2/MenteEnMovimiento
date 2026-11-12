import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Check, CircleDot, Copy, Image, Lock, LogOut, PersonStanding } from "lucide-react";
import { Boton, Cargando, IconoCirculo, PantallaAdulto } from "../componentes/comunes";
import { rolCuidador } from "../formato";
import { useSesion } from "../sesion";
import { leerSesionHoy } from "../sesionHoy";
import { hablar } from "../sonidos";
import { useVision } from "../vision/ProveedorVision";

export const ACTIVIDADES = [
  { tipo: "memoria", titulo: "Memoria", descripcion: "Parejas, opuestos y pasos del día", icono: Copy },
  { tipo: "atencion", titulo: "Atención", descripcion: "Encuentra, compara y sigue figuras", icono: CircleDot },
  { tipo: "coordinacion", titulo: "Coordinación", descripcion: "Estira los brazos y recuerda", icono: PersonStanding },
  { tipo: "historia", titulo: "Mi Historia", descripcion: "Recuerda con tus fotos familiares", icono: Image },
];

// Coordinación según la movilidad que eligió el cuidador.
const COORDINACION_POR_MOVILIDAD = {
  brazo_izquierdo: "Estira el brazo para responder",
  brazo_derecho: "Estira el brazo para responder",
  reducida: "Estírate un poco para responder",
  cabeza: "Gira la cabeza para responder",
};

/**
 * Pantalla 04: solo las actividades de la sesión que preparó el cuidador. La
 * persona elige el orden. Sin nivel ni configuración: eso es del cuidador.
 */
export default function Menu() {
  const navegar = useNavigate();
  const { paciente, recargar } = useSesion();
  const [hoy, setHoy] = useState(null);
  const { puntero, movilidad, conVoz } = useVision();
  const soloVoz = puntero === "voz";
  const rol = rolCuidador(paciente);

  useEffect(() => {
    recargar(); // el nivel o las actividades pudieron cambiar
    leerSesionHoy(paciente.id).then(setHoy).catch(() => setHoy({ estado: "error" }));
  }, [recargar, paciente.id]);

  const vigente = hoy?.estado === "lista" || hoy?.estado === "en_curso";
  const pendientes = vigente ? hoy.realizables.filter((t) => !hoy.hechas.includes(t)) : [];
  const ninguna = vigente && hoy.hechas.length === 0;
  const indicacion = soloVoz
    ? "Di el nombre de una actividad."
    : (puntero === "mirada"
      ? "Mira una actividad un momento."
      : "Mueve la mano hacia una actividad y déjala quieta un momento.")
      + (conVoz ? " O di su nombre." : "");
  const titulo = ninguna ? "¿Qué hacemos primero?" : "¿Qué hacemos ahora?";

  useEffect(() => {
    if (!hoy) return;
    // Sin sesión vigente (o ya terminada) la pantalla 03 explica qué pasa.
    if (!vigente) return navegar("/jugar/deteccion", { replace: true });
    if (pendientes.length === 0) return navegar("/jugar/fin", { replace: true });
    hablar(`${titulo} ${indicacion}`);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hoy]);

  if (!hoy || !vigente || pendientes.length === 0) return <Cargando texto="Un momento…" />;

  const preparadas = ACTIVIDADES.filter((a) => hoy.realizables.includes(a.tipo));
  const bloqueadas = paciente.mostrar_bloqueadas
    ? ACTIVIDADES.filter((a) => !hoy.realizables.includes(a.tipo) && !(soloVoz && a.tipo === "coordinacion"))
    : [];
  const total = hoy.realizables.length;

  return (
    <PantallaAdulto
      lateral={
        <>
          <h1>{titulo}</h1>
          <p>{indicacion}</p>
          {total > 1 && <p>Hoy: {hoy.hechas.length} de {total} hechas</p>}
        </>
      }
      acciones={<Boton variante="secundario" icono={LogOut} onClick={() => navegar("/jugar/fin")}>Salir</Boton>}
    >
      <div className="rejilla-actividades">
        {preparadas.map(({ tipo, titulo: nombre, descripcion: base, icono }) => {
          const descripcion = tipo === "coordinacion" ? COORDINACION_POR_MOVILIDAD[movilidad] || base : base;
          if (hoy.hechas.includes(tipo)) {
            // Ya hecha: se ve, pero no se puede elegir (no tiene data-elegible).
            return (
              <div key={tipo} className="tarjeta-actividad tarjeta-hecha" aria-disabled="true">
                <IconoCirculo icono={Check} tono="verde" tamano={72} />
                <h2>{nombre}</h2>
                <p><strong>Hecha</strong> · ¡Muy bien!</p>
              </div>
            );
          }
          return (
            <button
              key={tipo}
              type="button"
              className="tarjeta-actividad elegible-tarjeta"
              data-elegible=""
              onClick={() => navegar(`/jugar/actividad/${tipo}`)}
            >
              <IconoCirculo icono={icono} tamano={72} />
              <h2>{nombre}</h2>
              <p>{descripcion}</p>
            </button>
          );
        })}
        {bloqueadas.map(({ tipo, titulo: nombre }) => (
          <div key={tipo} className="tarjeta-actividad tarjeta-bloqueada" aria-disabled="true">
            <Lock size={48} aria-hidden="true" />
            <h2>{nombre}</h2>
            <p>Esta actividad está en pausa. Pídele a tu {rol} que la active.</p>
          </div>
        ))}
      </div>
    </PantallaAdulto>
  );
}
