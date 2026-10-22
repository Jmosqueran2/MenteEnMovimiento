import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { CheckCircle2, LogOut } from "lucide-react";
import { Arcos, Marca } from "../componentes/comunes";
import { useSesion } from "../sesion";

export default function LayoutCuidador() {
  const { paciente, salir } = useSesion();
  return (
    <div className="cuidador">
      <aside className="lateral">
        <Arcos />
        <Marca />
        {paciente && (
          <div className="perfil">
            <span className="avatar">{paciente.iniciales}</span>
            <div>
              <strong>{paciente.nombre} {paciente.apellido}</strong>
              <small>{paciente.edad ? `${paciente.edad} años · ` : ""}Perfil activo</small>
            </div>
          </div>
        )}
        <p className="nav-titulo">PANEL DEL CUIDADOR</p>
        <nav className="nav">
          <NavLink to="/cuidador" end>Inicio</NavLink>
          <NavLink to="/cuidador/historia">Mi Historia</NavLink>
          <NavLink to="/cuidador/seguimiento">Seguimiento</NavLink>
          <NavLink to="/cuidador/configuracion">Configuración</NavLink>
        </nav>
        <button type="button" className="salir" onClick={salir}>
          <LogOut size={20} /> Cerrar sesión
        </button>
      </aside>
      <main className="contenido">
        <Outlet />
      </main>
    </div>
  );
}

/** Mensaje breve de confirmación ("Cambios guardados"). */
export function useAvisoFlotante() {
  const [texto, setTexto] = useState(null);
  useEffect(() => {
    if (!texto) return undefined;
    const t = setTimeout(() => setTexto(null), 3000);
    return () => clearTimeout(t);
  }, [texto]);
  const elemento = texto && (
    <div className="aviso-flotante" role="status">
      <CheckCircle2 size={22} /> {texto}
    </div>
  );
  return [elemento, setTexto];
}

export function Encabezado({ etiqueta, titulo, children }) {
  return (
    <header className="encabezado">
      <div>
        <p className="etiqueta">{etiqueta}</p>
        <h1>{titulo}</h1>
      </div>
      {children}
    </header>
  );
}
