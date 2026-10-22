import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { tokenDeAcceso } from "../api";
import { guardarAjuste, leerAjuste } from "../ajustes";

/*
 * Cámara + WebSocket con el microservicio de visión.
 *
 * Se envía un frame JPEG pequeño y se espera la respuesta antes de mandar el
 * siguiente: el ritmo se adapta solo a la latencia hasta AWS.
 */

const ContextoVision = createContext(null);
const ANCHO_FRAME = 320;
const CALIDAD_JPEG = 0.7;
const REINTENTO_CAMARA_MS = 3000;
const REINTENTO_WS_MS = 2000;
const FRAME_PERDIDO_MS = 3000;
const RESTRICCIONES = { video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" }, audio: false };

export function ProveedorVision({ children }) {
  const [control, setControlEstado] = useState(() => leerAjuste("control"));
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
    enVuelo: false,
    enviadoEn: 0,
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
    lienzo.width = ANCHO_FRAME;
    lienzo.height = Math.round((ANCHO_FRAME * video.videoHeight) / video.videoWidth);
    lienzo.getContext("2d").drawImage(video, 0, 0, lienzo.width, lienzo.height);
    r.enVuelo = true;
    r.enviadoEn = performance.now();
    lienzo.toBlob(
      (blob) => {
        if (blob && ws.readyState === WebSocket.OPEN) ws.send(blob);
        else r.enVuelo = false;
      },
      "image/jpeg",
      CALIDAD_JPEG,
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
      ws.send(JSON.stringify({ accion: "config", modo: r.modo, espejo: true }));
      enviarFrame();
    };
    ws.onmessage = (evento) => {
      const datos = JSON.parse(evento.data);
      if (datos.tipo === "estado" || datos.tipo === "error") {
        r.enVuelo = false;
        if (datos.tipo === "estado") setEstado(datos);
        enviarFrame();
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

  const encender = useCallback(async () => {
    if (control === "mouse") return "activa";
    if (r.activo && r.stream) return "activa";
    r.activo = true;
    setCamara("solicitando");
    return pedirCamara();
  }, [control, r, pedirCamara]);

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

  const setModo = useCallback(
    (modo) => {
      if (r.modo === modo) return;
      r.modo = modo;
      enviarControl({ accion: "config", modo });
    },
    [r, enviarControl],
  );

  const calibrar = useCallback(() => enviarControl({ accion: "calibrar" }), [enviarControl]);

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
    camara,
    conexion,
    estado,
    stream,
    encender,
    apagar,
    reintentar,
    setModo,
    calibrar,
  };
  return <ContextoVision.Provider value={valor}>{children}</ContextoVision.Provider>;
}

export const useVision = () => useContext(ContextoVision);
