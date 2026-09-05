const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function fetchStations() {
  const response = await fetch(`${API_BASE_URL}/api/stations`);
  if (!response.ok) {
    throw new Error("Cannot load stations");
  }
  return response.json();
}

export async function fetchStationData({ stationId, startTime, endTime, resolution }) {
  const params = new URLSearchParams({
    start_time: new Date(startTime).toISOString(),
    end_time: new Date(endTime).toISOString(),
    resolution,
  });
  const response = await fetch(`${API_BASE_URL}/api/stations/${stationId}/data?${params}`);
  if (!response.ok) {
    throw new Error("Cannot load sensor data");
  }
  return response.json();
}

