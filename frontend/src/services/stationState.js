export function resolveBackendStations(result, fallbackStations) {
  return result?.source === "backend" ? result.stations : fallbackStations;
}

export function removeStationById(stations, stationId) {
  return stations.filter((station) => String(station.id) !== String(stationId));
}
