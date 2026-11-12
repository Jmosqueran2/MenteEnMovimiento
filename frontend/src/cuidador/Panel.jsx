import { useCallback, useEffect, useRef, useState } from "react";
import { useBlocker, useNavigate } from "react-router-dom";
import { AlertTriangle, BellRing, CircleCheck, Clock, Flag, Sparkles } from "lucide-react";
import { api } from "../api";
import { guardarAjuste, leerAjuste } from "../ajustes";
import { enumerar, fechaCorta, hora, NOMBRE_ACTIVIDAD, NOMBRE_NIVEL } from "../formato";
import { useSesion } from "../sesion";
import { ayudaAtendida, leerSesionHoy, marcarAcompanado, prepararSesion, terminarSesionHoy } from "../sesionHoy";
import { ACTIVIDADES } from "../adulto/Menu";
import { Encabezado, useAvisoFlotante } from "./LayoutCuidador";

const VERBO = { subir: "subir", mantener: "mantener", bajar: "bajar" };
const TIEMPOS = [[1500, "1,5 s"], [2000, "2 s"], [2500, "2,5 s"]];
// Cada cuánto se revisa el estado de la sesión de hoy mientras el panel está abierto.
const REVISAR_MS = 15000;

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

const nombresDe = (hoy) => enumerar(hoy.actividades.map((t) => NOMBRE_ACTIVIDAD[t]));

/** Franja de estado de la sesión de hoy: no preparada · lista · en curso · terminada. */
function EstadoSesion({ hoy, nombre, onIrAConfigurar, onTerminar, onSeguimiento, onPrepararOtra }) {
  if (!hoy) return null;
  const { estado } = hoy;
  if (estado === "no_preparada") {
    return (
      <div className="franja-sesion franja-no-preparada" role="status">
        <Clock size={28} aria-hidden="true" />
        <p><strong>Hoy no hay sesión preparada para {nombre}.</strong></p>
        {hoy.inicio_autonomo && (
          <button type="button" className="boton boton-secundario boton-compacto" onClick={onIrAConfigurar}>
            Preparar sesión de {nombre}
          </button>
        )}
      </div>
    );
  }
  if (estado === "lista") {
    return (
      <div className="franja-sesion franja-lista" role="status">
        <CircleCheck size={28} aria-hidden="true" />
        <p>
          <strong>Sesión lista: {nombresDe(hoy)} · {hoy.nivel_texto}.</strong>{" "}
          Preparada a las {hora(hoy.preparada)} · vale hasta hoy a las 23:59.
        </p>
        <button type="button" className="boton boton-secundario boton-compacto" onClick={onIrAConfigurar}>Cambiar</button>
      </div>
    );
  }
  if (estado === "en_curso") {
    const posibles = hoy.realizables.length;
    return (
      <div className="franja-sesion franja-en-curso" role="status">
        <span className="punto-latido" aria-hidden="true" />
        <p>
          <strong>{nombre} está haciendo su sesión</strong> · {hoy.hechas.length} de {posibles}{" "}
          {posibles === 1 ? "actividad" : "actividades"}.
        </p>
        <button type="button" className="boton boton-secundario boton-compacto" onClick={onTerminar}>
          Dar por terminada
        </button>
      </div>
    );
  }
  return (
    <div className="franja-sesion franja-terminada" role="status">
      <Flag size={28} aria-hidden="true" />
      <p>
        <strong>{nombre} terminó a las {hora(hoy.terminada)}</strong>
        {hoy.total > 0 ? ` · ${hoy.aciertos} de ${hoy.total} aciertos` : " · sin actividades completadas"}
        {!hoy.completa && hoy.total > 0 ? ` · hizo ${hoy.hechas.length} de ${hoy.realizables.length} actividades` : ""}.
      </p>
      <button type="button" className="boton boton-secundario boton-compacto" onClick={onSeguimiento}>Ver seguimiento</button>
      {hoy.inicio_autonomo && (
        <button type="button" className="boton boton-secundario boton-compacto" onClick={onPrepararOtra}>Preparar otra</button>
      )}
    </div>
  );
}

function notificar(titulo, cuerpo) {
  try {
    if ("Notification" in window && Notification.permission === "granted") new Notification(titulo, { body: cuerpo });
  } catch {
    // Algunos navegadores no permiten notificaciones fuera de un service worker.
  }
}

/** Pantalla 11: panel del cuidador. */
export default function Panel() {
  const navegar = useNavigate();
  const { cuidador, paciente, setPaciente } = useSesion();
  const [resumen, setResumen] = useState(null);
  const [hoy, setHoy] = useState(null);
  const [nivel, setNivel] = useState(paciente.nivel);
  const [actividades, setActividades] = useState(paciente.actividades_habilitadas);
  const [permanencia, setPermanencia] = useState(paciente.tiempo_permanencia_ms);
  const [autonomo, setAutonomo] = useState(paciente.inicio_autonomo);
  const [bloqueadas, setBloqueadas] = useState(paciente.mostrar_bloqueadas);
  const [historia, setHistoria] = useState(null);
  const [avisar, setAvisar] = useState(() => leerAjuste("avisar"));
  const [error, setError] = useState(null);
  const [guardando, setGuardando] = useState(false);
  const [aviso, mostrarAviso] = useAvisoFlotante();
  const [sugerenciaVista, setSugerenciaVista] = useState(false);
  const configurar = useRef(null);
  const saltarBloqueo = useRef(false);
  const anterior = useRef(null);
  const nombre = paciente.nombre;

  // Al cambiar de persona, el formulario toma sus valores.
  useEffect(() => {
    setNivel(paciente.nivel);
    setActividades(paciente.actividades_habilitadas);
    setPermanencia(paciente.tiempo_permanencia_ms);
    setAutonomo(paciente.inicio_autonomo);
    setBloqueadas(paciente.mostrar_bloqueadas);
    anterior.current = null;
  }, [paciente]);

  useEffect(() => {
    api(`/api/pacientes/${paciente.id}/resumen/`).then(setResumen).catch(() => {});
    api(`/api/historia/?paciente=${paciente.id}`)
      .then((lista) => setHistoria({
        fotos: lista.filter((c) => c.tipo === "imagen").length,
        audios: lista.filter((c) => c.tipo === "audio").length,
      }))
      .catch(() => {});
  }, [paciente.id]);

  // Estado de la sesión de hoy: se revisa cada 15 s y se avisa de los cambios.
  const revisar = useCallback(async () => {
    try {
      const nuevo = await leerSesionHoy(paciente.id);
      const previo = anterior.current;
      if (previo) {
        if (nuevo.ayuda && nuevo.ayuda.id !== previo.ayuda?.id) {
          notificar(`${nombre} pidió ayuda`, nuevo.ayuda.motivo_texto);
        }
        if (avisar && nuevo.estado === "terminada" && previo.estado !== "terminada" && nuevo.id === previo.id) {
          notificar(`${nombre} terminó su sesión`, nuevo.total ? `${nuevo.aciertos} de ${nuevo.total} aciertos` : "");
          api(`/api/pacientes/${paciente.id}/resumen/`).then(setResumen).catch(() => {});
        }
      }
      anterior.current = nuevo;
      setHoy(nuevo);
    } catch {
      // Sin conexión: se reintenta en la próxima vuelta.
    }
  }, [paciente.id, nombre, avisar]);

  useEffect(() => {
    revisar();
    const intervalo = setInterval(revisar, REVISAR_MS);
    return () => clearInterval(intervalo);
  }, [revisar]);

  const enCurso = hoy?.estado === "en_curso";

  const sucio =
    nivel !== paciente.nivel ||
    permanencia !== paciente.tiempo_permanencia_ms ||
    autonomo !== paciente.inicio_autonomo ||
    bloqueadas !== paciente.mostrar_bloqueadas ||
    [...actividades].sort().join() !== [...paciente.actividades_habilitadas].sort().join();

  // Avisar si hay cambios sin guardar.
  const bloqueo = useBlocker(({ currentLocation, nextLocation }) =>
    !saltarBloqueo.current && sucio && currentLocation.pathname !== nextLocation.pathname);
  useEffect(() => {
    if (!sucio) return undefined;
    const evitar = (e) => e.preventDefault();
    window.addEventListener("beforeunload", evitar);
    return () => window.removeEventListener("beforeunload", evitar);
  }, [sucio]);

  const alternar = (tipo) =>
    setActividades((actual) => (actual.includes(tipo) ? actual.filter((t) => t !== tipo) : [...actual, tipo]));

  const configuracion = () => ({
    nivel,
    actividades_habilitadas: actividades,
    tiempo_permanencia_ms: permanencia,
    inicio_autonomo: autonomo,
    mostrar_bloqueadas: bloqueadas,
  });

  const guardar = async () => {
    if (actividades.length === 0) return setError("Deja al menos una actividad habilitada.");
    setError(null);
    setGuardando(true);
    try {
      setPaciente(await api(`/api/pacientes/${paciente.id}/`, { metodo: "PATCH", datos: configuracion() }));
      mostrarAviso("Cambios guardados");
      revisar();
    } catch (e) {
      setError(e.message);
    } finally {
      setGuardando(false);
    }
  };

  /** «Preparar sesión de [nombre]»: guarda todo y deja lista la sesión de hoy. */
  const preparar = async () => {
    if (actividades.length === 0) return setError("Elige al menos una actividad para preparar la sesión.");
    setError(null);
    setGuardando(true);
    try {
      const r = await prepararSesion(paciente.id, configuracion());
      setPaciente(r.paciente);
      anterior.current = r.sesion_hoy;
      setHoy(r.sesion_hoy);
      return r;
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setGuardando(false);
    }
  };

  const prepararYAvisar = async () => {
    if (await preparar()) mostrarAviso(`Listo. ${nombre} ya puede empezar cuando quiera.`);
  };

  /** «Iniciar ahora con [nombre]»: primera sesión o perfil con acompañamiento. */
  const iniciarAhora = async () => {
    if (await preparar()) {
      marcarAcompanado(paciente.id);
      saltarBloqueo.current = true;
      navegar("/jugar");
    }
  };

  const darPorTerminada = async () => {
    try {
      const r = await terminarSesionHoy(paciente.id);
      anterior.current = r;
      setHoy(r);
    } catch (e) {
      setError(e.message);
    }
  };

  const entendido = async () => {
    try {
      const r = await ayudaAtendida(paciente.id);
      anterior.current = r;
      setHoy(r);
    } catch {
      // Se reintenta en la próxima revisión.
    }
  };

  const cambiarAvisar = async (valor) => {
    if (valor && "Notification" in window && Notification.permission === "default") {
      await Notification.requestPermission().catch(() => {});
    }
    setAvisar(valor);
    guardarAjuste("avisar", valor);
  };

  const confirmarAutonomia = async () => {
    try {
      setPaciente(await api(`/api/pacientes/${paciente.id}/`, { metodo: "PATCH", datos: { inicio_autonomo: true } }));
      mostrarAviso(`Listo. ${nombre} podrá empezar sola cuando prepares su sesión.`);
      revisar();
    } catch (e) {
      setError(e.message);
    }
  };

  const irAConfigurar = () => configurar.current?.scrollIntoView({ behavior: "smooth", block: "start" });

  const ultima = resumen?.ultima_sesion;
  const historiaActiva = actividades.includes("historia");
  const permisoDenegado = "Notification" in window && Notification.permission === "denied";

  // Un solo botón principal: preparar (puede iniciar sola) o iniciar ahora (acompañamiento).
  // Mientras la sesión está en curso no se configura nada.
  let principal;
  if (enCurso) {
    principal = (
      <button type="button" className="boton boton-principal" onClick={() => navegar("/cuidador/seguimiento")}>
        Ver seguimiento
      </button>
    );
  } else if (autonomo) {
    principal = (
      <button type="button" className="boton boton-principal boton-preparar" disabled={guardando} onClick={prepararYAvisar}>
        {guardando ? "Preparando…" : `Preparar sesión de ${nombre}`}
      </button>
    );
  } else {
    principal = (
      <button type="button" className="boton boton-principal boton-preparar" disabled={guardando} onClick={iniciarAhora}>
        {guardando ? "Preparando…" : `Iniciar ahora con ${nombre}`}
      </button>
    );
  }

  return (
    <>
      <Encabezado etiqueta="Inicio" titulo={`Hola, ${cuidador.first_name || cuidador.username}`} />

      {hoy?.ayuda && (
        <div className="franja-sesion franja-ayuda" role="alert">
          <BellRing size={28} aria-hidden="true" />
          <p><strong>{nombre} pidió ayuda a las {hora(hoy.ayuda.creado)}</strong> · {hoy.ayuda.motivo_texto}.</p>
          <button type="button" className="boton boton-secundario boton-compacto" onClick={entendido}>Entendido</button>
        </div>
      )}

      <EstadoSesion
        hoy={hoy}
        nombre={nombre}
        onIrAConfigurar={irAConfigurar}
        onTerminar={darPorTerminada}
        onSeguimiento={() => navegar("/cuidador/seguimiento")}
        onPrepararOtra={irAConfigurar}
      />

      {hoy?.sugerir_autonomia && !sugerenciaVista && (
        <div className="franja-sesion franja-lista" role="status">
          <Sparkles size={28} aria-hidden="true" />
          <p><strong>{nombre} completó su sesión sin ayuda.</strong> ¿Quieres que pueda empezar sola?</p>
          <button type="button" className="boton boton-principal boton-compacto" onClick={confirmarAutonomia}>Sí, puede sola</button>
          <button type="button" className="boton boton-secundario boton-compacto" onClick={() => setSugerenciaVista(true)}>
            Todavía no
          </button>
        </div>
      )}

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
        <div className="tarjeta bloque" ref={configurar}>
          <h2>Configurar la sesión</h2>
          {enCurso && (
            <p className="cambios-pendientes">
              <Clock size={20} /> Podrás cambiar la configuración cuando {nombre} termine.
            </p>
          )}
          <fieldset className="configurar-sesion" disabled={enCurso}>
            <h3>Nivel de dificultad</h3>
            <div className="segmentado" role="group" aria-label="Nivel de dificultad">
              {Object.entries(NOMBRE_NIVEL).map(([valor, texto]) => (
                <button key={valor} type="button" aria-pressed={nivel === valor} onClick={() => setNivel(valor)}>
                  {texto}
                </button>
              ))}
            </div>
            <p className="texto-apoyo" style={{ fontSize: 16 }}>
              El nivel también se ajusta solo después de cada actividad, según los aciertos, los reintentos, el tiempo
              de respuesta y las sesiones anteriores.
            </p>
            {ultima?.ajuste && <Recomendacion sesion={ultima} />}

            <h3>Actividades de hoy</h3>
            <div className="casillas">
              {ACTIVIDADES.map(({ tipo }) => (
                <label key={tipo} className="casilla">
                  <input type="checkbox" checked={actividades.includes(tipo)} onChange={() => alternar(tipo)} />
                  {NOMBRE_ACTIVIDAD[tipo]}
                </label>
              ))}
            </div>
            <label className="casilla casilla-chica">
              <input type="checkbox" checked={bloqueadas} onChange={(e) => setBloqueadas(e.target.checked)} />
              Mostrarle las actividades que no tocan hoy, con candado
            </label>

            <h3>Tiempo para elegir</h3>
            <div className="segmentado" role="group" aria-label="Tiempo para elegir">
              {TIEMPOS.map(([ms, texto]) => (
                <button key={ms} type="button" aria-pressed={permanencia === ms} onClick={() => setPermanencia(ms)}>
                  {texto}
                </button>
              ))}
            </div>
            {paciente.puntero === "mirada" && (
              <p className="texto-apoyo" style={{ fontSize: 16 }}>Con la mirada recomendamos 2 o 2,5 s.</p>
            )}

            {historiaActiva && (
              <p className="texto-apoyo" style={{ fontSize: 17 }}>
                <strong>Mi Historia:</strong>{" "}
                {historia ? `${historia.fotos} ${historia.fotos === 1 ? "foto" : "fotos"} · ${historia.audios} ${historia.audios === 1 ? "audio" : "audios"}` : "…"}{" "}
                · <button type="button" className="enlace" onClick={() => navegar("/cuidador/historia")}>Elegir fotos</button>
              </p>
            )}

            <h3>¿Cómo empieza sus sesiones?</h3>
            <div className="opciones-perfil" role="radiogroup" aria-label="Cómo empieza sus sesiones">
              <label className="casilla">
                <input type="radio" name="perfil" checked={autonomo} onChange={() => setAutonomo(true)} />
                <span><strong>Puede iniciar sola</strong> — Tú preparas la sesión y {nombre} la empieza cuando quiera.</span>
              </label>
              <label className="casilla">
                <input type="radio" name="perfil" checked={!autonomo} onChange={() => setAutonomo(false)} />
                <span><strong>Requiere acompañamiento</strong> — Tú inicias la sesión y te quedas a su lado.</span>
              </label>
            </div>
          </fieldset>

          <label className="casilla casilla-chica">
            <input type="checkbox" checked={avisar} onChange={(e) => cambiarAvisar(e.target.checked)} />
            Avisarme en este equipo cuando {nombre} termine
          </label>
          {avisar && permisoDenegado && (
            <p className="texto-apoyo" style={{ fontSize: 15 }}>
              El navegador bloqueó las notificaciones; el aviso se verá solo aquí, en el panel.
            </p>
          )}

          {error && <p className="error-texto">{error}</p>}
          {sucio && !enCurso && (
            <p className="cambios-pendientes">
              <AlertTriangle size={20} /> Tienes cambios sin guardar
            </p>
          )}
        </div>

        <div className="bloque">
          <h2>Acciones</h2>
          <div className="acciones-rapidas">
            {principal}
            {!enCurso && (
              <button type="button" className="boton boton-secundario" disabled={!sucio || guardando} onClick={guardar}>
                Guardar cambios
              </button>
            )}
            <button type="button" className="boton boton-secundario" onClick={() => navegar("/cuidador/historia")}>
              Subir foto o audio
            </button>
            {!enCurso && (
              <button type="button" className="boton boton-secundario" onClick={() => navegar("/cuidador/seguimiento")}>
                Ver seguimiento
              </button>
            )}
            {autonomo && !enCurso && (
              <button type="button" className="boton boton-secundario" disabled={guardando} onClick={iniciarAhora}>
                Iniciar ahora con {nombre}
              </button>
            )}
          </div>
        </div>
      </div>

      {bloqueo.state === "blocked" && (
        <div className="dialogo-fondo">
          <div className="dialogo" style={{ fontSize: 20 }}>
            <h2>Tienes cambios sin guardar</h2>
            <p>Si sales ahora, se perderán los cambios en la configuración de la sesión.</p>
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
