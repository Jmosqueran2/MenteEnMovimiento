import { useEffect, useState } from "react";
import { useBlocker, useNavigate } from "react-router-dom";
import { AlertTriangle, Sparkles } from "lucide-react";
import { api } from "../api";
import { fechaCorta, NOMBRE_ACTIVIDAD, NOMBRE_NIVEL } from "../formato";
import { useSesion } from "../sesion";
import { ACTIVIDADES } from "../adulto/Menu";
import { Encabezado, useAvisoFlotante } from "./LayoutCuidador";


const VERBO = { subir: "subir", mantener: "mantener", bajar: "bajar" };

function Recomendacion({ sesion }) {
  const quien = sesion.ajuste_metodo === "modelo" ? "el modelo de IA" : "las reglas automáticas";
  const confianza = sesion.ajuste_confianza ? ` (confianza ${Math.round(sesion.ajuste_confianza * 100)} %)` : "";
  const destino = sesion.ajuste === "mantener" ? `el nivel ${sesion.nivel_siguiente}` : `a ${sesion.nivel_siguiente}`;
  return (
    <p className="recomendacion">
      <Sparkles size={20} aria-hidden="true" />
      <span>
        Tras la última sesión, {quien} recomendó <strong>{VERBO[sesion.ajuste]} {destino}</strong>
        {confianza}. Puedes cambiarlo aquí si lo consideras necesario.
      </span>
    </p>
  );
}

/** Pantalla 11: panel del cuidador. */
export default function Panel() {
  const navegar = useNavigate();
  const { cuidador, paciente, setPaciente } = useSesion();
  const [resumen, setResumen] = useState(null);
  const [nivel, setNivel] = useState(paciente.nivel);
  const [actividades, setActividades] = useState(paciente.actividades_habilitadas);
  const [error, setError] = useState(null);
  const [guardando, setGuardando] = useState(false);
  const [aviso, mostrarAviso] = useAvisoFlotante();

  useEffect(() => {
    api(`/api/pacientes/${paciente.id}/resumen/`).then(setResumen).catch(() => {});
  }, [paciente.id]);

  const sucio =
    nivel !== paciente.nivel ||
    [...actividades].sort().join() !== [...paciente.actividades_habilitadas].sort().join();

  // Ajuste propuesto: avisar si hay cambios sin guardar.
  const bloqueo = useBlocker(({ currentLocation, nextLocation }) => sucio && currentLocation.pathname !== nextLocation.pathname);
  useEffect(() => {
    if (!sucio) return undefined;
    const avisar = (e) => e.preventDefault();
    window.addEventListener("beforeunload", avisar);
    return () => window.removeEventListener("beforeunload", avisar);
  }, [sucio]);

  const alternar = (tipo) =>
    setActividades((actual) => (actual.includes(tipo) ? actual.filter((t) => t !== tipo) : [...actual, tipo]));

  const guardar = async () => {
    if (actividades.length === 0) return setError("Deja al menos una actividad habilitada.");
    setError(null);
    setGuardando(true);
    try {
      const actualizado = await api(`/api/pacientes/${paciente.id}/`, {
        metodo: "PATCH",
        datos: { nivel, actividades_habilitadas: actividades },
      });
      setPaciente(actualizado);
      mostrarAviso("Cambios guardados");
    } catch (e) {
      setError(e.message);
    } finally {
      setGuardando(false);
    }
  };

  const ultima = resumen?.ultima_sesion;

  return (
    <>
      <Encabezado etiqueta="Inicio" titulo={`Hola, ${cuidador.first_name || cuidador.username}`} />

      <div className="cifras">
        <div className="tarjeta cifra">
          <strong>{ultima ? fechaCorta(ultima.fecha) : "Sin sesiones"}</strong>
          <span>Última sesión</span>
        </div>
        <div className="tarjeta cifra">
          <strong>{ultima ? `${ultima.aciertos} de ${ultima.total}` : "—"}</strong>
          <span>Aciertos</span>
        </div>
        <div className="tarjeta cifra">
          <strong>{NOMBRE_NIVEL[paciente.nivel]}</strong>
          <span>Nivel actual</span>
        </div>
      </div>

      <div className="columnas">
        <div className="tarjeta bloque">
          <h2>Nivel de dificultad</h2>
          <div className="segmentado" role="group" aria-label="Nivel de dificultad">
            {Object.entries(NOMBRE_NIVEL).map(([valor, texto]) => (
              <button key={valor} type="button" aria-pressed={nivel === valor} onClick={() => setNivel(valor)}>
                {texto}
              </button>
            ))}
          </div>
          <p className="texto-apoyo" style={{ fontSize: 16 }}>
            El nivel también se ajusta solo después de cada sesión, según los aciertos, los reintentos, el tiempo
            de respuesta y las sesiones anteriores.
          </p>
          {ultima?.ajuste && <Recomendacion sesion={ultima} />}
          <h2>Actividades habilitadas</h2>
          <div className="casillas">
            {ACTIVIDADES.map(({ tipo }) => (
              <label key={tipo} className="casilla">
                <input type="checkbox" checked={actividades.includes(tipo)} onChange={() => alternar(tipo)} />
                {NOMBRE_ACTIVIDAD[tipo]}
              </label>
            ))}
          </div>
          {error && <p className="error-texto">{error}</p>}
          {sucio && (
            <p className="cambios-pendientes">
              <AlertTriangle size={20} /> Tienes cambios sin guardar
            </p>
          )}
        </div>

        <div className="bloque">
          <h2>Acciones rápidas</h2>
          <div className="acciones-rapidas">
            <button type="button" className="boton boton-principal" onClick={() => navegar("/cuidador/historia")}>
              Subir foto o audio
            </button>
            <button type="button" className="boton boton-secundario" onClick={() => navegar("/cuidador/seguimiento")}>
              Ver seguimiento
            </button>
            <button type="button" className="boton boton-secundario" onClick={() => navegar("/jugar")}>
              Ver como {paciente.nombre}
            </button>
            <button type="button" className="boton boton-principal" disabled={!sucio || guardando} onClick={guardar}>
              {guardando ? "Guardando…" : "Guardar cambios"}
            </button>
          </div>
        </div>
      </div>

      {bloqueo.state === "blocked" && (
        <div className="dialogo-fondo">
          <div className="dialogo" style={{ fontSize: 20 }}>
            <h2>Tienes cambios sin guardar</h2>
            <p>Si sales ahora, se perderán los cambios en el nivel o las actividades.</p>
            <div className="acciones">
              <button type="button" className="boton boton-secundario" onClick={() => bloqueo.reset()}>
                Seguir editando
              </button>
              <button type="button" className="boton boton-principal" onClick={() => bloqueo.proceed()}>
                Salir sin guardar
              </button>
            </div>
          </div>
        </div>
      )}
      {aviso}
    </>
  );
}
