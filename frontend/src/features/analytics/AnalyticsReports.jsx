import { RefreshCcw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { fetchAnalyticsHeatmap, fetchAnalyticsScatter, fetchAnalyticsSeries } from "../../api.js";
import { queryOptimizationNote } from "../stations/stationTimeRange.js";
import { resolveSelectedStationIds } from "./analyticsSelection.js";

const metrics = [
  { value: "pm25", label: "PM2.5" },
  { value: "temperature", label: "Nhiệt độ" },
  { value: "humidity", label: "Độ ẩm" },
  { value: "wind_speed", label: "Tốc độ gió" },
];

const colors = ["#0891b2", "#dc2626", "#059669", "#ca8a04", "#7c3aed"];

function startForRange(range) {
  const now = new Date();
  const hours = range === "month" ? 24 * 30 : range === "week" ? 24 * 7 : 24;
  return new Date(now.getTime() - hours * 60 * 60 * 1000);
}

function heatColor(value) {
  if (value == null) return "bg-slate-100 text-slate-400";
  if (value <= 50) return "bg-emerald-100 text-emerald-800";
  if (value <= 100) return "bg-amber-100 text-amber-800";
  return "bg-red-100 text-red-800";
}

function chartRows(series) {
  const byTime = new Map();
  series.forEach((point) => {
    const key = new Date(point.time).toLocaleString("vi-VN", { day: "2-digit", month: "2-digit", hour: "2-digit" });
    const row = byTime.get(key) || { time: key };
    row[point.station_code || String(point.station_id)] = point.value;
    byTime.set(key, row);
  });
  return Array.from(byTime.values());
}

export default function AnalyticsReports({ currentUser, stations }) {
  const [selectedStationIds, setSelectedStationIds] = useState(() => stations.slice(0, 2).map((station) => station.id));
  const [metric, setMetric] = useState("pm25");
  const [range, setRange] = useState("week");
  const [series, setSeries] = useState([]);
  const [seriesMeta, setSeriesMeta] = useState(null);
  const [heatmap, setHeatmap] = useState([]);
  const [scatter, setScatter] = useState([]);
  const [scatterMeta, setScatterMeta] = useState(null);
  const [loading, setLoading] = useState(false);

  const selectedStations = useMemo(
    () => stations.filter((station) => selectedStationIds.includes(station.id)).slice(0, 5),
    [selectedStationIds, stations],
  );
  const startTime = useMemo(() => startForRange(range), [range]);
  const endTime = useMemo(() => new Date(), [range]);
  const rows = useMemo(() => chartRows(series), [series]);
  const analyticsOptimizationNote = queryOptimizationNote(seriesMeta) || queryOptimizationNote(scatterMeta);

  useEffect(() => {
    setSelectedStationIds((current) => resolveSelectedStationIds(stations, current));
  }, [stations]);

  function toggleStation(stationId) {
    setSelectedStationIds((current) => {
      if (current.includes(stationId)) return current.filter((id) => id !== stationId);
      return [...current, stationId].slice(0, 5);
    });
  }

  async function loadAnalytics() {
    if (selectedStations.length === 0) return;
    setLoading(true);
    const stationIds = selectedStations.map((station) => station.id);
    const resolution = range === "day" ? "1m" : range === "week" ? "1h" : "1d";
    try {
      const [seriesPayload, heatmapPayload, scatterPayload] = await Promise.all([
        fetchAnalyticsSeries({ stationIds, metric, startTime, endTime, resolution, currentUser }),
        fetchAnalyticsHeatmap({ stationId: stationIds[0], metric, startTime, endTime, currentUser }),
        fetchAnalyticsScatter({
          stationId: stationIds[0],
          xMetric: metric === "temperature" ? "humidity" : "temperature",
          yMetric: metric,
          startTime,
          endTime,
          resolution,
          currentUser,
        }),
      ]);
      setSeries(seriesPayload.points);
      setHeatmap(heatmapPayload);
      setScatter(scatterPayload.points);
      setSeriesMeta(seriesPayload.meta);
      setScatterMeta(scatterPayload.meta);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAnalytics();
  }, [currentUser, metric, range, selectedStationIds.join(","), stations.length]);

  return (
    <section className="space-y-4">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-center">
        <div>
          <h1 className="text-2xl font-semibold text-slate-950">Phân tích & Xuất dữ liệu</h1>
          <p className="mt-1 text-sm text-slate-500">So sánh đa trạm, heatmap ô nhiễm và scatter tương quan.</p>
        </div>
      </div>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="grid gap-3 lg:grid-cols-[1fr_180px_160px_auto]">
          <div>
            <p className="mb-2 text-sm font-medium text-slate-600">Chọn tối đa 5 trạm</p>
            <div className="flex flex-wrap gap-2">
              {stations.slice(0, 24).map((station) => (
                <button
                  className={`rounded-md border px-3 py-2 text-sm ${
                    selectedStationIds.includes(station.id) ? "border-cyan-700 bg-cyan-50 text-cyan-800" : "border-slate-200 text-slate-600"
                  }`}
                  key={station.id}
                  onClick={() => toggleStation(station.id)}
                  type="button"
                >
                  {station.code}
                </button>
              ))}
            </div>
          </div>
          <label className="grid gap-1 text-sm font-medium text-slate-600">
            Thông số
            <select className="h-10 rounded-md border border-slate-300 px-3" onChange={(event) => setMetric(event.target.value)} value={metric}>
              {metrics.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label className="grid gap-1 text-sm font-medium text-slate-600">
            Thời gian
            <select className="h-10 rounded-md border border-slate-300 px-3" onChange={(event) => setRange(event.target.value)} value={range}>
              <option value="day">24 giờ</option>
              <option value="week">7 ngày</option>
              <option value="month">30 ngày</option>
            </select>
          </label>
          <button
            className="mt-6 inline-flex h-10 items-center justify-center gap-2 rounded-md border border-slate-300 px-4 text-sm font-semibold"
            disabled={loading}
            onClick={loadAnalytics}
            type="button"
          >
            <RefreshCcw className={loading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
            Tải lại
          </button>
        </div>
      </section>

      {analyticsOptimizationNote && (
        <p className="rounded-md border border-cyan-200 bg-cyan-50 px-3 py-2 text-sm font-medium text-cyan-800">{analyticsOptimizationNote}</p>
      )}

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="text-lg font-semibold">Biến động theo thời gian</h2>
        <div className="mt-4 h-[360px]">
          <ResponsiveContainer height="100%" width="100%">
            <LineChart data={rows}>
              <CartesianGrid stroke="#e2e8f0" />
              <XAxis dataKey="time" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Legend />
              {selectedStations.map((station, index) => (
                <Line dataKey={station.code} dot={false} key={station.id} name={station.code} stroke={colors[index % colors.length]} strokeWidth={2} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-2">
        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <h2 className="text-lg font-semibold">Heatmap theo giờ/ngày</h2>
          <div className="mt-4 grid grid-cols-6 gap-2">
            {heatmap.slice(0, 60).map((point) => (
              <div className={`rounded-md px-2 py-2 text-center text-xs font-semibold ${heatColor(point.value)}`} key={`${point.day}-${point.hour}`}>
                <span className="block">{point.day.slice(5)}</span>
                <span className="block">{point.hour}h</span>
                <span className="block">{point.value?.toFixed?.(1) ?? "-"}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <h2 className="text-lg font-semibold">Scatter tương quan</h2>
          <div className="mt-4 h-[320px]">
            <ResponsiveContainer height="100%" width="100%">
              <ScatterChart>
                <CartesianGrid stroke="#e2e8f0" />
                <XAxis dataKey="x" name="X" tick={{ fontSize: 12 }} />
                <YAxis dataKey="y" name="Y" tick={{ fontSize: 12 }} />
                <Tooltip cursor={{ strokeDasharray: "3 3" }} />
                <Scatter data={scatter} fill="#0891b2">
                  {scatter.map((point, index) => (
                    <Cell key={`${point.time}-${index}`} />
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>
    </section>
  );
}
