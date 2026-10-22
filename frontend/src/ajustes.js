// Preferencias de este equipo (no viajan al servidor).
const POR_DEFECTO = {
  control: "camara", // "camara" | "mouse" (mouse: solo para pruebas sin cámara)
  voz: true, // narración de las instrucciones
};

export function leerAjuste(clave) {
  try {
    const valor = localStorage.getItem(`mm_${clave}`);
    return valor === null ? POR_DEFECTO[clave] : JSON.parse(valor);
  } catch {
    return POR_DEFECTO[clave];
  }
}

export function guardarAjuste(clave, valor) {
  try {
    localStorage.setItem(`mm_${clave}`, JSON.stringify(valor));
  } catch {
    // Sin almacenamiento disponible: se usa el valor por defecto.
  }
}
