import { leerAjuste } from "./ajustes";

let contexto = null;
// Lo último que dijo la narración: los comandos de voz no deben tomarlo como
// si lo hubiera dicho la persona.
let ultimaNarracion = { texto: "", fin: 0 };

function tonos(frecuencias, duracion, forma, volumen) {
  try {
    contexto ||= new AudioContext();
    contexto.resume();
    let t = contexto.currentTime;
    for (const frecuencia of frecuencias) {
      const oscilador = contexto.createOscillator();
      const ganancia = contexto.createGain();
      oscilador.type = forma;
      oscilador.frequency.value = frecuencia;
      ganancia.gain.setValueAtTime(0.0001, t);
      ganancia.gain.exponentialRampToValueAtTime(volumen, t + 0.02);
      ganancia.gain.exponentialRampToValueAtTime(0.0001, t + duracion);
      oscilador.connect(ganancia).connect(contexto.destination);
      oscilador.start(t);
      oscilador.stop(t + duracion + 0.02);
      t += duracion * 0.9;
    }
  } catch {
    // El navegador no permite audio todavía; no es grave.
  }
}

/** Do–mi–sol ascendente: "tono alegre" del prototipo. */
export const sonarAcierto = () => tonos([523.25, 659.25, 783.99], 0.16, "triangle", 0.25);
/** Dos notas suaves descendentes: "tono suave" para reintentar. */
export const sonarReintento = () => tonos([392, 349.23], 0.28, "sine", 0.15);
/** Clic corto al completar la permanencia sobre un elemento. */
export const sonarSeleccion = () => tonos([880], 0.07, "sine", 0.08);

export function hablar(texto) {
  if (!texto || !leerAjuste("voz") || !("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const frase = new SpeechSynthesisUtterance(texto);
  frase.lang = "es-ES";
  frase.rate = 0.9;
  const voz = window.speechSynthesis.getVoices().find((v) => v.lang.startsWith("es"));
  if (voz) frase.voice = voz;
  ultimaNarracion = { texto, fin: Infinity, frase };
  frase.onend = frase.onerror = () => { ultimaNarracion.fin = performance.now(); };
  window.speechSynthesis.speak(frase);
}

// Una frase de 2 palabras o más que coincide con la narración es eco: los
// parlantes se cuelan en el micrófono y se oye la oración entera o un trozo.
// Una sola palabra no: la narración dice "di «comenzar»" y la persona
// responde justamente "comenzar"; descartarla dejaba la voz sin hacer caso.
const PALABRAS_ECO = 2;
const ECO_MS = 3000;

/** ¿Lo que se oyó es la propia narración (sonando o recién terminada)? */
export function esEco(oido, normalizar) {
  const hablando = "speechSynthesis" in window && window.speechSynthesis.speaking;
  // Chrome a veces no dispara onend: si ya no habla, se da por terminada ahora.
  if (!hablando && ultimaNarracion.fin === Infinity) ultimaNarracion.fin = performance.now();
  if (!hablando && performance.now() - ultimaNarracion.fin >= ECO_MS) return false;
  const frase = normalizar(oido);
  if (!frase || frase.split(" ").length < PALABRAS_ECO) return false;
  return ` ${normalizar(ultimaNarracion.texto)} `.includes(` ${frase} `);
}

/** ¿La narración está hablando o acaba de terminar? (su eco puede seguir llegando) */
export function narrando() {
  const hablando = "speechSynthesis" in window && window.speechSynthesis.speaking;
  if (!hablando && ultimaNarracion.fin === Infinity) ultimaNarracion.fin = performance.now();
  return hablando || performance.now() - ultimaNarracion.fin < 500;
}

export const callar = () => "speechSynthesis" in window && window.speechSynthesis.cancel();
