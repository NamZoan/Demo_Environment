const regions = ["Ha Noi", "Da Nang", "Ho Chi Minh", "Can Tho", "Hai Phong"];
const statuses = ["online", "offline", "maintenance"];
const stationTypes = ["Không khí xung quanh", "Nước mặt", "Nước thải", "Khí thải"];

function stationStatus(index) {
  if (index % 17 === 0) return "offline";
  if (index % 23 === 0) return "maintenance";
  return statuses[index % statuses.length] === "offline" ? "online" : statuses[index % statuses.length];
}

export function createMockStations(total = 2000) {
  return Array.from({ length: total }, (_, index) => {
    const id = index + 1;
    const region = regions[index % regions.length];
    const latitude = 8.6 + ((index * 37) % 1450) / 100;
    const longitude = 102.2 + ((index * 29) % 780) / 100;

    return {
      id,
      code: `ENV-${String(id).padStart(4, "0")}`,
      name: `Tram quan trac ${region} ${String(id).padStart(4, "0")}`,
      region,
      type: stationTypes[index % stationTypes.length],
      qcvnStatus: index % 19 === 0 ? "critical" : index % 7 === 0 ? "warning" : "normal",
      datalogger: `DL-${String((index % 800) + 1).padStart(3, "0")}`,
      latitude: Number(latitude.toFixed(5)),
      longitude: Number(longitude.toFixed(5)),
      status: stationStatus(index),
      lastSeenAt: new Date(Date.now() - (index % 80) * 60_000).toISOString(),
      metrics: {
        temperature: Number((24 + (index % 16) + Math.sin(index) * 2).toFixed(1)),
        humidity: Number((52 + (index % 42)).toFixed(1)),
        pm25: Number((12 + (index % 95)).toFixed(1)),
        co: Number((0.2 + (index % 35) / 10).toFixed(1)),
      },
    };
  });
}

export function createMockSeries(stationId, range = "day") {
  const points = range === "month" ? 30 : range === "week" ? 14 : 24;
  const stepHours = range === "month" ? 24 : range === "week" ? 12 : 1;
  const seed = Number(stationId) || 1;

  return Array.from({ length: points }, (_, index) => {
    const time = new Date(Date.now() - (points - index - 1) * stepHours * 60 * 60 * 1000);
    const wave = Math.sin((index + seed) / 3);
    return {
      time: time.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", hour: "2-digit" }),
      temperature: Number((28 + wave * 4 + (seed % 5)).toFixed(1)),
      humidity: Number((66 - wave * 12 + (seed % 7)).toFixed(1)),
      pm25: Number((24 + Math.cos(index / 2) * 16 + (seed % 12)).toFixed(1)),
      co: Number((0.8 + Math.max(wave, 0) * 1.6 + (seed % 4) / 10).toFixed(1)),
    };
  });
}

export function addStation(stations, payload) {
  const nextId = Math.max(...stations.map((station) => station.id)) + 1;
  return [
    {
      id: nextId,
      code: `ENV-${String(nextId).padStart(4, "0")}`,
      status: "maintenance",
      lastSeenAt: new Date().toISOString(),
      metrics: { temperature: 0, humidity: 0, pm25: 0, co: 0 },
      ...payload,
    },
    ...stations,
  ];
}
