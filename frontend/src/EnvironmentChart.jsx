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

const metrics = {
  temperature: { label: "Temperature", color: "#d94f30" },
  humidity: { label: "Humidity", color: "#2374ab" },
  pm25: { label: "PM2.5", color: "#2f8f5b" },
};

export default function EnvironmentChart({ data, visibleMetrics }) {
  const rows = data.map((point) => ({
    ...point,
    label: new Date(point.time).toLocaleString(),
  }));

  return (
    <div className="chartPanel">
      <ResponsiveContainer width="100%" height={430}>
        <LineChart data={rows} margin={{ top: 16, right: 28, bottom: 12, left: 0 }}>
          <CartesianGrid stroke="#e6e8eb" />
          <XAxis dataKey="label" minTickGap={42} tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip />
          <Legend />
          {Object.entries(metrics).map(([key, metric]) =>
            visibleMetrics[key] ? (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                name={metric.label}
                stroke={metric.color}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            ) : null,
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

