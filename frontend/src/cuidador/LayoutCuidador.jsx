import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useNavigate, useParams } from "react-router-dom";
import { CheckCircle2, ChevronDown, ChevronsLeft, LogOut, Menu, UserPlus, Users } from "lucide-react";
import { guardarAjuste, leerAjuste } from "../ajustes";
import { Arcos, Marca } from "../componentes/comunes";
import { useSesion } from "../sesion";

/** Persona activa y menú para cambiar a otra o agregar una nueva. */
function SelectorPersona() {
  const navegar = useNavigate();
  const { paciente, pacientes } = useSesion();
  const [abierto, setAbierto] = useState(false);
  const caja = useRef(null);

  useEffect(() => {
    if (!abierto) return undefined;
    const cerrar = (e) => {
      if (e.type === "keydown" ? e.key === "Escape" : !caja.current?.contains(e.target)) setAbierto(false);
    };
    document.addEventListener("mousedown", cerrar);
    document.addEventListener("keydown", cerrar);
    return () => {
      document.removeEventListener("mousedown", cerrar);
      document.removeEventListener("keydown", cerrar);
    };
  }, [abierto]);

  const ir = (ruta) => {
    setAbierto(false);
    navegar(ruta);
  };

  if (!paciente) return null;
  const otras = pacientes.filter((p) => p.id !== paciente.id);
  return (
    <div className="selector-persona" ref={caja}>
      <p className="nav-titulo">PACIENTE ACTIVO {pacientes.length > 1 && `· ${pacientes.length} EN TOTAL`}</p>
      <button type="button" className="perfil perfil-boton" aria-expanded={abierto} aria-haspopup="true"
              onClick={() => setAbierto(!abierto)}>
        <span className="avatar">{paciente.iniciales}</span>
        <div>
          <strong>{paciente.nombre} {paciente.apellido}</strong>
          <small>{paciente.edad ? `${paciente.edad} años · ` : ""}Cambiar de paciente</small>
        </div>
        <ChevronDown size={20} className="perfil-flecha" aria-hidden="true" />
      </button>
      {abierto && (
        <ul className="lista-personas">
          {otras.map((p) => (
            <li key={p.id}>
              <button type="button" onClick={() => ir(`/cuidador/paciente/${p.id}`)}>
                <span className="avatar">{p.iniciales}</span>
                <span>{p.nombre} {p.apellido}</span>
              </button>
            </li>
          ))}
          <li>
            <button type="button" onClick={() => ir("/cuidador/nuevo-paciente")}>
              <span className="avatar avatar-agregar"><UserPlus size={22} /></span>
              <span>Agregar paciente</span>
            </button>
          </li>
          <li>
            <button type="button" onClick={() => ir("/cuidador/pacientes")}>
              <span className="avatar avatar-lista"><Users size={22} /></span>
              <span>Ver todos mis pacientes</span>
            </button>
          </li>
        </ul>
      )}
    </div>
  );
}

/**
 * Ruta /cuidador/paciente/:id. Cambiar de paciente es una navegación, así el
 * panel puede avisar si hay cambios sin guardar antes de cambiar.
 */
export function CambiarPersona() {
  const { id } = useParams();
  const navegar = useNavigate();
  const { elegirPaciente } = useSesion();
  useEffect(() => {
    elegirPaciente(Number(id));
    navegar("/cuidador", { replace: true });
  }, [id, elegirPaciente, navegar]);
  return null;
}

export default function LayoutCuidador() {
  const { cuidador, paciente, salir } = useSesion();
  // Menú lateral escondido o visible; el navegador lo recuerda.
  const [oculto, setOculto] = useState(() => leerAjuste("menuOculto"));
  const mostrarBoton = useRef(null);
  const esconderBoton = useRef(null);

  const cambiarMenu = (ocultar) => {
    setOculto(ocultar);
    guardarAjuste("menuOculto", ocultar);
  };

  // El foco sigue al botón que aparece, así con el teclado no se pierde.
  const primeraVez = useRef(true);
  useEffect(() => {
    if (primeraVez.current) {
      primeraVez.current = false;
      return;
    }
    (oculto ? mostrarBoton : esconderBoton).current?.focus();
  }, [oculto]);

  return (
    <div className={`cuidador ${oculto ? "menu-oculto" : ""}`}>
      {oculto && (
        <button type="button" ref={mostrarBoton} className="mostrar-menu" aria-controls="menu-cuidador"
                aria-expanded="false" onClick={() => cambiarMenu(false)}>
          <Menu size={24} aria-hidden="true" /> Menú
        </button>
      )}
      <aside className="lateral" id="menu-cuidador" hidden={oculto}>
        <Arcos />
        <div className="lateral-cabecera">
          <Marca />
          <button type="button" ref={esconderBoton} className="esconder-menu" aria-controls="menu-cuidador"
                  aria-expanded="true" aria-label="Esconder menú" title="Esconder menú" onClick={() => cambiarMenu(true)}>
            <ChevronsLeft size={24} aria-hidden="true" />
          </button>
        </div>
        <SelectorPersona />
        <p className="nav-titulo">PANEL DEL CUIDADOR</p>
        <nav className="nav">
          <NavLink to="/cuidador/pacientes">Mis pacientes</NavLink>
          <NavLink to="/cuidador" end>Inicio</NavLink>
          <NavLink to="/cuidador/historia">Mi Historia</NavLink>
          <NavLink to="/cuidador/seguimiento">Seguimiento</NavLink>
          <NavLink to="/cuidador/configuracion">Configuración</NavLink>
        </nav>
        <div className="cuenta">
          <small>Cuidador: {cuidador?.first_name || cuidador?.username}</small>
          <button type="button" className="salir" onClick={salir}>
            <LogOut size={20} /> Cerrar sesión
          </button>
        </div>
      </aside>
      <main className="contenido">
        {/* La clave vuelve a montar la página al cambiar de persona: ningún
            dato ni formulario de la persona anterior queda en pantalla. */}
        <Outlet key={paciente?.id ?? "sin-persona"} />
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
