import { useCallback, useState } from "react";
import { Check, HandHelping } from "lucide-react";
import { useSesion } from "../sesion";
import { rolCuidador } from "../formato";
import { pedirAyuda } from "../sesionHoy";
import { hablar } from "../sonidos";
import { Boton, IconoCirculo } from "./comunes";

/** «Pedir ayuda a mi cuidador»: avisa en el panel del cuidador (pantallas 05, 09 y 10). */
export function useAyuda(motivo) {
  const { paciente } = useSesion();
  const [estado, setEstado] = useState("inicial"); // inicial | enviando | pedida | error
  const rol = rolCuidador(paciente);

  const pedir = useCallback(async () => {
    setEstado("enviando");
    try {
      await pedirAyuda(paciente.id, motivo);
      setEstado("pedida");
      hablar(`Ya le avisamos a tu ${rol}. Puedes esperar aquí tranquila.`);
      return true;
    } catch {
      setEstado("error");
      return false;
    }
  }, [paciente.id, motivo, rol]);

  return { estado, pedida: estado === "pedida", pedir, rol };
}

export function BotonAyuda({ ayuda, variante = "secundario" }) {
  if (ayuda.pedida) return null;
  return (
    <Boton variante={variante} icono={HandHelping} onClick={ayuda.pedir} disabled={ayuda.estado === "enviando"}
           data-voz="ayuda, ayúdame, necesito ayuda">
      Pedir ayuda a mi {ayuda.rol}
    </Boton>
  );
}

export function AvisoAyudaPedida({ ayuda }) {
  if (ayuda.estado === "error") {
    return (
      <div className="aviso aviso-crema" role="status">
        <p>No pudimos avisarle a tu {ayuda.rol}. Intenta otra vez en un momento.</p>
      </div>
    );
  }
  if (!ayuda.pedida) return null;
  return (
    <div className="aviso aviso-menta" role="status">
      <IconoCirculo icono={Check} tono="verde" />
      <div>
        <h3>Ya le avisamos a tu {ayuda.rol}.</h3>
        <p>Puedes esperar aquí tranquila.</p>
      </div>
    </div>
  );
}
