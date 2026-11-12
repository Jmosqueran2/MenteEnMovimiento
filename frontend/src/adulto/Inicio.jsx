import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ArrowLeft, Check, Eraser, Info, Lock, LogOut, Play, Power, RotateCcw } from "lucide-react";
import { Boton, IconoCirculo, PantallaAdulto, Pasos } from "../componentes/comunes";
import { useSesion } from "../sesion";
import { hablar } from "../sonidos";
import { useVision } from "../vision/ProveedorVision";

/** Pantalla 01: permiso de cámara, o de micrófono si se elige con la voz. */
export function Consentimiento() {
  const navegar = useNavigate();
  const { encender, puntero, movilidad, conVoz } = useVision();
  const [pidiendo, setPidiendo] = useState(false);
  const soloVoz = puntero === "voz";
  const uso = soloVoz
    ? "Usamos el micrófono solo para oír la opción que eliges. La cámara no se enciende."
    : (puntero === "mirada" || movilidad === "cabeza"
      ? "Usamos la cámara solo para ver hacia dónde miras y cómo te mueves."
      : "Usamos la cámara solo para ver cómo mueves las manos y los brazos.")
      + (conVoz ? " El micrófono, para oír tus respuestas." : "");
  const tituloPrivacidad = soloVoz ? "Tu micrófono, tu privacidad" : "Tu cámara, tu privacidad";

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
          <p>Primero necesitamos tu permiso para usar {soloVoz ? "el micrófono" : "la cámara"}.</p>
          <Pasos actual={0} />
        </>
      }
      acciones={
        <>
          <Boton variante="secundario" onClick={() => navegar("/jugar/sin-permiso")}>Ahora no</Boton>
          <Boton onClick={aceptar} disabled={pidiendo} data-voz="sí, acepto">{pidiendo ? (soloVoz ? "Activando el micrófono…" : "Activando la cámara…") : "Aceptar y continuar"}</Boton>
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
          <p className="texto-apoyo">{soloVoz ? "Ni audios ni videos." : "Ni fotos ni videos."}</p>
        </div>
        <div className="tarjeta">
          <IconoCirculo icono={Eraser} />
          <h3>Se borra al instante</h3>
          <p className="texto-apoyo">{soloVoz ? "Solo se usa la palabra que dices." : "Cada imagen se analiza y se descarta."}</p>
        </div>
        <div className="tarjeta">
          <IconoCirculo icono={Power} />
          <h3>Tú tienes el control</h3>
          <p className="texto-apoyo">{soloVoz ? "Se apaga al terminar." : "Apágala cuando quieras."}</p>
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

/** Pantalla 03: detección de presencia, calibración y bienvenida. */
export function Deteccion() {
  const navegar = useNavigate();
  const { paciente } = useSesion();
  const { usaCamara, puntero, camara, estado, stream, calibrar } = useVision();
  const video = useRef(null);

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
  const listo = persona && calibrado && luzBuena;
  const alerta = estado?.alertas?.find((a) => CONSEJOS[a]);
  const comoElegir = soloVoz ? "Cuando quieras, di «comenzar»."
    : conMirada ? "Mira Comenzar sin mover la vista." : "Mantén la mano quieta sobre Comenzar.";
  const calibrandoMirada = conMirada && persona && luzBuena && mirada?.estado === "en_progreso";

  useEffect(() => {
    if (listo) hablar(`¡Hola, ${paciente.nombre}! ${soloVoz ? "Ya estamos listos." : "Ya te vemos."} ${comoElegir}`);
  }, [listo, paciente.nombre, comoElegir, soloVoz]);

  return (
    <PantallaAdulto
      lateral={
        <>
          <h1>{listo ? `¡Hola, ${paciente.nombre}!` : "Te estamos buscando"}</h1>
          <p>{listo ? `${soloVoz ? "Ya estamos listos" : "Ya te vemos"}. Cuando quieras, empezamos.` : "Siéntate cómodo frente a la pantalla."}</p>
          <Pasos actual={1} />
        </>
      }
      acciones={
        <>
          <Boton variante="secundario" icono={ArrowLeft} onClick={() => navegar("/jugar")}>Volver</Boton>
          <Boton icono={Play} disabled={!listo} onClick={() => navegar("/jugar/menu")} data-voz="comienza, comencemos, empezar, empecemos, listo, vamos">Comenzar</Boton>
        </>
      }
    >
      <p className="etiqueta">Paso 2 de 3</p>
      <h2 className="titulo">{listo ? "Te estamos viendo" : "Buscándote…"}</h2>
      <div className="vista-camara">
        {conMouse ? (
          <p style={{ color: "white" }}>
            {soloVoz ? "Eliges con la voz: la cámara está apagada." : "Modo de prueba: se usa el mouse en lugar de la cámara."}
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
      {calibrandoMirada && <CalibracionMirada calibracion={mirada} rostro={estado?.rostro} />}
      {!conMouse && !conMirada && persona && !calibrado && (
        <div style={{ display: "grid", gap: 10 }}>
          <p>Ajustando el sistema a tu postura… {Math.round((calibracion?.progreso || 0) * 100)} %</p>
          <div className="barra"><span style={{ width: `${(calibracion?.progreso || 0) * 100}%` }} /></div>
        </div>
      )}
      <p className="texto-apoyo">
        {listo ? comoElegir : alerta ? CONSEJOS[alerta] : "Un momento, por favor…"}
        {!conMouse && calibrado && (
          <button type="button" className="boton boton-secundario" style={{ marginLeft: 16, minHeight: 48, fontSize: 20, padding: "0 20px" }} onClick={calibrar} data-elegible="">
            <RotateCcw size={20} /> Volver a calibrar
          </button>
        )}
      </p>
    </PantallaAdulto>
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

/** Fin del recorrido del adulto mayor. */
export function Despedida() {
  const navegar = useNavigate();
  const { paciente } = useSesion();
  const { apagar, puntero } = useVision();

  useEffect(() => {
    apagar();
    hablar(`¡Hasta pronto, ${paciente.nombre}! Gracias por ejercitar tu mente hoy.`);
  }, [apagar, paciente.nombre]);

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
      <p className="etiqueta">Sesión terminada</p>
      <h2 className="titulo">Gracias por ejercitar tu mente hoy</h2>
      <p className="texto-apoyo">
        {puntero === "voz" ? "El micrófono ya está apagado." : "La cámara ya está apagada."} Tus resultados quedaron
        guardados para tu cuidador.
      </p>
    </PantallaAdulto>
  );
}
