import {
  Activity,
  AlertTriangle,
  Database,
  FileText,
  Gauge,
  MapPinned,
  RadioTower,
  Server,
  ShieldAlert,
  Thermometer,
  Wind,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { fetchFtpFiles, fetchFtpStatus } from "../../api.js";

const statusLabels = {
  all: "Tất cả trạng thái",
  online: "Đang online",
  offline: "Mất kết nối",
  maintenance: "Bảo trì",
};

const alertLabels = {
  all: "Tất cả mức cảnh báo",
  normal: "Bình thường",
  warning: "Cảnh báo",
  critical: "Nghiêm trọng",
};

const pieColors = {
  online: "#059669",
  offline: "#64748b",
  maintenance: "#d97706",
  warning: "#f59e0b",
  critical: "#dc2626",
};

function uniqueOptions(stations, key, fallbackLabel) {
  return [...new Set(stations.map((station) => station[key]).filter(Boolean))].map((value) => ({
    value,
    label: value || fallbackLabel,
  }));
}

function average(stations, selector) {
  if (stations.length === 0) return 0;
  const total = stations.reduce((sum, station) => sum + Number(selector(station) || 0), 0);
  return Number((total / stations.length).toFixed(1));
}

function maxMetric(stations, selector) {
  if (stations.length === 0) return 0;
  return Math.max(...stations.map((station) => Number(selector(station) || 0)));
}

function countBy(stations, selector) {
  return stations.reduce((summary, station) => {
    const key = selector(station);
    summary[key] = (summary[key] || 0) + 1;
    return summary;
  }, {});
}

function formatDateTime(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString("vi-VN");
}

function latestStations(stations) {
  return [...stations]
    .sort((left, right) => new Date(right.lastSeenAt || 0).getTime() - new Date(left.lastSeenAt || 0).getTime())
    .slice(0, 8);
}

function KpiCard({ icon: Icon, label, tone, value, helper }) {
  return (
    <article className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-slate-500">{label}</p>
          <strong className="mt-3 block text-3xl text-slate-950">{value}</strong>
        </div>
        <span className={`grid h-10 w-10 place-items-center rounded-md ${tone}`}>
          <Icon className="h-5 w-5" />
        </span>
      </div>
      <p className="mt-3 text-xs text-slate-500">{helper}</p>
    </article>
  );
}

export default function Dashboard({ dataSource, stations, onOpenStations }) {
  const [statusFilter, setStatusFilter] = useState("all");
  const [alertFilter, setAlertFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [ftpStatus, setFtpStatus] = useState(null);
  const [ftpFolders, setFtpFolders] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetchFtpStatus({ currentUser: { id: 1 } }).then((status) => {
      if (!cancelled) setFtpStatus(status);
    });
    fetchFtpFiles({ path: "/data", currentUser: { id: 1 } }).then((listing) => {
      if (!cancelled) setFtpFolders(listing.entries?.filter((entry) => entry.type === "folder").length || 0);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const filteredStations = useMemo(
    () =>
      stations.filter((station) => {
        const matchesStatus = statusFilter === "all" || station.status === statusFilter;
        const matchesAlert = alertFilter === "all" || station.qcvnStatus === alertFilter;
        const matchesType = typeFilter === "all" || station.type === typeFilter;
        return matchesStatus && matchesAlert && matchesType;
      }),
    [alertFilter, stations, statusFilter, typeFilter],
  );

  const counts = useMemo(
    () => ({
      total: filteredStations.length,
      online: filteredStations.filter((station) => station.status === "online").length,
      offline: filteredStations.filter((station) => station.status === "offline").length,
      maintenance: filteredStations.filter((station) => station.status === "maintenance").length,
      warning: filteredStations.filter((station) => station.qcvnStatus === "warning").length,
      critical: filteredStations.filter((station) => station.qcvnStatus === "critical").length,
    }),
    [filteredStations],
  );

  const metricSummary = useMemo(
    () => ({
      pm25Average: average(filteredStations, (station) => station.metrics.pm25),
      pm25Max: maxMetric(filteredStations, (station) => station.metrics.pm25),
      temperatureAverage: average(filteredStations, (station) => station.metrics.temperature),
      humidityAverage: average(filteredStations, (station) => station.metrics.humidity),
      windAverage: average(filteredStations, (station) => station.metrics.windSpeed),
    }),
    [filteredStations],
  );

  const statusData = Object.entries(countBy(filteredStations, (station) => station.status)).map(([name, value]) => ({
    name: statusLabels[name] || name,
    key: name,
    value,
  }));
  const typeData = Object.entries(countBy(filteredStations, (station) => station.type)).map(([name, value]) => ({ name, value }));
  const topPm25 = [...filteredStations]
    .sort((left, right) => right.metrics.pm25 - left.metrics.pm25)
    .slice(0, 8)
    .map((station) => ({ code: station.code, name: station.name, pm25: station.metrics.pm25 }));
  const recentStations = latestStations(filteredStations);
  const typeOptions = uniqueOptions(stations, "type", "Chưa phân loại");

  const kpis = [
    { label: "Tổng trạm theo bộ lọc", value: counts.total, icon: MapPinned, tone: "bg-cyan-50 text-cyan-700", helper: "Số trạm đang được đưa vào phân tích" },
    { label: "Trạm đang online", value: counts.online, icon: RadioTower, tone: "bg-emerald-50 text-emerald-700", helper: "Có dữ liệu mới trong ngưỡng theo dõi" },
    { label: "Cảnh báo môi trường", value: counts.warning + counts.critical, icon: ShieldAlert, tone: "bg-amber-50 text-amber-700", helper: "Bao gồm cảnh báo và nghiêm trọng" },
    { label: "PM2.5 cao nhất", value: metricSummary.pm25Max, icon: Gauge, tone: "bg-red-50 text-red-700", helper: "Giá trị lớn nhất trong tập trạm hiện tại" },
  ];

  return (
    <section className="space-y-5">
      <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
              <Activity className="h-3.5 w-3.5" />
              Trung tâm phân tích dữ liệu quan trắc
            </div>
            <h1 className="mt-3 text-2xl font-semibold text-slate-950">Dashboard tổng hợp môi trường</h1>
            <p className="mt-1 max-w-3xl text-sm text-slate-500">
              Theo dõi trạng thái trạm, chất lượng không khí, luồng FTP và dữ liệu thời gian thực từ hệ thống quan trắc tự động.
            </p>
          </div>
          <button className="w-fit rounded-md bg-cyan-700 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-800" onClick={onOpenStations} type="button">
            Mở danh sách trạm
          </button>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <label className="grid gap-1 text-sm font-medium text-slate-600">
            Trạng thái trạm
            <select className="h-10 rounded-md border border-slate-300 bg-white px-3" onChange={(event) => setStatusFilter(event.target.value)} value={statusFilter}>
              {Object.entries(statusLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="grid gap-1 text-sm font-medium text-slate-600">
            Mức cảnh báo
            <select className="h-10 rounded-md border border-slate-300 bg-white px-3" onChange={(event) => setAlertFilter(event.target.value)} value={alertFilter}>
              {Object.entries(alertLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="grid gap-1 text-sm font-medium text-slate-600">
            Loại hình quan trắc
            <select className="h-10 rounded-md border border-slate-300 bg-white px-3" onChange={(event) => setTypeFilter(event.target.value)} value={typeFilter}>
              <option value="all">Tất cả loại hình</option>
              {typeOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {kpis.map((kpi) => (
          <KpiCard key={kpi.label} {...kpi} />
        ))}
      </div>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-950">Phân bổ trạng thái</h2>
          <div className="mt-4 h-[260px]">
            <ResponsiveContainer height="100%" width="100%">
              <PieChart>
                <Pie data={statusData} dataKey="value" innerRadius={58} nameKey="name" outerRadius={90}>
                  {statusData.map((item) => (
                    <Cell fill={pieColors[item.key] || "#0891b2"} key={item.key} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="grid gap-2 text-sm">
            <div className="flex items-center justify-between rounded-md bg-emerald-50 px-3 py-2 text-emerald-800">
              <span>Online</span>
              <strong>{counts.online}</strong>
            </div>
            <div className="flex items-center justify-between rounded-md bg-amber-50 px-3 py-2 text-amber-800">
              <span>Cảnh báo</span>
              <strong>{counts.warning + counts.critical}</strong>
            </div>
            <div className="flex items-center justify-between rounded-md bg-slate-100 px-3 py-2 text-slate-700">
              <span>Mất kết nối</span>
              <strong>{counts.offline}</strong>
            </div>
          </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-3">
        <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm xl:col-span-2">
          <h2 className="text-lg font-semibold text-slate-950">Top trạm có PM2.5 cao nhất</h2>
          <div className="mt-4 h-[320px]">
            <ResponsiveContainer height="100%" width="100%">
              <BarChart data={topPm25} layout="vertical" margin={{ bottom: 0, left: 20, right: 20, top: 0 }}>
                <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
                <XAxis type="number" tick={{ fontSize: 12 }} />
                <YAxis dataKey="code" type="category" width={92} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="pm25" fill="#d97706" name="PM2.5" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-950">Trung bình thông số</h2>
          <div className="mt-4 grid gap-3">
            <div className="flex items-center justify-between rounded-md border border-slate-200 px-3 py-2">
              <span className="inline-flex items-center gap-2 text-sm text-slate-600">
                <Gauge className="h-4 w-4 text-amber-600" />
                PM2.5
              </span>
              <strong>{metricSummary.pm25Average} ug/m3</strong>
            </div>
            <div className="flex items-center justify-between rounded-md border border-slate-200 px-3 py-2">
              <span className="inline-flex items-center gap-2 text-sm text-slate-600">
                <Thermometer className="h-4 w-4 text-red-600" />
                Nhiệt độ
              </span>
              <strong>{metricSummary.temperatureAverage} C</strong>
            </div>
            <div className="flex items-center justify-between rounded-md border border-slate-200 px-3 py-2">
              <span className="inline-flex items-center gap-2 text-sm text-slate-600">
                <Wind className="h-4 w-4 text-emerald-600" />
                Tốc độ gió
              </span>
              <strong>{metricSummary.windAverage} km/h</strong>
            </div>
            <div className="flex items-center justify-between rounded-md border border-slate-200 px-3 py-2">
              <span className="text-sm text-slate-600">Độ ẩm</span>
              <strong>{metricSummary.humidityAverage}%</strong>
            </div>
          </div>
        </section>
      </div>

      <div className="grid gap-4 xl:grid-cols-[.95fr_1.05fr]">
        <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-950">Nguồn dữ liệu hệ thống</h2>
          <div className="mt-4 grid gap-3">
            <div className="flex items-center justify-between rounded-md border border-slate-200 px-3 py-2">
              <span className="inline-flex items-center gap-2 text-sm text-slate-600">
                <Database className="h-4 w-4 text-cyan-700" />
                Giao diện đang đọc
              </span>
              <strong>{dataSource === "backend" ? "Backend + TimescaleDB" : "Mock fallback"}</strong>
            </div>
            <div className="flex items-center justify-between rounded-md border border-slate-200 px-3 py-2">
              <span className="inline-flex items-center gap-2 text-sm text-slate-600">
                <Server className="h-4 w-4 text-emerald-700" />
                FTP server
              </span>
              <strong className={ftpStatus?.connected ? "text-emerald-700" : "text-red-700"}>{ftpStatus?.connected ? "Đang kết nối" : "Mất kết nối"}</strong>
            </div>
            <div className="flex items-center justify-between rounded-md border border-slate-200 px-3 py-2">
              <span className="inline-flex items-center gap-2 text-sm text-slate-600">
                <FileText className="h-4 w-4 text-amber-600" />
                Thư mục sensor trên FTP
              </span>
              <strong>{ftpFolders}</strong>
            </div>
          </div>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-950">Trạm cập nhật gần nhất</h2>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[620px] text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-3 py-2">Mã trạm</th>
                  <th className="px-3 py-2">PM2.5</th>
                  <th className="px-3 py-2">Trạng thái</th>
                  <th className="px-3 py-2">Cập nhật cuối</th>
                </tr>
              </thead>
              <tbody>
                {recentStations.map((station) => (
                  <tr className="border-t border-slate-100" key={station.id}>
                    <td className="px-3 py-2 font-medium text-slate-900">{station.code}</td>
                    <td className="px-3 py-2 text-slate-700">{station.metrics.pm25}</td>
                    <td className="px-3 py-2 text-slate-700">{alertLabels[station.qcvnStatus] || station.qcvnStatus}</td>
                    <td className="px-3 py-2 text-slate-600">{formatDateTime(station.lastSeenAt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-950">Cơ cấu loại hình quan trắc</h2>
        <div className="mt-4 h-[260px]">
          <ResponsiveContainer height="100%" width="100%">
            <BarChart data={typeData} margin={{ bottom: 40, left: 0, right: 20, top: 10 }}>
              <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
              <XAxis dataKey="name" interval={0} tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="value" fill="#0891b2" name="Số trạm" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>
    </section>
  );
}
