import { useEffect, useRef, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { ArrowLeft, CameraOff, LogOut, RotateCw, Sun, WifiOff } from "lucide-react";
import { Boton, IconoCirculo, PantallaAdulto } from "../componentes/comunes";
import { useSesion } from "../sesion";
import { hablar } from "../sonidos";
import { useVision } from "../vision/ProveedorVision";
import ComandosVoz from "../vision/ComandosVoz";
import Puntero from "../vision/Puntero";

// En estas pantallas todavía no hay cámara, así que no se muestran errores de visión.
const SIN_AVISOS = ["/jugar", "/jugar/sin-permiso", "/jugar/fin"];
const LUZ_BAJA_MS = 2000;
const SIN_CONEXION_MS = 5000;

export default function LayoutAdulto() {
  const { paciente } = useSesion();
  const { apagar } = useVision();
  const { pathname } = useLocation();
  const conVoz = paciente.comandos_voz && !pathname.startsWith("/jugar/fin");

  // Al salir del modo adulto mayor se apaga la cámara.
  useEffect(() => apagar, [apagar]);

  return (
    <>
      <Outlet />
      <AvisosVision />
      <Puntero permanenciaMs={paciente.tiempo_permanencia_ms} />
      {conVoz && <ComandosVoz />}
    </>
  );
}

/** Pantallas 09 (poca luz) y 10 (cámara desconectada) como capa sobre la actividad. */
function AvisosVision() {
  const { control, camara, conexion, estado, reintentar } = useVision();
  const { pathname } = useLocation();
  const navegar = useNavigate();
  const [aviso, setAviso] = useState(null);
  const desde = useRef({ luz: null, conexion: null });
  const ignorarHasta = useRef(0);

  const activo = control === "camara" && !SIN_AVISOS.includes(pathname.replace(/\/$/, ""));
  const enMenu = pathname.startsWith("/jugar/menu");

  useEffect(() => {
    if (!activo) return setAviso(null);
    const ahora = Date.now();

    if (camara === "desconectada") return setAviso("camara");

    const sinConexion = camara === "activa" && conexion !== "abierta";
    desde.current.conexion = sinConexion ? (desde.current.conexion ?? ahora) : null;
    if (sinConexion && ahora - desde.current.conexion > SIN_CONEXION_MS) return setAviso("conexion");

    const oscuro = estado?.alertas.includes("poca_luz");
    desde.current.luz = oscuro ? (desde.current.luz ?? ahora) : null;
    if (oscuro && ahora - desde.current.luz > LUZ_BAJA_MS && ahora > ignorarHasta.current) return setAviso("luz");
    if (!oscuro || ahora <= ignorarHasta.current) setAviso((a) => (a === "luz" ? null : a));
    if (conexion === "abierta") setAviso((a) => (a === "conexion" || a === "camara" ? null : a));
  }, [activo, camara, conexion, estado]);

  // El efecto anterior depende de mensajes; sin mensajes (conexión caída) se revisa cada segundo.
  const [, refrescar] = useState(0);
  useEffect(() => {
    if (!activo || conexion === "abierta") return undefined;
    const intervalo = setInterval(() => refrescar((n) => n + 1), 1000);
    return () => clearInterval(intervalo);
  }, [activo, conexion]);

  useEffect(() => {
    if (aviso === "luz") hablar("Hay poca luz. Enciende una luz o ponte frente a una ventana.");
    if (aviso === "camara") hablar("Se desconectó la cámara. No te preocupes, tu avance está guardado.");
  }, [aviso]);

  if (!aviso) return null;

  const salida = enMenu ? (
    <Boton variante="secundario" icono={LogOut} onClick={() => navegar("/jugar/fin")}>Salir</Boton>
  ) : (
    <Boton variante="secundario" icono={ArrowLeft} onClick={() => navegar("/jugar/menu")}>Volver al menú</Boton>
  );

  if (aviso === "luz") {
    return (
      <div className="capa">
        <PantallaAdulto
          lateral={
            <div className="lateral-cuerpo lateral-centro">
              <span className="halo halo-naranja"><IconoCirculo icono={Sun} tono="naranja" tamano={120} /></span>
              <h1>Hay poca luz</h1>
              <p>No podemos ver bien tus manos.</p>
            </div>
          }
          acciones={
            <>
              {salida}
              <Boton icono={RotateCw} onClick={() => { ignorarHasta.current = Date.now() + 5000; setAviso(null); }}>
                Reintentar
              </Boton>
            </>
          }
        >
          <p className="etiqueta">Ajusta la luz</p>
          <h2 className="titulo">Busquemos más luz</h2>
          <p className="chip chip-naranja" style={{ alignSelf: "flex-start" }}>Imagen muy oscura</p>
          <p><strong>Prueba esto:</strong></p>
          <ol className="lista-numerada">
            <li data-n="1">Enciende una luz.</li>
            <li data-n="2">Mira hacia una ventana.</li>
            <li data-n="3">Evita tener luz detrás de ti.</li>
          </ol>
          <p className="texto-apoyo"><span className="spinner" style={{ display: "inline-block", width: 24, height: 24, verticalAlign: "middle", marginRight: 10 }} />Buscándote de nuevo…</p>
        </PantallaAdulto>
      </div>
    );
  }

  const esConexion = aviso === "conexion";
  return (
    <div className="capa">
      <PantallaAdulto
        lateral={
          <div className="lateral-cuerpo lateral-centro">
            <span className="halo halo-rojo"><IconoCirculo icono={esConexion ? WifiOff : CameraOff} tono="rojo" tamano={120} /></span>
            <h1>{esConexion ? "Perdimos la conexión" : "Se desconectó la cámara"}</h1>
            <p>No te preocupes, tu avance está guardado.</p>
          </div>
        }
        acciones={
          <>
            {salida}
            <Boton icono={RotateCw} onClick={reintentar}>Reintentar</Boton>
          </>
        }
      >
        <p className="etiqueta">Reconectando</p>
        <h2 className="titulo">{esConexion ? "Estamos volviendo a conectarnos" : "Estamos buscando tu cámara"}</h2>
        <div className="tarjeta" style={{ display: "flex", gap: 18, alignItems: "center" }}>
          <span className="spinner" aria-hidden="true" />
          <div>
            <strong>Reconectando automáticamente…</strong>
            <p className="texto-apoyo">Esto toma solo unos segundos.</p>
          </div>
        </div>
        <p><strong>Mientras tanto:</strong></p>
        <ol className="lista-numerada">
          {esConexion ? (
            <li data-n="1">Revisa que el internet esté funcionando.</li>
          ) : (
            <li data-n="1">Revisa que el cable de la cámara esté bien conectado.</li>
          )}
          <li data-n="2">Acércate a la pantalla y espera.</li>
          <li data-n="3">Si sigue igual, pide ayuda a tu cuidador.</li>
        </ol>
      </PantallaAdulto>
    </div>
  );
}
