import { Edit2, Eye, Plus, RefreshCcw, Server, Trash2, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  createFtpConfig,
  deleteFtpConfig,
  fetchFtpConfigs,
  testFtpConnection,
  updateFtpConfig,
} from "../../api.js";

const blankForm = {
  station_id: "",
  host: "",
  port: 21,
  user: "",
  password: "",
  root_path: "/data",
  timeout_seconds: 5,
};

export default function FtpManagement({ currentUser, stations }) {
  const navigate = useNavigate();
  const [configs, setConfigs] = useState([]);
  const [form, setForm] = useState(blankForm);
  const [editingStationId, setEditingStationId] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  async function loadConfigs() {
    setLoading(true);
    try {
      setConfigs(await fetchFtpConfigs(currentUser));
      setMessage(null);
    } catch (error) {
      setMessage({ tone: "error", text: error.message });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadConfigs();
  }, []);

  const configuredStationIds = useMemo(() => new Set(configs.map((item) => item.station_id)), [configs]);
  const availableStations = stations.filter((station) => !configuredStationIds.has(station.id));

  function openCreate() {
    setEditingStationId(null);
    setForm({ ...blankForm, station_id: availableStations[0]?.id || "" });
    setMessage(null);
    setModalOpen(true);
  }

  function openEdit(config) {
    setEditingStationId(config.station_id);
    setForm({ ...config, password: "" });
    setMessage(null);
    setModalOpen(true);
  }

  async function handleTest() {
    setMessage({ tone: "info", text: "Đang kiểm tra kết nối..." });
    try {
      const result = await testFtpConnection(form, currentUser);
      setMessage({ tone: result.connected ? "success" : "error", text: result.connected ? "Kết nối FTP thành công" : result.error || "Không thể kết nối FTP" });
    } catch (error) {
      setMessage({ tone: "error", text: error.message });
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSaving(true);
    try {
      const payload = { ...form, port: Number(form.port), timeout_seconds: Number(form.timeout_seconds) };
      const saved = editingStationId ? await updateFtpConfig(editingStationId, payload, currentUser) : await createFtpConfig(payload, currentUser);
      setConfigs((current) => editingStationId ? current.map((item) => item.station_id === saved.station_id ? saved : item) : [...current, saved]);
      setModalOpen(false);
      setMessage({ tone: "success", text: "Đã lưu cấu hình FTP" });
    } catch (error) {
      setMessage({ tone: "error", text: error.message });
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(config) {
    if (!window.confirm(`Xóa cấu hình FTP của trạm ${config.station_code}?`)) return;
    try {
      await deleteFtpConfig(config.station_id, currentUser);
      setConfigs((current) => current.filter((item) => item.station_id !== config.station_id));
      setMessage({ tone: "success", text: "Đã xóa cấu hình FTP" });
    } catch (error) {
      setMessage({ tone: "error", text: error.message });
    }
  }

  function updateField(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-center">
        <div>
          <h1 className="text-2xl font-semibold text-slate-950">Quản lý FTP</h1>
          <p className="mt-1 text-sm text-slate-500">Quản lý máy FTP theo từng trạm và truy cập danh sách file.</p>
        </div>
        <div className="flex gap-2">
          <button className="inline-flex items-center gap-2 rounded-md border border-slate-300 px-3 py-2 text-sm font-semibold" onClick={loadConfigs} type="button"><RefreshCcw className="h-4 w-4" />Làm mới</button>
          <button className="inline-flex items-center gap-2 rounded-md bg-cyan-700 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50" disabled={availableStations.length === 0} onClick={openCreate} type="button"><Plus className="h-4 w-4" />Thêm FTP</button>
        </div>
      </div>

      {message && <p className={`rounded-md px-3 py-2 text-sm ${message.tone === "error" ? "bg-red-50 text-red-700" : message.tone === "success" ? "bg-emerald-50 text-emerald-700" : "bg-cyan-50 text-cyan-700"}`}>{message.text}</p>}

      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="w-full min-w-[900px] text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="px-4 py-3">Trạm</th><th className="px-4 py-3">FTP</th><th className="px-4 py-3">User</th><th className="px-4 py-3">Thư mục</th><th className="px-4 py-3 text-right">Hành động</th></tr></thead>
          <tbody>
            {loading ? <tr><td className="px-4 py-8 text-center text-slate-500" colSpan="5">Đang tải cấu hình FTP...</td></tr> : configs.length === 0 ? <tr><td className="px-4 py-8 text-center text-slate-500" colSpan="5">Chưa có cấu hình FTP. Hãy tạo trạm trước.</td></tr> : configs.map((config) => (
              <tr className="border-t border-slate-100" key={config.station_id}>
                <td className="px-4 py-3"><strong>{config.station_name}</strong><span className="block text-xs text-slate-500">{config.station_code}</span></td>
                <td className="px-4 py-3 font-mono">{config.host}:{config.port}</td>
                <td className="px-4 py-3">{config.user}</td>
                <td className="px-4 py-3 font-mono text-xs">{config.root_path}</td>
                <td className="px-4 py-3"><div className="flex justify-end gap-2"><button className="rounded-md border border-slate-200 p-2" onClick={() => navigate(`/stations/${config.station_id}`)} title="Xem file" type="button"><Eye className="h-4 w-4" /></button><button className="rounded-md border border-slate-200 p-2" onClick={() => openEdit(config)} title="Sửa" type="button"><Edit2 className="h-4 w-4" /></button><button className="rounded-md border border-red-200 p-2 text-red-600" onClick={() => handleDelete(config)} title="Xóa" type="button"><Trash2 className="h-4 w-4" /></button></div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {modalOpen && <div className="fixed inset-0 z-40 grid place-items-center bg-slate-950/50 p-4"><form className="w-full max-w-2xl rounded-lg bg-white shadow-xl" onSubmit={handleSubmit}><div className="flex items-center justify-between border-b border-slate-200 px-5 py-4"><h2 className="text-lg font-semibold">{editingStationId ? "Sửa cấu hình FTP" : "Thêm cấu hình FTP"}</h2><button className="rounded-md p-2 text-slate-500" onClick={() => setModalOpen(false)} type="button"><X className="h-5 w-5" /></button></div><div className="grid gap-3 p-5 md:grid-cols-2">
        {!editingStationId && <label className="grid gap-1 text-sm">Trạm<select className="h-10 rounded-md border border-slate-300 px-3" onChange={(event) => updateField("station_id", Number(event.target.value))} required value={form.station_id}>{availableStations.map((station) => <option key={station.id} value={station.id}>{station.code} - {station.name}</option>)}</select></label>}
        <label className="grid gap-1 text-sm">Host<input className="h-10 rounded-md border border-slate-300 px-3" onChange={(event) => updateField("host", event.target.value)} required value={form.host} /></label><label className="grid gap-1 text-sm">Port<input className="h-10 rounded-md border border-slate-300 px-3" min="1" max="65535" onChange={(event) => updateField("port", event.target.value)} required type="number" value={form.port} /></label><label className="grid gap-1 text-sm">User<input className="h-10 rounded-md border border-slate-300 px-3" onChange={(event) => updateField("user", event.target.value)} required value={form.user} /></label><label className="grid gap-1 text-sm">Mật khẩu<input className="h-10 rounded-md border border-slate-300 px-3" onChange={(event) => updateField("password", event.target.value)} required={!editingStationId} type="password" value={form.password} /></label><label className="grid gap-1 text-sm md:col-span-2">Thư mục gốc<input className="h-10 rounded-md border border-slate-300 px-3" onChange={(event) => updateField("root_path", event.target.value)} required value={form.root_path} /></label>
      </div><div className="flex justify-end gap-2 border-t border-slate-200 px-5 py-4"><button className="mr-auto inline-flex items-center gap-2 rounded-md border border-cyan-700 px-3 py-2 text-sm font-semibold text-cyan-700" onClick={handleTest} type="button"><Server className="h-4 w-4" />Kiểm tra kết nối</button><button className="rounded-md border border-slate-300 px-4 py-2" onClick={() => setModalOpen(false)} type="button">Hủy</button><button className="rounded-md bg-cyan-700 px-4 py-2 font-semibold text-white disabled:opacity-50" disabled={saving} type="submit">{saving ? "Đang lưu..." : "Lưu"}</button></div></form></div>}
    </section>
  );
}
