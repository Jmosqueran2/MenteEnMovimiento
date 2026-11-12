import { useEffect, useState } from "react";
import { BarChart3, Cpu, Crosshair, Download, Eye, FileText, HandHelping, PersonStanding } from "lucide-react";
import { api } from "../api";
import { IconoCirculo } from "../componentes/comunes";
import { decimal, etiquetaDia, hoyIso } from "../formato";
import { useSesion } from "../sesion";
import { Encabezado } from "./LayoutCuidador";

const PERIODOS = [7, 30];
const NOMBRE_PUNTERO = { mano: "La mano", mirada: "La mirada", cabeza: "La cabeza", voz: "La voz", mouse: "Mouse (pruebas)" };
const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;

/** Una línea por sesión: lo que vio la IA de visión. */
function textoObservado(ia) {
  if (!ia) return "—";
  const partes = [];
  if (ia.postura_vigilada) {
    partes.push(ia.avisos_postura === 0 ? "Postura bien" : plural(ia.avisos_postura, "aviso de postura", "avisos de postura"));
  }
  if (ia.pedidos_ayuda) partes.push(`Pidió ayuda ${plural(ia.pedidos_ayuda, "vez", "veces")}`);
  if (ia.error_mirada !== null && ia.error_mirada !== undefined) partes.push(`Mirada ±${decimal(100 * ia.error_mirada)} %`);
  if (!partes.length && ia.puntero) partes.push(`Eligió con ${NOMBRE_PUNTERO[ia.puntero]?.toLowerCase() || ia.puntero}`);
  return partes.join(" · ") || "—";
}

/** Totales del periodo de lo que observó la IA de visión durante las actividades. */
function LoObservadoPorLaIA({ ia, nombre }) {
  if (!ia) return null;
  const sinDatos = !ia.sesiones_con_datos;
  const punteros = Object.entries(ia.punteros || {})
    .sort((a, b) => b[1] - a[1])
    .map(([p, n]) => `${NOMBRE_PUNTERO[p] || p} (${n})`)
    .join(", ");

  return (
    <div className="tarjeta bloque observado-ia">
      <h2><Cpu size={26} aria-hidden="true" /> Lo que observó la IA</h2>
      <p className="texto-apoyo" style={{ fontSize: 16 }}>
        Durante cada actividad, la IA de visión analiza la cámara imagen por imagen y la descarta al instante:
        no se graba nada. Esto es lo que detectó.
      </p>
      {sinDatos ? (
        <p className="texto-apoyo">
          Todavía no hay actividades con datos de la cámara en este periodo. Aparecerán cuando {nombre} haga una
          actividad con la mano o con la mirada.
        </p>
      ) : (
        <div className="observado-ia-cifras">
          <div className="observado-ia-cifra">
            <PersonStanding size={30} aria-hidden="true" />
            {ia.sesiones_postura ? (
              <>
                <strong>{plural(ia.avisos_postura, "aviso", "avisos")} de postura</strong>
                <span>
                  {ia.sesiones_sin_avisos} de {ia.sesiones_postura} sesiones sin ningún aviso
                  {ia.minutos_mala_postura > 0 ? ` · ${decimal(ia.minutos_mala_postura)} min encorvada o ladeada` : ""}
                </span>
              </>
            ) : (
              <>
                <strong>Postura</strong>
                <span>No se vigiló en este periodo</span>
              </>
            )}
          </div>
          <div className="observado-ia-cifra">
            <HandHelping size={30} aria-hidden="true" />
            <strong>{plural(ia.pedidos_ayuda, "pedido", "pedidos")} de ayuda</strong>
            <span>Desde las pantallas de poca luz o sin cámara</span>
          </div>
          <div className="observado-ia-cifra">
            <Crosshair size={30} aria-hidden="true" />
            <strong>Cursor</strong>
            <span>{punteros || "—"}</span>
          </div>
          {ia.error_mirada !== null && (
            <div className="observado-ia-cifra">
              <Eye size={30} aria-hidden="true" />
              <strong>Mirada ±{decimal(100 * ia.error_mirada)} %</strong>
              <span>Error de la calibración · {plural(ia.correcciones_mirada, "ajuste automático", "ajustes automáticos")}</span>
            </div>
          )}
          {ia.imagenes_analizadas > 0 && (
            <div className="observado-ia-cifra">
              <Cpu size={30} aria-hidden="true" />
              <strong>{ia.imagenes_analizadas.toLocaleString("es-EC")} imágenes</strong>
              <span>Analizadas por la IA{ia.ms_por_imagen ? ` · ${ia.ms_por_imagen} ms cada una` : ""}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** Pantalla 15: seguimiento del progreso. */
export default function Seguimiento() {
  const { paciente } = useSesion();
  const [dias, setDias] = useState(7);
  const [datos, setDatos] = useState(null);
  const [exportando, setExportando] = useState(null); // "csv" | "pdf" | null
  const [error, setError] = useState(null);

  useEffect(() => {
    setDatos(null);
    api(`/api/pacientes/${paciente.id}/seguimiento/?dias=${dias}`).then(setDatos).catch(() => {});
  }, [paciente.id, dias]);

  const exportar = async (formato) => {
    setExportando(formato);
    setError(null);
    try {
      const respuesta = await api(`/api/pacientes/${paciente.id}/seguimiento-${formato}/?dias=${dias}`, { crudo: true });
      const enlace = document.createElement("a");
      enlace.href = URL.createObjectURL(await respuesta.blob());
      enlace.download = `seguimiento_${paciente.nombre.toLowerCase()}_${hoyIso()}.${formato}`;
      enlace.click();
      URL.revokeObjectURL(enlace.href);
    } catch {
      setError("No pudimos generar el archivo. Intenta de nuevo.");
    } finally {
      setExportando(null);
    }
  };

  return (
    <>
      <Encabezado etiqueta="Seguimiento" titulo={`Progreso de ${paciente.nombre}`}>
        <div className="segmentado" role="group" aria-label="Periodo">
          {PERIODOS.map((p) => (
            <button key={p} type="button" aria-pressed={dias === p} onClick={() => setDias(p)}>
              {p} días
            </button>
          ))}
        </div>
      </Encabezado>

      {!datos ? (
        <p className="texto-apoyo">Cargando…</p>
      ) : datos.sesiones === 0 ? (
        <div className="tarjeta vacio">
          <IconoCirculo icono={BarChart3} tamano={72} />
          <h2>Aún no hay sesiones registradas</h2>
          <p>Cuando {paciente.nombre} complete una actividad, aquí verás su progreso.</p>
        </div>
      ) : (
        <>
          <div className="cifras">
            <div className="tarjeta cifra"><strong>{datos.tasa_aciertos} %</strong><span>Aciertos</span></div>
            <div className="tarjeta cifra"><strong>{decimal(datos.tiempo_promedio_s)} s</strong><span>Tiempo medio</span></div>
            <div className="tarjeta cifra"><strong>{datos.sesiones}</strong><span>Sesiones</span></div>
            <div className="tarjeta cifra"><strong>{datos.nivel_texto}</strong><span>Nivel</span></div>
          </div>

          <div className="columnas" style={{ gridTemplateColumns: "1fr 1fr" }}>
            <div className="tarjeta bloque">
              <h2>Aciertos por sesión</h2>
              <div className="grafica" role="img" aria-label="Porcentaje de aciertos por sesión">
                {datos.por_sesion.map((s, i) => (
                  <div key={s.etiqueta} className={`barra-grafica ${i === datos.por_sesion.length - 1 ? "ultima" : ""}`}>
                    <span>{s.porcentaje}</span>
                    <span style={{ height: `${s.porcentaje}%` }} title={`${s.etiqueta}: ${s.porcentaje} %`} />
                  </div>
                ))}
              </div>
              <div className="ejes">
                {datos.por_sesion.map((s) => <span key={s.etiqueta}>{s.etiqueta}</span>)}
              </div>
            </div>

            <div className="tarjeta bloque">
              <h2>Sesiones recientes</h2>
              <table className="tabla">
                <thead>
                  <tr><th>Día</th><th>Actividad</th><th>Aciertos</th><th>La IA observó</th></tr>
                </thead>
                <tbody>
                  {datos.recientes.map((s) => (
                    <tr key={s.fecha}>
                      <td>{etiquetaDia(s.fecha)}</td>
                      <td>{s.actividad}</td>
                      <td>{s.aciertos}/{s.total}</td>
                      <td className="celda-ia">{textoObservado(s.ia)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <LoObservadoPorLaIA ia={datos.ia} nombre={paciente.nombre} />
        </>
      )}

      <div className="encabezado" style={{ alignItems: "center", marginTop: "auto" }}>
        <p className="texto-apoyo">
          {error || `Los datos se registran solos en cada sesión. Se exportan los últimos ${dias} días.`}
        </p>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <button type="button" className="boton boton-secundario" disabled={!datos?.sesiones || Boolean(exportando)} onClick={() => exportar("csv")}>
            <Download size={22} /> {exportando === "csv" ? "Exportando…" : "Exportar CSV"}
          </button>
          <button type="button" className="boton boton-principal" disabled={!datos?.sesiones || Boolean(exportando)} onClick={() => exportar("pdf")}>
            <FileText size={22} /> {exportando === "pdf" ? "Generando PDF…" : "Exportar PDF"}
          </button>
        </div>
      </div>
    </>
  );
}
