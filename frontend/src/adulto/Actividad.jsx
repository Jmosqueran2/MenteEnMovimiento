import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft, ArrowRight, Check, Flag, Lightbulb, Pause, Play, RotateCw, Trophy, Volume2,
} from "lucide-react";
import { api } from "../api";
import { Boton, Cargando, IconoCirculo, PantallaAdulto } from "../componentes/comunes";
import { AvisoAyudaPedida, BotonAyuda, useAyuda } from "../componentes/ayuda";
import { NOMBRE_ACTIVIDAD, rolCuidador } from "../formato";
import { useSesion } from "../sesion";
import { leerSesionHoy } from "../sesionHoy";
import { callar, hablar, sonarAcierto, sonarReintento } from "../sonidos";
import { useVision } from "../vision/ProveedorVision";
import { formasDeNumero } from "../vision/voz";
import { JuegoOrden, JuegoParejas, Memorizar, SigueFigura, TarjetaOpcion } from "./Juegos";

const TITULOS = {
  memoria: "Ejercicio de memoria",
  atencion: "Atención",
  coordinacion: "Coordinación",
  historia: "Mi Historia",
};

/** Pantallas 05 a 08: pregunta → acierto / reintento → … → resumen. */
export default function Actividad() {
  const { tipo } = useParams();
  return <ActividadDeTipo key={tipo} tipo={tipo} />;
}

function ActividadDeTipo({ tipo }) {
  const navegar = useNavigate();
  const { paciente } = useSesion();
  const { setModo, reiniciarObservaciones, tomarObservaciones } = useVision();
  // Para el cierre al desmontar (cancelada), que no ve las funciones nuevas.
  const observaciones = useRef(tomarObservaciones);
  observaciones.current = tomarObservaciones;

  const [sesion, setSesion] = useState(null);
  const [error, setError] = useState(null);
  const [indice, setIndice] = useState(0);
  // pregunta | acierto | reintento | revelada | resumen
  const [fase, setFase] = useState("pregunta");
  const [resultado, setResultado] = useState(null);
  const [marcas, setMarcas] = useState([]);
  const [resumen, setResumen] = useState(null);
  const [pausa, setPausa] = useState(false);

  const inicioPregunta = useRef(0);
  const enviando = useRef(false);
  const sesionActual = useRef(null);
  const terminada = useRef(false);

  // Crear la sesión. En Coordinación la zona activa crece para obligar a estirar los brazos.
  useEffect(() => {
    let vigente = true;
    setModo(tipo === "coordinacion" ? "coordinacion" : "seleccion");
    api("/api/sesiones/", { metodo: "POST", datos: { paciente: paciente.id, tipo } })
      .then((nueva) => {
        if (!vigente) return;
        sesionActual.current = nueva;
        reiniciarObservaciones(); // lo que la IA observe desde aquí es de esta actividad
        setSesion(nueva);
        inicioPregunta.current = performance.now();
      })
      .catch((e) => vigente && setError(e.message));
    return () => {
      vigente = false;
      setModo("seleccion");
    };
  }, [tipo, paciente.id, setModo, reiniciarObservaciones]);

  // Si se sale a mitad de la actividad, la sesión queda como cancelada.
  useEffect(
    () => () => {
      callar();
      const s = sesionActual.current;
      if (s && !terminada.current) {
        api(`/api/sesiones/${s.id}/finalizar/`, { metodo: "POST", datos: { cancelada: true, observaciones: observaciones.current() } }).catch(() => {});
      }
    },
    [],
  );

  const pregunta = sesion?.preguntas[indice];
  const total = sesion?.preguntas.length || 0;

  useEffect(() => {
    if (fase === "pregunta" && pregunta) {
      if (pregunta.juego === "alcanza_recuerda") {
        const { enunciado_inicial: inicial, recordar } = pregunta.ajustes;
        return hablar(`${inicial}: ${recordar.texto}.`);
      }
      // En Sigue la figura el enunciado ya nombra la figura.
      const estimulo = pregunta.estimulo?.texto && pregunta.juego !== "sigue_figura"
        ? ` ${pregunta.estimulo.texto}.` : "";
      hablar(`${pregunta.enunciado}${estimulo}`);
    }
  }, [fase, pregunta]);

  const marcar = (valor) =>
    setMarcas((anteriores) => {
      const copia = [...anteriores];
      copia[indice] = valor;
      return copia;
    });

  // respuesta: { opcion } | { orden } (secuencias) | { errores } (parejas)
  const responder = async (respuesta) => {
    if (enviando.current || pausa) return;
    enviando.current = true;
    try {
      const r = await api(`/api/sesiones/${sesion.id}/responder/`, {
        metodo: "POST",
        datos: {
          indice_pregunta: indice,
          ...respuesta,
          tiempo_ms: Math.round(performance.now() - inicioPregunta.current),
        },
      });
      setResultado(r);
      if (r.completado) {
        // Parejas siempre termina: con pocos errores es un acierto.
        marcar(r.correcta ? "acierto" : "resuelta");
        sonarAcierto();
        hablar(r.correcta ? "¡Encontraste todas las parejas! Muy buena memoria." : "¡Encontraste todas las parejas! Muy bien.");
        setFase("acierto");
      } else if (r.correcta) {
        marcar(r.intento === 1 ? "acierto" : "resuelta");
        sonarAcierto();
        hablar(pregunta.modo === "orden" ? "¡Muy bien! Ese es el orden correcto." : `¡Muy bien! Elegiste ${r.opcion_elegida.texto}.`);
        setFase("acierto");
      } else if (r.puede_reintentar) {
        sonarReintento();
        hablar(`Casi lo logras. Te damos una pista: ${r.pista}`);
        setFase("reintento");
      } else {
        marcar("fallada");
        sonarReintento();
        hablar(`La respuesta era ${r.respuesta_correcta.texto}. Sigamos adelante.`);
        setFase("revelada");
      }
    } catch (e) {
      setError(e.message);
    } finally {
      enviando.current = false;
    }
  };

  const finalizar = useCallback(async () => {
    try {
      const r = await api(`/api/sesiones/${sesion.id}/finalizar/`, {
        metodo: "POST", datos: { observaciones: tomarObservaciones() },
      });
      terminada.current = true;
      setResumen(r);
      setFase("resumen");
      sonarAcierto();
      hablar(`¡Terminaste tu sesión! Tuviste ${r.aciertos} aciertos de ${r.total}. Hiciste un gran trabajo hoy.`);
    } catch (e) {
      setError(e.message);
    }
  }, [sesion, tomarObservaciones]);

  const siguiente = () => {
    if (indice + 1 >= total) return finalizar();
    setIndice(indice + 1);
    setResultado(null);
    setFase("pregunta");
    inicioPregunta.current = performance.now();
  };

  const reintentar = () => {
    setFase("pregunta");
    inicioPregunta.current = performance.now();
  };

  const menu = () => navegar("/jugar/menu");

  if (error) return <NoPudimosEmpezar tipo={tipo} error={error} menu={menu} />;

  if (!sesion) return <Cargando texto="Preparando tu actividad…" />;

  const comunes = { tipo, indice, total, marcas, pregunta, resultado, menu };

  return (
    <>
      {fase === "pregunta" && (
        <Pregunta
          {...comunes}
          onResponder={responder}
          onPausa={() => setPausa(true)}
          // El tiempo cuenta desde que se puede responder, no durante animaciones.
          onListo={() => { inicioPregunta.current = performance.now(); }}
        />
      )}
      {fase === "acierto" && <Acierto {...comunes} onSiguiente={siguiente} />}
      {fase === "revelada" && <Acierto {...comunes} revelada onSiguiente={siguiente} />}
      {fase === "reintento" && <Reintento {...comunes} onReintentar={reintentar} />}
      {fase === "resumen" && <Resumen resumen={resumen} paciente={paciente} menu={menu} tipo={tipo} />}
      {pausa && (
        <div className="dialogo-fondo">
          <div className="dialogo">
            <IconoCirculo icono={Pause} tamano={96} />
            <h2 className="titulo" style={{ justifyContent: "center" }}>En pausa</h2>
            <p>Tómate tu tiempo. Cuando quieras, seguimos.</p>
            <div className="acciones">
              <Boton variante="secundario" icono={ArrowLeft} onClick={menu}>Volver al menú</Boton>
              <Boton icono={Play} onClick={() => { setPausa(false); inicioPregunta.current = performance.now(); }}>
                Continuar
              </Boton>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function Puntos({ total, marcas, actual }) {
  return (
    <div className="puntos" aria-label={`Pregunta ${actual + 1} de ${total}`}>
      {Array.from({ length: total }, (_, i) => (
        <span key={i} className={marcas[i] || (i === actual ? "actual" : "")}>
          {marcas[i] === "acierto" && <Check size={16} strokeWidth={4} />}
        </span>
      ))}
    </div>
  );
}

function Estimulo({ pregunta }) {
  const audio = useRef(null);
  const medio = pregunta.medio;
  if (medio?.tipo === "imagen") {
    return (
      <div className="estimulo">
        <img src={medio.url} alt="Foto de Mi Historia" />
      </div>
    );
  }
  if (medio?.tipo === "audio") {
    return (
      <div className="estimulo">
        <audio ref={audio} src={medio.url} autoPlay controls />
        <Boton
          variante="secundario"
          icono={Volume2}
          onClick={() => {
            audio.current.currentTime = 0;
            audio.current.play();
          }}
        >
          Escuchar otra vez
        </Boton>
      </div>
    );
  }
  if (!pregunta.estimulo?.emoji && !pregunta.estimulo?.texto) return null;
  return (
    <div className="estimulo">
      <span className="estimulo-emoji" role="img" aria-label={pregunta.estimulo.texto}>
        {pregunta.estimulo.emoji}
      </span>
      <span>{pregunta.estimulo.texto}</span>
    </div>
  );
}

// Juegos en los que hay que encontrar algo con la vista: con la voz se elige
// solo por número, porque decir el nombre los resolvería sin mirar.
const JUEGOS_DE_MIRAR = new Set(["pareja_igual", "foto_igual", "quien_es"]);

// Consigna de arriba para los juegos que no son "elige la respuesta".
const CONSIGNAS = {
  parejas: "Destapa dos cartas a la vez",
  orden: "Señala los pasos en orden",
  ordenar_recuerdos: "Señala los recuerdos en orden",
  sigue_figura: "No le quites la vista",
};

function Pregunta({ tipo, indice, total, marcas, pregunta, onResponder, onPausa, onListo }) {
  const coordinacion = tipo === "coordinacion";
  const { puntero, movilidad, conVoz } = useVision();
  const soloVoz = puntero === "voz";
  const conMirada = puntero === "mirada" && !coordinacion;
  const conCabeza = coordinacion && movilidad === "cabeza";
  const { juego, modo } = pregunta;
  // Alcanza y recuerda: primero se memoriza el objeto, después aparecen las respuestas.
  const [memorizando, setMemorizando] = useState(juego === "alcanza_recuerda");

  useEffect(() => {
    if (modo === "eleccion" && juego !== "sigue_figura" && !memorizando) onListo();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [memorizando]);

  const terminarMemorizar = () => {
    setMemorizando(false);
    hablar(pregunta.enunciado);
  };

  const consigna = CONSIGNAS[juego] || CONSIGNAS[modo]
    || (memorizando ? "Mira bien y recuérdalo"
      : !coordinacion ? "Elige la respuesta"
      : conCabeza ? "Gira la cabeza hacia la respuesta"
      : movilidad === "brazo_izquierdo" ? "Estira el brazo izquierdo hacia la respuesta"
      : movilidad === "brazo_derecho" ? "Estira el brazo derecho hacia la respuesta"
      : "Estira el brazo hacia la respuesta");
  const enunciado = memorizando ? pregunta.ajustes.enunciado_inicial : pregunta.enunciado;
  const elegir = (i) => onResponder({ opcion: i });
  const soloNumero = soloVoz && JUEGOS_DE_MIRAR.has(juego);

  let contenido;
  if (modo === "parejas") {
    contenido = <JuegoParejas pregunta={pregunta} onTerminar={(errores) => onResponder({ errores })} onListo={onListo} />;
  } else if (modo === "orden") {
    contenido = <JuegoOrden pregunta={pregunta} onTerminar={(orden) => onResponder({ orden })} onListo={onListo} />;
  } else if (juego === "sigue_figura") {
    contenido = <SigueFigura pregunta={pregunta} onElegir={elegir} onListo={onListo} />;
  } else if (memorizando) {
    contenido = <Memorizar objeto={pregunta.ajustes.recordar} duracionMs={pregunta.ajustes.memorizar_ms} onFin={terminarMemorizar} />;
  } else {
    contenido = (
      <div className={`opciones ${coordinacion ? "opciones-coordinacion" : ""} ${pregunta.opciones.length === 3 ? "opciones-tres" : ""}`}>
        {pregunta.opciones.map((opcion, i) => (
          <TarjetaOpcion
            key={`${indice}-${i}`}
            opcion={opcion}
            className="elegible-tarjeta"
            data-elegible=""
            // Con la voz cada opción lleva número; en los juegos de mirar, solo vale el número.
            numeroVoz={soloVoz ? i + 1 : null}
            sinTexto={soloNumero}
            data-voz={soloVoz && !soloNumero ? formasDeNumero(i + 1) : undefined}
            data-voz-solo={soloNumero ? formasDeNumero(i + 1) : undefined}
            onClick={() => elegir(i)}
          />
        ))}
      </div>
    );
  }

  const ayuda = soloVoz
    ? (modo === "parejas" || juego === "sigue_figura" ? "Di el número de la carta."
      : soloNumero ? "Busca el igual con la vista y di su número."
      : modo === "orden" ? "Di los pasos en orden, uno por uno."
      : "Di la respuesta o su número.")
    : conMirada ? "Mira la opción y mantén la vista en ella."
    : conCabeza ? "Apunta con la cabeza a la respuesta y quédate quieto un momento."
    : "Mueve la mano hacia la opción y déjala quieta.";

  return (
    <PantallaAdulto
      lateral={
        <>
          <p className="etiqueta" style={{ color: "var(--amarillo)" }}>{TITULOS[tipo]}</p>
          <Puntos total={total} marcas={marcas} actual={indice} />
          <p>Pregunta {indice + 1} de {total}</p>
          <h1 className="pregunta">{enunciado}</h1>
          {juego !== "alcanza_recuerda" && <Estimulo pregunta={pregunta} />}
          <Boton variante="secundario" icono={Pause} onClick={onPausa} style={{ alignSelf: "flex-start" }} data-voz="parar, espera, descansar">
            Pausa
          </Boton>
        </>
      }
    >
      <p className="etiqueta">{consigna}</p>
      {contenido}
      {!memorizando && (
        <p className="texto-apoyo">
          {ayuda}
          {conVoz && !soloVoz && " También puedes decirla en voz alta."}
        </p>
      )}
    </PantallaAdulto>
  );
}

/** Pantalla 06 (y la variante cuando se agotan los intentos). */
function Acierto({ indice, total, marcas, pregunta, resultado, menu, onSiguiente, revelada = false }) {
  const aciertos = marcas.filter((m) => m === "acierto").length;
  const respondidas = marcas.filter(Boolean).length;
  const ultima = indice + 1 >= total;
  const correcta = resultado.respuesta_correcta;

  return (
    <PantallaAdulto
      lateral={
        <div className="lateral-cuerpo lateral-centro">
          <span className="halo">
            <IconoCirculo icono={revelada ? ArrowRight : Check} tono="amarillo" tamano={120} />
          </span>
          <h1>{revelada ? "Sigamos adelante" : "¡Muy bien!"}</h1>
          <p>{revelada ? "La próxima te saldrá mejor."
            : resultado.completado || pregunta.modo === "orden" ? "Lo hiciste muy bien."
            : `Elegiste: ${resultado.opcion_elegida.texto}.`}</p>
          <span className="pastilla"><Volume2 size={22} /> {revelada ? "Suena un tono suave" : "Suena un tono alegre"}</span>
        </div>
      }
      acciones={
        <>
          <Boton variante="secundario" icono={ArrowLeft} onClick={menu}>Volver al menú</Boton>
          <Boton icono={ultima ? Flag : ArrowRight} onClick={onSiguiente} data-voz="sigue, otra, resultados">{ultima ? "Ver resultados" : "Siguiente"}</Boton>
        </>
      }
    >
      <p className="etiqueta">Pregunta {indice + 1} de {total}</p>
      <h2 className="titulo">
        {revelada ? (pregunta.modo === "orden" ? "Este era el orden" : `La respuesta era: ${correcta.texto}`)
          : resultado.completado ? "¡Encontraste todas las parejas!"
          : pregunta.modo === "orden" ? "¡Orden correcto!"
          : "¡Respuesta correcta!"}
      </h2>
      <div className="resultado">
        <TarjetaOpcion opcion={correcta} tabIndex={-1} />
        <div className="progreso-caja">
          <strong style={{ fontSize: 24 }}>Tu progreso</strong>
          <Puntos total={total} marcas={marcas} actual={-1} />
          <strong>{aciertos} {aciertos === 1 ? "acierto" : "aciertos"} de {respondidas}</strong>
          <span>¡Sigue así!</span>
        </div>
      </div>
    </PantallaAdulto>
  );
}

/** Pantalla 07: reintentar con pista. */
function Reintento({ indice, total, resultado, menu, onReintentar }) {
  const elegida = resultado.opcion_elegida;
  return (
    <PantallaAdulto
      lateral={
        <div className="lateral-cuerpo lateral-centro">
          <span className="halo halo-naranja">
            <IconoCirculo icono={RotateCw} tono="naranja" tamano={120} />
          </span>
          <h1>Casi lo logras</h1>
          <p>Vuelve a intentarlo, tú puedes.</p>
          <span className="pastilla"><Volume2 size={22} /> Suena un tono suave</span>
        </div>
      }
      acciones={
        <>
          <Boton variante="secundario" icono={ArrowLeft} onClick={menu}>Volver al menú</Boton>
          <Boton icono={RotateCw} onClick={onReintentar} data-voz="otra vez, de nuevo">Intentar de nuevo</Boton>
        </>
      }
    >
      <p className="etiqueta">Pregunta {indice + 1} de {total}</p>
      <h2 className="titulo">Te damos una pista</h2>
      <div className="aviso aviso-crema">
        <IconoCirculo icono={Lightbulb} tono="amarillo" tamano={72} />
        <div>
          <p className="aviso-etiqueta">Pista</p>
          <h3>{resultado.pista}</h3>
        </div>
      </div>
      <div className="elegiste">
        {elegida.emoji && <span className="mini" aria-hidden="true">{elegida.emoji}</span>}
        <div>
          <strong>Elegiste: {elegida.texto}</strong>
          <p className="texto-apoyo">Esta vez no era la correcta.</p>
        </div>
      </div>
    </PantallaAdulto>
  );
}

/** Pantalla 05, variante de error: con «Pedir ayuda a mi cuidador» como acción principal. */
function NoPudimosEmpezar({ tipo, error, menu }) {
  const ayuda = useAyuda("actividad");
  return (
    <PantallaAdulto
      lateral={<h1>{TITULOS[tipo]}</h1>}
      acciones={
        <>
          <Boton variante={ayuda.pedida ? "principal" : "secundario"} icono={ArrowLeft} onClick={menu}>Volver al menú</Boton>
          <BotonAyuda ayuda={ayuda} variante="principal" />
        </>
      }
    >
      <p className="etiqueta">Un momento</p>
      <h2 className="titulo">No pudimos empezar</h2>
      <div className="aviso aviso-crema">
        <IconoCirculo icono={Lightbulb} tono="amarillo" />
        <h3>{error}</h3>
      </div>
      <AvisoAyudaPedida ayuda={ayuda} />
    </PantallaAdulto>
  );
}

/**
 * Pantalla 08: resumen de la actividad, en positivo: sin nivel ni errores.
 * Si queda otra actividad preparada para hoy, el botón principal lleva a ella.
 */
function Resumen({ resumen, paciente, menu, tipo }) {
  const navegar = useNavigate();
  const [hoy, setHoy] = useState(null);
  const rol = rolCuidador(paciente);

  useEffect(() => {
    leerSesionHoy(paciente.id).then(setHoy).catch(() => setHoy({ estado: "error" }));
  }, [paciente.id]);

  const siguiente = hoy?.estado === "en_curso" ? hoy.realizables.find((t) => !hoy.hechas.includes(t)) : null;

  return (
    <PantallaAdulto
      lateral={
        <div className="lateral-cuerpo lateral-centro">
          <span className="halo"><IconoCirculo icono={Trophy} tono="amarillo" tamano={120} /></span>
          <h1>¡Gran trabajo, {paciente.nombre}!</h1>
          <p>Hiciste un gran trabajo hoy.</p>
        </div>
      }
      acciones={
        siguiente ? (
          <>
            <Boton variante="secundario" icono={ArrowLeft} onClick={menu}>Volver al menú</Boton>
            <Boton icono={ArrowRight} onClick={() => navegar(`/jugar/actividad/${siguiente}`)}>
              Seguir con {NOMBRE_ACTIVIDAD[siguiente]}
            </Boton>
          </>
        ) : (
          <Boton icono={Flag} disabled={!hoy} onClick={() => navegar("/jugar/fin")}>Terminar</Boton>
        )
      }
    >
      <p className="etiqueta">Resumen</p>
      <h2 className="titulo">{siguiente ? `¡Terminaste ${NOMBRE_ACTIVIDAD[tipo]}!` : "¡Terminaste tu sesión!"}</h2>
      <div className="estadisticas">
        <div className="estadistica">
          <strong>{resumen.aciertos}</strong>
          {resumen.aciertos === 1 ? "Acierto" : "Aciertos"}
        </div>
        <div className="estadistica">
          <strong>{resumen.duracion_min} min</strong>
          De ejercicio
        </div>
      </div>
      <div className="aviso aviso-menta">
        <IconoCirculo icono={Check} tono="verde" />
        <p>Tus resultados se guardaron para que tu {rol} los vea.</p>
      </div>
    </PantallaAdulto>
  );
}
