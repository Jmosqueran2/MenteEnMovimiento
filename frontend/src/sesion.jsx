import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, guardarTokens, haySesion, iniciarSesion } from "./api";

const ContextoSesion = createContext(null);

export function ProveedorSesion({ children }) {
  const [cuidador, setCuidador] = useState(null);
  const [paciente, setPaciente] = useState(null);
  const [cargando, setCargando] = useState(haySesion());

  const cargar = useCallback(async () => {
    if (!haySesion()) {
      setCuidador(null);
      setPaciente(null);
      setCargando(false);
      return;
    }
    try {
      const yo = await api("/api/auth/yo/");
      setCuidador(yo);
      // El prototipo trabaja con una persona a cargo; se toma la primera.
      setPaciente((actual) => yo.adultos_mayores.find((p) => p.id === actual?.id) || yo.adultos_mayores[0] || null);
    } catch {
      guardarTokens(null);
      setCuidador(null);
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargar();
    const alVencer = () => {
      setCuidador(null);
      setPaciente(null);
    };
    window.addEventListener("mm:sesion-vencida", alVencer);
    return () => window.removeEventListener("mm:sesion-vencida", alVencer);
  }, [cargar]);

  const entrar = async (usuario, clave) => {
    await iniciarSesion(usuario, clave);
    setCargando(true);
    await cargar();
  };

  const salir = () => {
    guardarTokens(null);
    setCuidador(null);
    setPaciente(null);
  };

  return (
    <ContextoSesion.Provider value={{ cuidador, paciente, setPaciente, cargando, entrar, salir, recargar: cargar }}>
      {children}
    </ContextoSesion.Provider>
  );
}

export const useSesion = () => useContext(ContextoSesion);
