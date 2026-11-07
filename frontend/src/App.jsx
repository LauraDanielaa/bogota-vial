import { useCallback, useEffect, useState } from "react";
import Header from "./components/Header.jsx";
import MapaPage from "./pages/MapaPage.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";
import ListadoPage from "./pages/ListadoPage.jsx";

// Rutas con hash: #/ (mapa, página principal), #/dashboard, #/listado
const VISTAS_VALIDAS = ["dashboard", "listado"];
const leerVista = () => {
  const h = window.location.hash.replace(/^#\/?/, "");
  return VISTAS_VALIDAS.includes(h) ? h : "mapa";
};

// Enlaces de SECOP que el usuario pega en el listado. Por ahora se guardan en
// el navegador; más adelante irán al backend.
const CLAVE_ENLACES = "bogota-vial:enlaces";
function leerEnlaces() {
  try {
    return JSON.parse(localStorage.getItem(CLAVE_ENLACES)) || {};
  } catch {
    return {};
  }
}

export default function App() {
  const [vista, setVista] = useState(leerVista);
  const [enlaces, setEnlaces] = useState(leerEnlaces);

  useEffect(() => {
    const alCambiar = () => {
      setVista(leerVista());
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", alCambiar);
    return () => window.removeEventListener("hashchange", alCambiar);
  }, []);

  const navegar = useCallback((v) => {
    window.location.hash = v === "mapa" ? "/" : `/${v}`;
  }, []);

  const vincular = useCallback((id, url) => {
    setEnlaces((prev) => {
      const nuevo = { ...prev };
      if (url) nuevo[id] = url;
      else delete nuevo[id];
      try {
        localStorage.setItem(CLAVE_ENLACES, JSON.stringify(nuevo));
      } catch {
        /* sin almacenamiento disponible: se mantiene solo en memoria */
      }
      return nuevo;
    });
  }, []);

  return (
    <>
      <Header vista={vista} onNavegar={navegar} />
      <main>
        {vista === "mapa" && <MapaPage />}
        {vista === "dashboard" && <DashboardPage />}
        {vista === "listado" && (
          <ListadoPage enlaces={enlaces} onVincular={vincular} />
        )}
      </main>
    </>
  );
}
