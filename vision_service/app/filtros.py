"""Filtro One Euro (Casiez, Roussel y Vogel, 2012).

Suaviza mucho cuando la mano está casi quieta (elimina el temblor) y poco
cuando se mueve rápido (evita que el cursor se quede atrás).
"""

import math


def _alfa(dt, frecuencia_corte):
    tau = 1.0 / (2 * math.pi * frecuencia_corte)
    return 1.0 / (1.0 + tau / dt)


class FiltroOneEuro:
    def __init__(self, corte_minimo=0.8, beta=0.6, corte_derivada=1.0):
        self.corte_minimo = corte_minimo
        self.beta = beta
        self.corte_derivada = corte_derivada
        self.reiniciar()

    def reiniciar(self):
        self._x = None
        self._dx = 0.0
        self._t = None

    def __call__(self, x, t):
        """x: valor nuevo, t: tiempo en segundos."""
        if self._x is None:
            self._x, self._t = x, t
            return x
        dt = t - self._t
        if dt <= 0:
            return self._x

        dx = (x - self._x) / dt
        a_d = _alfa(dt, self.corte_derivada)
        self._dx = a_d * dx + (1 - a_d) * self._dx

        corte = self.corte_minimo + self.beta * abs(self._dx)
        a = _alfa(dt, corte)
        self._x = a * x + (1 - a) * self._x
        self._t = t
        return self._x
