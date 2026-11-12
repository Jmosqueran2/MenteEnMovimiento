import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { tokenDeAcceso } from "../api";
import { guardarAjuste, leerAjuste } from "../ajustes";
import { useSesion } from "../sesion";

/*
 * Cámara + WebSocket con el microservicio de visión.
 *
 * Se envía un frame JPEG pequeño y se espera la respuesta antes de mandar el
 * siguiente: el ritmo se adapta solo a la latencia hasta AWS.
 */

const ContextoVision = createContext(null);
const ANCHO_FRAME = 320;
// Con la mirada se manda más resolución y mejor calidad: el iris mide pocos
// píxeles y la compresión JPEG borra su borde.
const ANCHO_FRAME_MIRADA = 960;
const CALIDAD_JPEG = 0.7;
const CALIDAD_JPEG_MIRADA = 0.85;
const REINTENTO_CAMARA_MS = 3000;
const REINTENTO_WS_MS = 2000;
const FRAME_PERDIDO_MS = 3000;
// Se pide 720p: con la mano se reduce a 320 px igual, pero a la mirada le sirve
// cada píxel. Si la cámara no llega, el navegador da la mayor que tenga.
const RESTRICCIONES = { video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" }, audio: false };

// --- Lo que observa la IA durante una actividad -------------------------------
// El servicio de visión no guarda nada: el navegador junta lo que reporta en
// cada imagen y lo manda al finalizar la actividad (pantalla 15 lo muestra).

const PROBLEMAS_POSTURA = ["encorvado", "inclinado"];

function observacionesVacias() {
  return {
    desde: performance.now(),
    imagenes: 0,
    msTotal: 0,
    fuentes: {},
    posturaVigilada: false,
    avisos: { encorvado: 0, inclinado: 0 },
    msMalaPostura: 0,
    posturaAnterior: null,
    ultimoT: null,
    correccionesMirada: 0,
  };
}

function observar(obs, datos) {
  const ahora = performance.now();
  obs.imagenes += 1;
  if (typeof datos.ms === "number") obs.msTotal += datos.ms;
  const fuente = datos.cursor?.fuente;
  if (fuente) obs.fuentes[fuente] = (obs.fuentes[fuente] || 0) + 1;

  const postura = datos.postura_sentado;
  if (postura && postura !== "pausa") obs.posturaVigilada = true;
  const mala = PROBLEMAS_POSTURA.includes(postura);
  // Un aviso nuevo cuando pasa de bien (o de otro problema) a un problema.
  if (mala && postura !== obs.posturaAnterior) obs.avisos[postura] += 1;
  // Tiempo con mala postura: entre imágenes, mientras dura el aviso (con tope por si hubo un corte).
  if (mala && PROBLEMAS_POSTURA.includes(obs.posturaAnterior) && obs.ultimoT !== null) {
    obs.msMalaPostura += Math.min(ahora - obs.ultimoT, 2000);
  }
  obs.posturaAnterior = postura;
  obs.ultimoT = ahora;
}

export function ProveedorVision({ children }) {
  const [control, setControlEstado] = useState(() => leerAjuste("control"));
  const [sensibilidad, setSensibilidadEstado] = useState(() => leerAjuste("sensibilidad"));
  // Qué mueve el cursor y cómo puede moverse la persona: vienen de su perfil,
  // así la acompañan en cualquier equipo.
  const { paciente } = useSesion();
  const puntero = paciente?.puntero || "mano";
  const movilidad = paciente?.movilidad || "completa";
  // Con "La voz" la persona elige hablando y la cámara no se enciende.
  const soloVoz = puntero === "voz";
  const usaCamara = control === "camara" && !soloVoz;
  // Con "La voz" la cámara no mueve el cursor, pero se enciende para vigilar
  // la postura (si el control es la cámara y la persona da permiso).
  const camaraPostura = control === "camara" && soloVoz;
  // apagada | solicitando | activa | denegada | desconectada
  const [camara, setCamara] = useState("apagada");
  // cerrada | conectando | abierta
  const [conexion, setConexion] = useState("cerrada");
  const [estado, setEstado] = useState(null);
  const [stream, setStream] = useState(null);

  const r = useRef({
    activo: false,
    ws: null,
    stream: null,
    modo: "seleccion",
    puntero: "mano",
    movilidad: "completa",
    sensibilidad: 1,
    // Calibración de la mirada de esta visita: se reenvía si se reconecta el
    // WebSocket, para no tener que volver a mirar los 9 puntos.
    modeloMirada: null,
    // Alcance real de la mano (calibración guiada a la postura) de esta visita:
    // también se reenvía al reconectar. pedirAlcance: falta medirlo.
    alcance: null,
    pedirAlcance: false,
    enVuelo: false,
    enviadoEn: 0,
    // Lo que observa la IA en la actividad actual, y el error de la última calibración de la mirada.
    obs: observacionesVacias(),
    errorMirada: null,
    temporizadores: {},
  }).current;

  if (!r.video) {
    r.video = document.createElement("video");
    r.video.muted = true;
    r.video.playsInline = true;
    r.lienzo = document.createElement("canvas");
  }

  const enviarFrame = useCallback(() => {
    const { ws, video, lienzo } = r;
    if (!r.activo || !ws || ws.readyState !== WebSocket.OPEN || r.enVuelo) return;
    if (video.readyState < 2 || !video.videoWidth) {
      clearTimeout(r.temporizadores.frame);
      r.temporizadores.frame = setTimeout(enviarFrame, 100);
      return;
    }
    const conMirada = r.puntero === "mirada";
    // Nunca más ancho que la cámara: agrandar no agrega detalle.
    lienzo.width = Math.min(conMirada ? ANCHO_FRAME_MIRADA : ANCHO_FRAME, video.videoWidth);
    // El alto sale del ancho real del lienzo; si no, la cara llega estirada.
    lienzo.height = Math.round((lienzo.width * video.videoHeight) / video.videoWidth);
    lienzo.getContext("2d").drawImage(video, 0, 0, lienzo.width, lienzo.height);
    r.enVuelo = true;
    r.enviadoEn = performance.now();
    lienzo.toBlob(
      (blob) => {
        if (blob && ws.readyState === WebSocket.OPEN) ws.send(blob);
        else r.enVuelo = false;
      },
      "image/jpeg",
      conMirada ? CALIDAD_JPEG_MIRADA : CALIDAD_JPEG,
    );
  }, [r]);

  const abrirConexion = useCallback(() => {
    if (!r.activo || (r.ws && r.ws.readyState <= WebSocket.OPEN)) return;
    const protocolo = location.protocol === "https:" ? "wss" : "ws";
    const token = tokenDeAcceso();
    const ws = new WebSocket(
      `${protocolo}://${location.host}/ws/vision${token ? `?token=${encodeURIComponent(token)}` : ""}`,
    );
    r.ws = ws;
    r.enVuelo = false;
    setConexion("conectando");

    ws.onopen = () => {
      setConexion("abierta");
      const config = {
        accion: "config", modo: r.modo, espejo: true, puntero: r.puntero, movilidad: r.movilidad,
        sensibilidad: r.sensibilidad, vigilar_postura: Boolean(r.vigilarPostura),
      };
      if (r.puntero === "mirada" && r.modeloMirada) config.modelo_mirada = r.modeloMirada;
      if (r.alcance) config.alcance = r.alcance;
      else if (r.pedirAlcance) config.alcance_guiado = true;
      ws.send(JSON.stringify(config));
      enviarFrame();
    };
    ws.onmessage = (evento) => {
      const datos = JSON.parse(evento.data);
      if (datos.tipo === "estado" || datos.tipo === "error") {
        r.enVuelo = false;
        if (datos.tipo === "estado") {
          const mirada = datos.calibracion_mirada;
          if (mirada?.estado === "completa" && mirada.modelo) r.modeloMirada = mirada.modelo;
          if (mirada?.estado === "completa" && typeof mirada.error === "number") r.errorMirada = mirada.error;
          observar(r.obs, datos);
          const calibracion = datos.calibracion;
          if (calibracion?.estado === "completa") {
            if (calibracion.alcance) r.alcance = calibracion.alcance;
            if (calibracion.alcance || calibracion.alcance_omitido) r.pedirAlcance = false;
          }
          setEstado(datos);
        }
        enviarFrame();
      } else if (datos.tipo === "correccion_mirada" && datos.aplicada) {
        r.obs.correccionesMirada += 1;
      }
    };
    ws.onclose = () => {
      if (r.ws === ws) r.ws = null;
      setConexion("cerrada");
      if (r.activo) r.temporizadores.ws = setTimeout(abrirConexion, REINTENTO_WS_MS);
    };
  }, [r, enviarFrame]);

  const usarStream = useCallback(
    (nuevo) => {
      r.stream = nuevo;
      r.video.srcObject = nuevo;
      r.video.play().catch(() => {});
      setStream(nuevo);
      setCamara("activa");
      nuevo.getVideoTracks()[0]?.addEventListener("ended", () => {
        if (!r.activo || r.stream !== nuevo) return;
        // Pantalla 10: el cable se soltó o el sistema quitó la cámara.
        setCamara("desconectada");
        setEstado(null);
        setStream(null);
        programarReintentoCamara();
      });
      abrirConexion();
      enviarFrame();
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [r, abrirConexion, enviarFrame],
  );

  const pedirCamara = useCallback(async () => {
    try {
      usarStream(await navigator.mediaDevices.getUserMedia(RESTRICCIONES));
      return "activa";
    } catch (error) {
      if (error.name === "NotAllowedError" || error.name === "SecurityError") {
        setCamara("denegada");
        return "denegada";
      }
      setCamara("desconectada");
      programarReintentoCamara();
      return "desconectada";
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [usarStream]);

  function programarReintentoCamara() {
    clearTimeout(r.temporizadores.camara);
    r.temporizadores.camara = setTimeout(() => r.activo && pedirCamara(), REINTENTO_CAMARA_MS);
  }

  // Con "La voz" el permiso que importa es el del micrófono: se pide aquí, en la
  // pantalla de privacidad, y no por sorpresa cuando empieza a escuchar.
  const pedirMicrofono = useCallback(async () => {
    try {
      const prueba = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      prueba.getTracks().forEach((pista) => pista.stop()); // solo era para el permiso
      return "activa";
    } catch (error) {
      return error.name === "NotAllowedError" || error.name === "SecurityError" ? "denegada" : "sin_microfono";
    }
  }, []);

  const encender = useCallback(async () => {
    if (soloVoz) {
      // Con la voz, lo indispensable es el micrófono. La cámara (solo para la
      // postura) se pide después; si no se permite, se juega igual con la voz.
      const microfono = await pedirMicrofono();
      if (microfono !== "activa" || !camaraPostura) return microfono;
      if (r.activo && r.stream) return "activa";
      r.activo = true;
      setCamara("solicitando");
      await pedirCamara();
      return "activa";
    }
    if (!usaCamara) return "activa";
    if (r.activo && r.stream) return "activa";
    r.activo = true;
    setCamara("solicitando");
    return pedirCamara();
  }, [soloVoz, usaCamara, camaraPostura, r, pedirCamara, pedirMicrofono]);

  const apagar = useCallback(() => {
    r.activo = false;
    Object.values(r.temporizadores).forEach(clearTimeout);
    r.ws?.close();
    r.ws = null;
    r.stream?.getTracks().forEach((pista) => pista.stop());
    r.stream = null;
    r.video.srcObject = null;
    setStream(null);
    setEstado(null);
    setCamara("apagada");
    setConexion("cerrada");
  }, [r]);

  const reintentar = useCallback(() => {
    if (!r.activo) return encender();
    if (!r.stream) return pedirCamara();
    abrirConexion();
    return Promise.resolve("activa");
  }, [r, encender, pedirCamara, abrirConexion]);

  const enviarControl = useCallback(
    (mensaje) => r.ws?.readyState === WebSocket.OPEN && r.ws.send(JSON.stringify(mensaje)),
    [r],
  );

  /**
   * Se eligió un botón con la mirada: dónde estaba (centro y tamaño, en
   * fracción de pantalla). El servicio lo usa para corregir la deriva.
   */
  const objetivoMirada = useCallback(
    (rect) => {
      const ancho = window.innerWidth;
      const alto = window.innerHeight;
      const limitar = (v) => Math.min(Math.max(v, 0), 1);
      enviarControl({
        accion: "objetivo_mirada",
        punto: [limitar((rect.left + rect.width / 2) / ancho), limitar((rect.top + rect.height / 2) / alto)],
        tamano: [limitar(rect.width / ancho), limitar(rect.height / alto)],
      });
    },
    [enviarControl],
  );

  /** Empieza una actividad: se observa desde cero. */
  const reiniciarObservaciones = useCallback(() => {
    r.obs = observacionesVacias();
  }, [r]);

  /**
   * Lo que observó la IA desde el último reinicio, en el formato que espera
   * el backend al finalizar la sesión. Sin cámara, solo dice cómo eligió.
   */
  const tomarObservaciones = useCallback(() => {
    const o = r.obs;
    const usada = Object.entries(o.fuentes).sort((a, b) => b[1] - a[1])[0]?.[0];
    const datos = {
      puntero: soloVoz ? "voz" : !usaCamara ? "mouse" : usada || (puntero === "mirada" ? "mirada" : "mano"),
    };
    if (o.imagenes > 0) {
      datos.imagenes_analizadas = o.imagenes;
      datos.ms_por_imagen = Math.round((o.msTotal / o.imagenes) * 10) / 10;
      datos.postura_vigilada = o.posturaVigilada;
      if (o.posturaVigilada) {
        datos.avisos_encorvado = o.avisos.encorvado;
        datos.avisos_inclinado = o.avisos.inclinado;
        datos.segundos_mala_postura = Math.round(o.msMalaPostura / 100) / 10;
      }
      if (datos.puntero === "mirada") {
        datos.correcciones_mirada = o.correccionesMirada;
        if (typeof r.errorMirada === "number") datos.error_mirada = Math.min(Math.max(r.errorMirada, 0), 1);
      }
    }
    return datos;
  }, [r, soloVoz, usaCamara, puntero]);

  /** Vigilar la postura al estar sentado (durante las actividades). */
  const setVigilarPostura = useCallback(
    (activa) => {
      if (Boolean(r.vigilarPostura) === activa) return;
      r.vigilarPostura = activa;
      enviarControl({ accion: "config", vigilar_postura: activa });
    },
    [r, enviarControl],
  );

  const setModo = useCallback(
    (modo) => {
      if (r.modo === modo) return;
      r.modo = modo;
      enviarControl({ accion: "config", modo });
    },
    [r, enviarControl],
  );

  const calibrar = useCallback(() => {
    r.modeloMirada = null;
    r.alcance = null;
    enviarControl({ accion: "calibrar" });
  }, [r, enviarControl]);

  // Calibración guiada a la postura: la persona lleva la mano hacia cada lado
  // hasta donde llega cómoda. Si el WebSocket aún no abrió, se pide al abrir.
  const calibrarAlcance = useCallback(() => {
    r.alcance = null;
    r.pedirAlcance = true;
    enviarControl({ accion: "config", alcance_guiado: true });
  }, [r, enviarControl]);

  const omitirAlcance = useCallback(() => {
    r.pedirAlcance = false;
    enviarControl({ accion: "omitir_alcance" });
  }, [r, enviarControl]);

  // Si no se puede usar la cámara (mouse de pruebas), se apaga.
  useEffect(() => {
    if (!usaCamara && !camaraPostura && r.activo) apagar();
  }, [usaCamara, camaraPostura, r, apagar]);

  // La calibración de la mirada es de cada persona: al cambiar de persona se descarta.
  const pacienteId = paciente?.id ?? null;
  useEffect(() => {
    if (r.pacienteId === pacienteId) return;
    r.pacienteId = pacienteId;
    r.modeloMirada = null;
    r.alcance = null;
    r.pedirAlcance = false;
  }, [r, pacienteId]);

  // Con "La voz" el servicio no busca la mano ni manda cursor: solo la postura.
  useEffect(() => {
    if (r.puntero === puntero && r.movilidad === movilidad) return;
    if (r.puntero !== puntero) r.modeloMirada = null; // otro puntero
    r.puntero = puntero;
    r.movilidad = movilidad;
    enviarControl({ accion: "config", puntero, movilidad });
  }, [r, puntero, movilidad, enviarControl]);

  // r.sensibilidad la lee onopen: así una reconexión manda el valor actual.
  r.sensibilidad = sensibilidad;
  const setSensibilidad = useCallback(
    (nueva) => {
      guardarAjuste("sensibilidad", nueva);
      r.sensibilidad = nueva;
      setSensibilidadEstado(nueva);
      enviarControl({ accion: "config", sensibilidad: nueva });
    },
    [r, enviarControl],
  );

  const setControl = useCallback(
    (nuevo) => {
      guardarAjuste("control", nuevo);
      if (nuevo === "mouse") apagar();
      setControlEstado(nuevo);
    },
    [apagar],
  );

  // Si una respuesta nunca llega (red caída a medias), se vuelve a enviar.
  useEffect(() => {
    const vigilante = setInterval(() => {
      if (r.enVuelo && performance.now() - r.enviadoEn > FRAME_PERDIDO_MS) {
        r.enVuelo = false;
        enviarFrame();
      }
    }, 1000);
    return () => clearInterval(vigilante);
  }, [r, enviarFrame]);

  useEffect(() => apagar, [apagar]);

  const valor = {
    control,
    setControl,
    sensibilidad,
    setSensibilidad,
    // Con el mouse no hay mirada: así las pantallas solo preguntan por "mirada".
    puntero: soloVoz ? "voz" : control === "camara" ? puntero : "mano",
    // Si la cámara participa (no con el mouse de pruebas ni con "La voz").
    usaCamara,
    // Con "La voz": cámara encendida solo para vigilar la postura.
    camaraPostura,
    // Elegir diciendo la opción: siempre con "La voz", o como ayuda extra.
    conVoz: soloVoz || Boolean(paciente?.comandos_voz),
    movilidad,
    camara,
    conexion,
    estado,
    stream,
    encender,
    apagar,
    reintentar,
    setModo,
    calibrar,
    calibrarAlcance,
    omitirAlcance,
    objetivoMirada,
    setVigilarPostura,
    reiniciarObservaciones,
    tomarObservaciones,
  };
  return <ContextoVision.Provider value={valor}>{children}</ContextoVision.Provider>;
}

export const useVision = () => useContext(ContextoVision);
