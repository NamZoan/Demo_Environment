const now = Date.now();
const hour = 60 * 60 * 1000;

export const demoStations = [
  {
    id: 1,
    code: "HN001",
    name: "Ha Noi Urban Station 001",
    latitude: 21.0278,
    longitude: 105.8342,
    address: "Ha Noi",
    status: "active",
    metadata: {},
  },
  {
    id: 2,
    code: "HCM001",
    name: "Ho Chi Minh Urban Station 001",
    latitude: 10.8231,
    longitude: 106.6297,
    address: "Ho Chi Minh City",
    status: "active",
    metadata: {},
  },
];

export const demoLiveStations = demoStations.map((station, index) => ({
  ...station,
  region_id: index + 1,
  last_seen_at: new Date(now - index * 4 * 60 * 1000).toISOString(),
  time: new Date(now - index * 4 * 60 * 1000).toISOString(),
  temperature: index === 0 ? 31.5 : 28.2,
  humidity: index === 0 ? 74 : 88,
  wind_speed: index === 0 ? 14.2 : 8.6,
  pm25: index === 0 ? 42 : 18,
  live_status: index === 0 ? "warning" : "online",
}));

export function demoSensorData(stationId) {
  const stationOffset = Number(stationId) === 2 ? 3 : 0;
  return Array.from({ length: 24 }, (_, index) => {
    const wave = Math.sin(index / 3);
    return {
      time: new Date(now - (23 - index) * hour).toISOString(),
      temperature: Number((29 + stationOffset + wave * 2).toFixed(2)),
      humidity: Number((68 - wave * 7).toFixed(2)),
      wind_speed: Number((8 + Math.abs(wave) * 12).toFixed(2)),
      pm25: Number((21 + stationOffset * 1.5 + Math.cos(index / 2) * 5).toFixed(2)),
      samples: 60,
    };
  });
}
