import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { registroAbierto } from "../api";
import { Marca } from "../componentes/comunes";
import { useSesion } from "../sesion";

export default function Login() {
  const navegar = useNavigate();
  const { cuidador, entrar } = useSesion();
  const [usuario, setUsuario] = useState("");
  const [clave, setClave] = useState("");
  const [error, setError] = useState(null);
  const [enviando, setEnviando] = useState(false);
  const [puedeRegistrarse, setPuedeRegistrarse] = useState(false);

  useEffect(() => {
    registroAbierto().then(setPuedeRegistrarse);
  }, []);

  if (cuidador) return <Navigate to="/cuidador" replace />;

  const enviar = async (e) => {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      await entrar(usuario, clave);
      navegar("/cuidador");
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="login">
      <form onSubmit={enviar}>
        <Marca />
        <h1 style={{ fontSize: 30 }}>Panel del cuidador</h1>
        <div className="campo">
          <label htmlFor="usuario">Usuario</label>
          <input id="usuario" autoComplete="username" value={usuario} onChange={(e) => setUsuario(e.target.value)} required />
        </div>
        <div className="campo">
          <label htmlFor="clave">Clave</label>
          <input id="clave" type="password" autoComplete="current-password" value={clave}
                 onChange={(e) => setClave(e.target.value)} required />
        </div>
        {error && <p className="error-texto">{error}</p>}
        <button type="submit" className="boton boton-principal" disabled={enviando}>
          {enviando ? "Entrando…" : "Entrar"}
        </button>
        {import.meta.env.DEV && <p className="pista-demo">Demo: cuidador / MenteEnMovimiento2026</p>}
        {puedeRegistrarse && (
          <p className="enlace-login">
            ¿Primera vez? <Link to="/registro">Crear una cuenta</Link>
          </p>
        )}
      </form>
    </div>
  );
}
