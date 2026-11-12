/*
 * Elegir con la voz: la persona dice la opción ("cuchara", "comenzar",
 * "pausa") y se pulsa el elemento [data-elegible] cuyo texto coincide.
 * Sinónimos extra en data-voz="sí, acepto".
 */

const Reconocedor = typeof window !== "undefined" && (window.SpeechRecognition || window.webkitSpeechRecognition);

export const vozDisponible = () => Boolean(Reconocedor);

// Palabras que no ayudan a distinguir una opción de otra.
const VACIAS = new Set([
  "el", "la", "los", "las", "un", "una", "unos", "unas", "y", "o", "de", "del", "a", "al", "con", "en",
  "por", "para", "mi", "tu", "su", "que", "es", "esa", "ese", "esta", "este", "creo", "quiero", "elijo",
]);

export function normalizar(texto) {
  return (texto || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9ñ ]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

// Las 5 primeras letras bastan para unir formas de un verbo o un plural.
const raiz = (palabra) => (palabra.length >= 5 ? palabra.slice(0, 5) : palabra);

const palabras = (texto) => normalizar(texto).split(" ").filter((p) => p && !VACIAS.has(p));

/**
 * candidatos: [{ id, textos: ["Aceptar y continuar", "sí"] }]
 * Devuelve el id elegido, o null si nada coincide o si hay empate (mejor no
 * adivinar: un clic equivocado frustra más que repetir).
 * Con soloCompleta solo vale si dijo la etiqueta o un sinónimo entero: es lo
 * que se exige a un resultado parcial, que todavía puede cambiar.
 */
export const PUNTAJE_COMPLETA = 100;

export function elegirPorVoz(frase, candidatos, { soloCompleta = false } = {}) {
  const dichas = new Set(palabras(frase));
  const fraseNorm = ` ${normalizar(frase)} `;
  let mejor = null;
  let mejorPuntaje = 0;
  let empate = false;

  for (const { id, textos } of candidatos) {
    let puntaje = 0;
    for (const texto of textos) {
      const norm = normalizar(texto);
      if (!norm) continue;
      if (fraseNorm.includes(` ${norm} `)) {
        puntaje = Math.max(puntaje, PUNTAJE_COMPLETA + norm.length); // dijo la etiqueta completa
        continue;
      }
      const propias = palabras(texto).filter((p) => p.length >= 3);
      const acertadas = propias.filter((p) => dichas.has(p)).length;
      if (acertadas) puntaje = Math.max(puntaje, (acertadas / propias.length) * 50 + acertadas);
      // Otra forma de la misma palabra ("empezamos" por "empezar"): vale menos.
      const raices = new Set([...dichas].map(raiz));
      const parecidas = propias.filter((p) => raices.has(raiz(p))).length;
      if (parecidas) puntaje = Math.max(puntaje, (parecidas / propias.length) * 25 + parecidas);
    }
    if (puntaje > mejorPuntaje) {
      mejor = id;
      mejorPuntaje = puntaje;
      empate = false;
    } else if (puntaje && puntaje === mejorPuntaje) {
      empate = true;
    }
  }
  if (empate || (soloCompleta && mejorPuntaje < PUNTAJE_COMPLETA)) return null;
  if (soloCompleta) {
    // "volver" puede ser el comienzo de "volver a calibrar": se espera a que termine.
    const dicho = normalizar(frase);
    const sigue = candidatos.some(({ id, textos }) => id !== mejor
      && textos.some((t) => normalizar(t).startsWith(`${dicho} `)));
    if (sigue) return null;
  }
  return mejor;
}

/** Elementos elegibles que la persona ve ahora (no tapados por un aviso). */
export function elegiblesVisibles() {
  return [...document.querySelectorAll("[data-elegible]")].filter((el) => {
    if (el.disabled || el.getAttribute("aria-disabled") === "true") return false;
    const caja = el.getBoundingClientRect();
    if (!caja.width || !caja.height) return false;
    const x = Math.min(Math.max(caja.left + caja.width / 2, 0), window.innerWidth - 1);
    const y = Math.min(Math.max(caja.top + caja.height / 2, 0), window.innerHeight - 1);
    const encima = document.elementFromPoint(x, y);
    return encima === el || el.contains(encima) || encima?.closest?.(".puntero");
  });
}

const NUMEROS = ["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez",
  "once", "doce"];

/** Formas de decir el número n: "3", "tres", "número 3", "la tres"… */
export function formasDeNumero(n) {
  const palabra = NUMEROS[n] || String(n);
  return [n, palabra, `número ${n}`, `número ${palabra}`, `opción ${n}`, `carta ${n}`, `carta ${palabra}`]
    .map(String).join(", ");
}

export function textosDe(el) {
  // data-voz-solo: solo vale lo indicado (p. ej. el número de una opción), no
  // el texto visible. Así decir "tortuga" no resuelve "encuentra el mismo dibujo".
  if (el.dataset.vozSolo !== undefined) return el.dataset.vozSolo.split(",").filter(Boolean);
  const textos = [el.getAttribute("aria-label"), el.innerText];
  if (el.dataset.voz) textos.push(...el.dataset.voz.split(","));
  return textos.filter(Boolean);
}

/**
 * Escucha continua con resultados parciales: alOir(alternativas, { final })
 * recibe la frase mientras la persona todavía habla, sin esperar el silencio
 * con que el navegador cierra el resultado final (≈ 1 s). Si alOir devuelve
 * true, ya actuó: el resto de esa frase se ignora para no elegir dos veces.
 * Devuelve una función para detenerla.
 */

// El español de la persona (es-CO, es-MX…) se reconoce mejor y más rápido con
// su variante; si el navegador no está en español, se usa es-ES.
const idioma = () => {
  const preferido = typeof navigator !== "undefined" ? navigator.language : "";
  return preferido?.toLowerCase().startsWith("es") ? preferido : "es-ES";
};
export function escuchar({ alOir, alCambiarEstado }) {
  if (!Reconocedor) return () => {};
  let activo = true;
  let reintento;
  const rec = new Reconocedor();
  rec.lang = idioma();
  rec.continuous = true;
  rec.interimResults = true;
  rec.maxAlternatives = 3;
  // Índices de resultados de esta sesión que ya eligieron algo.
  let usados = new Set();

  // Chrome reciente puede reconocer sin enviar el audio a sus servidores.
  if ("processLocally" in rec && Reconocedor.available) {
    Reconocedor.available({ langs: [rec.lang], processLocally: true })
      .then((estado) => { if (estado === "available") rec.processLocally = true; })
      .catch(() => {});
  }

  rec.onstart = () => {
    usados = new Set(); // cada sesión del reconocedor numera desde 0
    alCambiarEstado?.("escuchando");
  };
  rec.onresult = (evento) => {
    for (let i = evento.resultIndex; i < evento.results.length; i++) {
      if (usados.has(i)) continue;
      const resultado = evento.results[i];
      const alternativas = [...resultado].map((alternativa) => alternativa.transcript);
      if (alOir(alternativas, { final: resultado.isFinal })) usados.add(i);
    }
  };
  rec.onerror = (evento) => {
    if (evento.error === "not-allowed" || evento.error === "service-not-allowed") {
      activo = false;
      alCambiarEstado?.("denegado");
    } else if (evento.error === "network") {
      // Chrome y Edge reconocen la voz en sus servidores: sin internet no oyen.
      alCambiarEstado?.("sin_red");
    } else if (evento.error === "audio-capture") {
      alCambiarEstado?.("sin_microfono");
    }
    // "no-speech" y "aborted" son normales: onend vuelve a escuchar.
  };
  // El navegador corta tras un silencio: se vuelve a escuchar.
  rec.onend = () => {
    if (!activo) return alCambiarEstado?.("apagado");
    // Casi sin pausa: lo que se diga en ese hueco se pierde.
    reintento = setTimeout(() => {
      try { rec.start(); } catch { /* ya estaba escuchando */ }
    }, 50);
  };

  try {
    rec.start();
  } catch {
    alCambiarEstado?.("apagado");
  }
  return () => {
    activo = false;
    clearTimeout(reintento);
    rec.abort();
  };
}
