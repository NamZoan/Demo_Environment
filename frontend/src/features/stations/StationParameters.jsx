import {
  CalendarDays,
  ChevronUp,
  Droplets,
  FileText,
  Flame,
  Folder,
  Gauge,
  MapPin,
  RefreshCcw,
  Server,
  Thermometer,
  Wind,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { createMockSeries } from "../../services/mockApi.js";
import { fetchFtpFile, fetchFtpFiles, fetchFtpStatus, fetchStationData } from "../../api.js";

const rangeOptions = [
  { value: "day", label: "Ngày" },
  { value: "week", label: "Tuần" },
  { value: "month", label: "Tháng" },
];

const metricConfig = [
  { key: "temperature", label: "Nhiệt độ", unit: "C", icon: Thermometer, warning: 38, critical: 42 },
  { key: "humidity", label: "Độ ẩm", unit: "%", icon: Droplets, warning: 85, critical: 95 },
  { key: "windSpeed", label: "Tốc độ gió", unit: "km/h", icon: Wind, warning: 35, critical: 50 },
  { key: "pm25", label: "PM2.5", unit: "ug/m3", icon: Gauge, warning: 35, critical: 150 },
  { key: "co", label: "CO", unit: "ppm", icon: Flame, warning: 5, critical: 10 },
];

const lineColors = {
  temperature: "#dc2626",
  humidity: "#2563eb",
  windSpeed: "#059669",
  pm25: "#ca8a04",
  co: "#7c3aed",
};

const rangeConfig = {
  day: { hours: 24, resolution: "1m" },
  week: { hours: 24 * 7, resolution: "1h" },
  month: { hours: 24 * 30, resolution: "1d" },
};

function chartTimeLabel(value, range) {
  const date = new Date(value);
  if (range === "day") {
    return date.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
  }
  return date.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit" });
}

function normalizeSeries(points, range) {
  return points.map((point) => ({
    time: chartTimeLabel(point.time, range),
    temperature: point.temperature,
    humidity: point.humidity,
    windSpeed: point.wind_speed,
    pm25: point.pm25,
    co: point.co ?? null,
  }));
}

function defaultFtpPath(station) {
  return `/data/${station.code}`;
}

function parentFtpPath(path) {
  if (!path || path === "/data") return "/data";
  const segments = path.split("/").filter(Boolean);
  segments.pop();
  return `/${segments.join("/") || "data"}`;
}

function formatDateTime(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString("vi-VN");
}

function formatFileSize(size) {
  if (size === null || size === undefined) return "-";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function parseCsvPreview(content) {
  const lines = content.trim().split(/\r?\n/).filter(Boolean);
  if (lines.length === 0) return { headers: [], rows: [] };
  const [headerLine, ...bodyLines] = lines;
  const headers = headerLine.split(",").map((header) => header.trim());
  const rows = bodyLines.map((line) => line.split(",").map((cell) => cell.trim()));
  return { headers, rows };
}

function levelFor(value, metric) {
  if (value >= metric.critical) return "critical";
  if (value >= metric.warning) return "warning";
  return "normal";
}

function cardStyle(level) {
  if (level === "critical") return "border-red-200 bg-red-50 text-red-800";
  if (level === "warning") return "border-amber-200 bg-amber-50 text-amber-800";
  return "border-emerald-200 bg-emerald-50 text-emerald-800";
}

export default function StationParameters({ onBack, station }) {
  const [range, setRange] = useState("day");
  const [backendSeries, setBackendSeries] = useState([]);
  const [dataSource, setDataSource] = useState("mock");
  const [ftpStatus, setFtpStatus] = useState(null);
  const [ftpPath, setFtpPath] = useState(() => defaultFtpPath(station));
  const [ftpListing, setFtpListing] = useState({ path: defaultFtpPath(station), entries: [] });
  const [ftpLoading, setFtpLoading] = useState(false);
  const [ftpRefreshKey, setFtpRefreshKey] = useState(0);
  const [csvPreview, setCsvPreview] = useState(null);
  const [csvLoading, setCsvLoading] = useState(false);
  const mockSeries = useMemo(() => createMockSeries(station.id, range), [range, station.id]);
  const series = backendSeries.length > 0 ? backendSeries : mockSeries;
  const parsedCsv = useMemo(() => parseCsvPreview(csvPreview?.content || ""), [csvPreview]);
  const stationDetails = [
    { label: "Mã trạm", value: station.code },
    { label: "Khu vực", value: station.region },
    { label: "Loại hình", value: station.type },
    { label: "Datalogger", value: station.datalogger },
    { label: "Trạng thái", value: station.status },
    { label: "Lần nhận dữ liệu cuối", value: formatDateTime(station.lastSeenAt) },
    { label: "Tọa độ", value: `${station.latitude}, ${station.longitude}` },
    { label: "Nguồn", value: station.code.startsWith("sensor_") ? "IoT simulator qua FTP" : "Database seed/API" },
  ];

  useEffect(() => {
    let cancelled = false;
    const now = new Date();
    const selectedRange = rangeConfig[range];
    const start = new Date(now.getTime() - selectedRange.hours * 60 * 60 * 1000);

    fetchStationData({
      stationId: station.id,
      startTime: start,
      endTime: now,
      resolution: selectedRange.resolution,
      currentUser: { id: 1 },
    }).then((points) => {
      if (cancelled) return;
      const normalized = normalizeSeries(points, range);
      setBackendSeries(normalized);
      setDataSource(normalized.length > 0 ? "backend" : "mock");
    });

    return () => {
      cancelled = true;
    };
  }, [range, station.id]);

  useEffect(() => {
    setFtpPath(defaultFtpPath(station));
    setCsvPreview(null);
  }, [station.code]);

  useEffect(() => {
    let cancelled = false;
    fetchFtpStatus({ id: 1 }).then((status) => {
      if (!cancelled) setFtpStatus(status);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setFtpLoading(true);
    fetchFtpFiles({ path: ftpPath, currentUser: { id: 1 } }).then((listing) => {
      if (!cancelled) {
        setFtpListing(listing);
        setFtpLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [ftpPath, ftpRefreshKey]);

  function openFtpEntry(entry) {
    if (entry.type === "folder") {
      setFtpPath(entry.path);
      setCsvPreview(null);
      return;
    }
    if (!entry.name.toLowerCase().endsWith(".csv")) {
      setCsvPreview({ name: entry.name, path: entry.path, content: "", error: "Chỉ hỗ trợ xem trước file CSV." });
      return;
    }
    setCsvLoading(true);
    fetchFtpFile({ path: entry.path, currentUser: { id: 1 } }).then((preview) => {
      setCsvPreview(preview);
      setCsvLoading(false);
    });
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-center">
        <div>
          <button className="mb-2 text-sm font-medium text-cyan-700" onClick={onBack} type="button">
            Quay lại danh sách
          </button>
          <h1 className="text-2xl font-semibold text-slate-950">{station.name}</h1>
          <p className="mt-1 text-sm text-slate-500">
            {station.code} - {station.region} - {station.latitude}, {station.longitude}
          </p>
        </div>
        <label className="grid gap-1 text-sm text-slate-600">
          <span className="flex items-center gap-2">
            <CalendarDays className="h-4 w-4" />
            Khoảng thời gian
          </span>
          <select
            className="h-10 rounded-md border border-slate-300 bg-white px-3 outline-none focus:border-cyan-600"
            onChange={(event) => setRange(event.target.value)}
            value={range}
          >
            {rangeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        {metricConfig.map((metric) => {
          const Icon = metric.icon;
          const value = station.metrics[metric.key];
          const level = levelFor(value, metric);
          return (
            <article className={`rounded-lg border p-4 ${cardStyle(level)}`} key={metric.key}>
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">{metric.label}</span>
                <Icon className="h-5 w-5" />
              </div>
              <div className="mt-4 flex items-end gap-2">
                <strong className="text-3xl leading-none">{value}</strong>
                <span className="text-sm">{metric.unit}</span>
              </div>
              <p className="mt-3 text-xs uppercase tracking-wide">{level}</p>
            </article>
          );
        })}
      </div>

      <div className="grid gap-4 xl:grid-cols-[.8fr_1.2fr]">
        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="mb-4 flex items-center gap-2">
            <MapPin className="h-5 w-5 text-cyan-700" />
            <h2 className="text-lg font-semibold">Thông tin trạm</h2>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {stationDetails.map((item) => (
              <div className="rounded-md border border-slate-200 px-3 py-2" key={item.label}>
                <p className="text-xs font-medium uppercase text-slate-400">{item.label}</p>
                <p className="mt-1 break-words text-sm font-semibold text-slate-800">{item.value || "-"}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="mb-4 flex flex-col justify-between gap-3 md:flex-row md:items-center">
            <div>
              <div className="flex items-center gap-2">
                <Server className="h-5 w-5 text-cyan-700" />
                <h2 className="text-lg font-semibold">FTP đang kết nối</h2>
              </div>
              <p className="mt-1 text-sm text-slate-500">
                {ftpStatus?.host || "127.0.0.1"}:{ftpStatus?.port || 21} - user {ftpStatus?.user || "station"}
              </p>
            </div>
            <span
              className={`inline-flex w-fit items-center rounded-full px-3 py-1 text-xs font-semibold ${
                ftpStatus?.connected ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"
              }`}
            >
              {ftpStatus?.connected ? "Connected" : "Disconnected"}
            </span>
          </div>

          {ftpStatus?.error && <p className="mb-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{ftpStatus.error}</p>}

          <div className="mb-3 flex flex-col gap-2 md:flex-row md:items-center">
            <code className="min-w-0 flex-1 rounded-md bg-slate-950 px-3 py-2 text-sm text-cyan-100">{ftpListing.path || ftpPath}</code>
            <div className="flex gap-2">
              <button
                className="inline-flex items-center gap-2 rounded-md border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700"
                onClick={() => setFtpPath(parentFtpPath(ftpPath))}
                type="button"
              >
                <ChevronUp className="h-4 w-4" />
                Lên
              </button>
              <button
                className="inline-flex items-center gap-2 rounded-md border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700"
                onClick={() => setFtpRefreshKey((current) => current + 1)}
                type="button"
              >
                <RefreshCcw className="h-4 w-4" />
                Refresh
              </button>
            </div>
          </div>

          <div className="max-h-[320px] overflow-auto rounded-md border border-slate-200">
            <table className="w-full min-w-[620px] text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-3 py-2">Tên</th>
                  <th className="px-3 py-2">Loại</th>
                  <th className="px-3 py-2">Dung lượng</th>
                  <th className="px-3 py-2">Modified</th>
                </tr>
              </thead>
              <tbody>
                {ftpLoading ? (
                  <tr>
                    <td className="px-3 py-5 text-center text-slate-500" colSpan="4">
                      Đang tải FTP...
                    </td>
                  </tr>
                ) : ftpListing.entries.length > 0 ? (
                  ftpListing.entries.map((entry) => {
                    const Icon = entry.type === "folder" ? Folder : FileText;
                    return (
                      <tr className="border-t border-slate-100 hover:bg-slate-50" key={entry.path}>
                        <td className="px-3 py-2">
                          <button
                            className="inline-flex max-w-[300px] items-center gap-2 truncate text-left font-medium text-slate-800 hover:text-cyan-700"
                            onClick={() => openFtpEntry(entry)}
                            type="button"
                          >
                            <Icon className="h-4 w-4 shrink-0 text-cyan-700" />
                            <span className="truncate">{entry.name}</span>
                          </button>
                        </td>
                        <td className="px-3 py-2 text-slate-600">{entry.type === "folder" ? "Folder" : "File"}</td>
                        <td className="px-3 py-2 text-slate-600">{formatFileSize(entry.size)}</td>
                        <td className="px-3 py-2 text-slate-600">{entry.modified || "-"}</td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td className="px-3 py-5 text-center text-slate-500" colSpan="4">
                      Chưa có file hoặc không truy cập được thư mục này.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {(csvLoading || csvPreview) && (
            <section className="mt-4 rounded-md border border-cyan-200 bg-cyan-50/40">
              <div className="flex items-center justify-between gap-3 border-b border-cyan-100 px-3 py-2">
                <div className="min-w-0">
                  <h3 className="truncate text-sm font-semibold text-slate-900">Nội dung CSV: {csvPreview?.name || "Đang tải..."}</h3>
                  <p className="truncate text-xs text-slate-500">{csvPreview?.path || ""}</p>
                </div>
                <button className="rounded-md p-1.5 text-slate-500 hover:bg-white" onClick={() => setCsvPreview(null)} type="button">
                  <X className="h-4 w-4" />
                </button>
              </div>
              {csvLoading ? (
                <p className="px-3 py-5 text-center text-sm text-slate-500">Đang đọc file CSV...</p>
              ) : csvPreview?.error ? (
                <p className="px-3 py-3 text-sm text-red-700">{csvPreview.error}</p>
              ) : (
                <div className="max-h-[260px] overflow-auto">
                  <table className="w-full min-w-[760px] text-sm">
                    <thead className="bg-white text-left text-xs uppercase text-slate-500">
                      <tr>
                        {parsedCsv.headers.map((header) => (
                          <th className="border-b border-cyan-100 px-3 py-2" key={header}>
                            {header}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {parsedCsv.rows.map((row, rowIndex) => (
                        <tr className="border-b border-cyan-100/70 bg-white/60" key={`${csvPreview.path}-${rowIndex}`}>
                          {parsedCsv.headers.map((header, cellIndex) => (
                            <td className="px-3 py-2 text-slate-700" key={`${header}-${cellIndex}`}>
                              {row[cellIndex] || "-"}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          )}
        </section>
      </div>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">Biểu đồ biến thiên thông số</h2>
            <p className="text-sm text-slate-500">
              Dữ liệu {dataSource === "backend" ? "từ Backend API + TimescaleDB" : "mock fallback"} theo{" "}
              {rangeOptions.find((item) => item.value === range)?.label.toLowerCase()}.
            </p>
          </div>
        </div>
        <div className="h-[420px]">
          <ResponsiveContainer height="100%" width="100%">
            <LineChart data={series} margin={{ bottom: 8, left: 0, right: 20, top: 10 }}>
              <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
              <XAxis dataKey="time" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Legend />
              {metricConfig.map((metric) => (
                <Line
                  connectNulls
                  dataKey={metric.key}
                  dot={false}
                  key={metric.key}
                  name={metric.label}
                  stroke={lineColors[metric.key]}
                  strokeWidth={2}
                  type="monotone"
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>
    </section>
  );
}
