import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CheckCircle2, Trash2, UserPlus } from "lucide-react";
import { useSesion } from "../sesion";
import DialogoEliminarPaciente from "./EliminarPaciente";
import { Encabezado, useAvisoFlotante } from "./LayoutCuidador";

/** Todos los pacientes de la cuenta del cuidador; cada uno con sus propios datos. */
export default function Pacientes() {
  const navegar = useNavigate();
  const { cuidador, pacientes, paciente } = useSesion();
  const nombreCuidador = cuidador?.first_name || cuidador?.username;
  const [eliminando, setEliminando] = useState(null);
  const [aviso, mostrarAviso] = useAvisoFlotante();
  const cerrar = useCallback(() => setEliminando(null), []);

  return (
    <>
      <Encabezado etiqueta={`Cuidador: ${nombreCuidador}`} titulo="Mis pacientes">
        <button type="button" className="boton boton-principal boton-compacto"
                onClick={() => navegar("/cuidador/nuevo-paciente")}>
          <UserPlus size={22} /> Agregar paciente
        </button>
      </Encabezado>
      <p className="texto-apoyo" style={{ fontSize: 17 }}>
        {pacientes.length === 0
          ? "Aún no tienes pacientes. Agrega el primero para empezar."
          : `Tienes ${pacientes.length} ${pacientes.length === 1 ? "paciente" : "pacientes"} a tu cargo. `
            + "Cada uno tiene su propio perfil, su Mi Historia y su progreso; elige con quién vas a trabajar."}
      </p>
      <div className="grilla-pacientes">
        {pacientes.map((p) => {
          const activo = p.id === paciente?.id;
          return (
            <div key={p.id} className={`tarjeta tarjeta-paciente${activo ? " tarjeta-paciente-activa" : ""}`}>
              <span className="avatar avatar-grande">{p.iniciales}</span>
              <div className="tarjeta-paciente-datos">
                <strong>{p.nombre} {p.apellido}</strong>
                <span className="texto-apoyo">
                  {p.edad ? `${p.edad} años · ` : ""}Nivel {p.nivel_texto?.toLowerCase()}
                </span>
              </div>
              {activo ? (
                <span className="paciente-activo"><CheckCircle2 size={20} /> Paciente activo</span>
              ) : (
                <button type="button" className="boton boton-secundario boton-compacto"
                        onClick={() => navegar(`/cuidador/paciente/${p.id}`)}>
                  Elegir
                </button>
              )}
              <button type="button" className="eliminar-paciente" onClick={() => setEliminando(p)}>
                <Trash2 size={18} aria-hidden="true" /> Eliminar
              </button>
            </div>
          );
        })}
        <button type="button" className="tarjeta tarjeta-paciente tarjeta-agregar"
                onClick={() => navegar("/cuidador/nuevo-paciente")}>
          <span className="avatar avatar-grande avatar-agregar"><UserPlus size={28} /></span>
          <strong>Agregar paciente</strong>
        </button>
      </div>
      {eliminando && (
        <DialogoEliminarPaciente
          paciente={eliminando}
          onCerrar={cerrar}
          onEliminado={() => {
            mostrarAviso(`Se eliminó a ${eliminando.nombre}`);
            setEliminando(null);
          }}
        />
      )}
      {aviso}
    </>
  );
}
