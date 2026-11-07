import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import {
  CircleMarker,
  GeoJSON,
  MapContainer,
  ScaleControl,
  TileLayer,
  Tooltip,
  useMap,
  useMapEvents,
} from "react-leaflet";
import Icon from "./Icon.jsx";
import { colorAvance } from "../utils/stats.js";

// Área urbana de Bogotá
const LIMITES = [
  [4.53, -74.2],
  [4.765, -74.03],
];

// Color del contorno de la localidad: verde azulado, contrasta con los puntos cálidos
const ESTILO_CONTORNO = {
  color: "#0f766e",
  weight: 3,
  fillColor: "#14b8a6",
  fillOpacity: 0.08,
};

// Mapa base: Mapbox (token en MAPBOX_API_KEY del .env). Sin token, OpenStreetMap.
const TOKEN = import.meta.env.MAPBOX_API_KEY;
const ATRIB_MAPBOX =
  '&copy; <a href="https://www.mapbox.com/about/maps/">Mapbox</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> <a href="https://www.mapbox.com/map-feedback/">Mejora este mapa</a>';
const mapbox = (estilo) => ({
  url: `https://api.mapbox.com/styles/v1/mapbox/${estilo}/tiles/512/{z}/{x}/{y}@2x?access_token=${TOKEN}`,
  attribution: ATRIB_MAPBOX,
  tileSize: 512,
  zoomOffset: -1,
});
const BASES = TOKEN
  ? { calles: mapbox("streets-v12"), claro: mapbox("light-v11") }
  : {
      calles: {
        url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      },
      claro: {
        url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>',
      },
    };

/** Recalcula el tamaño del mapa cuando cambia su contenedor (layout, pantalla completa). */
function AjustarTamano() {
  const map = useMap();
  useEffect(() => {
    let primera = true;
    const ro = new ResizeObserver(() => {
      map.invalidateSize();
      if (primera) {
        map.fitBounds(LIMITES);
        primera = false;
      }
    });
    ro.observe(map.getContainer());
    return () => ro.disconnect();
  }, [map]);
  return null;
}

/** Acerca el mapa a la localidad elegida, o vuelve a toda la ciudad al quitarla. */
function EncuadrarContorno({ contorno }) {
  const map = useMap();
  const primera = useRef(true);
  useEffect(() => {
    if (primera.current) {
      primera.current = false;
      if (!contorno) return;
    }
    if (contorno) map.flyToBounds(L.geoJSON(contorno).getBounds(), { padding: [30, 30], duration: 0.6 });
    else map.flyToBounds(LIMITES, { duration: 0.6 });
  }, [contorno, map]);
  return null;
}

/** Clic en una zona vacía del mapa: quita la selección. */
function ClicEnMapa({ onClic }) {
  useMapEvents({ click: onClic });
  return null;
}

function Controles({ base, onBase, contorno }) {
  const map = useMap();
  const encuadrar = () =>
    contorno
      ? map.flyToBounds(L.geoJSON(contorno).getBounds(), { padding: [30, 30], duration: 0.6 })
      : map.flyToBounds(LIMITES, { duration: 0.6 });
  return (
    <div className="map-controls">
      <button type="button" title="Acercar" onClick={() => map.zoomIn()}>
        <Icon name="plus" size={18} />
      </button>
      <button type="button" title="Alejar" onClick={() => map.zoomOut()}>
        <Icon name="minus" size={18} />
      </button>
      <button type="button" title={contorno ? "Ver la localidad" : "Ver toda la ciudad"} onClick={encuadrar}>
        <Icon name="locate" size={18} />
      </button>
      <button
        type="button"
        title={base === "calles" ? "Mapa base claro" : "Mapa base de calles"}
        onClick={() => onBase(base === "calles" ? "claro" : "calles")}
      >
        <Icon name="layers" size={18} />
      </button>
    </div>
  );
}

const pctTexto = (v) => (v === null || v === undefined ? "sin dato" : `${Math.round(v)} %`);

export default function MapaObras({ obras, seleccionadaId, onSeleccionar, contorno, etiquetaZona }) {
  const [base, setBase] = useState("calles");
  const seleccionada = obras.find((o) => o.id === seleccionadaId);

  const clicObra = (id) => (e) => {
    L.DomEvent.stopPropagation(e);
    onSeleccionar(id);
  };

  return (
    <div className={`map-frame ${TOKEN ? "" : "base-osm"}`}>
      <MapContainer bounds={LIMITES} zoomControl={false} zoomSnap={0.25} scrollWheelZoom className="leaflet-root">
        <TileLayer key={base} {...BASES[base]} />
        <ScaleControl position="bottomleft" imperial={false} />
        <AjustarTamano />
        <EncuadrarContorno contorno={contorno} />
        <ClicEnMapa onClic={() => onSeleccionar(null)} />
        <Controles base={base} onBase={setBase} contorno={contorno} />

        {contorno && (
          <GeoJSON key={contorno.properties?.localidad_codigo} data={contorno} style={ESTILO_CONTORNO} interactive={false} />
        )}

        {obras.map((o) =>
          o.id === seleccionadaId ? null : (
            <CircleMarker
              key={o.id}
              center={[o.lat, o.lon]}
              radius={8}
              pathOptions={{ color: "#fff", weight: 2, fillColor: colorAvance(o.avance), fillOpacity: 0.95 }}
              eventHandlers={{ click: clicObra(o.id) }}
            >
              <Tooltip direction="top" offset={[0, -8]}>
                {o.corto} · {pctTexto(o.avance)}
              </Tooltip>
            </CircleMarker>
          )
        )}

        {seleccionada && (
          <>
            <CircleMarker
              center={[seleccionada.lat, seleccionada.lon]}
              radius={20}
              interactive={false}
              pathOptions={{ stroke: false, fillColor: colorAvance(seleccionada.avance), fillOpacity: 0.28 }}
            />
            <CircleMarker
              key={`sel-${seleccionada.id}`}
              center={[seleccionada.lat, seleccionada.lon]}
              radius={11}
              pathOptions={{ color: "#fff", weight: 3, fillColor: colorAvance(seleccionada.avance), fillOpacity: 1 }}
              eventHandlers={{ click: (e) => L.DomEvent.stopPropagation(e) }}
            >
              <Tooltip permanent direction="right" offset={[16, 0]} className="map-label">
                {seleccionada.corto} · {pctTexto(seleccionada.avance)}
              </Tooltip>
            </CircleMarker>
          </>
        )}
      </MapContainer>

      <div className="map-chip">
        <Icon name="pin" size={16} />
        {etiquetaZona}
      </div>
    </div>
  );
}
