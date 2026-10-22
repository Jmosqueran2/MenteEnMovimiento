import { useEffect, useState } from "react";
import { BarChart3, Download } from "lucide-react";
import { api } from "../api";
import { IconoCirculo } from "../componentes/comunes";
import { decimal, etiquetaDia, hoyIso } from "../formato";
import { useSesion } from "../sesion";
import { Encabezado } from "./LayoutCuidador";

const PERIODOS = [7, 30];

/** Pantalla 15: seguimiento del progreso. */
export default function Seguimiento() {
  const { paciente } = useSesion();
  const [dias, setDias] = useState(7);
  const [datos, setDatos] = useState(null);
  const [exportando, setExportando] = useState(false);

  useEffect(() => {
    setDatos(null);
    api(`/api/pacientes/${paciente.id}/seguimiento/?dias=${dias}`).then(setDatos).catch(() => {});
  }, [paciente.id, dias]);

  const exportar = async () => {
    setExportando(true);
    try {
      const respuesta = await api(`/api/pacientes/${paciente.id}/seguimiento-csv/?dias=${dias}`, { crudo: true });
      const enlace = document.createElement("a");
      enlace.href = URL.createObjectURL(await respuesta.blob());
      enlace.download = `seguimiento_${paciente.nombre.toLowerCase()}_${hoyIso()}.csv`;
      enlace.click();
      URL.revokeObjectURL(enlace.href);
    } finally {
      setExportando(false);
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
                  <tr><th>Día</th><th>Actividad</th><th>Aciertos</th></tr>
                </thead>
                <tbody>
                  {datos.recientes.map((s) => (
                    <tr key={s.fecha}>
                      <td>{etiquetaDia(s.fecha)}</td>
                      <td>{s.actividad}</td>
                      <td>{s.aciertos}/{s.total}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      <div className="encabezado" style={{ alignItems: "center", marginTop: "auto" }}>
        <p className="texto-apoyo">Los datos se registran solos en cada sesión.</p>
        <button type="button" className="boton boton-principal" disabled={!datos?.sesiones || exportando} onClick={exportar}>
          <Download size={22} /> {exportando ? "Exportando…" : "Exportar CSV"}
        </button>
      </div>
    </>
  );
}
