import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowUp, CheckCircle2, FileX, Music, Trash2 } from "lucide-react";
import { api, ErrorApi } from "../api";
import { IconoCirculo } from "../componentes/comunes";
import { useSesion } from "../sesion";
import { Encabezado } from "./LayoutCuidador";

const PERMITIDOS = /\.(jpe?g|png|mp3)$/i;
const mensajeFormato = (nombre) =>
  `«${nombre}» no se pudo subir. Este formato no está permitido. Usa una foto JPG o PNG, o un audio MP3.`;

/** Pantallas 12 (subir), 13 (formato no permitido) y 14 (contenido guardado). */
export default function MiHistoria() {
  const navegar = useNavigate();
  const { paciente } = useSesion();
  const entrada = useRef(null);
  const [contenidos, setContenidos] = useState([]);
  const [archivo, setArchivo] = useState(null);
  const [vistaPrevia, setVistaPrevia] = useState(null);
  const [titulo, setTitulo] = useState("");
  const [pista, setPista] = useState("");
  const [errorArchivo, setErrorArchivo] = useState(null);
  const [error, setError] = useState(null);
  const [arrastrando, setArrastrando] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [guardado, setGuardado] = useState(null);

  const cargar = useCallback(
    () => api(`/api/historia/?paciente=${paciente.id}`).then(setContenidos).catch(() => {}),
    [paciente.id],
  );
  useEffect(() => {
    cargar();
  }, [cargar]);

  useEffect(() => () => vistaPrevia && URL.revokeObjectURL(vistaPrevia), [vistaPrevia]);

  const elegirArchivo = (nuevo) => {
    if (!nuevo) return;
    setError(null);
    if (!PERMITIDOS.test(nuevo.name)) {
      setArchivo(null);
      setVistaPrevia(null);
      setErrorArchivo({ nombre: nuevo.name, mensaje: mensajeFormato(nuevo.name) });
      return;
    }
    setErrorArchivo(null);
    setArchivo(nuevo);
    setVistaPrevia(/\.mp3$/i.test(nuevo.name) ? null : URL.createObjectURL(nuevo));
  };

  const reiniciar = () => {
    setArchivo(null);
    setVistaPrevia(null);
    setTitulo("");
    setPista("");
    setErrorArchivo(null);
    setError(null);
    setGuardado(null);
  };

  const guardar = async () => {
    if (!archivo) return setError("Elige una foto o un audio.");
    if (!titulo.trim()) return setError("Escribe un título.");
    const formulario = new FormData();
    formulario.append("paciente", paciente.id);
    formulario.append("titulo", titulo.trim());
    formulario.append("pista", pista.trim());
    formulario.append("archivo", archivo);
    setEnviando(true);
    try {
      const nuevo = await api("/api/historia/", { metodo: "POST", formulario });
      setGuardado(nuevo);
      cargar();
    } catch (e) {
      if (e instanceof ErrorApi && e.datos?.archivo) {
        setErrorArchivo({ nombre: archivo.name, mensaje: e.datos.archivo[0] });
        setArchivo(null);
        setVistaPrevia(null);
      } else {
        setError(e.message);
      }
    } finally {
      setEnviando(false);
    }
  };

  const borrar = async (contenido) => {
    if (!window.confirm(`¿Borrar «${contenido.titulo}» de Mi Historia?`)) return;
    await api(`/api/historia/${contenido.id}/`, { metodo: "DELETE" });
    cargar();
  };

  const galeria = (
    <div className="bloque">
      <h2>Contenido guardado</h2>
      {contenidos.length === 0 ? (
        <p className="texto-apoyo">Todavía no hay fotos ni audios.</p>
      ) : (
        <div className="galeria">
          {contenidos.map((c) => (
            <figure key={c.id} className={`miniatura ${guardado?.id === c.id ? "nueva" : ""}`} style={{ margin: 0 }}>
              {guardado?.id === c.id && <span className="nuevo">Nuevo</span>}
              <span className="imagen">
                {c.tipo === "imagen" ? <img src={c.url} alt="" /> : <Music size={40} />}
              </span>
              <figcaption>{c.titulo}</figcaption>
              <button type="button" className="borrar" aria-label={`Borrar ${c.titulo}`} onClick={() => borrar(c)}>
                <Trash2 size={18} />
              </button>
            </figure>
          ))}
        </div>
      )}
    </div>
  );

  // Pantalla 14
  if (guardado) {
    return (
      <>
        <Encabezado etiqueta="Mi Historia" titulo={<><CheckCircle2 color="var(--verde)" size={34} /> Contenido guardado</>} />
        <div className="columnas">
          <div className="bloque">
            <div className="tarjeta" style={{ display: "flex", gap: 20, alignItems: "center", border: "2px solid var(--verde)" }}>
              <span className="miniatura" style={{ width: 120 }}>
                <span className="imagen">
                  {guardado.tipo === "imagen" ? <img src={guardado.url} alt="" /> : <Music size={40} />}
                </span>
              </span>
              <div style={{ display: "grid", gap: 6 }}>
                <strong style={{ fontSize: 22 }}>{guardado.titulo}</strong>
                {guardado.pista && <span className="texto-apoyo">Pista: {guardado.pista}</span>}
                <span className="chip chip-verde" style={{ fontSize: 15, justifySelf: "start" }}>
                  Se agregó a la actividad Mi Historia
                </span>
              </div>
            </div>
            <h2>¿Qué deseas hacer ahora?</h2>
            <div className="segmentado">
              <button type="button" className="boton boton-secundario" onClick={reiniciar}>Cargar otra</button>
              <button type="button" className="boton boton-secundario" onClick={() => navegar("/jugar")}>
                Ver como {paciente.nombre}
              </button>
            </div>
          </div>
          {galeria}
        </div>
        <div className="acciones">
          <button type="button" className="boton boton-principal" onClick={() => navegar("/cuidador")}>
            Volver al panel
          </button>
        </div>
      </>
    );
  }

  const conError = Boolean(errorArchivo);
  return (
    <>
      <Encabezado etiqueta="Mi Historia" titulo="Subir contenido" />
      <div className="columnas">
        <div className="bloque">
          <div
            role="button"
            tabIndex={0}
            className={`zona-subida ${arrastrando ? "arrastrando" : ""} ${conError ? "con-error" : ""}`}
            onClick={() => entrada.current.click()}
            onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && entrada.current.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setArrastrando(true);
            }}
            onDragLeave={() => setArrastrando(false)}
            onDrop={(e) => {
              e.preventDefault();
              setArrastrando(false);
              elegirArchivo(e.dataTransfer.files[0]);
            }}
          >
            {conError ? (
              <>
                <IconoCirculo icono={FileX} tono="rojo" tamano={56} />
                <strong className="error-texto">No pudimos subir «{errorArchivo.nombre}»</strong>
                <span>{errorArchivo.mensaje.replace(`«${errorArchivo.nombre}» no se pudo subir. `, "")}</span>
              </>
            ) : archivo ? (
              <>
                {vistaPrevia ? <img src={vistaPrevia} alt="Vista previa" /> : <IconoCirculo icono={Music} tamano={56} />}
                <strong>{archivo.name}</strong>
                <span className="texto-apoyo">Haz clic para elegir otro archivo</span>
              </>
            ) : (
              <>
                <IconoCirculo icono={ArrowUp} tamano={56} />
                <strong>Arrastra una foto o audio</strong>
                <span>o selecciona un archivo</span>
                <span className="texto-apoyo">JPG, PNG o MP3 · hasta 10 MB</span>
              </>
            )}
          </div>
          <input
            ref={entrada}
            type="file"
            accept=".jpg,.jpeg,.png,.mp3,image/jpeg,image/png,audio/mpeg"
            hidden
            onChange={(e) => {
              elegirArchivo(e.target.files[0]);
              e.target.value = "";
            }}
          />
          <div className="campo">
            <label htmlFor="titulo">Título</label>
            <input id="titulo" value={titulo} disabled={conError} placeholder="Boda de Rosa y Juan" maxLength={120}
                   onChange={(e) => setTitulo(e.target.value)} />
          </div>
          <div className="campo">
            <label htmlFor="pista">Pista para la actividad</label>
            <input id="pista" value={pista} disabled={conError} placeholder="¿Quién está a tu lado?" maxLength={200}
                   onChange={(e) => setPista(e.target.value)} />
          </div>
          {error && <p className="error-texto">{error}</p>}
        </div>
        {galeria}
      </div>
      <div className="acciones">
        <button type="button" className="boton boton-secundario" onClick={() => navegar("/cuidador")}>Cancelar</button>
        {conError ? (
          <button type="button" className="boton boton-principal" onClick={() => { setErrorArchivo(null); entrada.current.click(); }}>
            Elegir otro archivo
          </button>
        ) : (
          <button type="button" className="boton boton-principal" disabled={enviando} onClick={guardar}>
            {enviando ? "Guardando…" : "Guardar"}
          </button>
        )}
      </div>
    </>
  );
}

