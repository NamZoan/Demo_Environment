import { CalendarDays, Droplets, Flame, Gauge, Thermometer } from "lucide-react";
import { useMemo, useState } from "react";
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

const rangeOptions = [
  { value: "day", label: "Ngay" },
  { value: "week", label: "Tuan" },
  { value: "month", label: "Thang" },
];

const metricConfig = [
  { key: "temperature", label: "Nhiet do", unit: "C", icon: Thermometer, warning: 38, critical: 42 },
  { key: "humidity", label: "Do am", unit: "%", icon: Droplets, warning: 85, critical: 95 },
  { key: "pm25", label: "PM2.5", unit: "ug/m3", icon: Gauge, warning: 35, critical: 150 },
  { key: "co", label: "CO", unit: "ppm", icon: Flame, warning: 5, critical: 10 },
];

const lineColors = {
  temperature: "#dc2626",
  humidity: "#2563eb",
  pm25: "#ca8a04",
  co: "#7c3aed",
};

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
  const series = useMemo(() => createMockSeries(station.id, range), [range, station.id]);

  return (
    <section className="space-y-4">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-center">
        <div>
          <button className="mb-2 text-sm font-medium text-cyan-700" onClick={onBack} type="button">
            Quay lai danh sach
          </button>
          <h1 className="text-2xl font-semibold text-slate-950">{station.name}</h1>
          <p className="mt-1 text-sm text-slate-500">
            {station.code} - {station.region} - {station.latitude}, {station.longitude}
          </p>
        </div>
        <label className="grid gap-1 text-sm text-slate-600">
          <span className="flex items-center gap-2">
            <CalendarDays className="h-4 w-4" />
            Khoang thoi gian
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

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
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

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">Bieu do bien thien thong so</h2>
            <p className="text-sm text-slate-500">Du lieu mock theo {rangeOptions.find((item) => item.value === range)?.label.toLowerCase()}.</p>
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
