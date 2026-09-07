export function stationTableRows(points) {
  return points.map((point) => ({
    time: point.time,
    temperature: point.temperature,
    humidity: point.humidity,
    windSpeed: point.wind_speed,
    pm25: point.pm25,
  }));
}
