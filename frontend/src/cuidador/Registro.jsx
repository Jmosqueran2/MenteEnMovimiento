import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { registroAbierto } from "../api";
import { Cargando, Marca } from "../componentes/comunes";
import { useSesion } from "../sesion";

/** Cuenta nueva de cuidador: cada cuenta ve solo a las personas que agrega. */
export default function Registro() {
  const navegar = useNavigate();
  const { cuidador, registrar } = useSesion();
  const [abierto, setAbierto] = useState(null);
  const [datos, setDatos] = useState({ nombre: "", usuario: "", email: "", clave: "", repetir: "" });
  const [errores, setErrores] = useState({});
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    registroAbierto().then(setAbierto);
  }, []);

  if (cuidador) return <Navigate to="/cuidador" replace />;
  if (abierto === null) return <Cargando />;

  const cambiar = (campo) => (e) => setDatos({ ...datos, [campo]: e.target.value });

  const enviar = async (e) => {
    e.preventDefault();
    if (datos.clave !== datos.repetir) return setErrores({ repetir: "Las claves no coinciden." });
    setEnviando(true);
    setErrores({});
    try {
      await registrar({
        nombre: datos.nombre.trim(),
        usuario: datos.usuario.trim(),
        email: datos.email.trim(),
        clave: datos.clave,
      });
      navegar("/cuidador/configuracion");
    } catch (err) {
      // Los errores de cada campo se muestran debajo del campo; el resto, abajo.
      const porCampo = {};
      if (err.datos && typeof err.datos === "object" && !err.datos.detail) {
        for (const [campo, mensajes] of Object.entries(err.datos)) {
          porCampo[campo] = [].concat(mensajes).join(" ");
        }
      }
      setErrores(Object.keys(porCampo).length ? porCampo : { general: err.message });
      setEnviando(false);
    }
  };

  const error = (campo) => errores[campo] && <p className="error-texto" id={`error-${campo}`}>{errores[campo]}</p>;

  return (
    <div className="login">
      <form onSubmit={enviar}>
        <Marca />
        <h1 style={{ fontSize: 30 }}>Crear cuenta de cuidador</h1>
        {!abierto ? (
          <p>La creación de cuentas está desactivada. Pide una cuenta al administrador.</p>
        ) : (
          <>
            <p className="pista-demo">
              Con tu cuenta podrás agregar a una o varias personas a tu cargo. Cada una tiene su propio perfil,
              su Mi Historia y su progreso.
            </p>
            <div className="campo">
              <label htmlFor="nombre">Tu nombre</label>
              <input id="nombre" autoComplete="name" value={datos.nombre} onChange={cambiar("nombre")}
                     maxLength={150} required aria-describedby={errores.nombre ? "error-nombre" : undefined} />
              {error("nombre")}
            </div>
            <div className="campo">
              <label htmlFor="usuario">Usuario (para entrar)</label>
              <input id="usuario" autoComplete="username" value={datos.usuario} onChange={cambiar("usuario")}
                     maxLength={150} required aria-describedby={errores.usuario ? "error-usuario" : undefined} />
              {error("usuario")}
            </div>
            <div className="campo">
              <label htmlFor="email">Correo (opcional)</label>
              <input id="email" type="email" autoComplete="email" value={datos.email} onChange={cambiar("email")}
                     aria-describedby={errores.email ? "error-email" : undefined} />
              {error("email")}
            </div>
            <div className="campo">
              <label htmlFor="clave">Clave</label>
              <input id="clave" type="password" autoComplete="new-password" value={datos.clave}
                     onChange={cambiar("clave")} required minLength={8}
                     aria-describedby={errores.clave ? "error-clave" : "ayuda-clave"} />
              {error("clave") || <p className="pista-demo" id="ayuda-clave">Al menos 8 caracteres, que no sean solo números.</p>}
            </div>
            <div className="campo">
              <label htmlFor="repetir">Repite la clave</label>
              <input id="repetir" type="password" autoComplete="new-password" value={datos.repetir}
                     onChange={cambiar("repetir")} required
                     aria-describedby={errores.repetir ? "error-repetir" : undefined} />
              {error("repetir")}
            </div>
            {error("general")}
            <button type="submit" className="boton boton-principal" disabled={enviando}>
              {enviando ? "Creando cuenta…" : "Crear cuenta"}
            </button>
          </>
        )}
        <p className="enlace-login">
          ¿Ya tienes cuenta? <Link to="/login">Entrar</Link>
        </p>
      </form>
    </div>
  );
}
