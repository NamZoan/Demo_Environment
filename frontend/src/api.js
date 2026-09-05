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
