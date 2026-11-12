import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useSesion } from "../sesion";

/**
 * Confirmación para eliminar a un paciente y todo lo suyo (Mi Historia,
 * sesiones, seguimiento). Se usa desde «Mis pacientes» y desde Configuración.
 */
export default function DialogoEliminarPaciente({ paciente, onCerrar, onEliminado }) {
  const { quitarPaciente } = useSesion();
  const [borrando, setBorrando] = useState(false);
  const [error, setError] = useState(null);
  const cancelar = useRef(null);

  // El foco empieza en «Cancelar» (la opción segura) y Escape cierra.
  useEffect(() => {
    cancelar.current?.focus();
    const alTeclear = (e) => e.key === "Escape" && !borrando && onCerrar();
    document.addEventListener("keydown", alTeclear);
    return () => document.removeEventListener("keydown", alTeclear);
  }, [borrando, onCerrar]);

  const eliminar = async () => {
    setBorrando(true);
    setError(null);
    try {
      await api(`/api/pacientes/${paciente.id}/`, { metodo: "DELETE" });
      quitarPaciente(paciente.id);
      onEliminado?.();
    } catch (err) {
      setError(err.message);
      setBorrando(false);
    }
  };

  return (
    <div className="dialogo-fondo">
      <div className="dialogo" style={{ fontSize: 20 }} role="alertdialog" aria-modal="true"
           aria-labelledby="titulo-eliminar" aria-describedby="detalle-eliminar">
        <h2 id="titulo-eliminar">¿Eliminar a {paciente.nombre} {paciente.apellido}?</h2>
        <p id="detalle-eliminar">
          Se borrarán sus fotos y audios de Mi Historia, sus sesiones y su seguimiento. No se puede deshacer.
        </p>
        {error && <p className="error-texto">{error}</p>}
        <div className="acciones">
          <button type="button" ref={cancelar} className="boton boton-secundario" disabled={borrando} onClick={onCerrar}>
            Cancelar
          </button>
          <button type="button" className="boton boton-peligro" disabled={borrando} onClick={eliminar}>
            {borrando ? "Eliminando…" : "Sí, eliminar"}
          </button>
        </div>
      </div>
    </div>
  );
}
