import { useEffect, useRef, useState } from "react";
import { PersonStanding, ThumbsUp } from "lucide-react";
import { useSesion } from "../sesion";
import { hablar } from "../sonidos";
import { useVision } from "../vision/ProveedorVision";

const MENSAJES = {
  encorvado: {
    titulo: "Endereza la espalda",
    texto: "Siéntate derecho, con la espalda apoyada en la silla.",
  },
  inclinado: {
    titulo: "Ponte derecho",
    texto: "Tus hombros se inclinaron hacia un lado. Siéntate derecho.",
  },
};
// No repetir en voz alta más seguido que esto: que ayude, sin regañar.
const NARRAR_CADA_MS = 45000;
const FELICITAR_MS = 2500;

/**
 * Aviso de postura arriba de la pantalla durante las actividades. No tapa el
 * ejercicio ni se puede elegir (no tiene data-elegible): solo recuerda
 * sentarse bien y se va solo cuando la persona se endereza.
 */
export default function AvisoPostura() {
  const { estado } = useVision();
  const { paciente } = useSesion();
  const postura = estado?.postura_sentado;
  const problema = MENSAJES[postura] ? postura : null;
  const [felicitar, setFelicitar] = useState(false);
  const anterior = useRef(null);
  const ultimaVoz = useRef(0);

  useEffect(() => {
    const antes = anterior.current;
    anterior.current = problema;
    if (problema && problema !== antes) {
      setFelicitar(false);
      const ahora = Date.now();
      // Si está sonando la pregunta, no se la interrumpe: el aviso igual se ve.
      const hablando = "speechSynthesis" in window && window.speechSynthesis.speaking;
      if (!hablando && ahora - ultimaVoz.current > NARRAR_CADA_MS) {
        ultimaVoz.current = ahora;
        hablar(`${paciente.nombre}, ${MENSAJES[problema].texto.charAt(0).toLowerCase()}${MENSAJES[problema].texto.slice(1)}`);
      }
    }
    if (!problema && antes && postura === "buena") {
      setFelicitar(true);
      const t = setTimeout(() => setFelicitar(false), FELICITAR_MS);
      return () => clearTimeout(t);
    }
    return undefined;
  }, [problema, postura, paciente.nombre]);

  if (problema) {
    const { titulo, texto } = MENSAJES[problema];
    return (
      <div className="aviso-postura" role="status" aria-live="polite">
        <PersonStanding size={44} aria-hidden="true" />
        <div>
          <strong>{titulo}</strong>
          <span>{texto}</span>
        </div>
      </div>
    );
  }
  if (felicitar) {
    return (
      <div className="aviso-postura aviso-postura-bien" role="status" aria-live="polite">
        <ThumbsUp size={40} aria-hidden="true" />
        <div><strong>¡Así está muy bien!</strong></div>
      </div>
    );
  }
  return null;
}
