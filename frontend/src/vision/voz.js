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

const palabras = (texto) => normalizar(texto).split(" ").filter((p) => p && !VACIAS.has(p));

/**
 * candidatos: [{ id, textos: ["Aceptar y continuar", "sí"] }]
 * Devuelve el id elegido, o null si nada coincide o si hay empate (mejor no
 * adivinar: un clic equivocado frustra más que repetir).
 */
export function elegirPorVoz(frase, candidatos) {
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
        puntaje = Math.max(puntaje, 100 + norm.length); // dijo la etiqueta completa
        continue;
      }
      const propias = palabras(texto).filter((p) => p.length >= 3);
      const acertadas = propias.filter((p) => dichas.has(p)).length;
      if (acertadas) puntaje = Math.max(puntaje, (acertadas / propias.length) * 50 + acertadas);
    }
    if (puntaje > mejorPuntaje) {
      mejor = id;
      mejorPuntaje = puntaje;
      empate = false;
    } else if (puntaje && puntaje === mejorPuntaje) {
      empate = true;
    }
  }
  return empate ? null : mejor;
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

export function textosDe(el) {
  const textos = [el.getAttribute("aria-label"), el.innerText];
  if (el.dataset.voz) textos.push(...el.dataset.voz.split(","));
  return textos.filter(Boolean);
}

/**
 * Escucha continua. alOir(frase) recibe cada frase final reconocida.
 * Devuelve una función para detenerla.
 */
export function escuchar({ alOir, alCambiarEstado }) {
  if (!Reconocedor) return () => {};
  let activo = true;
  let reintento;
  const rec = new Reconocedor();
  rec.lang = "es-ES";
  rec.continuous = true;
  rec.interimResults = false;
  rec.maxAlternatives = 3;

  // Chrome reciente puede reconocer sin enviar el audio a sus servidores.
  if ("processLocally" in rec && Reconocedor.available) {
    Reconocedor.available({ langs: ["es-ES"], processLocally: true })
      .then((estado) => { if (estado === "available") rec.processLocally = true; })
      .catch(() => {});
  }

  rec.onstart = () => alCambiarEstado?.("escuchando");
  rec.onresult = (evento) => {
    for (let i = evento.resultIndex; i < evento.results.length; i++) {
      const resultado = evento.results[i];
      if (!resultado.isFinal) continue;
      alOir([...resultado].map((alternativa) => alternativa.transcript));
    }
  };
  rec.onerror = (evento) => {
    if (evento.error === "not-allowed" || evento.error === "service-not-allowed") {
      activo = false;
      alCambiarEstado?.("denegado");
    }
  };
  // El navegador corta tras un silencio: se vuelve a escuchar.
  rec.onend = () => {
    if (!activo) return alCambiarEstado?.("apagado");
    reintento = setTimeout(() => {
      try { rec.start(); } catch { /* ya estaba escuchando */ }
    }, 300);
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
