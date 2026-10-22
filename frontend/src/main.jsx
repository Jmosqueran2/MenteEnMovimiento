import { createRoot } from "react-dom/client";
import { createBrowserRouter, Navigate, RouterProvider } from "react-router-dom";
import Actividad from "./adulto/Actividad";
import { Consentimiento, Despedida, Deteccion, SinPermiso } from "./adulto/Inicio";
import LayoutAdulto from "./adulto/LayoutAdulto";
import Menu from "./adulto/Menu";
import { Cargando } from "./componentes/comunes";
import Configuracion from "./cuidador/Configuracion";
import LayoutCuidador from "./cuidador/LayoutCuidador";
import Login from "./cuidador/Login";
import MiHistoria from "./cuidador/MiHistoria";
import Panel from "./cuidador/Panel";
import Seguimiento from "./cuidador/Seguimiento";
import { ProveedorSesion, useSesion } from "./sesion";
import { ProveedorVision } from "./vision/ProveedorVision";
import "./estilos.css";

function RequiereSesion({ children, conPaciente = false }) {
  const { cuidador, paciente, cargando } = useSesion();
  if (cargando) return <Cargando />;
  if (!cuidador) return <Navigate to="/login" replace />;
  if (conPaciente && !paciente) return <Navigate to="/cuidador/configuracion" replace />;
  return children;
}

const rutas = createBrowserRouter([
  { path: "/", element: <Navigate to="/cuidador" replace /> },
  { path: "/login", element: <Login /> },
  {
    path: "/cuidador",
    element: (
      <RequiereSesion>
        <LayoutCuidador />
      </RequiereSesion>
    ),
    children: [
      { index: true, element: <RequiereSesion conPaciente><Panel /></RequiereSesion> },
      { path: "historia", element: <RequiereSesion conPaciente><MiHistoria /></RequiereSesion> },
      { path: "seguimiento", element: <RequiereSesion conPaciente><Seguimiento /></RequiereSesion> },
      { path: "configuracion", element: <Configuracion /> },
    ],
  },
  {
    path: "/jugar",
    element: (
      <RequiereSesion conPaciente>
        <LayoutAdulto />
      </RequiereSesion>
    ),
    children: [
      { index: true, element: <Consentimiento /> },
      { path: "sin-permiso", element: <SinPermiso /> },
      { path: "deteccion", element: <Deteccion /> },
      { path: "menu", element: <Menu /> },
      { path: "actividad/:tipo", element: <Actividad /> },
      { path: "fin", element: <Despedida /> },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);

// Sin StrictMode: en desarrollo montaría dos veces Actividad y crearía dos sesiones.
createRoot(document.getElementById("root")).render(
  <ProveedorSesion>
    <ProveedorVision>
      <RouterProvider router={rutas} />
    </ProveedorVision>
  </ProveedorSesion>,
);
