import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";

const statusColors = {
  online: "#21835b",
  warning: "#b7791f",
  critical: "#c2410c",
  offline: "#6b7280",
};

function markerIcon(status) {
  const color = statusColors[status] || statusColors.offline;
  return L.divIcon({
    className: "stationMarker",
    html: `<span style="background:${color}"></span>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
    popupAnchor: [0, -8],
  });
}

export default function StationMap({ stations, selectedStationId, onSelectStation }) {
  const validStations = stations.filter((station) => station.latitude && station.longitude);
  const center = validStations[0] ? [validStations[0].latitude, validStations[0].longitude] : [16.0471, 108.2068];

  return (
    <section className="mapPanel">
      <MapContainer center={center} zoom={6} scrollWheelZoom className="stationMap">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {validStations.map((station) => (
          <Marker
            eventHandlers={{ click: () => onSelectStation(String(station.id)) }}
            icon={markerIcon(station.live_status)}
            key={station.id}
            position={[station.latitude, station.longitude]}
            zIndexOffset={String(station.id) === selectedStationId ? 1000 : 0}
          >
            <Popup>
              <strong>{station.code}</strong>
              <br />
              {station.name}
              <br />
              PM2.5: {station.pm25 ?? "-"} ug/m3
              <br />
              Status: {station.live_status}
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </section>
  );
}
