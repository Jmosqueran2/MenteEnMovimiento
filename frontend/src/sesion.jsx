import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, guardarTokens, haySesion, iniciarSesion, registrarCuenta } from "./api";
import { guardarAjuste, leerAjuste } from "./ajustes";

const ContextoSesion = createContext(null);

export function ProveedorSesion({ children }) {
  const [cuidador, setCuidador] = useState(null);
  const [paciente, setPacienteEstado] = useState(null);
  const [cargando, setCargando] = useState(haySesion());

  const cargar = useCallback(async () => {
    if (!haySesion()) {
      setCuidador(null);
      setPacienteEstado(null);
      setCargando(false);
      return;
    }
    try {
      const yo = await api("/api/auth/yo/");
      setCuidador(yo);
      // Cada cuidador puede tener varias personas a cargo: se sigue con la que
      // estaba elegida (o la última elegida en este navegador), si no la primera.
      setPacienteEstado((actual) => {
        const buscada = actual?.id ?? leerAjuste("paciente");
        return yo.adultos_mayores.find((p) => p.id === buscada) || yo.adultos_mayores[0] || null;
      });
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
      setPacienteEstado(null);
    };
    window.addEventListener("mm:sesion-vencida", alVencer);
    return () => window.removeEventListener("mm:sesion-vencida", alVencer);
  }, [cargar]);

  /** Actualiza la persona activa (p. ej. tras guardar su perfil) y la lista. */
  const setPaciente = useCallback((nuevo) => {
    setPacienteEstado(nuevo);
    if (!nuevo) return;
    guardarAjuste("paciente", nuevo.id);
    setCuidador((c) => {
      if (!c) return c;
      const existe = c.adultos_mayores.some((p) => p.id === nuevo.id);
      const lista = existe
        ? c.adultos_mayores.map((p) => (p.id === nuevo.id ? nuevo : p))
        : [...c.adultos_mayores, nuevo];
      return { ...c, adultos_mayores: lista.sort((a, b) => `${a.nombre} ${a.apellido}`.localeCompare(`${b.nombre} ${b.apellido}`, "es")) };
    });
  }, []);

  /** Cambia a otra persona a cargo. */
  const elegirPaciente = useCallback(
    (id) => {
      const elegido = cuidador?.adultos_mayores.find((p) => p.id === id);
      if (elegido) setPaciente(elegido);
    },
    [cuidador, setPaciente],
  );

  /** Quita a una persona de la lista (tras eliminar su perfil) y pasa a otra. */
  const quitarPaciente = useCallback(
    (id) => {
      const lista = (cuidador?.adultos_mayores || []).filter((p) => p.id !== id);
      setCuidador((c) => c && { ...c, adultos_mayores: c.adultos_mayores.filter((p) => p.id !== id) });
      setPacienteEstado((actual) => (actual?.id === id ? lista[0] || null : actual));
    },
    [cuidador],
  );

  const entrar = async (usuario, clave) => {
    await iniciarSesion(usuario, clave);
    setCargando(true);
    await cargar();
  };

  const registrar = async (datos) => {
    await registrarCuenta(datos);
    setCargando(true);
    await cargar();
  };

  const salir = () => {
    guardarTokens(null);
    guardarAjuste("paciente", null);
    setCuidador(null);
    setPacienteEstado(null);
  };

  return (
    <ContextoSesion.Provider
      value={{
        cuidador,
        pacientes: cuidador?.adultos_mayores || [],
        paciente,
        setPaciente,
        elegirPaciente,
        quitarPaciente,
        cargando,
        entrar,
        registrar,
        salir,
        recargar: cargar,
      }}
    >
      {children}
    </ContextoSesion.Provider>
  );
}

export const useSesion = () => useContext(ContextoSesion);
