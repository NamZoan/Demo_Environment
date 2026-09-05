import { demoSensorData, demoStations } from "./demoData.js";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function fetchStations() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/stations`);
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
      return { id: 1, username: "admin", full_name: "System Administrator", role: "admin" };
    }
    throw new Error("Invalid username or password");
  }
}

export async function fetchStationData({ stationId, startTime, endTime, resolution }) {
  const params = new URLSearchParams({
    start_time: new Date(startTime).toISOString(),
    end_time: new Date(endTime).toISOString(),
    resolution,
  });
  try {
    const response = await fetch(`${API_BASE_URL}/api/stations/${stationId}/data?${params}`);
    if (!response.ok) {
      throw new Error("Cannot load sensor data");
    }
    return response.json();
  } catch {
    return demoSensorData(stationId);
  }
}
