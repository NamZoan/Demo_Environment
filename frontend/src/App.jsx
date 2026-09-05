import { useEffect, useMemo, useState } from "react";

import EnvironmentChart from "./EnvironmentChart.jsx";
import { fetchStationData, fetchStations } from "./api.js";

const initialEnd = new Date();
const initialStart = new Date(initialEnd.getTime() - 24 * 60 * 60 * 1000);

function toLocalInputValue(date) {
  const offset = date.getTimezoneOffset() * 60 * 1000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

export default function App() {
  const [stations, setStations] = useState([]);
  const [stationId, setStationId] = useState("");
  const [startTime, setStartTime] = useState(toLocalInputValue(initialStart));
  const [endTime, setEndTime] = useState(toLocalInputValue(initialEnd));
  const [resolution, setResolution] = useState("1h");
  const [data, setData] = useState([]);
  const [visibleMetrics, setVisibleMetrics] = useState({
    temperature: true,
    humidity: true,
    pm25: true,
  });
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    fetchStations()
      .then((items) => {
        setStations(items);
        setStationId(items[0]?.id ? String(items[0].id) : "");
        setStatus("idle");
      })
      .catch((error) => setStatus(error.message));
  }, []);

  useEffect(() => {
    if (!stationId) return;
    setStatus("loading");
    fetchStationData({ stationId, startTime, endTime, resolution })
      .then((items) => {
        setData(items);
        setStatus("idle");
      })
      .catch((error) => setStatus(error.message));
  }, [stationId, startTime, endTime, resolution]);

  const selectedStation = useMemo(
    () => stations.find((station) => String(station.id) === stationId),
    [stations, stationId],
  );

  return (
    <main className="appShell">
      <header className="topBar">
        <div>
          <h1>Environment Monitoring</h1>
          <p>{selectedStation ? `${selectedStation.code} - ${selectedStation.name}` : "No station"}</p>
        </div>
        <div className="status">{status}</div>
      </header>

      <section className="controls">
        <label>
          Station
          <select value={stationId} onChange={(event) => setStationId(event.target.value)}>
            {stations.map((station) => (
              <option key={station.id} value={station.id}>
                {station.code} - {station.name}
              </option>
            ))}
          </select>
        </label>

        <label>
          Start
          <input type="datetime-local" value={startTime} onChange={(event) => setStartTime(event.target.value)} />
        </label>

        <label>
          End
          <input type="datetime-local" value={endTime} onChange={(event) => setEndTime(event.target.value)} />
        </label>

        <label>
          Resolution
          <select value={resolution} onChange={(event) => setResolution(event.target.value)}>
            <option value="1m">1 minute</option>
            <option value="1h">1 hour</option>
            <option value="1d">1 day</option>
          </select>
        </label>
      </section>

      <section className="metricToggles">
        {Object.keys(visibleMetrics).map((metric) => (
          <label key={metric}>
            <input
              type="checkbox"
              checked={visibleMetrics[metric]}
              onChange={(event) =>
                setVisibleMetrics((current) => ({ ...current, [metric]: event.target.checked }))
              }
            />
            {metric}
          </label>
        ))}
      </section>

      <EnvironmentChart data={data} visibleMetrics={visibleMetrics} />
    </main>
  );
}

