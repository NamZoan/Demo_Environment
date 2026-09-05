import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { MapContainer, Marker, TileLayer, useMapEvents } from "react-leaflet";

const selectedIcon = L.divIcon({
  className: "coordinate-marker",
  html: '<span style="display:block;height:18px;width:18px;border-radius:999px;background:#0891b2;border:3px solid #fff;box-shadow:0 2px 10px rgba(15,23,42,.35)"></span>',
  iconAnchor: [9, 9],
  iconSize: [18, 18],
});

function ClickHandler({ onChange }) {
  useMapEvents({
    click(event) {
      onChange({
        latitude: Number(event.latlng.lat.toFixed(5)),
        longitude: Number(event.latlng.lng.toFixed(5)),
      });
    },
  });
  return null;
}

export default function CoordinatePicker({ latitude, longitude, onChange }) {
  const center = [latitude || 16.0471, longitude || 108.2068];

  return (
    <div className="h-64 overflow-hidden rounded-md border border-slate-300">
      <MapContainer center={center} scrollWheelZoom zoom={6}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <ClickHandler onChange={onChange} />
        {latitude && longitude && <Marker icon={selectedIcon} position={[latitude, longitude]} />}
      </MapContainer>
    </div>
  );
}
