import { Activity, AlertTriangle, Camera, CheckCircle2, Database, FileCheck2, MapPinned, ServerCog, Siren } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { fetchBackendHealth, fetchCmsStations } from "./api.js";
import AdminLayout from "./components/layout/AdminLayout.jsx";
import StationManager from "./features/stations/StationManager.jsx";
import StationParameters from "./features/stations/StationParameters.jsx";
import { addStation, createMockStations } from "./services/mockApi.js";

function Dashboard({ dataSource, stations, onOpenStations }) {
  const counts = useMemo(
    () =>
      stations.reduce(
        (summary, station) => {
          summary[station.status] += 1;
          return summary;
        },
        { total: stations.length, online: 0, offline: 0, maintenance: 0 },
      ),
    [stations],
  );
  const qcvnWarnings = stations.filter((station) => station.qcvnStatus === "warning").length;
  const qcvnCritical = stations.filter((station) => station.qcvnStatus === "critical").length;
  const typeCounts = stations.reduce((summary, station) => {
    summary[station.type] = (summary[station.type] || 0) + 1;
    return summary;
  }, {});

  const cards = [
    { label: "Tổng trạm", value: counts.total, icon: MapPinned, tone: "bg-cyan-50 text-cyan-800" },
    { label: "Đang online", value: counts.online, icon: Activity, tone: "bg-emerald-50 text-emerald-800" },
    { label: "Mất tín hiệu", value: counts.offline, icon: AlertTriangle, tone: "bg-red-50 text-red-800" },
    { label: "Bảo trì", value: counts.maintenance, icon: ServerCog, tone: "bg-amber-50 text-amber-800" },
  ];

  return (
    <section className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold text-slate-950">Điều hành dữ liệu quan trắc tự động</h1>
        <p className="mt-1 text-sm text-slate-500">
          Màn hình nghiệp vụ theo luồng Envisoft: tiếp nhận dữ liệu, giám sát WebGIS, cảnh báo QCVN và kiểm duyệt.
        </p>
        <div className="mt-3 inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-600">
          <Database className="h-3.5 w-3.5 text-cyan-700" />
          Nguồn dữ liệu: {dataSource === "backend" ? "Backend API + PostgreSQL/TimescaleDB" : "Mock fallback"}
        </div>
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => {
          const Icon = card.icon;
          return (
            <article className={`rounded-lg border border-slate-200 p-4 ${card.tone}`} key={card.label}>
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">{card.label}</span>
                <Icon className="h-5 w-5" />
              </div>
              <strong className="mt-4 block text-3xl">{card.value}</strong>
            </article>
          );
        })}
      </div>
      <div className="grid gap-4 xl:grid-cols-[1.2fr_.8fr]">
        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold">Giám sát nghiệp vụ</h2>
            <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700">Realtime</span>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-md border border-red-200 bg-red-50 p-3 text-red-800">
              <Siren className="mb-3 h-5 w-5" />
              <p className="text-sm font-medium">Vượt QCVN nghiêm trọng</p>
              <strong className="mt-2 block text-2xl">{qcvnCritical}</strong>
            </div>
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-amber-800">
              <AlertTriangle className="mb-3 h-5 w-5" />
              <p className="text-sm font-medium">Cảnh báo cần kiểm tra</p>
              <strong className="mt-2 block text-2xl">{qcvnWarnings}</strong>
            </div>
            <div className="rounded-md border border-cyan-200 bg-cyan-50 p-3 text-cyan-800">
              <FileCheck2 className="mb-3 h-5 w-5" />
              <p className="text-sm font-medium">Lô dữ liệu chờ duyệt</p>
              <strong className="mt-2 block text-2xl">128</strong>
            </div>
          </div>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <h2 className="text-lg font-semibold">Loại hình quan trắc</h2>
          <div className="mt-4 space-y-3">
            {Object.entries(typeCounts).map(([type, value]) => (
              <div className="flex items-center justify-between text-sm" key={type}>
                <span className="text-slate-600">{type}</span>
                <strong>{value}</strong>
              </div>
            ))}
          </div>
        </section>
      </div>

      <div className="flex flex-wrap gap-2">
        <button className="rounded-md bg-cyan-700 px-4 py-2 text-sm font-semibold text-white" onClick={onOpenStations} type="button">
          Mở WebGIS & quản lý trạm
        </button>
        <button className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700" type="button">
          <Camera className="h-4 w-4" />
          Theo dõi camera
        </button>
        <button className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700" type="button">
          <CheckCircle2 className="h-4 w-4" />
          Kiểm duyệt dữ liệu
        </button>
      </div>
    </section>
  );
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

export default function App() {
  const [activePage, setActivePage] = useState("dashboard");
  const [globalSearch, setGlobalSearch] = useState("");
  const [selectedStation, setSelectedStation] = useState(null);
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
    setSelectedStation(station);
    setActivePage("parameters");
  }

  function createStation(payload) {
    setStations((current) => addStation(current, payload));
  }

  function deleteStation(stationId) {
    setStations((current) => current.filter((station) => station.id !== stationId));
    if (selectedStation?.id === stationId) {
      setSelectedStation(null);
    }
  }

  function renderPage() {
    if (activePage === "dashboard") {
      return <Dashboard dataSource={dataSource} onOpenStations={() => setActivePage("stations")} stations={stations} />;
    }
    if (activePage === "stations") {
      return (
        <StationManager
          onCreateStation={createStation}
          onDeleteStation={deleteStation}
          onOpenDetails={openDetails}
          stations={visibleStations}
        />
      );
    }
    if (activePage === "parameters") {
      return selectedStation ? (
        <StationParameters onBack={() => setActivePage("stations")} station={selectedStation} />
      ) : (
        <StationManager
          onCreateStation={createStation}
          onDeleteStation={deleteStation}
          onOpenDetails={openDetails}
          stations={visibleStations}
        />
      );
    }
    if (activePage === "qcvn") {
      return <PlaceholderPage description="Cấu hình ngưỡng, quy chuẩn, cấp cảnh báo và luồng xác nhận sự cố vượt QCVN." title="Cảnh báo QCVN" />;
    }
    if (activePage === "approval") {
      return <PlaceholderPage description="Hàng đợi kiểm duyệt dữ liệu tự động, loại bỏ bất thường và duyệt dữ liệu vào kho chính thức." title="Kiểm duyệt dữ liệu" />;
    }
    if (activePage === "camera") {
      return <PlaceholderPage description="Theo dõi camera trạm, lịch lấy mẫu tự động và trạng thái lệnh điều khiển thiết bị." title="Camera & Lấy mẫu" />;
    }
    if (activePage === "backend") {
      return <BackendDatabasePage backendHealth={backendHealth} dataSource={dataSource} stations={stations} />;
    }
    if (activePage === "settings") return <PlaceholderPage description="Quản lý datalogger, FTP/MQTT, QCVN, thông số và kết nối liên thông." title="Cấu hình hệ thống" />;
    if (activePage === "rbac") return <PlaceholderPage description="Quản lý người dùng, vai trò, đơn vị và phạm vi dữ liệu theo khu vực." title="Phân quyền" />;
    return <PlaceholderPage description="Tra cứu, biểu đồ và xuất dữ liệu quan trắc theo trạm, thông số và thời gian." title="Dữ liệu thông số" />;
  }

  return (
    <AdminLayout
      activePage={activePage}
      alertCount={alertCount}
      globalSearch={globalSearch}
      onGlobalSearch={setGlobalSearch}
      onNavigate={setActivePage}
    >
      {renderPage()}
    </AdminLayout>
  );
}
