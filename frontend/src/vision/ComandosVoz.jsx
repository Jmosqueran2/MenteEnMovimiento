import { useEffect, useRef, useState } from "react";
import { Mic, MicOff } from "lucide-react";
import { callar, esEco, narrando, sonarSeleccion } from "../sonidos";
import { elegiblesVisibles, elegirPorVoz, escuchar, normalizar, textosDe, vozDisponible } from "./voz";

const AVISO_MS = 2500;

const TEXTO_ESTADO = {
  escuchando: "Puedes decir tu respuesta",
  denegado: "Micrófono bloqueado",
  sin_red: "Sin internet: la voz no funciona",
  sin_microfono: "No encuentro el micrófono",
  apagado: "Micrófono apagado",
};

/** Elegir diciendo la opción en voz alta (se activa en el perfil del paciente). */
export default function ComandosVoz() {
  // apagado | escuchando | denegado | sin_red | sin_microfono
  const [estado, setEstado] = useState("apagado");
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
      alOir: (alternativas, { final }) => {
        // Mientras habla la narración, su eco llega por partes: solo se
        // confía en el resultado final, que trae la frase entera para compararla.
        if (!final && narrando()) return false;
        if (alternativas.some((frase) => esEco(frase, normalizar))) return false;
        const elementos = elegiblesVisibles();
        const candidatos = elementos.map((el, id) => ({ id, textos: textosDe(el) }));
        for (const frase of alternativas) {
          // Parcial: se elige al instante, pero solo si dijo la opción entera.
          const id = elegirPorVoz(frase, candidatos, { soloCompleta: !final });
          if (id !== null) {
            mostrar(`Escuché: «${frase.trim()}»`);
            callar(); // si la narración seguía hablando, se calla
            sonarSeleccion();
            elementos[id].click();
            return true;
          }
        }
        // Mostrar lo que se oyó ayuda a ver si el problema es el micrófono o la palabra.
        if (final) mostrar(`No te entendí («${alternativas[0]?.trim() || "…"}»). Di el nombre de una opción.`);
        return false;
      },
    });
    return () => {
      detener();
      clearTimeout(temporizador.current);
    };
  }, []);

  if (!vozDisponible()) return null;
  const Icono = estado === "escuchando" ? Mic : MicOff;
  return (
    <div className={`chip-voz ${estado === "escuchando" ? "chip-voz-activo" : ""}`} role="status" aria-live="polite">
      <Icono size={24} aria-hidden="true" />
      {aviso || TEXTO_ESTADO[estado] || TEXTO_ESTADO.apagado}
    </div>
  );
}
