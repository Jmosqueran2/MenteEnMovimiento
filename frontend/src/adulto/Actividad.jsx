import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft, ArrowRight, Check, Flag, Lightbulb, Pause, Play, RotateCw, Trophy, Volume2,
} from "lucide-react";
import { api } from "../api";
import { Boton, Cargando, IconoCirculo, PantallaAdulto } from "../componentes/comunes";
import { decimal, NOMBRE_NIVEL, ORDEN_NIVEL } from "../formato";
import { useSesion } from "../sesion";
import { callar, hablar, sonarAcierto, sonarReintento } from "../sonidos";
import { useVision } from "../vision/ProveedorVision";

const TITULOS = {
  memoria: "Ejercicio de memoria",
  atencion: "Atención",
  coordinacion: "Coordinación",
  historia: "Mi Historia",
};

/** Pantallas 05 a 08: pregunta → acierto / reintento → … → resumen. */
export default function Actividad() {
  const { tipo } = useParams();
  const navegar = useNavigate();
  const { paciente } = useSesion();
  const { setModo } = useVision();

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
        setSesion(nueva);
        inicioPregunta.current = performance.now();
      })
      .catch((e) => vigente && setError(e.message));
    return () => {
      vigente = false;
      setModo("seleccion");
    };
  }, [tipo, paciente.id, setModo]);

  // Si se sale a mitad de la actividad, la sesión queda como cancelada.
  useEffect(
    () => () => {
      callar();
      const s = sesionActual.current;
      if (s && !terminada.current) {
        api(`/api/sesiones/${s.id}/finalizar/`, { metodo: "POST", datos: { cancelada: true } }).catch(() => {});
      }
    },
    [],
  );

  const pregunta = sesion?.preguntas[indice];
  const total = sesion?.preguntas.length || 0;

  useEffect(() => {
    if (fase === "pregunta" && pregunta) {
      const estimulo = pregunta.estimulo?.texto ? ` ${pregunta.estimulo.texto}.` : "";
      hablar(`${pregunta.enunciado}${estimulo}`);
    }
  }, [fase, pregunta]);

  const marcar = (valor) =>
    setMarcas((anteriores) => {
      const copia = [...anteriores];
      copia[indice] = valor;
      return copia;
    });

  const elegir = async (opcion) => {
    if (enviando.current || pausa) return;
    enviando.current = true;
    try {
      const r = await api(`/api/sesiones/${sesion.id}/responder/`, {
        metodo: "POST",
        datos: {
          indice_pregunta: indice,
          opcion,
          tiempo_ms: Math.round(performance.now() - inicioPregunta.current),
        },
      });
      setResultado(r);
      if (r.correcta) {
        marcar(r.intento === 1 ? "acierto" : "resuelta");
        sonarAcierto();
        hablar(`¡Muy bien! Elegiste ${r.opcion_elegida.texto}.`);
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
      const r = await api(`/api/sesiones/${sesion.id}/finalizar/`, { metodo: "POST", datos: {} });
      terminada.current = true;
      setResumen(r);
      setFase("resumen");
      sonarAcierto();
      hablar(`¡Terminaste tu sesión! Tuviste ${r.aciertos} aciertos de ${r.total}. Hiciste un gran trabajo hoy.`);
    } catch (e) {
      setError(e.message);
    }
  }, [sesion]);

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

  if (error) {
    return (
      <PantallaAdulto
        lateral={<h1>{TITULOS[tipo]}</h1>}
        acciones={<Boton icono={ArrowLeft} onClick={menu}>Volver al menú</Boton>}
      >
        <p className="etiqueta">Un momento</p>
        <h2 className="titulo">No pudimos empezar</h2>
        <div className="aviso aviso-crema">
          <IconoCirculo icono={Lightbulb} tono="amarillo" />
          <h3>{error}</h3>
        </div>
      </PantallaAdulto>
    );
  }

  if (!sesion) return <Cargando texto="Preparando tu actividad…" />;

  const comunes = { tipo, indice, total, marcas, pregunta, resultado, menu };

  return (
    <>
      {fase === "pregunta" && <Pregunta {...comunes} onElegir={elegir} onPausa={() => setPausa(true)} />}
      {fase === "acierto" && <Acierto {...comunes} onSiguiente={siguiente} />}
      {fase === "revelada" && <Acierto {...comunes} revelada onSiguiente={siguiente} />}
      {fase === "reintento" && <Reintento {...comunes} onReintentar={reintentar} />}
      {fase === "resumen" && <Resumen resumen={resumen} nombre={paciente.nombre} menu={menu} />}
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

function TarjetaOpcion({ opcion, ...props }) {
  return (
    <button type="button" className={`opcion ${opcion.emoji ? "" : "opcion-solo-texto"}`} {...props}>
      {opcion.emoji && (
        <span className="opcion-imagen" aria-hidden="true">
          {opcion.emoji}
        </span>
      )}
      {opcion.texto}
    </button>
  );
}

function Pregunta({ tipo, indice, total, marcas, pregunta, onElegir, onPausa }) {
  const coordinacion = tipo === "coordinacion";
  return (
    <PantallaAdulto
      lateral={
        <>
          <p className="etiqueta" style={{ color: "var(--amarillo)" }}>{TITULOS[tipo]}</p>
          <Puntos total={total} marcas={marcas} actual={indice} />
          <p>Pregunta {indice + 1} de {total}</p>
          <h1 className="pregunta">{pregunta.enunciado}</h1>
          <Estimulo pregunta={pregunta} />
          <Boton variante="secundario" icono={Pause} onClick={onPausa} style={{ alignSelf: "flex-start" }}>
            Pausa
          </Boton>
        </>
      }
    >
      <p className="etiqueta">{coordinacion ? "Estira el brazo hacia la respuesta" : "Elige la respuesta"}</p>
      <div className={`opciones ${coordinacion ? "opciones-coordinacion" : ""}`}>
        {pregunta.opciones.map((opcion, i) => (
          <TarjetaOpcion
            key={`${indice}-${i}`}
            opcion={opcion}
            className={`opcion elegible-tarjeta ${opcion.emoji ? "" : "opcion-solo-texto"}`}
            data-elegible=""
            onClick={() => onElegir(i)}
          />
        ))}
      </div>
      <p className="texto-apoyo">Mueve la mano hacia la respuesta y déjala quieta.</p>
    </PantallaAdulto>
  );
}

/** Pantalla 06 (y la variante cuando se agotan los intentos). */
function Acierto({ indice, total, marcas, resultado, menu, onSiguiente, revelada = false }) {
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
          <p>{revelada ? "La próxima te saldrá mejor." : `Elegiste: ${resultado.opcion_elegida.texto}.`}</p>
          <span className="pastilla"><Volume2 size={22} /> {revelada ? "Suena un tono suave" : "Suena un tono alegre"}</span>
        </div>
      }
      acciones={
        <>
          <Boton variante="secundario" icono={ArrowLeft} onClick={menu}>Volver al menú</Boton>
          <Boton icono={ultima ? Flag : ArrowRight} onClick={onSiguiente}>{ultima ? "Ver resultados" : "Siguiente"}</Boton>
        </>
      }
    >
      <p className="etiqueta">Pregunta {indice + 1} de {total}</p>
      <h2 className="titulo">{revelada ? `La respuesta era: ${correcta.texto}` : "¡Respuesta correcta!"}</h2>
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
          <Boton icono={RotateCw} onClick={onReintentar}>Intentar de nuevo</Boton>
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

/** Pantalla 08: resumen de la sesión. */
function Resumen({ resumen, nombre, menu }) {
  const navegar = useNavigate();
  const subio = ORDEN_NIVEL.indexOf(resumen.nivel_siguiente) > ORDEN_NIVEL.indexOf(resumen.nivel_anterior);
  const nivel = NOMBRE_NIVEL[resumen.nivel_siguiente];

  return (
    <PantallaAdulto
      lateral={
        <div className="lateral-cuerpo lateral-centro">
          <span className="halo"><IconoCirculo icono={Trophy} tono="amarillo" tamano={120} /></span>
          <h1>¡Gran trabajo, {nombre}!</h1>
          <p>Hiciste un gran trabajo hoy.</p>
        </div>
      }
      acciones={
        <>
          <Boton variante="secundario" icono={ArrowLeft} onClick={menu}>Volver al menú</Boton>
          <Boton icono={Flag} onClick={() => navegar("/jugar/fin")}>Terminar</Boton>
        </>
      }
    >
      <p className="etiqueta">Resumen de la sesión</p>
      <h2 className="titulo">¡Terminaste tu sesión!</h2>
      <div className="estadisticas">
        <div className="estadistica">
          <strong>{resumen.aciertos} de {resumen.total}</strong>
          Aciertos
        </div>
        <div className="estadistica">
          <strong>{decimal(resumen.tiempo_promedio_s)} s</strong>
          Tiempo promedio de respuesta
        </div>
        <div className="estadistica">
          <strong>{resumen.duracion_min} min</strong>
          Duración de la sesión
        </div>
      </div>
      <div className="aviso aviso-menta">
        <IconoCirculo icono={Check} tono="verde" />
        <p>Tus resultados se guardaron para que tu cuidador los vea.</p>
      </div>
      <p style={{ fontSize: 30, fontWeight: 700 }}>
        {resumen.cambio_nivel && subio ? "¡Subiste de nivel! " : ""}Próxima sesión: Nivel {nivel}
      </p>
    </PantallaAdulto>
  );
}
