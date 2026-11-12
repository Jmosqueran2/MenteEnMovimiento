import { useEffect, useRef, useState } from "react";
import { RotateCcw } from "lucide-react";
import { Boton } from "../componentes/comunes";
import { hablar, sonarAcierto, sonarReintento } from "../sonidos";
import { formasDeNumero } from "../vision/voz";

/*
 * Juegos que no son "elegir una opción y listo". Todos se eligen igual que el
 * resto (permanencia, mouse o voz) porque usan [data-elegible]; un elemento
 * que no se puede elegir en ese momento simplemente no lo lleva.
 */

/**
 * Opción con emoji, con foto de Mi Historia o solo con texto.
 * numeroVoz: número para elegirla diciéndolo. sinTexto: se oculta el nombre
 * (en "encuentra el igual", el nombre resolvería el juego sin mirar).
 */
export function TarjetaOpcion({ opcion, numero, numeroVoz, sinTexto = false, className = "", ...props }) {
  const conDibujo = opcion.emoji || opcion.imagen;
  return (
    <button type="button" className={`opcion ${conDibujo ? "" : "opcion-solo-texto"} ${className}`}
            aria-label={sinTexto ? `Opción ${numeroVoz}` : undefined} {...props}>
      {numero != null && <span className="orden-numero" aria-hidden="true">{numero}</span>}
      {numeroVoz != null && <span className="voz-numero" aria-hidden="true">{numeroVoz}</span>}
      {opcion.imagen ? (
        <img className="opcion-foto" src={opcion.imagen} alt="" />
      ) : opcion.emoji ? (
        <span className="opcion-imagen" aria-hidden="true">{opcion.emoji}</span>
      ) : null}
      {!sinTexto && opcion.texto}
    </button>
  );
}

/**
 * Parejas de Memoria: cartas boca abajo; se destapan de a dos. Si van juntas
 * quedan a la vista; si no, se vuelven a tapar. Al terminar se informa cuántos
 * errores hubo (el servidor decide si fue acierto).
 */
export function JuegoParejas({ pregunta, onTerminar, onListo }) {
  const cartas = pregunta.opciones;
  const [abiertas, setAbiertas] = useState([]);
  const [encontradas, setEncontradas] = useState(() => new Set());
  const [bloqueado, setBloqueado] = useState(false);
  const errores = useRef(0);
  const temporizador = useRef();

  useEffect(() => {
    onListo?.();
    return () => clearTimeout(temporizador.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const destapar = (i) => {
    if (bloqueado || encontradas.has(i) || abiertas.includes(i)) return;
    const nuevas = [...abiertas, i];
    if (nuevas.length < 2) return setAbiertas(nuevas);

    const [a, b] = nuevas;
    if (cartas[a].pareja === cartas[b].pareja) {
      const todas = new Set([...encontradas, a, b]);
      setEncontradas(todas);
      setAbiertas([]);
      sonarAcierto();
      if (todas.size === cartas.length) {
        temporizador.current = setTimeout(() => onTerminar(errores.current), 900);
      } else {
        hablar(`¡Pareja! ${cartas[a].texto} y ${cartas[b].texto}.`);
      }
    } else {
      // Se dejan ver un momento para que se puedan recordar, y se tapan.
      errores.current += 1;
      setAbiertas(nuevas);
      setBloqueado(true);
      sonarReintento();
      temporizador.current = setTimeout(() => {
        setAbiertas([]);
        setBloqueado(false);
      }, 1400);
    }
  };

  const columnas = cartas.length <= 6 ? 3 : 4;
  return (
    <div className="cartas" style={{ gridTemplateColumns: `repeat(${columnas}, 1fr)` }}>
      {cartas.map((carta, i) => {
        const visible = abiertas.includes(i) || encontradas.has(i);
        const elegible = !visible && !bloqueado;
        return (
          <button
            key={i}
            type="button"
            className={`carta ${visible ? "carta-abierta" : ""} ${encontradas.has(i) ? "carta-encontrada" : ""} ${elegible ? "elegible-tarjeta" : ""}`}
            data-elegible={elegible ? "" : undefined}
            data-voz-solo={elegible ? formasDeNumero(i + 1) : undefined}
            aria-label={visible ? carta.texto : `Carta ${i + 1}`}
            onClick={() => destapar(i)}
          >
            {visible ? (
              <>
                <span className="carta-emoji" aria-hidden="true">{carta.emoji}</span>
                <span className="carta-texto">{carta.texto}</span>
              </>
            ) : (
              <span className="carta-dorso" aria-hidden="true">{i + 1}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

/**
 * Secuencias y "Ordena los recuerdos": se señalan las opciones en orden; cada
 * una recibe su número. Al completar todas se envía el orden.
 */
export function JuegoOrden({ pregunta, onTerminar, onListo }) {
  const [elegidos, setElegidos] = useState([]);
  const temporizador = useRef();
  const opciones = pregunta.opciones;

  useEffect(() => {
    onListo?.();
    return () => clearTimeout(temporizador.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const elegir = (i) => {
    if (elegidos.includes(i)) return;
    const nuevos = [...elegidos, i];
    setElegidos(nuevos);
    if (nuevos.length === opciones.length) {
      // Un instante para ver el último número antes de enviar.
      temporizador.current = setTimeout(() => onTerminar(nuevos), 700);
    } else {
      hablar(`${nuevos.length}: ${opciones[i].texto}. ¿Y después?`);
    }
  };

  const completo = elegidos.length === opciones.length;
  return (
    <>
      <div className={`opciones opciones-orden ${opciones.length > 4 ? "opciones-cinco" : ""}`}>
        {opciones.map((opcion, i) => {
          const puesto = elegidos.indexOf(i);
          const libre = puesto === -1 && !completo;
          return (
            <TarjetaOpcion
              key={i}
              opcion={opcion}
              numero={puesto === -1 ? null : puesto + 1}
              className={`${libre ? "elegible-tarjeta" : "opcion-elegida"}`}
              data-elegible={libre ? "" : undefined}
              onClick={() => libre && elegir(i)}
            />
          );
        })}
      </div>
      {elegidos.length > 0 && !completo && (
        <Boton variante="secundario" icono={RotateCcw} onClick={() => setElegidos([])} style={{ alignSelf: "flex-start" }}
               data-voz="borrar, de nuevo, empezar otra vez">
          Empezar de nuevo
        </Boton>
      )}
    </>
  );
}

/**
 * Atención sostenida: se muestran las cartas con la figura pedida resaltada,
 * se tapan y se cruzan despacio. Al detenerse, hay que elegir dónde quedó.
 */
export function SigueFigura({ pregunta, onElegir, onListo }) {
  const { intercambios, paso_ms: paso, mostrar_ms: mostrar } = pregunta.ajustes;
  const n = pregunta.opciones.length;
  // puesto[i] = en qué lugar (columna) está ahora la opción i.
  const [puesto, setPuesto] = useState(() => [...Array(n).keys()]);
  const [fase, setFase] = useState("mostrar"); // mostrar | mover | elegir
  const [moviendo, setMoviendo] = useState([]);
  const objetivo = pregunta.estimulo?.texto;

  useEffect(() => {
    const temporizadores = [];
    let actual = [...Array(n).keys()];
    temporizadores.push(setTimeout(() => {
      setFase("mover");
      hablar("Ahora síguela con la vista.");
    }, mostrar));
    for (let k = 0; k < intercambios; k++) {
      temporizadores.push(setTimeout(() => {
        // Se cruzan dos lugares al azar (siempre distintos).
        const a = Math.floor(Math.random() * n);
        const b = (a + 1 + Math.floor(Math.random() * (n - 1))) % n;
        const ia = actual.indexOf(a);
        const ib = actual.indexOf(b);
        actual = [...actual];
        actual[ia] = b;
        actual[ib] = a;
        setPuesto(actual);
        setMoviendo([ia, ib]);
      }, mostrar + 700 + k * paso));
    }
    temporizadores.push(setTimeout(() => {
      setMoviendo([]);
      setFase("elegir");
      hablar(`¿Dónde quedó ${objetivo}?`);
      onListo?.();
    }, mostrar + 700 + intercambios * paso));
    return () => temporizadores.forEach(clearTimeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="sigue" style={{ gridTemplateColumns: `repeat(${n}, 1fr)`, "--paso": `${paso * 0.8}ms` }}>
      {pregunta.opciones.map((opcion, i) => {
        const tapada = fase !== "mostrar";
        const elegible = fase === "elegir";
        const esObjetivo = opcion.texto === objetivo;
        return (
          <button
            key={i}
            type="button"
            className={`carta sigue-carta ${tapada ? "" : "carta-abierta"} ${!tapada && esObjetivo ? "sigue-objetivo" : ""} ${moviendo.includes(i) ? "sigue-moviendo" : ""} ${elegible ? "elegible-tarjeta" : ""}`}
            style={{ transform: `translateX(calc(${puesto[i] - i} * (100% + 20px)))` }}
            data-elegible={elegible ? "" : undefined}
            data-voz-solo={elegible ? formasDeNumero(puesto[i] + 1) : undefined}
            aria-label={tapada ? `Carta ${puesto[i] + 1}` : opcion.texto}
            onClick={() => elegible && onElegir(i)}
          >
            {tapada ? (
              <span className="carta-dorso" aria-hidden="true">?</span>
            ) : (
              <>
                <span className="carta-emoji" aria-hidden="true">{opcion.emoji}</span>
                <span className="carta-texto">{opcion.texto}</span>
              </>
            )}
          </button>
        );
      })}
    </div>
  );
}

/** Alcanza y recuerda: el objeto se ve unos segundos y luego desaparece. */
export function Memorizar({ objeto, duracionMs, onFin }) {
  useEffect(() => {
    const t = setTimeout(onFin, duracionMs);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <div className="memorizar" role="status">
      <span className="memorizar-emoji" aria-hidden="true">{objeto.emoji}</span>
      <strong>{objeto.texto}</strong>
      <div className="barra memorizar-barra"><span style={{ animationDuration: `${duracionMs}ms` }} /></div>
    </div>
  );
}
