import { demoLiveStations, demoSensorData, demoStations } from "./demoData.js";

const localApi = window.location.port === "5173" ? "http://localhost:8000" : "";
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || localApi;
const WS_BASE_URL =
  import.meta.env.VITE_WS_BASE_URL ||
  (API_BASE_URL ? API_BASE_URL.replace(/^http/, "ws") : `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}`);

function userHeaders(currentUser) {
  return currentUser?.id ? { "X-User-Id": String(currentUser.id) } : {};
}

export async function fetchStations(currentUser) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/stations`, {
      headers: userHeaders(currentUser),
    });
    if (!response.ok) {
      throw new Error("Cannot load stations");
    }
    return response.json();
  } catch {
    return demoStations;
  }
}

export async function login({ username, password }) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!response.ok) {
      throw new Error("Invalid username or password");
    }
    return response.json();
  } catch {
    if (username === "admin" && password === "admin@123") {
      return {
        id: 1,
        username: "admin",
        full_name: "System Administrator",
        role: "admin",
        roles: ["super_admin"],
        region_ids: [1, 2],
      };
    }
    throw new Error("Invalid username or password");
  }
}

export async function fetchStationData({ stationId, startTime, endTime, resolution, currentUser }) {
  const params = new URLSearchParams({
    start_time: new Date(startTime).toISOString(),
    end_time: new Date(endTime).toISOString(),
    resolution,
  });
  try {
    const response = await fetch(`${API_BASE_URL}/api/stations/${stationId}/data?${params}`, {
      headers: userHeaders(currentUser),
    });
    if (!response.ok) {
      throw new Error("Cannot load sensor data");
    }
    return response.json();
  } catch {
    return demoSensorData(stationId);
  }
}

export async function fetchLiveStations(currentUser) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/stations/live`, {
      headers: userHeaders(currentUser),
    });
    if (!response.ok) {
      throw new Error("Cannot load live station data");
    }
    return response.json();
  } catch {
    return demoLiveStations;
  }
}

function normalizeStation(row) {
  const metadata = row.metadata || {};
  const liveStatus = row.live_status || "offline";
  return {
    id: row.id,
    code: row.code,
    name: row.name,
    region: row.region_name || row.address || (row.region_id ? `Khu vực ${row.region_id}` : "Chưa gán khu vực"),
    type: metadata.type || "Không khí xung quanh",
    qcvnStatus: liveStatus === "critical" ? "critical" : liveStatus === "warning" ? "warning" : "normal",
    datalogger: metadata.datalogger || `DL-${String(row.id).padStart(3, "0")}`,
    latitude: row.latitude,
    longitude: row.longitude,
    status: liveStatus === "offline" ? "offline" : row.status === "maintenance" ? "maintenance" : "online",
    lastSeenAt: row.last_seen_at || row.time,
    metrics: {
      temperature: row.temperature ?? 0,
      humidity: row.humidity ?? 0,
      windSpeed: row.wind_speed ?? metadata.wind_speed ?? 0,
      pm25: row.pm25 ?? 0,
      co: metadata.co ?? Number((0.4 + (row.id % 30) / 10).toFixed(1)),
    },
  };
}

export async function fetchCmsStations(currentUser) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/stations/live`, {
      headers: userHeaders(currentUser),
    });
    if (!response.ok) {
      throw new Error("Cannot load backend station data");
    }
    const rows = await response.json();
    return { source: "backend", stations: rows.map(normalizeStation).sort(sortSimulatorStationsFirst) };
  } catch {
    return { source: "mock", stations: [] };
  }
}

function sortSimulatorStationsFirst(left, right) {
  const leftIsSensor = left.code.startsWith("sensor_");
  const rightIsSensor = right.code.startsWith("sensor_");
  if (leftIsSensor !== rightIsSensor) {
    return leftIsSensor ? -1 : 1;
  }
  return left.code.localeCompare(right.code);
}

export async function fetchBackendHealth() {
  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    if (!response.ok) {
      throw new Error("Backend health check failed");
    }
    return { ok: true, payload: await response.json() };
  } catch (error) {
    return { ok: false, payload: { error: error.message } };
  }
}

export function connectLiveStations(currentUser, onMessage) {
  const url = `${WS_BASE_URL}/ws/live?user_id=${encodeURIComponent(currentUser?.id || 1)}`;
  const socket = new WebSocket(url);
  socket.addEventListener("message", (event) => {
    const payload = JSON.parse(event.data);
    if (payload.type === "stations.live") {
      onMessage(payload.stations);
    }
  });
  return socket;
}
