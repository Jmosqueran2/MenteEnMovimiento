import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  ArrowDown, ArrowLeft, ArrowRight, ArrowUp, CalendarClock, Check, Eraser, Info, Lock, LogOut, PersonStanding, Play, Power,
  RotateCcw,
} from "lucide-react";
import { Boton, IconoCirculo, PantallaAdulto, Pasos } from "../componentes/comunes";
import { enumerar, NOMBRE_ACTIVIDAD, rolCuidador } from "../formato";
import { useSesion } from "../sesion";
import { comenzarSesionHoy, estaAcompanado, leerSesionHoy, marcarAcompanado, terminarSesionHoy } from "../sesionHoy";
import { ACTIVIDADES } from "./Menu";
import { hablar } from "../sonidos";
import { useVision } from "../vision/ProveedorVision";

/** Pantalla 01: permiso de cámara, o de micrófono si se elige con la voz. */
export function Consentimiento() {
  const navegar = useNavigate();
  const { encender, puntero, movilidad, conVoz, camaraPostura } = useVision();
  const [pidiendo, setPidiendo] = useState(false);
  const soloVoz = puntero === "voz";
  const uso = soloVoz
    ? "Usamos el micrófono solo para oír la opción que eliges."
      + (camaraPostura ? " La cámara, solo para revisar cómo estás sentado." : " La cámara no se enciende.")
    : (puntero === "mirada" || movilidad === "cabeza"
      ? "Usamos la cámara solo para ver hacia dónde miras, cómo te mueves y cómo estás sentado."
      : "Usamos la cámara solo para ver cómo mueves las manos y los brazos, y cómo estás sentado.")
      + (conVoz ? " El micrófono, para oír tus respuestas." : "");
  const tituloPrivacidad = soloVoz
    ? (camaraPostura ? "Tu micrófono y tu cámara, tu privacidad" : "Tu micrófono, tu privacidad")
    : "Tu cámara, tu privacidad";
  const aparatos = soloVoz ? (camaraPostura ? "el micrófono y la cámara" : "el micrófono") : "la cámara";

  useEffect(() => hablar(`${tituloPrivacidad}. ${uso}`), [tituloPrivacidad, uso]);

  const aceptar = async () => {
    setPidiendo(true);
    const resultado = await encender();
    navegar(resultado === "denegada" || resultado === "sin_microfono"
      ? `/jugar/sin-permiso${resultado === "sin_microfono" ? "?motivo=sin_microfono" : ""}`
      : "/jugar/deteccion");
  };

  return (
    <PantallaAdulto
      lateral={
        <>
          <h1>Hola, empecemos juntos</h1>
          <p>Primero necesitamos tu permiso para usar {aparatos}.</p>
          <Pasos actual={0} />
        </>
      }
      acciones={
        <>
          <Boton variante="secundario" onClick={() => navegar("/jugar/sin-permiso")}>Ahora no</Boton>
          <Boton onClick={aceptar} disabled={pidiendo} data-voz="sí, acepto">{pidiendo ? `Activando ${aparatos}…` : "Aceptar y continuar"}</Boton>
        </>
      }
    >
      <p className="etiqueta">Paso 1 de 3</p>
      <h2 className="titulo">{tituloPrivacidad}</h2>
      <p className="texto-apoyo">{uso}</p>
      <div className="tarjetas-tres">
        <div className="tarjeta">
          <IconoCirculo icono={Lock} />
          <h3>Nada se graba</h3>
          <p className="texto-apoyo">{soloVoz ? (camaraPostura ? "Ni audios, ni fotos, ni videos." : "Ni audios ni videos.") : "Ni fotos ni videos."}</p>
        </div>
        <div className="tarjeta">
          <IconoCirculo icono={Eraser} />
          <h3>Se borra al instante</h3>
          <p className="texto-apoyo">
            {soloVoz
              ? (camaraPostura ? "Solo se usa la palabra que dices; cada imagen se descarta." : "Solo se usa la palabra que dices.")
              : "Cada imagen se analiza y se descarta."}
          </p>
        </div>
        <div className="tarjeta">
          <IconoCirculo icono={Power} />
          <h3>Tú tienes el control</h3>
          <p className="texto-apoyo">{soloVoz ? (camaraPostura ? "Se apagan al terminar." : "Se apaga al terminar.") : "Apágala cuando quieras."}</p>
        </div>
      </div>
      <p className="nota">Lo puede autorizar el usuario o su cuidador.</p>
    </PantallaAdulto>
  );
}

/** Pantalla 02: sin permiso de cámara. */
export function SinPermiso() {
  const navegar = useNavigate();
  const { camara, puntero } = useVision();
  const soloVoz = puntero === "voz";
  const sinMicrofono = new URLSearchParams(useLocation().search).get("motivo") === "sin_microfono";
  const aparato = soloVoz ? "el micrófono" : "la cámara";

  useEffect(() => hablar(`No activamos ${aparato}. No pasa nada, puedes volver cuando quieras.`), [aparato]);

  return (
    <PantallaAdulto
      lateral={
        <>
          <h1>Está bien, sin prisa</h1>
          <p>{soloVoz ? "Sin el micrófono no podemos oír tus respuestas." : "Sin la cámara no podemos ver tus movimientos."}</p>
          <Pasos actual={0} />
        </>
      }
      acciones={
        <>
          <Boton variante="secundario" icono={LogOut} onClick={() => navegar("/jugar/fin")}>Salir</Boton>
          <Boton icono={ArrowLeft} onClick={() => navegar("/jugar")}>Volver</Boton>
        </>
      }
    >
      <p className="etiqueta">Paso 1 de 3</p>
      <h2 className="titulo">No activamos {aparato}</h2>
      <p className="texto-apoyo">No pasa nada. Puedes volver cuando quieras.</p>
      <div className="aviso aviso-crema">
        <IconoCirculo icono={Info} tono="amarillo" />
        <div>
          <h3>Mente en Movimiento necesita {aparato}</h3>
          <p>{soloVoz ? "Así oye la opción que eliges. Nada se graba." : "Así reconoce tus manos y brazos. Nada se graba."}</p>
        </div>
      </div>
      <p><strong>Puedes:</strong></p>
      <ol className="lista-numerada">
        <li data-n="1">Volver y aceptar cuando estés listo.</li>
        <li data-n="2">Pedir ayuda a tu cuidador.</li>
      </ol>
      {soloVoz && (
        <p className="nota">
          {sinMicrofono
            ? "Para el cuidador: no encontramos un micrófono. Conecta uno o revisa que el sistema lo reconozca."
            : "Para el cuidador: si el navegador bloqueó el micrófono, permítelo con el ícono del candado junto a la dirección de la página y vuelve a intentarlo. También puedes elegir «La mano» o «La mirada» en Configuración."}
        </p>
      )}
      {!soloVoz && camara === "denegada" && (
        <p className="nota">
          Para el cuidador: el navegador bloqueó la cámara. Permítela con el ícono del candado junto a la dirección
          de la página y vuelve a intentarlo.
        </p>
      )}
    </PantallaAdulto>
  );
}

const CONSEJOS = {
  sin_persona: "No te vemos. Siéntate frente a la cámara.",
  muy_lejos: "Acércate un poco a la cámara.",
  muy_cerca: "Aléjate un poco de la cámara.",
  descentrado: "Muévete un poco hacia el centro.",
  rostro_no_visible: "Mira hacia la pantalla.",
  poca_luz: "Busca un lugar con más luz.",
  contraluz: "Evita tener una ventana o una luz detrás de ti.",
};

/**
 * Pantalla 03: detección de presencia, calibración y bienvenida. Antes de
 * pedir la calibración se revisa la sesión de hoy: si el cuidador la dejó
 * lista, se muestra el resumen y «Comenzar»; si no, un mensaje y «Salir».
 */
export function Deteccion() {
  const navegar = useNavigate();
  const { paciente, recargar } = useSesion();
  const {
    usaCamara, camaraPostura, puntero, camara, estado, stream, calibrar, calibrarAlcance, omitirAlcance,
  } = useVision();
  const video = useRef(null);
  const [hoy, setHoy] = useState(null);
  const [comenzando, setComenzando] = useState(false);
  const rol = rolCuidador(paciente);

  useEffect(() => {
    recargar(); // tiempo de permanencia y actividades al día
    leerSesionHoy(paciente.id).then(setHoy).catch(() => setHoy({ estado: "error" }));
  }, [paciente.id, recargar]);

  // lista | sin_sesion | hecha | esperar | error
  let modo = null;
  if (hoy) {
    const autonomo = hoy.inicio_autonomo ?? paciente.inicio_autonomo;
    if (hoy.estado === "error") modo = "error";
    else if (!autonomo && !estaAcompanado(paciente.id)) modo = "esperar";
    else if (hoy.estado === "lista" || hoy.estado === "en_curso") modo = "lista";
    else if (hoy.estado === "terminada") modo = "hecha";
    else modo = "sin_sesion";
  }
  const hayQueJugar = modo === "lista";

  // Con la mano, cuando hay sesión se ajusta el sistema a la postura de hoy:
  // la persona lleva la mano hacia cada lado. Sin sesión no se le pide ese
  // esfuerzo: para un solo botón grande alcanza la estimación por hombros.
  useEffect(() => {
    if (hayQueJugar && usaCamara && puntero === "mano") calibrarAlcance();
  }, [hayQueJugar, usaCamara, puntero, calibrarAlcance]);

  useEffect(() => {
    if (usaCamara && camara === "apagada") navegar("/jugar", { replace: true });
    if (camara === "denegada") navegar("/jugar/sin-permiso", { replace: true });
  }, [usaCamara, camara, navegar]);

  useEffect(() => {
    if (video.current) video.current.srcObject = stream;
  }, [stream]);

  // Sin cámara (mouse de pruebas o "La voz") no hay nada que detectar ni calibrar.
  const conMouse = !usaCamara;
  const soloVoz = puntero === "voz";
  const persona = conMouse || Boolean(estado?.postura?.persona);
  const conMirada = puntero === "mirada";
  const calibracion = estado?.calibracion;
  const mirada = estado?.calibracion_mirada;
  const calibrado = conMouse || (conMirada ? mirada?.estado === "completa" : calibracion?.estado === "completa");
  const luzBuena = conMouse || estado?.luz?.estado === "ok";
  const listo = Boolean(modo) && persona && calibrado && luzBuena;
  const alerta = estado?.alertas?.find((a) => CONSEJOS[a]);
  const botonPrincipal = hayQueJugar ? "Comenzar" : "Salir";
  const comoElegir = soloVoz ? `Cuando quieras, di «${botonPrincipal.toLowerCase()}».`
    : conMirada ? `Mira ${botonPrincipal} sin mover la vista.` : `Mantén la mano quieta sobre ${botonPrincipal}.`;
  const calibrandoMirada = conMirada && persona && luzBuena && mirada?.estado === "en_progreso";
  const calibrandoAlcance = hayQueJugar && !conMouse && !conMirada && calibracion?.estado === "alcance";

  const nombreDe = (t) => NOMBRE_ACTIVIDAD[t];
  const realizables = hoy?.realizables || [];
  const hechas = hoy?.hechas || [];
  const faltan = realizables.filter((t) => !hechas.includes(t));
  const yaEmpezo = hoy?.estado === "en_curso" && hechas.length > 0;
  const quitadas = (hoy?.quitadas || []).map(nombreDe);

  const MENSAJES = {
    lista: {
      titulo: yaEmpezo ? "Sigamos con tu sesión de hoy" : `Tu ${rol} dejó lista tu sesión de hoy`,
      texto: yaEmpezo
        ? `Ya hiciste ${enumerar(hechas.map(nombreDe))}. Te falta ${enumerar(faltan.map(nombreDe))}.`
        : `${enumerar(realizables.map(nombreDe))}. Cuando quieras, empezamos.`,
    },
    sin_sesion: {
      titulo: "Aún no hay actividades listas para hoy",
      texto: `Pídele a tu ${rol} que las prepare.`,
    },
    hecha: {
      titulo: "Ya terminaste tu sesión de hoy",
      texto: `¡Muy bien! Tus resultados se guardaron para que tu ${rol} los vea.`,
    },
    esperar: {
      titulo: `Espera a tu ${rol} para empezar`,
      texto: `Cuando tu ${rol} esté a tu lado, empiezan juntos.`,
    },
    error: {
      titulo: "No pudimos revisar tu sesión de hoy",
      texto: `Pídele ayuda a tu ${rol}.`,
    },
  };
  const mensaje = modo ? MENSAJES[modo] : null;

  useEffect(() => {
    if (!listo || !mensaje) return;
    const avisoQuitadas = hayQueJugar && quitadas.length
      ? ` Hoy no toca ${enumerar(quitadas)}. Si quieres hacerla, pídesela a tu ${rol}.` : "";
    hablar(`¡Hola, ${paciente.nombre}! ${mensaje.titulo}. ${mensaje.texto}${avisoQuitadas} ${comoElegir}`);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [listo, modo, paciente.nombre, comoElegir]);

  const comenzar = async () => {
    setComenzando(true);
    try {
      await comenzarSesionHoy(paciente.id);
      navegar("/jugar/menu");
    } catch {
      // La sesión cambió mientras tanto (p. ej. el cuidador la dio por terminada).
      setComenzando(false);
      leerSesionHoy(paciente.id).then(setHoy).catch(() => setHoy({ estado: "error" }));
    }
  };

  return (
    <PantallaAdulto
      lateral={
        <>
          <h1>{listo ? `¡Hola, ${paciente.nombre}!` : "Te estamos buscando"}</h1>
          <p>{listo ? (soloVoz ? "Ya estamos listos." : "Ya te vemos.") : "Siéntate cómodo frente a la pantalla."}</p>
          <Pasos actual={1} />
        </>
      }
      acciones={
        hayQueJugar ? (
          <>
            <Boton variante="secundario" icono={LogOut} onClick={() => navegar("/jugar/fin")}>Salir</Boton>
            <Boton icono={Play} disabled={!listo || comenzando} onClick={comenzar} data-voz="comienza, comencemos, empezar, empecemos, listo, vamos">Comenzar</Boton>
          </>
        ) : (
          <Boton icono={LogOut} disabled={!listo} onClick={() => navegar("/jugar/fin")} data-voz="salir, adiós, chao">Salir</Boton>
        )
      }
    >
      <p className="etiqueta">Paso 2 de 3</p>
      {listo ? (
        <>
          <h2 className="titulo">{mensaje.titulo}</h2>
          <div className={`resumen-sesion ${hayQueJugar ? "" : "resumen-sesion-vacia"}`}>
            {hayQueJugar ? (
              <div className="resumen-sesion-actividades">
                {ACTIVIDADES.filter((a) => realizables.includes(a.tipo)).map(({ tipo, titulo, icono }) => {
                  const hecha = hechas.includes(tipo);
                  return (
                    <div key={tipo} className={hecha ? "hecha" : ""}>
                      <IconoCirculo icono={hecha ? Check : icono} tono={hecha ? "verde" : "menta"} tamano={72} />
                      <span>{titulo}</span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <IconoCirculo icono={modo === "hecha" ? Check : CalendarClock} tono={modo === "hecha" ? "verde" : "amarillo"} tamano={96} />
            )}
            <p className="texto-apoyo">{mensaje.texto}</p>
          </div>
          {hayQueJugar && (usaCamara || camaraPostura) && camara === "activa" && (
            <EstadoPostura postura={estado?.postura_sentado} />
          )}
          {hayQueJugar && quitadas.length > 0 && (
            <p className="nota">Hoy no toca {enumerar(quitadas)}. Si quieres hacerla, pídesela a tu {rol}.</p>
          )}
          <p className="texto-apoyo">
            {comoElegir}
            {hayQueJugar && !conMouse && calibrado && (
              <button type="button" className="boton boton-secundario" style={{ marginLeft: 16, minHeight: 48, fontSize: 20, padding: "0 20px" }}
                      onClick={puntero === "mano" ? calibrarAlcance : calibrar} data-elegible="">
                <RotateCcw size={20} /> Volver a calibrar
              </button>
            )}
          </p>
        </>
      ) : (
        <>
          <h2 className="titulo">Buscándote…</h2>
          <div className="vista-camara">
            {conMouse ? (
              <p style={{ color: "white" }}>
                {soloVoz
                  ? (camaraPostura ? "Eliges con la voz. La cámara solo revisa tu postura." : "Eliges con la voz: la cámara está apagada.")
                  : "Modo de prueba: se usa el mouse en lugar de la cámara."}
              </p>
            ) : (
              <>
                <video ref={video} autoPlay muted playsInline />
                <span className="guia" />
                <span className={`chip chip-izq ${persona ? "chip-verde" : ""}`}>
                  {persona ? <><Check size={20} /> Usuario detectado</> : "Buscándote…"}
                </span>
                <span className="chip chip-der">
                  <span className={`punto ${luzBuena ? "punto-amarillo" : "punto-rojo"}`} />
                  {luzBuena ? "Luz buena" : "Poca luz"}
                </span>
              </>
            )}
          </div>
          {!conMouse && !conMirada && persona && !calibrado && !calibrandoAlcance && (
            <div style={{ display: "grid", gap: 10 }}>
              <p>Ajustando el sistema a tu postura… {Math.round((calibracion?.progreso || 0) * 100)} %</p>
              <div className="barra"><span style={{ width: `${(calibracion?.progreso || 0) * 100}%` }} /></div>
            </div>
          )}
          <p className="texto-apoyo">{alerta ? CONSEJOS[alerta] : "Un momento, por favor…"}</p>
        </>
      )}
      {calibrandoMirada && <CalibracionMirada calibracion={mirada} rostro={estado?.rostro} />}
      {calibrandoAlcance && (
        <CalibracionAlcance calibracion={calibracion} persona={persona} onOmitir={omitirAlcance} />
      )}
    </PantallaAdulto>
  );
}

/** Pantalla 03: la cámara revisa cómo está sentada antes de empezar. */
function EstadoPostura({ postura }) {
  if (postura === "buena") {
    return <p className="chip chip-verde estado-postura"><Check size={22} aria-hidden="true" /> Postura: estás bien sentado</p>;
  }
  if (postura === "encorvado" || postura === "inclinado") {
    return (
      <p className="chip chip-naranja estado-postura">
        <PersonStanding size={22} aria-hidden="true" /> {postura === "encorvado" ? "Endereza la espalda" : "Ponte derecho"}
      </p>
    );
  }
  return (
    <p className="chip estado-postura">
      <PersonStanding size={22} aria-hidden="true" /> Revisando tu postura…
    </p>
  );
}

/**
 * Calibración de la mirada: un punto grande que la persona sigue con la vista
 * (y con la cabeza, si quiere). Cubre toda la pantalla porque los puntos van
 * hasta cerca de las esquinas.
 */
function CalibracionMirada({ calibracion, rostro }) {
  const indice = calibracion.indice ?? 0;
  const total = calibracion.total ?? 9;
  const [x, y] = calibracion.punto || [0.5, 0.5];
  // La calibración se detiene si no se ve la cara o los ojos: hay que decirlo,
  // si no parece que el sistema se colgó.
  const aviso = rostro?.detectado === false
    ? "No veo tu cara: ponte de frente a la cámara, con luz en la cara"
    : rostro?.ojos_abiertos === false
      ? "Abre bien los ojos y mira el punto"
      : null;

  // Solo se dice en voz alta si falta la cara: un parpadeo no debe narrarse.
  const sinCara = rostro?.detectado === false;
  useEffect(() => {
    if (sinCara) hablar("No veo tu cara. Ponte de frente a la cámara.");
  }, [sinCara]);

  useEffect(() => {
    hablar(indice === 0
      ? "Ahora mira el punto amarillo. Síguelo con la vista cada vez que cambie de lugar."
      : "Muy bien. Mira el punto otra vez.");
  }, [indice]);

  return (
    <div className="calibracion-mirada" role="status" aria-live="polite">
      <p className="calibracion-mirada-texto">
        {aviso || "Mira el punto amarillo"} · {indice + 1} de {total}
      </p>
      <span
        key={indice}
        className="calibracion-mirada-punto"
        style={{ left: `${x * 100}%`, top: `${y * 100}%`, "--progreso": calibracion.progreso * total - indice }}
      />
    </div>
  );
}

const DIRECCIONES_ALCANCE = {
  arriba: { texto: "hacia arriba", Flecha: ArrowUp },
  derecha: { texto: "hacia la derecha", Flecha: ArrowRight },
  abajo: { texto: "hacia abajo", Flecha: ArrowDown },
  izquierda: { texto: "hacia la izquierda", Flecha: ArrowLeft },
};

/**
 * Calibración guiada a la postura: la persona lleva la mano hacia cada lado
 * hasta donde llega sin esfuerzo y la deja quieta. El anillo de la flecha se
 * llena mientras la mano está quieta. Cubre la pantalla, así no hay botones
 * debajo de la mano que se puedan elegir sin querer.
 */
function CalibracionAlcance({ calibracion, persona, onOmitir }) {
  const { paso = 0, total = 4, direccion = "arriba", objetivo = [0.5, 0.1], quieto = 0, mano } = calibracion;
  const { texto, Flecha } = DIRECCIONES_ALCANCE[direccion] || DIRECCIONES_ALCANCE.arriba;
  const [x, y] = objetivo;

  useEffect(() => {
    hablar(paso === 0
      ? `Vamos a ajustar el sistema a tu cuerpo. Levanta una mano y llévala ${texto}, hasta donde llegues sin esfuerzo. Después deja la mano quieta un momento.`
      : `Muy bien. Ahora lleva la mano ${texto}.`);
  }, [paso, texto]);

  const ayuda = !persona
    ? "No te vemos: siéntate frente a la cámara"
    : !mano
      ? "Levanta una mano para que la veamos"
      : quieto > 0
        ? "¡Así! Deja la mano quieta…"
        : "Hasta donde llegues, sin forzarte";

  return (
    <div className="calibracion-mirada calibracion-alcance" role="status" aria-live="polite">
      <div className="calibracion-alcance-texto">
        <p>Lleva la mano {texto}</p>
        <p className="calibracion-alcance-ayuda">{ayuda}</p>
        <p className="calibracion-alcance-paso">Paso {paso + 1} de {total}</p>
      </div>
      <span
        key={paso}
        className="calibracion-alcance-objetivo"
        style={{ left: `${x * 100}%`, top: `${y * 100}%`, "--progreso": quieto }}
      >
        <Flecha size={52} strokeWidth={3} />
      </span>
      {/* Solo con el mouse: es para el cuidador, no se elige con la mano. */}
      <button type="button" className="calibracion-alcance-omitir" onClick={onOmitir}>
        Omitir (ajuste automático)
      </button>
    </div>
  );
}

/** Fin del recorrido del adulto mayor. */
export function Despedida() {
  const navegar = useNavigate();
  const { paciente } = useSesion();
  const { apagar, puntero, camaraPostura } = useVision();
  const [hizoAlgo, setHizoAlgo] = useState(false);
  const rol = rolCuidador(paciente);

  useEffect(() => {
    apagar();
    marcarAcompanado(null);
    hablar(`¡Hasta pronto, ${paciente.nombre}! Gracias por ejercitar tu mente hoy.`);
    // Si sale a mitad de la sesión, en el panel queda como terminada.
    terminarSesionHoy(paciente.id).then((r) => setHizoAlgo(r.total > 0)).catch(() => {});
  }, [apagar, paciente.nombre, paciente.id]);

  return (
    <PantallaAdulto
      lateral={<h1>¡Hasta pronto, {paciente.nombre}!</h1>}
      acciones={
        <>
          <Boton variante="secundario" elegible={false} onClick={() => navegar("/cuidador")}>Panel del cuidador</Boton>
          <Boton elegible={false} onClick={() => navegar("/jugar")}>Volver a empezar</Boton>
        </>
      }
    >
      <p className="etiqueta">Hasta pronto</p>
      <h2 className="titulo">Gracias por ejercitar tu mente hoy</h2>
      <p className="texto-apoyo">
        {puntero !== "voz" ? "La cámara ya está apagada."
          : camaraPostura ? "El micrófono y la cámara ya están apagados." : "El micrófono ya está apagado."}
        {hizoAlgo ? ` Tus resultados se guardaron para que tu ${rol} los vea.` : ""}
      </p>
    </PantallaAdulto>
  );
}
