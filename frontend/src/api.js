import { demoLiveStations, demoSensorData, demoStations } from "./demoData.js";

const browserWindow = typeof window !== "undefined" ? window : null;
const localApi = browserWindow?.location?.port === "5173" ? "http://localhost:8000" : "";
const API_BASE_URL = import.meta.env?.VITE_API_BASE_URL || localApi;
const WS_BASE_URL =
  import.meta.env?.VITE_WS_BASE_URL ||
  (API_BASE_URL
    ? API_BASE_URL.replace(/^http/, "ws")
    : `${browserWindow?.location?.protocol === "https:" ? "wss" : "ws"}://${browserWindow?.location?.host || "localhost"}`);

function userHeaders(currentUser) {
  return currentUser?.id ? { "X-User-Id": String(currentUser.id) } : {};
}

export function normalizeQueryEnvelope(payload) {
  if (Array.isArray(payload)) return { meta: null, points: payload };
  return {
    meta: payload?.meta || null,
    points: Array.isArray(payload?.points) ? payload.points : [],
  };
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

export async function fetchStationData({ stationId, startTime, endTime, resolution, maxPoints = 1000, currentUser }) {
  const params = new URLSearchParams({
    start_time: new Date(startTime).toISOString(),
    end_time: new Date(endTime).toISOString(),
    resolution,
    max_points: String(maxPoints),
  });
  try {
    const response = await fetch(`${API_BASE_URL}/api/stations/${stationId}/data?${params}`, {
      headers: userHeaders(currentUser),
    });
    if (!response.ok) {
      throw new Error("Cannot load sensor data");
    }
    return normalizeQueryEnvelope(await response.json());
  } catch {
    return normalizeQueryEnvelope(demoSensorData(stationId));
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

export async function fetchAnalyticsSeries({ stationIds, metric, startTime, endTime, resolution, maxPoints = 1000, currentUser }) {
  const params = new URLSearchParams({
    station_ids: stationIds.join(","),
    metric,
    start_time: new Date(startTime).toISOString(),
    end_time: new Date(endTime).toISOString(),
    resolution,
    max_points: String(maxPoints),
  });
  const response = await fetch(`${API_BASE_URL}/api/analytics/series?${params}`, {
    headers: userHeaders(currentUser),
  });
  if (!response.ok) throw new Error("Cannot load analytics series");
  return normalizeQueryEnvelope(await response.json());
}

export async function fetchAnalyticsHeatmap({ stationId, metric, startTime, endTime, currentUser }) {
  const params = new URLSearchParams({
    station_id: String(stationId),
    metric,
    start_time: new Date(startTime).toISOString(),
    end_time: new Date(endTime).toISOString(),
  });
  const response = await fetch(`${API_BASE_URL}/api/analytics/heatmap?${params}`, {
    headers: userHeaders(currentUser),
  });
  if (!response.ok) throw new Error("Cannot load analytics heatmap");
  return response.json();
}

export async function fetchAnalyticsScatter({ stationId, xMetric, yMetric, startTime, endTime, resolution, maxPoints = 1000, currentUser }) {
  const params = new URLSearchParams({
    station_id: String(stationId),
    x_metric: xMetric,
    y_metric: yMetric,
    start_time: new Date(startTime).toISOString(),
    end_time: new Date(endTime).toISOString(),
    resolution,
    max_points: String(maxPoints),
  });
  const response = await fetch(`${API_BASE_URL}/api/analytics/scatter?${params}`, {
    headers: userHeaders(currentUser),
  });
  if (!response.ok) throw new Error("Cannot load analytics scatter");
  return normalizeQueryEnvelope(await response.json());
}

export function normalizeStation(row) {
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
    qcvnThresholds: row.qcvn_thresholds || {},
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

export async function createStation(payload, currentUser) {
  const response = await fetch(`${API_BASE_URL}/api/stations`, {
    method: "POST",
    headers: { ...userHeaders(currentUser), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || "Không thể tạo trạm");
  }
  return response.json();
}

export async function testFtpConnection(payload, currentUser) {
  const response = await fetch(`${API_BASE_URL}/api/ftp/test`, {
    method: "POST",
    headers: { ...userHeaders(currentUser), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("Không thể kiểm tra kết nối FTP");
  return response.json();
}

export async function fetchFtpConfigs(currentUser) {
  const response = await fetch(`${API_BASE_URL}/api/ftp/configs`, { headers: userHeaders(currentUser) });
  if (!response.ok) throw new Error("Không thể tải cấu hình FTP");
  return response.json();
}

export async function createFtpConfig(payload, currentUser) {
  const response = await fetch(`${API_BASE_URL}/api/ftp/configs`, {
    method: "POST",
    headers: { ...userHeaders(currentUser), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || "Không thể thêm cấu hình FTP");
  return response.json();
}

export async function updateFtpConfig(ftpId, payload, currentUser) {
  const response = await fetch(`${API_BASE_URL}/api/ftp/configs/${ftpId}`, {
    method: "PUT",
    headers: { ...userHeaders(currentUser), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || "Không thể cập nhật cấu hình FTP");
  return response.json();
}

export async function deleteFtpConfig(ftpId, currentUser) {
  const response = await fetch(`${API_BASE_URL}/api/ftp/configs/${ftpId}`, {
    method: "DELETE",
    headers: userHeaders(currentUser),
  });
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || "Không thể xóa cấu hình FTP");
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

export async function fetchFtpStatus({ currentUser, stationId } = {}) {
  try {
    const params = stationId ? `?station_id=${encodeURIComponent(stationId)}` : "";
    const response = await fetch(`${API_BASE_URL}/api/ftp/status${params}`, {
      headers: userHeaders(currentUser),
    });
    if (!response.ok) {
      throw new Error("Cannot load FTP status");
    }
    return response.json();
  } catch (error) {
    return {
      connected: false,
      host: "127.0.0.1",
      port: 21,
      user: "station",
      root_path: "/data",
      error: error.message,
    };
  }
}

export async function fetchFtpFiles({ path, stationId, currentUser }) {
  try {
    const params = new URLSearchParams({ ...(path ? { path } : {}), ...(stationId ? { station_id: String(stationId) } : {}) });
    const response = await fetch(`${API_BASE_URL}/api/ftp/files?${params}`, {
      headers: userHeaders(currentUser),
    });
    if (!response.ok) {
      throw new Error("Cannot browse FTP directory");
    }
    return response.json();
  } catch (error) {
    return {
      path,
      entries: [],
      error: error.message,
    };
  }
}

export async function fetchFtpIndex({ stationId, currentUser }) {
  const params = new URLSearchParams({ station_id: String(stationId) });
  try {
    const response = await fetch(`${API_BASE_URL}/api/ftp/index?${params}`, {
      headers: userHeaders(currentUser),
    });
    if (!response.ok) throw new Error("Cannot load FTP file index");
    return response.json();
  } catch (error) {
    return { path: "/data", entries: [], error: error.message };
  }
}

export async function fetchFtpFile({ path, stationId, currentUser }) {
  try {
    const params = new URLSearchParams({ path, ...(stationId ? { station_id: String(stationId) } : {}) });
    const response = await fetch(`${API_BASE_URL}/api/ftp/file?${params}`, {
      headers: userHeaders(currentUser),
    });
    if (!response.ok) {
      throw new Error("Cannot read FTP file");
    }
    return response.json();
  } catch (error) {
    return {
      path,
      name: path.split("/").pop(),
      content: "",
      size: 0,
      error: error.message,
    };
  }
}

async function rbacRequest(path, options = {}, currentUser) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: { ...userHeaders(currentUser), ...(options.body ? { "Content-Type": "application/json" } : {}), ...(options.headers || {}) },
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || "Không thể thực hiện thao tác phân quyền");
  }
  return response.status === 204 ? null : response.json();
}

export function fetchRbacOptions(currentUser) {
  return rbacRequest("/api/rbac/options", {}, currentUser);
}

export function fetchRbacUsers(currentUser) {
  return rbacRequest("/api/rbac/users", {}, currentUser);
}

export function createRbacUser(payload, currentUser) {
  return rbacRequest("/api/rbac/users", { method: "POST", body: JSON.stringify(payload) }, currentUser);
}

export function updateRbacUser(userId, payload, currentUser) {
  return rbacRequest(`/api/rbac/users/${userId}`, { method: "PUT", body: JSON.stringify(payload) }, currentUser);
}

export function disableRbacUser(userId, currentUser) {
  return rbacRequest(`/api/rbac/users/${userId}`, { method: "DELETE" }, currentUser);
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
