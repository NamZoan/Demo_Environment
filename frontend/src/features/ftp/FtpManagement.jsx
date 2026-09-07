import { ChevronUp, Edit2, Eye, FileText, Folder, Plus, RefreshCcw, Server, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { createFtpConfig, deleteFtpConfig, fetchFtpConfigs, fetchFtpFile, fetchFtpFiles, testFtpConnection, updateFtpConfig } from "../../api.js";

const blankForm = { name: "", host: "", port: 21, user: "", password: "", root_path: "/data", timeout_seconds: 5, station_ids: [] };

function parentPath(path, rootPath) {
  if (path === rootPath) return rootPath;
  const parent = path.split("/").slice(0, -1).join("/") || "/data";
  return parent.startsWith(rootPath) ? parent : rootPath;
}

function formatFileSize(size) {
  if (size === null || size === undefined) return "-";
  if (size < 1024) return size + " B";
  if (size < 1024 * 1024) return (size / 1024).toFixed(1) + " KB";
  return (size / (1024 * 1024)).toFixed(1) + " MB";
}

export default function FtpManagement({ currentUser, stations }) {
  const navigate = useNavigate();
  const [configs, setConfigs] = useState([]);
  const [form, setForm] = useState(blankForm);
  const [editingFtpId, setEditingFtpId] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
 const [message, setMessage] = useState(null);
  const [browser, setBrowser] = useState(null);

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

  useEffect(() => { loadConfigs(); }, []);

  function openCreate() {
    setEditingFtpId(null);
    setForm(blankForm);
    setMessage(null);
    setModalOpen(true);
  }

  function openEdit(config) {
    setEditingFtpId(config.id);
    setForm({ name: config.name, host: config.host, port: config.port, user: config.user, password: "", root_path: config.root_path, timeout_seconds: config.timeout_seconds, station_ids: config.station_ids || [] });
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
      const saved = editingFtpId ? await updateFtpConfig(editingFtpId, payload, currentUser) : await createFtpConfig(payload, currentUser);
      setConfigs((current) => editingFtpId ? current.map((item) => item.id === saved.id ? saved : item) : [...current, saved]);
      setModalOpen(false);
      setMessage({ tone: "success", text: editingFtpId ? "Đã cập nhật FTP" : "Đã tạo FTP" });
    } catch (error) {
      setMessage({ tone: "error", text: error.message });
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(config) {
    if (!window.confirm(`Xóa FTP ${config.name}? Các trạm đang gán sẽ được bỏ gán.`)) return;
    try {
     await deleteFtpConfig(config.id, currentUser);
      if (browser?.config.id === config.id) setBrowser(null);
     setConfigs((current) => current.filter((item) => item.id !== config.id));
      setMessage({ tone: "success", text: "Đã xóa FTP" });
    } catch (error) {
      setMessage({ tone: "error", text: error.message });
    }
  }

 function updateField(field, value) { setForm((current) => ({ ...current, [field]: value })); }

  async function loadBrowser(config, path = config.root_path || "/data") {
    setBrowser((current) => ({
      config,
      path,
      entries: current?.config.id === config.id ? current.entries : [],
      loading: true,
      error: null,
      preview: current?.config.id === config.id ? current.preview : null,
      previewLoading: false,
    }));
    const listing = await fetchFtpFiles({ path, ftpId: config.id, currentUser });
    setBrowser((current) => ({ ...current, path: listing.path || path, entries: listing.entries || [], loading: false, error: listing.error || null }));
  }

  async function openBrowser(config) {
    await loadBrowser(config);
  }

  async function openEntry(entry) {
    if (!browser) return;
    if (entry.type === "folder") {
      await loadBrowser(browser.config, entry.path);
      return;
    }
    setBrowser((current) => ({ ...current, previewLoading: true, preview: null }));
    const preview = await fetchFtpFile({ path: entry.path, ftpId: browser.config.id, currentUser });
    setBrowser((current) => ({ ...current, previewLoading: false, preview }));
  }

  function toggleStation(stationId) {
    setForm((current) => ({ ...current, station_ids: current.station_ids.includes(stationId) ? current.station_ids.filter((id) => id !== stationId) : [...current.station_ids, stationId] }));
  }

  function assignedNames(config) {
    const assigned = (config.station_ids || []).map((id) => stations.find((station) => station.id === id)?.code || `Trạm #${id}`);
    return assigned.length ? assigned.join(", ") : "Chưa gán trạm";
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-center"><div><h1 className="text-2xl font-semibold text-slate-950">Danh mục FTP</h1><p className="mt-1 text-sm text-slate-500">Tạo máy FTP độc lập trước, sau đó gán cho một hoặc nhiều trạm.</p></div><div className="flex gap-2"><button className="inline-flex items-center gap-2 rounded-md border border-slate-300 px-3 py-2 text-sm font-semibold" onClick={loadConfigs} type="button"><RefreshCcw className="h-4 w-4" />Làm mới</button><button className="inline-flex items-center gap-2 rounded-md bg-cyan-700 px-3 py-2 text-sm font-semibold text-white" onClick={openCreate} type="button"><Plus className="h-4 w-4" />Thêm FTP</button></div></div>
      {message && <p className={`rounded-md px-3 py-2 text-sm ${message.tone === "error" ? "bg-red-50 text-red-700" : message.tone === "success" ? "bg-emerald-50 text-emerald-700" : "bg-cyan-50 text-cyan-700"}`}>{message.text}</p>}
      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white"><table className="w-full min-w-[980px] text-sm"><thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="px-4 py-3">Tên FTP</th><th className="px-4 py-3">Máy chủ</th><th className="px-4 py-3">User</th><th className="px-4 py-3">Thư mục</th><th className="px-4 py-3">Trạm được gán</th><th className="px-4 py-3 text-right">Hành động</th></tr></thead><tbody>
        {loading ? <tr><td className="px-4 py-8 text-center text-slate-500" colSpan="6">Đang tải danh mục FTP...</td></tr> : configs.length === 0 ? <tr><td className="px-4 py-8 text-center text-slate-500" colSpan="6">Chưa có FTP. Có thể tạo FTP ngay cả khi chưa có trạm.</td></tr> : configs.map((config) => <tr className="border-t border-slate-100" key={config.id}><td className="px-4 py-3"><strong>{config.name}</strong></td><td className="px-4 py-3 font-mono">{config.host}:{config.port}</td><td className="px-4 py-3">{config.user}</td><td className="px-4 py-3 font-mono text-xs">{config.root_path}</td><td className="max-w-sm px-4 py-3 text-slate-600">{assignedNames(config)}</td><td className="px-4 py-3"><div className="flex justify-end gap-2">{config.station_ids?.[0] && <button className="rounded-md border border-slate-200 p-2" onClick={() => navigate(`/stations/${config.station_ids[0]}`)} title="Xem file" type="button"><Eye className="h-4 w-4" /></button>}<button className="rounded-md border border-slate-200 p-2" onClick={() => openEdit(config)} title="Sửa" type="button"><Edit2 className="h-4 w-4" /></button><button className="rounded-md border border-red-200 p-2 text-red-600" onClick={() => handleDelete(config)} title="Xóa" type="button"><Trash2 className="h-4 w-4" /></button></div></td></tr>)}
      </tbody></table></div>
      <div className="flex flex-col gap-3 rounded-lg border border-cyan-200 bg-cyan-50/50 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div><h2 className="font-semibold text-slate-950">Truy cập thư mục và file FTP</h2><p className="text-sm text-slate-600">Chọn một máy FTP để duyệt thư mục, mở file văn bản và xem nội dung.</p></div>
        <div className="flex gap-2"><select className="h-10 min-w-48 rounded-md border border-slate-300 bg-white px-3 text-sm" onChange={(event) => { const config = configs.find((item) => String(item.id) === event.target.value); if (config) openBrowser(config); }} value={browser?.config.id || ""}><option value="">Chọn FTP</option>{configs.map((config) => <option key={config.id} value={config.id}>{config.name} - {config.host}:{config.port}</option>)}</select><button className="inline-flex items-center gap-2 rounded-md bg-cyan-700 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50" disabled={!browser} onClick={() => browser && openBrowser(browser.config)} type="button"><Eye className="h-4 w-4" />Mở thư mục</button></div>
      </div>
      {browser && <section className="space-y-3 rounded-lg border border-cyan-200 bg-white p-4"><div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-center"><div><h2 className="text-lg font-semibold text-slate-950">Duyệt file: {browser.config.name}</h2><p className="text-sm text-slate-500">{browser.config.host}:{browser.config.port}</p></div><button className="inline-flex items-center gap-2 self-start rounded-md border border-slate-300 px-3 py-2 text-sm font-semibold" onClick={() => setBrowser(null)} type="button"><X className="h-4 w-4" />Đóng</button></div><div className="flex flex-col gap-2 sm:flex-row"><code className="min-w-0 flex-1 rounded-md bg-slate-950 px-3 py-2 text-sm text-cyan-100">{browser.path}</code><div className="flex gap-2"><button className="inline-flex items-center gap-2 rounded-md border border-slate-300 px-3 py-2 text-sm font-semibold disabled:opacity-50" disabled={browser.path === browser.config.root_path} onClick={() => loadBrowser(browser.config, parentPath(browser.path, browser.config.root_path))} type="button"><ChevronUp className="h-4 w-4" />Lên</button><button className="inline-flex items-center gap-2 rounded-md border border-slate-300 px-3 py-2 text-sm font-semibold" onClick={() => loadBrowser(browser.config, browser.path)} type="button"><RefreshCcw className="h-4 w-4" />Làm mới</button></div></div>{browser.error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{browser.error}</p>}<div className="max-h-[320px] overflow-auto rounded-md border border-slate-200"><table className="w-full min-w-[620px] text-sm"><thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="px-3 py-2">Tên</th><th className="px-3 py-2">Loại</th><th className="px-3 py-2">Dung lượng</th><th className="px-3 py-2">Cập nhật</th></tr></thead><tbody>{browser.loading ? <tr><td className="px-3 py-5 text-center text-slate-500" colSpan="4">Đang tải FTP...</td></tr> : browser.entries.length === 0 ? <tr><td className="px-3 py-5 text-center text-slate-500" colSpan="4">Thư mục trống hoặc không truy cập được.</td></tr> : browser.entries.map((entry) => { const Icon = entry.type === "folder" ? Folder : FileText; return <tr className="border-t border-slate-100 hover:bg-slate-50" key={entry.path}><td className="px-3 py-2"><button className="inline-flex max-w-[360px] items-center gap-2 truncate text-left font-medium text-slate-800 hover:text-cyan-700" onClick={() => openEntry(entry)} type="button"><Icon className="h-4 w-4 shrink-0 text-cyan-700" /><span className="truncate">{entry.name}</span></button></td><td className="px-3 py-2 text-slate-600">{entry.type === "folder" ? "Thư mục" : "File"}</td><td className="px-3 py-2 text-slate-600">{formatFileSize(entry.size)}</td><td className="px-3 py-2 text-slate-600">{entry.modified || "-"}</td></tr>; })}</tbody></table></div>{(browser.previewLoading || browser.preview) && <div className="rounded-md border border-cyan-200 bg-cyan-50/40"><div className="border-b border-cyan-100 px-3 py-2 text-sm font-semibold">{browser.previewLoading ? "Đang tải file..." : "Nội dung: " + browser.preview.name}</div>{browser.preview?.error ? <p className="px-3 py-3 text-sm text-red-700">{browser.preview.error}</p> : browser.preview && <pre className="max-h-[360px] overflow-auto whitespace-pre-wrap break-words p-3 text-xs text-slate-800">{browser.preview.content}</pre>}</div>}</section>}
      {modalOpen && <div className="fixed inset-0 z-40 grid place-items-center bg-slate-950/50 p-4"><form className="w-full max-w-3xl rounded-lg bg-white shadow-xl" onSubmit={handleSubmit}><div className="flex items-center justify-between border-b border-slate-200 px-5 py-4"><h2 className="text-lg font-semibold">{editingFtpId ? "Sửa FTP" : "Thêm FTP độc lập"}</h2><button className="rounded-md p-2 text-slate-500" onClick={() => setModalOpen(false)} type="button"><X className="h-5 w-5" /></button></div><div className="grid gap-3 p-5 md:grid-cols-2">
        <label className="grid gap-1 text-sm">Tên FTP<input className="h-10 rounded-md border border-slate-300 px-3" onChange={(event) => updateField("name", event.target.value)} required value={form.name} /></label><label className="grid gap-1 text-sm">Host<input className="h-10 rounded-md border border-slate-300 px-3" onChange={(event) => updateField("host", event.target.value)} required value={form.host} /></label><label className="grid gap-1 text-sm">Port<input className="h-10 rounded-md border border-slate-300 px-3" min="1" max="65535" onChange={(event) => updateField("port", event.target.value)} required type="number" value={form.port} /></label><label className="grid gap-1 text-sm">User<input className="h-10 rounded-md border border-slate-300 px-3" onChange={(event) => updateField("user", event.target.value)} required value={form.user} /></label><label className="grid gap-1 text-sm">Mật khẩu{editingFtpId && <span className="text-xs text-slate-400">Để trống nếu không đổi</span>}<input className="h-10 rounded-md border border-slate-300 px-3" required={!editingFtpId} type="password" onChange={(event) => updateField("password", event.target.value)} value={form.password} /></label><label className="grid gap-1 text-sm">Thư mục gốc<input className="h-10 rounded-md border border-slate-300 px-3" onChange={(event) => updateField("root_path", event.target.value)} required value={form.root_path} /></label>
        <fieldset className="md:col-span-2"><legend className="text-sm font-semibold">Gán cho trạm</legend><div className="mt-2 grid max-h-40 gap-2 overflow-y-auto rounded-md border border-slate-200 p-3 sm:grid-cols-2">{stations.length === 0 ? <p className="text-sm text-slate-500">Chưa có trạm. FTP vẫn được lưu độc lập.</p> : stations.map((station) => <label className="flex items-center gap-2 text-sm" key={station.id}><input checked={form.station_ids.includes(station.id)} onChange={() => toggleStation(station.id)} type="checkbox" />{station.code} - {station.name}</label>)}</div><p className="mt-2 text-xs text-slate-500">Một FTP có thể gán cho nhiều trạm. Bỏ chọn tất cả để lưu FTP chưa gán.</p></fieldset>
      </div><div className="flex justify-end gap-2 border-t border-slate-200 px-5 py-4"><button className="mr-auto inline-flex items-center gap-2 rounded-md border border-cyan-700 px-3 py-2 text-sm font-semibold text-cyan-700" onClick={handleTest} type="button"><Server className="h-4 w-4" />Kiểm tra kết nối</button><button className="rounded-md border border-slate-300 px-4 py-2" onClick={() => setModalOpen(false)} type="button">Hủy</button><button className="rounded-md bg-cyan-700 px-4 py-2 font-semibold text-white disabled:opacity-50" disabled={saving} type="submit">{saving ? "Đang lưu..." : "Lưu FTP"}</button></div></form></div>}
    </section>
  );
}
