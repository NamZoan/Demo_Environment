import { Edit3, Plus, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";

import { createQcvnConfig, deleteQcvnConfig, fetchQcvnConfigs, updateQcvnConfig } from "../../api.js";

const emptyForm = {
  station_id: "",
  metric: "pm25",
  warning_min: "",
  warning_max: "",
  critical_min: "",
  critical_max: "",
  enabled: true,
};

const metricLabels = {
  pm25: "PM2.5",
  temperature: "Nhiệt độ",
  humidity: "Độ ẩm",
};

function numberValue(value) {
  return value === null || value === undefined ? "" : String(value);
}

function formFromConfig(config) {
  return {
    station_id: String(config.station_id),
    metric: config.metric,
    warning_min: numberValue(config.warning_min),
    warning_max: numberValue(config.warning_max),
    critical_min: numberValue(config.critical_min),
    critical_max: numberValue(config.critical_max),
    enabled: config.enabled,
  };
}

function payloadFromForm(form) {
  const nullableNumber = (value) => (value === "" ? null : Number(value));
  return {
    station_id: Number(form.station_id),
    metric: form.metric,
    warning_min: nullableNumber(form.warning_min),
    warning_max: nullableNumber(form.warning_max),
    critical_min: nullableNumber(form.critical_min),
    critical_max: nullableNumber(form.critical_max),
    enabled: form.enabled,
  };
}

export default function QcvnManagement({ currentUser, onStationsChanged, stations }) {
  const [configs, setConfigs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingConfig, setEditingConfig] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [message, setMessage] = useState(null);

  async function load() {
    setLoading(true);
    try {
      setConfigs(await fetchQcvnConfigs(currentUser));
      setMessage(null);
    } catch (error) {
      setMessage({ tone: "error", text: error.message });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [currentUser]);

  function openCreate() {
    setEditingConfig(null);
    setForm({ ...emptyForm, station_id: stations[0]?.id ? String(stations[0].id) : "" });
    setModalOpen(true);
  }

  function openEdit(config) {
    setEditingConfig(config);
    setForm(formFromConfig(config));
    setModalOpen(true);
  }

  function updateField(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    try {
      const payload = payloadFromForm(form);
      if (editingConfig) {
        await updateQcvnConfig(editingConfig.id, payload, currentUser);
      } else {
        await createQcvnConfig(payload, currentUser);
      }
      setModalOpen(false);
      setMessage({ tone: "success", text: editingConfig ? "Đã cập nhật QCVN" : "Đã thêm QCVN cho trạm" });
      await load();
      await onStationsChanged?.();
    } catch (error) {
      setMessage({ tone: "error", text: error.message });
    }
  }

  async function handleDelete(config) {
    if (!window.confirm(`Xóa QCVN ${metricLabels[config.metric]} của trạm ${config.station_code}?`)) return;
    try {
      await deleteQcvnConfig(config.id, currentUser);
      setMessage({ tone: "success", text: "Đã xóa QCVN" });
      await load();
      await onStationsChanged?.();
    } catch (error) {
      setMessage({ tone: "error", text: error.message });
    }
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-end">
        <div>
          <h1 className="text-2xl font-semibold text-slate-950">Quản lý QCVN</h1>
          <p className="mt-1 text-sm text-slate-500">Chỉ trạm được gắn QCVN tại đây mới phát sinh cảnh báo trên trang chủ.</p>
        </div>
        <button className="inline-flex items-center justify-center gap-2 rounded-md bg-cyan-700 px-3 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50" disabled={stations.length === 0} onClick={openCreate} type="button">
          <Plus className="h-4 w-4" /> Thêm QCVN
        </button>
      </div>

      {message && <p className={`rounded-md px-3 py-2 text-sm ${message.tone === "error" ? "bg-red-50 text-red-700" : "bg-emerald-50 text-emerald-700"}`}>{message.text}</p>}
      {stations.length === 0 && <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">Chưa có trạm để gắn QCVN.</p>}

      <section className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr><th className="px-4 py-3">Trạm</th><th className="px-4 py-3">Thông số</th><th className="px-4 py-3">Cảnh báo</th><th className="px-4 py-3">Nghiêm trọng</th><th className="px-4 py-3">Trạng thái</th><th className="px-4 py-3 text-right">Hành động</th></tr>
            </thead>
            <tbody>
              {loading ? <tr><td className="px-4 py-8 text-center text-slate-500" colSpan="6">Đang tải cấu hình QCVN...</td></tr> : configs.length === 0 ? <tr><td className="px-4 py-8 text-center text-slate-500" colSpan="6">Chưa có QCVN nào được gắn cho trạm.</td></tr> : configs.map((config) => (
                <tr className="border-t border-slate-100" key={config.id}>
                  <td className="px-4 py-3"><p className="font-medium text-slate-900">{config.station_code}</p><p className="text-xs text-slate-500">{config.station_name}</p></td>
                  <td className="px-4 py-3">{metricLabels[config.metric]}</td>
                  <td className="px-4 py-3">{config.warning_min ?? "-"} đến {config.warning_max ?? "-"}</td>
                  <td className="px-4 py-3">{config.critical_min ?? "-"} đến {config.critical_max ?? "-"}</td>
                  <td className="px-4 py-3"><span className={`rounded-full px-2 py-1 text-xs font-medium ${config.enabled ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>{config.enabled ? "Đang áp dụng" : "Đã tắt"}</span></td>
                  <td className="px-4 py-3 text-right"><div className="inline-flex gap-2"><button className="rounded-md border border-slate-300 p-2 text-slate-600 hover:bg-slate-50" onClick={() => openEdit(config)} title="Sửa" type="button"><Edit3 className="h-4 w-4" /></button><button className="rounded-md border border-red-200 p-2 text-red-600 hover:bg-red-50" onClick={() => handleDelete(config)} title="Xóa" type="button"><Trash2 className="h-4 w-4" /></button></div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {modalOpen && <div className="fixed inset-0 z-40 grid place-items-center bg-slate-950/50 p-4"><form className="w-full max-w-2xl rounded-lg bg-white shadow-xl" onSubmit={handleSubmit}><div className="flex items-center justify-between border-b border-slate-200 px-5 py-4"><h2 className="text-lg font-semibold">{editingConfig ? "Sửa QCVN" : "Thêm QCVN cho trạm"}</h2><button className="rounded-md p-2 text-slate-500" onClick={() => setModalOpen(false)} type="button"><X className="h-5 w-5" /></button></div><div className="grid gap-3 p-5 md:grid-cols-2">
        <label className="grid gap-1 text-sm">Trạm<select className="h-10 rounded-md border border-slate-300 px-3" onChange={(event) => updateField("station_id", event.target.value)} required value={form.station_id}>{stations.map((station) => <option key={station.id} value={station.id}>{station.code} - {station.name}</option>)}</select></label>
        <label className="grid gap-1 text-sm">Thông số<select className="h-10 rounded-md border border-slate-300 px-3" onChange={(event) => updateField("metric", event.target.value)} value={form.metric}>{Object.entries(metricLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        {["warning_min", "warning_max", "critical_min", "critical_max"].map((field) => <label className="grid gap-1 text-sm" key={field}>{field === "warning_min" ? "Cảnh báo tối thiểu" : field === "warning_max" ? "Cảnh báo tối đa" : field === "critical_min" ? "Nghiêm trọng tối thiểu" : "Nghiêm trọng tối đa"}<input className="h-10 rounded-md border border-slate-300 px-3" onChange={(event) => updateField(field, event.target.value)} step="any" type="number" value={form[field]} /></label>)}
        <label className="flex items-center gap-2 text-sm"><input checked={form.enabled} onChange={(event) => updateField("enabled", event.target.checked)} type="checkbox" /> Áp dụng cấu hình</label>
      </div><div className="flex justify-end gap-2 border-t border-slate-200 px-5 py-4"><button className="rounded-md border border-slate-300 px-3 py-2 text-sm" onClick={() => setModalOpen(false)} type="button">Hủy</button><button className="rounded-md bg-cyan-700 px-3 py-2 text-sm font-semibold text-white" type="submit">Lưu</button></div></form></div>}
    </section>
  );
}
