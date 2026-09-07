export const stationResolutionOptions = [
  { value: "15m", label: "Trung bình 15 phút", defaultHours: 24 },
  { value: "1h", label: "Trung bình giờ", defaultHours: 24 * 7 },
  { value: "1d", label: "Trung bình ngày", defaultHours: 24 * 30 },
];

export function defaultStationTimeRange(resolution, now = new Date()) {
  const option = stationResolutionOptions.find((item) => item.value === resolution) || stationResolutionOptions[0];
  const end = new Date(now);
  const start = new Date(end.getTime() - option.defaultHours * 60 * 60 * 1000);
  return {
    startTime: toDateTimeLocalValue(start),
    endTime: toDateTimeLocalValue(end),
  };
}

export function toDateTimeLocalValue(date) {
  const value = new Date(date);
  const offsetMs = value.getTimezoneOffset() * 60 * 1000;
  return new Date(value.getTime() - offsetMs).toISOString().slice(0, 16);
}

export function stationDataQuery({ startTime, endTime, resolution, page = 1, pageSize = 100 }) {
  return {
    startTime: new Date(startTime),
    endTime: new Date(endTime),
    resolution,
    page,
    pageSize,
  };
}

export function isStationTimeRangeValid({ startTime, endTime }) {
  const start = new Date(startTime);
  const end = new Date(endTime);
  return !Number.isNaN(start.getTime()) && !Number.isNaN(end.getTime()) && start <= end;
}

export function preferredStationResolution({ startTime, endTime }) {
  const start = new Date(startTime);
  const end = new Date(endTime);
  const hours = (end.getTime() - start.getTime()) / (60 * 60 * 1000);
  if (!Number.isFinite(hours)) return "15m";
  if (hours > 24 * 90) return "1d";
  if (hours > 48) return "1h";
  return "15m";
}

export function queryOptimizationNote(meta) {
  if (!meta) return "";
  if (meta.requested_resolution !== meta.effective_resolution) {
    return `Dữ liệu đã được tối ưu: hiển thị ${meta.effective_resolution} thay vì ${meta.requested_resolution} vì khoảng thời gian quá dài.`;
  }
  if (meta.downsampled) {
    return `Dữ liệu đã được tối ưu: hiển thị tối đa ${meta.max_points} điểm đại diện.`;
  }
  return "";
}
