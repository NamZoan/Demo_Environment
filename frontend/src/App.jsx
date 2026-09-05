import { useEffect, useMemo, useState } from "react";

import EnvironmentChart from "./EnvironmentChart.jsx";
import LiveStationTable from "./LiveStationTable.jsx";
import StationMap from "./StationMap.jsx";
import { connectLiveStations, fetchLiveStations, fetchStationData, fetchStations, login } from "./api.js";

const initialEnd = new Date();
const initialStart = new Date(initialEnd.getTime() - 24 * 60 * 60 * 1000);

function toLocalInputValue(date) {
  const offset = date.getTimezoneOffset() * 60 * 1000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

export default function App() {
  const [currentUser, setCurrentUser] = useState(() => {
    const saved = window.localStorage.getItem("currentUser");
    return saved ? JSON.parse(saved) : null;
  });
  const [loginForm, setLoginForm] = useState({ username: "admin", password: "admin@123" });
  const [stations, setStations] = useState([]);
  const [liveStations, setLiveStations] = useState([]);
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
    if (!currentUser) return;
    fetchStations(currentUser)
      .then((items) => {
        setStations(items);
        setStationId(items[0]?.id ? String(items[0].id) : "");
        setStatus("idle");
      })
      .catch((error) => setStatus(error.message));
  }, [currentUser]);

  useEffect(() => {
    if (!currentUser) return;
    let socket;
    let cancelled = false;

    fetchLiveStations(currentUser).then((items) => {
      if (!cancelled) {
        setLiveStations(items);
        if (items[0]?.id) {
          setStationId((current) => current || String(items[0].id));
        }
      }
    });

    try {
      socket = connectLiveStations(currentUser, (items) => {
        setLiveStations(items);
        setStatus("idle");
      });
      socket.addEventListener("error", () => {
        fetchLiveStations(currentUser).then((items) => {
          if (!cancelled) setLiveStations(items);
        });
      });
    } catch {
      fetchLiveStations(currentUser).then((items) => {
        if (!cancelled) setLiveStations(items);
      });
    }

    return () => {
      cancelled = true;
      if (socket) socket.close();
    };
  }, [currentUser]);

  useEffect(() => {
    if (!stationId) return;
    setStatus("loading");
    fetchStationData({ stationId, startTime, endTime, resolution, currentUser })
      .then((items) => {
        setData(items);
        setStatus("idle");
      })
      .catch((error) => setStatus(error.message));
  }, [stationId, startTime, endTime, resolution]);

  const selectedStation = useMemo(
    () =>
      liveStations.find((station) => String(station.id) === stationId) ||
      stations.find((station) => String(station.id) === stationId),
    [liveStations, stations, stationId],
  );

  const overview = useMemo(() => {
    const seed = { total: liveStations.length, online: 0, warning: 0, critical: 0, offline: 0 };
    return liveStations.reduce((counts, station) => {
      counts[station.live_status] += 1;
      return counts;
    }, seed);
  }, [liveStations]);

  async function handleLogin(event) {
    event.preventDefault();
    setStatus("loading");
    try {
      const user = await login(loginForm);
      window.localStorage.setItem("currentUser", JSON.stringify(user));
      setCurrentUser(user);
      setStatus("idle");
    } catch (error) {
      setStatus(error.message);
    }
  }

  function handleLogout() {
    window.localStorage.removeItem("currentUser");
    setCurrentUser(null);
    setStations([]);
    setLiveStations([]);
    setData([]);
  }

  if (!currentUser) {
    return (
      <main className="loginShell">
        <form className="loginPanel" onSubmit={handleLogin}>
          <h1>Station Management</h1>
          <label>
            Username
            <input
              value={loginForm.username}
              onChange={(event) => setLoginForm((current) => ({ ...current, username: event.target.value }))}
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={loginForm.password}
              onChange={(event) => setLoginForm((current) => ({ ...current, password: event.target.value }))}
            />
          </label>
          <button type="submit">Sign in</button>
          <p>{status === "loading" ? "" : status}</p>
        </form>
      </main>
    );
  }

  return (
    <main className="appShell">
      <header className="topBar">
        <div>
          <h1>Environment Monitoring</h1>
          <p>{selectedStation ? `${selectedStation.code} - ${selectedStation.name}` : "No station"}</p>
        </div>
        <div className="sessionBox">
          <span>{currentUser.username}</span>
          <button type="button" onClick={handleLogout}>
            Sign out
          </button>
        </div>
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

      <section className="overviewGrid">
        {Object.entries(overview).map(([key, value]) => (
          <div className="overviewItem" key={key}>
            <span>{key}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </section>

      <section className="operationsGrid">
        <StationMap
          stations={liveStations.length ? liveStations : stations}
          selectedStationId={stationId}
          onSelectStation={setStationId}
        />
        <LiveStationTable
          stations={liveStations.length ? liveStations : stations}
          selectedStationId={stationId}
          onSelectStation={setStationId}
        />
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
