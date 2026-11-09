import { useEffect, useRef, useState } from "react";
import { Mic, MicOff } from "lucide-react";
import { esEco, sonarSeleccion } from "../sonidos";
import { elegiblesVisibles, elegirPorVoz, escuchar, normalizar, textosDe, vozDisponible } from "./voz";

const AVISO_MS = 2500;

/** Elegir diciendo la opción en voz alta (se activa en el perfil del paciente). */
export default function ComandosVoz() {
  const [estado, setEstado] = useState("apagado"); // apagado | escuchando | denegado
  const [aviso, setAviso] = useState(null);
  const temporizador = useRef();

  useEffect(() => {
    if (!vozDisponible()) return undefined;
    const mostrar = (texto) => {
      setAviso(texto);
      clearTimeout(temporizador.current);
      temporizador.current = setTimeout(() => setAviso(null), AVISO_MS);
    };

    const detener = escuchar({
      alCambiarEstado: setEstado,
      alOir: (alternativas) => {
        if (alternativas.some((frase) => esEco(frase, normalizar))) return;
        const elementos = elegiblesVisibles();
        const candidatos = elementos.map((el, id) => ({ id, textos: textosDe(el) }));
        for (const frase of alternativas) {
          const id = elegirPorVoz(frase, candidatos);
          if (id !== null) {
            mostrar(`Escuché: «${frase.trim()}»`);
            sonarSeleccion();
            elementos[id].click();
            return;
          }
        }
        mostrar("No te entendí. Di el nombre de una opción.");
      },
    });
    return () => {
      detener();
      clearTimeout(temporizador.current);
    };
  }, []);

  if (!vozDisponible()) return null;
  const Icono = estado === "denegado" ? MicOff : Mic;
  return (
    <div className={`chip-voz ${estado === "escuchando" ? "chip-voz-activo" : ""}`} role="status" aria-live="polite">
      <Icono size={24} aria-hidden="true" />
      {aviso || (estado === "denegado" ? "Micrófono bloqueado" : estado === "escuchando" ? "Puedes decir tu respuesta" : "Micrófono apagado")}
    </div>
  );
}
