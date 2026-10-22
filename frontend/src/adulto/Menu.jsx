import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CircleDot, Copy, Image, LogOut, PersonStanding } from "lucide-react";
import { api } from "../api";
import { Boton, IconoCirculo, PantallaAdulto } from "../componentes/comunes";
import { hoyIso, NOMBRE_NIVEL } from "../formato";
import { useSesion } from "../sesion";
import { hablar } from "../sonidos";

export const ACTIVIDADES = [
  { tipo: "memoria", titulo: "Memoria", descripcion: "Empareja imágenes de la vida diaria", icono: Copy },
  { tipo: "atencion", titulo: "Atención", descripcion: "Encuentra la figura correcta", icono: CircleDot },
  { tipo: "coordinacion", titulo: "Coordinación", descripcion: "Estira los brazos para responder", icono: PersonStanding },
  { tipo: "historia", titulo: "Mi Historia", descripcion: "Recuerda con tus fotos familiares", icono: Image },
];

const META_DIARIA = 2;

/** Pantalla 04: menú de actividades. */
export default function Menu() {
  const navegar = useNavigate();
  const { paciente, recargar } = useSesion();
  const [hechasHoy, setHechasHoy] = useState(0);

  useEffect(() => {
    recargar(); // el nivel pudo cambiar al terminar la sesión anterior
    hablar("¿Qué hacemos hoy? Mueve la mano hacia una actividad y déjala quieta un momento.");
  }, [recargar]);

  useEffect(() => {
    api(`/api/sesiones/?paciente=${paciente.id}&desde=${hoyIso()}`)
      .then((sesiones) => setHechasHoy(sesiones.filter((s) => s.estado === "finalizada").length))
      .catch(() => {});
  }, [paciente.id]);

  // Ajuste de la prueba de usabilidad: lo deshabilitado por el cuidador no aparece.
  const disponibles = ACTIVIDADES.filter((a) => paciente.actividades_habilitadas.includes(a.tipo));

  return (
    <PantallaAdulto
      lateral={
        <>
          <h1>¿Qué hacemos hoy?</h1>
          <p>Mueve la mano hacia una actividad y déjala quieta un momento.</p>
          <span className="insignia">Nivel: {NOMBRE_NIVEL[paciente.nivel]}</span>
          <p>Actividades de hoy: {Math.min(hechasHoy, META_DIARIA)} de {META_DIARIA} completadas</p>
        </>
      }
      acciones={<Boton variante="secundario" icono={LogOut} onClick={() => navegar("/jugar/fin")}>Salir</Boton>}
    >
      <div className="rejilla-actividades">
        {disponibles.map(({ tipo, titulo, descripcion, icono }) => (
          <button
            key={tipo}
            type="button"
            className="tarjeta-actividad elegible-tarjeta"
            data-elegible=""
            onClick={() => navegar(`/jugar/actividad/${tipo}`)}
          >
            <IconoCirculo icono={icono} tamano={72} />
            <h2>{titulo}</h2>
            <p>{descripcion}</p>
          </button>
        ))}
      </div>
    </PantallaAdulto>
  );
}
