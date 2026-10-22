import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Check, Eraser, Info, Lock, LogOut, Play, Power, RotateCcw } from "lucide-react";
import { Boton, IconoCirculo, PantallaAdulto, Pasos } from "../componentes/comunes";
import { useSesion } from "../sesion";
import { hablar } from "../sonidos";
import { useVision } from "../vision/ProveedorVision";

/** Pantalla 01: consentimiento de cámara. */
export function Consentimiento() {
  const navegar = useNavigate();
  const { encender } = useVision();
  const [pidiendo, setPidiendo] = useState(false);

  useEffect(() => hablar("Tu cámara, tu privacidad. Usamos la cámara solo para ver cómo mueves las manos y los brazos."), []);

  const aceptar = async () => {
    setPidiendo(true);
    const resultado = await encender();
    navegar(resultado === "denegada" ? "/jugar/sin-permiso" : "/jugar/deteccion");
  };

  return (
    <PantallaAdulto
      lateral={
        <>
          <h1>Hola, empecemos juntos</h1>
          <p>Primero necesitamos tu permiso para usar la cámara.</p>
          <Pasos actual={0} />
        </>
      }
      acciones={
        <>
          <Boton variante="secundario" onClick={() => navegar("/jugar/sin-permiso")}>Ahora no</Boton>
          <Boton onClick={aceptar} disabled={pidiendo}>{pidiendo ? "Activando…" : "Aceptar y continuar"}</Boton>
        </>
      }
    >
      <p className="etiqueta">Paso 1 de 3</p>
      <h2 className="titulo">Tu cámara, tu privacidad</h2>
      <p className="texto-apoyo">Usamos la cámara solo para ver cómo mueves las manos y los brazos.</p>
      <div className="tarjetas-tres">
        <div className="tarjeta">
          <IconoCirculo icono={Lock} />
          <h3>Nada se graba</h3>
          <p className="texto-apoyo">Ni fotos ni videos.</p>
        </div>
        <div className="tarjeta">
          <IconoCirculo icono={Eraser} />
          <h3>Se borra al instante</h3>
          <p className="texto-apoyo">Cada imagen se analiza y se descarta.</p>
        </div>
        <div className="tarjeta">
          <IconoCirculo icono={Power} />
          <h3>Tú tienes el control</h3>
          <p className="texto-apoyo">Apágala cuando quieras.</p>
        </div>
      </div>
      <p className="nota">Lo puede autorizar el usuario o su cuidador.</p>
    </PantallaAdulto>
  );
}

/** Pantalla 02: sin permiso de cámara. */
export function SinPermiso() {
  const navegar = useNavigate();
  const { camara } = useVision();

  useEffect(() => hablar("No activamos la cámara. No pasa nada, puedes volver cuando quieras."), []);

  return (
    <PantallaAdulto
      lateral={
        <>
          <h1>Está bien, sin prisa</h1>
          <p>Sin la cámara no podemos ver tus movimientos.</p>
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
      <h2 className="titulo">No activamos la cámara</h2>
      <p className="texto-apoyo">No pasa nada. Puedes volver cuando quieras.</p>
      <div className="aviso aviso-crema">
        <IconoCirculo icono={Info} tono="amarillo" />
        <div>
          <h3>Mente en Movimiento necesita la cámara</h3>
          <p>Así reconoce tus manos y brazos. Nada se graba.</p>
        </div>
      </div>
      <p><strong>Puedes:</strong></p>
      <ol className="lista-numerada">
        <li data-n="1">Volver y aceptar cuando estés listo.</li>
        <li data-n="2">Pedir ayuda a tu cuidador.</li>
      </ol>
      {camara === "denegada" && (
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
  const { control, camara, estado, stream, calibrar } = useVision();
  const video = useRef(null);

  useEffect(() => {
    if (control === "camara" && camara === "apagada") navegar("/jugar", { replace: true });
    if (camara === "denegada") navegar("/jugar/sin-permiso", { replace: true });
  }, [control, camara, navegar]);

  useEffect(() => {
    if (video.current) video.current.srcObject = stream;
  }, [stream]);

  const conMouse = control === "mouse";
  const persona = conMouse || Boolean(estado?.postura?.persona);
  const calibracion = estado?.calibracion;
  const calibrado = conMouse || calibracion?.estado === "completa";
  const luzBuena = conMouse || estado?.luz?.estado === "ok";
  const listo = persona && calibrado && luzBuena;
  const alerta = estado?.alertas?.find((a) => CONSEJOS[a]);

  useEffect(() => {
    if (listo) hablar(`¡Hola, ${paciente.nombre}! Ya te vemos. Mantén la mano quieta sobre Comenzar.`);
  }, [listo, paciente.nombre]);

  return (
    <PantallaAdulto
      lateral={
        <>
          <h1>{listo ? `¡Hola, ${paciente.nombre}!` : "Te estamos buscando"}</h1>
          <p>{listo ? "Ya te vemos. Cuando quieras, empezamos." : "Siéntate cómodo frente a la pantalla."}</p>
          <Pasos actual={1} />
        </>
      }
      acciones={
        <>
          <Boton variante="secundario" icono={ArrowLeft} onClick={() => navegar("/jugar")}>Volver</Boton>
          <Boton icono={Play} disabled={!listo} onClick={() => navegar("/jugar/menu")}>Comenzar</Boton>
        </>
      }
    >
      <p className="etiqueta">Paso 2 de 3</p>
      <h2 className="titulo">{listo ? "Te estamos viendo" : "Buscándote…"}</h2>
      <div className="vista-camara">
        {conMouse ? (
          <p style={{ color: "white" }}>Modo de prueba: se usa el mouse en lugar de la cámara.</p>
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
      {!conMouse && persona && !calibrado && (
        <div style={{ display: "grid", gap: 10 }}>
          <p>Ajustando el sistema a tu postura… {Math.round((calibracion?.progreso || 0) * 100)} %</p>
          <div className="barra"><span style={{ width: `${(calibracion?.progreso || 0) * 100}%` }} /></div>
        </div>
      )}
      <p className="texto-apoyo">
        {listo ? "Mantén la mano quieta sobre Comenzar." : alerta ? CONSEJOS[alerta] : "Un momento, por favor…"}
        {!conMouse && calibrado && (
          <button type="button" className="boton boton-secundario" style={{ marginLeft: 16, minHeight: 48, fontSize: 20, padding: "0 20px" }} onClick={calibrar} data-elegible="">
            <RotateCcw size={20} /> Volver a calibrar
          </button>
        )}
      </p>
    </PantallaAdulto>
  );
}

/** Fin del recorrido del adulto mayor. */
export function Despedida() {
  const navegar = useNavigate();
  const { paciente } = useSesion();
  const { apagar } = useVision();

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
      <p className="texto-apoyo">La cámara ya está apagada. Tus resultados quedaron guardados para tu cuidador.</p>
    </PantallaAdulto>
  );
}
