from django.core.management.base import BaseCommand

from adaptacion import modelo


class Command(BaseCommand):
    help = "Entrena el modelo de dificultad adaptativa (scikit-learn) y lo guarda."

    def add_arguments(self, parser):
        parser.add_argument("--muestras", type=int, default=6000)
        parser.add_argument("--semilla", type=int, default=42)

    def handle(self, *args, **opciones):
        self.stdout.write(f"Generando {opciones['muestras']} sesiones simuladas y entrenando…")
        clasificador, info = modelo.entrenar(opciones["muestras"], opciones["semilla"])
        destino = modelo.guardar(clasificador, info)

        m = info["metricas"]
        self.stdout.write(f"Distribución de etiquetas: {info['distribucion']}")
        self.stdout.write(
            f"Exactitud: {m['exactitud']:.1%} · F1 macro: {m['f1_macro']:.3f} · "
            f"F1 macro (validación cruzada 5 pliegues): {m['f1_macro_validacion_cruzada']:.3f}"
        )
        self.stdout.write("\n" + info["reporte"])
        self.stdout.write("Importancia de las variables:")
        for nombre, valor in info["importancias"].items():
            self.stdout.write(f"  {nombre:<18} {'#' * round(valor * 50)} {valor:.3f}")
        self.stdout.write(self.style.SUCCESS(f"Modelo guardado en {destino}"))
