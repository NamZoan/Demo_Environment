import { Database } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";

import { fetchBackendHealth, fetchCmsStations } from "./api.js";
import AdminLayout from "./components/layout/AdminLayout.jsx";
import Dashboard from "./features/dashboard/Dashboard.jsx";
import StationManager from "./features/stations/StationManager.jsx";
import StationParameters from "./features/stations/StationParameters.jsx";
import { addStation, createMockStations } from "./services/mockApi.js";

const routeByPage = {
  dashboard: "/dashboard",
  stations: "/stations",
  parameters: "/data",
  qcvn: "/alerts",
  approval: "/approval",
  camera: "/camera",
  backend: "/backend",
  settings: "/settings",
  rbac: "/rbac",
};

function activePageFromPath(pathname) {
  if (pathname.startsWith("/stations/")) return "stations";
  if (pathname.startsWith("/stations")) return "stations";
  if (pathname.startsWith("/data")) return "parameters";
  if (pathname.startsWith("/alerts")) return "qcvn";
  if (pathname.startsWith("/approval")) return "approval";
  if (pathname.startsWith("/camera")) return "camera";
  if (pathname.startsWith("/backend")) return "backend";
  if (pathname.startsWith("/settings")) return "settings";
  if (pathname.startsWith("/rbac")) return "rbac";
  return "dashboard";
}

function PlaceholderPage({ title, description }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-8">
      <h1 className="text-2xl font-semibold text-slate-950">{title}</h1>
      <p className="mt-2 text-sm text-slate-500">{description}</p>
    </section>
  );
}

function BackendDatabasePage({ backendHealth, dataSource, stations }) {
  const tables = [
    "users",
    "roles",
    "regions",
    "user_roles",
    "user_regions",
    "stations",
    "sensor_data",
    "latest_station_readings",
    "alert_configs",
    "audit_logs",
  ];
  const endpoints = ["GET /health", "GET /api/stations", "GET /api/stations/live", "GET /api/overview", "WS /ws/live"];

  return (
    <section className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold text-slate-950">Backend & Database</h1>
        <p className="mt-1 text-sm text-slate-500">Theo dõi kết nối API, dữ liệu seed và các bảng chính trong PostgreSQL/TimescaleDB.</p>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <article className="rounded-lg border border-slate-200 bg-white p-4">
          <p className="text-sm text-slate-500">Backend health</p>
          <strong className={backendHealth.ok ? "mt-2 block text-2xl text-emerald-700" : "mt-2 block text-2xl text-amber-700"}>
            {backendHealth.ok ? "Online" : "Chưa kết nối"}
          </strong>
        </article>
        <article className="rounded-lg border border-slate-200 bg-white p-4">
          <p className="text-sm text-slate-500">Nguồn dữ liệu UI</p>
          <strong className="mt-2 block text-2xl text-cyan-800">{dataSource === "backend" ? "Database" : "Mock"}</strong>
        </article>
        <article className="rounded-lg border border-slate-200 bg-white p-4">
          <p className="text-sm text-slate-500">Số trạm hiển thị</p>
          <strong className="mt-2 block text-2xl text-slate-900">{stations.length}</strong>
        </article>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <h2 className="text-lg font-semibold">API endpoints</h2>
          <div className="mt-3 space-y-2">
            {endpoints.map((endpoint) => (
              <code className="block rounded-md bg-slate-950 px-3 py-2 text-sm text-cyan-100" key={endpoint}>
                {endpoint}
              </code>
            ))}
          </div>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <h2 className="text-lg font-semibold">Database tables</h2>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {tables.map((table) => (
              <div className="rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-700" key={table}>
                {table}
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="text-lg font-semibold">Seed data</h2>
        <p className="mt-2 text-sm text-slate-500">
          File <code>db/init/002_seed_data.sql</code> tạo 2000 trạm ENV, 24 điểm dữ liệu sensor cho mỗi trạm và bảng latest snapshot.
        </p>
      </section>
    </section>
  );
}

function StationDetailRoute({ stations }) {
  const navigate = useNavigate();
  const { stationId } = useParams();
  const station = stations.find((item) => String(item.id) === String(stationId) || item.code === stationId);

  if (!station) {
    return <PlaceholderPage description="Không tìm thấy trạm hoặc dữ liệu trạm chưa tải xong từ backend." title="Không tìm thấy trạm" />;
  }

  return <StationParameters onBack={() => navigate("/stations")} station={station} />;
}

function AppShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const activePage = activePageFromPath(location.pathname);
  const [globalSearch, setGlobalSearch] = useState("");
  const [stations, setStations] = useState(() => createMockStations());
  const [dataSource, setDataSource] = useState("mock");
  const [backendHealth, setBackendHealth] = useState({ ok: false, payload: {} });

  useEffect(() => {
    let cancelled = false;
    fetchBackendHealth().then((health) => {
      if (!cancelled) setBackendHealth(health);
    });
    fetchCmsStations({ id: 1 }).then((result) => {
      if (!cancelled && result.source === "backend" && result.stations.length > 0) {
        setStations(result.stations);
        setDataSource("backend");
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const visibleStations = useMemo(() => {
    const normalized = globalSearch.trim().toLowerCase();
    if (!normalized) return stations;
    return stations.filter(
      (station) =>
        station.name.toLowerCase().includes(normalized) ||
        station.code.toLowerCase().includes(normalized) ||
        station.region.toLowerCase().includes(normalized),
    );
  }, [globalSearch, stations]);

  const alertCount = stations.filter((station) => station.status === "offline" || station.metrics.pm25 >= 80).length;

  function openDetails(station) {
    navigate(`/stations/${station.id}`);
  }

  function createStation(payload) {
    setStations((current) => addStation(current, payload));
  }

  function deleteStation(stationId) {
    setStations((current) => current.filter((station) => station.id !== stationId));
    if (location.pathname === `/stations/${stationId}`) {
      navigate("/stations");
    }
  }

  function navigatePage(pageId) {
    navigate(routeByPage[pageId] || "/dashboard");
  }

  return (
    <AdminLayout
      activePage={activePage}
      alertCount={alertCount}
      globalSearch={globalSearch}
      onGlobalSearch={setGlobalSearch}
      onNavigate={navigatePage}
    >
      <Routes>
        <Route element={<Navigate replace to="/dashboard" />} path="/" />
        <Route element={<Dashboard dataSource={dataSource} onOpenStations={() => navigate("/stations")} stations={stations} />} path="/dashboard" />
        <Route
          element={
            <StationManager
              onCreateStation={createStation}
              onDeleteStation={deleteStation}
              onOpenDetails={openDetails}
              stations={visibleStations}
            />
          }
          path="/stations"
        />
        <Route element={<StationDetailRoute stations={stations} />} path="/stations/:stationId" />
        <Route element={<PlaceholderPage description="Tra cứu, biểu đồ và xuất dữ liệu quan trắc theo trạm, thông số và thời gian." title="Dữ liệu quan trắc" />} path="/data" />
        <Route element={<PlaceholderPage description="Cấu hình ngưỡng, quy chuẩn, cấp cảnh báo và luồng xác nhận sự cố vượt QCVN." title="Cảnh báo QCVN" />} path="/alerts" />
        <Route element={<PlaceholderPage description="Hàng đợi kiểm duyệt dữ liệu tự động, loại bỏ bất thường và duyệt dữ liệu vào kho chính thức." title="Kiểm duyệt dữ liệu" />} path="/approval" />
        <Route element={<PlaceholderPage description="Theo dõi camera trạm, lịch lấy mẫu tự động và trạng thái lệnh điều khiển thiết bị." title="Camera & Lấy mẫu" />} path="/camera" />
        <Route element={<BackendDatabasePage backendHealth={backendHealth} dataSource={dataSource} stations={stations} />} path="/backend" />
        <Route element={<PlaceholderPage description="Quản lý datalogger, FTP/MQTT, QCVN, thông số và kết nối liên thông." title="Cấu hình hệ thống" />} path="/settings" />
        <Route element={<PlaceholderPage description="Quản lý người dùng, vai trò, đơn vị và phạm vi dữ liệu theo khu vực." title="Phân quyền" />} path="/rbac" />
        <Route element={<Navigate replace to="/dashboard" />} path="*" />
      </Routes>
    </AdminLayout>
  );
}

export default function App() {
  return <AppShell />;
}
