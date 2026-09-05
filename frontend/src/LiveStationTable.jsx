const statusLabels = {
  online: "Online",
  warning: "Warning",
  critical: "Critical",
  offline: "Offline",
};

function formatNumber(value) {
  return value === null || value === undefined ? "-" : Number(value).toFixed(1);
}

function formatTime(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString();
}

export default function LiveStationTable({ stations, selectedStationId, onSelectStation }) {
  return (
    <section className="livePanel">
      <div className="panelHeader">
        <h2>Live Stations</h2>
        <span>{stations.length} stations</span>
      </div>
      <div className="tableWrap">
        <table>
          <thead>
            <tr>
              <th>Station</th>
              <th>Status</th>
              <th>PM2.5</th>
              <th>Temp</th>
              <th>Humidity</th>
              <th>Last Seen</th>
            </tr>
          </thead>
          <tbody>
            {stations.map((station) => (
              <tr
                className={String(station.id) === selectedStationId ? "selectedRow" : ""}
                key={station.id}
                onClick={() => onSelectStation(String(station.id))}
              >
                <td>
                  <strong>{station.code}</strong>
                  <span>{station.name}</span>
                </td>
                <td>
                  <span className={`statusPill ${station.live_status}`}>
                    {statusLabels[station.live_status] || station.live_status}
                  </span>
                </td>
                <td>{formatNumber(station.pm25)}</td>
                <td>{formatNumber(station.temperature)}</td>
                <td>{formatNumber(station.humidity)}</td>
                <td>{formatTime(station.last_seen_at || station.time)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
