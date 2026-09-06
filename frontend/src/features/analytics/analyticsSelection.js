export function resolveSelectedStationIds(stations, selectedIds, limit = 2) {
  if (stations.length === 0) return [];
  const availableIds = new Set(stations.map((station) => station.id));
  const validIds = selectedIds.filter((id) => availableIds.has(id));
  if (validIds.length > 0) return validIds;
  return stations.slice(0, limit).map((station) => station.id);
}
