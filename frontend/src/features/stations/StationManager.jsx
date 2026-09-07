import { flexRender, getCoreRowModel, getPaginationRowModel, useReactTable } from "@tanstack/react-table";
import { Edit2, Plus, Trash2, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { fetchFtpConfigs, fetchFtpFiles } from "../../api.js";

const statusOptions = [
  { value: "all", label: "Tất cả trạng thái" },
  { value: "online", label: "Online" },
  { value: "offline", label: "Offline" },
  { value: "maintenance", label: "Bảo trì" },
];

const statusStyles = { online: "bg-emerald-100 text-emerald-700", offline: "bg-slate-200 text-slate-700", maintenance: "bg-amber-100 text-amber-700" };

const initialForm = {
  code: "",
  name: "",
  address: "",
  type: "Không khí xung quanh",
  latitude: "",
  longitude: "",
  status: "active",
  ftp_assignment: { ftp_server_id: "", folder_path: "" },
};

function formFromStation(station) {
  return {
    ...initialForm,
    code: station.code || "",
    name: station.name || "",
    address: station.address || "",
    type: station.type || "Không khí xung quanh",
    latitude: station.latitude ?? "",
    longitude: station.longitude ?? "",
    status: station.status === "maintenance" ? "maintenance" : "active",
    ftp_assignment: station.ftp_assignment
      ? { ftp_server_id: String(station.ftp_assignment.ftp_server_id), folder_path: station.ftp_assignment.folder_path }
      : { ...initialForm.ftp_assignment },
  };
}

export default function StationManager({ currentUser, onCreateStation, onDeleteStation, onEditStation, onOpenDetails, stations }) {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [modalOpen, setModalOpen] = useState(false);
  const [editingStation, setEditingStation] = useState(null);
  const [form, setForm] = useState(initialForm);
  const [ftpConfigs, setFtpConfigs] = useState([]);
  const [ftpFolders, setFtpFolders] = useState([]);
  const [ftpFoldersLoading, setFtpFoldersLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");

  useEffect(() => {
    fetchFtpConfigs(currentUser).then(setFtpConfigs).catch((error) => setFormError(error.message));
  }, [currentUser]);

  useEffect(() => {
    const ftpId = form.ftp_assignment.ftp_server_id;
    if (!ftpId) {
      setFtpFolders([]);
      return;
    }
    const ftpConfig = ftpConfigs.find((config) => String(config.id) === String(ftpId));
    const rootPath = ftpConfig?.root_path || "/data";
    setFtpFoldersLoading(true);
    fetchFtpFiles({ path: rootPath, ftpId, currentUser })
      .then((listing) => {
        if (listing.error) throw new Error(listing.error);
        setFtpFolders((listing.entries || []).filter((entry) => entry.type === "folder"));
      })
      .catch((error) => {
        setFtpFolders([]);
        setFormError(error.message);
      })
      .finally(() => setFtpFoldersLoading(false));
  }, [currentUser, ftpConfigs, form.ftp_assignment.ftp_server_id]);

  const filteredStations = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    return stations.filter((station) => {
      const matchesSearch = !normalized || station.name.toLowerCase().includes(normalized) || station.code.toLowerCase().includes(normalized) || station.region.toLowerCase().includes(normalized);
      const matchesStatus = statusFilter === "all" || station.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [search, statusFilter, stations]);

  const columns = useMemo(() => [
    { accessorKey: "id", header: "ID", cell: ({ row }) => <span className="font-mono text-xs text-slate-500">#{row.original.id}</span> },
    { accessorKey: "name", header: "Tên trạm", cell: ({ row }) => <button className="text-left" onClick={() => onOpenDetails(row.original)} type="button"><span className="block font-medium text-slate-900">{row.original.name}</span><span className="block text-xs text-slate-500">{row.original.code}</span></button> },
    { accessorKey: "type", header: "Loại hình", cell: ({ row }) => <span className="text-xs text-slate-600">{row.original.type}</span> },
    { accessorKey: "coordinates", header: "Tọa độ", cell: ({ row }) => <span className="text-xs text-slate-600">{row.original.latitude ?? "—"}, {row.original.longitude ?? "—"}</span> },
    { accessorKey: "status", header: "Trạng thái", cell: ({ row }) => <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${statusStyles[row.original.status] || statusStyles.offline}`}>{statusOptions.find((item) => item.value === row.original.status)?.label || row.original.status}</span> },
    { id: "actions", header: "Hành động", cell: ({ row }) => <div className="flex justify-end gap-2"><button className="rounded-md border border-slate-200 p-2 text-slate-600 hover:bg-slate-50" onClick={() => openEdit(row.original)} title="Sửa" type="button"><Edit2 className="h-4 w-4" /></button><button className="rounded-md border border-red-200 p-2 text-red-600 hover:bg-red-50" onClick={() => handleDelete(row.original)} title="Xóa" type="button"><Trash2 className="h-4 w-4" /></button></div> },
  ], [onDeleteStation, onEditStation, onOpenDetails]);

  const table = useReactTable({ columns, data: filteredStations, getCoreRowModel: getCoreRowModel(), getPaginationRowModel: getPaginationRowModel(), initialState: { pagination: { pageSize: 12 } } });

  function openCreate() {
    setEditingStation(null);
    setForm({ ...initialForm, ftp_assignment: { ...initialForm.ftp_assignment } });
    setFormError("");
    setModalOpen(true);
  }

  function openEdit(station) {
    setEditingStation(station);
    setForm(formFromStation(station));
    setFormError("");
    setModalOpen(true);
  }

  function updateField(field, value) { setForm((current) => ({ ...current, [field]: value })); }
  function updateFtpAssignment(field, value) {
    setForm((current) => ({ ...current, ftp_assignment: { ...current.ftp_assignment, [field]: value } }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSaving(true);
    setFormError("");
    try {
      const payload = { code: form.code.trim(), name: form.name.trim(), address: form.address.trim() || null, latitude: Number(form.latitude), longitude: Number(form.longitude), status: form.status, metadata: { type: form.type } };
      if (!form.ftp_assignment.ftp_server_id || !form.ftp_assignment.folder_path) throw new Error("Vui lòng chọn máy FTP và folder dữ liệu");
      payload.ftp_assignment = { ftp_server_id: Number(form.ftp_assignment.ftp_server_id), folder_path: form.ftp_assignment.folder_path };
      if (editingStation) await onEditStation(editingStation.id, payload);
      else await onCreateStation(payload);
      setModalOpen(false);
      setForm(initialForm);
    } catch (error) {
      setFormError(error.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(station) {
    if (!window.confirm(`Xóa trạm ${station.code} - ${station.name}? Dữ liệu liên quan có thể bị xóa theo trạm.`)) return;
    try {
      await onDeleteStation(station.id);
    } catch (error) {
      setFormError(error.message);
    }
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-center"><div><h1 className="text-2xl font-semibold text-slate-950">WebGIS & Quản lý trạm</h1><p className="mt-1 text-sm text-slate-500">Quản lý trạm và nhập trực tiếp địa chỉ, vĩ độ, kinh độ.</p></div><button className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-cyan-700 px-4 text-sm font-semibold text-white hover:bg-cyan-800" onClick={openCreate} type="button"><Plus className="h-4 w-4" />Thêm trạm mới</button></div>
      <div className="rounded-lg border border-slate-200 bg-white"><div className="grid gap-3 border-b border-slate-200 p-4 md:grid-cols-[1fr_220px]"><input className="h-10 rounded-md border border-slate-300 px-3 text-sm outline-none focus:border-cyan-600" onChange={(event) => setSearch(event.target.value)} placeholder="Tìm theo tên trạm, mã trạm, khu vực" value={search} /><select className="h-10 rounded-md border border-slate-300 px-3 text-sm outline-none focus:border-cyan-600" onChange={(event) => setStatusFilter(event.target.value)} value={statusFilter}>{statusOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></div><div className="overflow-x-auto"><table className="w-full min-w-[920px] border-collapse text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500">{table.getHeaderGroups().map((headerGroup) => <tr key={headerGroup.id}>{headerGroup.headers.map((header) => <th className="border-b border-slate-200 px-4 py-3 text-left font-semibold" key={header.id}>{flexRender(header.column.columnDef.header, header.getContext())}</th>)}</tr>)}</thead><tbody>{table.getRowModel().rows.map((row) => <tr className="hover:bg-slate-50" key={row.id}>{row.getVisibleCells().map((cell) => <td className="border-b border-slate-100 px-4 py-3" key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>)}</tr>)}</tbody></table></div><div className="flex flex-col gap-3 p-4 text-sm text-slate-600 md:flex-row md:items-center md:justify-between"><span>Hiển thị {table.getRowModel().rows.length} / {filteredStations.length} trạm</span><div className="flex items-center gap-2"><button className="rounded-md border border-slate-300 px-3 py-2 disabled:opacity-40" disabled={!table.getCanPreviousPage()} onClick={() => table.previousPage()} type="button">Trước</button><span>Trang {table.getState().pagination.pageIndex + 1} / {Math.max(table.getPageCount(), 1)}</span><button className="rounded-md border border-slate-300 px-3 py-2 disabled:opacity-40" disabled={!table.getCanNextPage()} onClick={() => table.nextPage()} type="button">Sau</button></div></div></div>

      {modalOpen && <div className="fixed inset-0 z-40 grid place-items-center bg-slate-950/50 p-4"><form className="max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-lg bg-white shadow-xl" onSubmit={handleSubmit}><div className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white px-5 py-4"><h2 className="text-lg font-semibold">{editingStation ? "Sửa trạm" : "Thêm trạm mới"}</h2><button className="rounded-md p-2 text-slate-500 hover:bg-slate-100" onClick={() => setModalOpen(false)} type="button"><X className="h-5 w-5" /></button></div><div className="grid gap-4 p-5 md:grid-cols-2">
        <label className="grid gap-1 text-sm">Mã trạm<input className="h-10 rounded-md border border-slate-300 px-3" onChange={(event) => updateField("code", event.target.value)} required value={form.code} /></label><label className="grid gap-1 text-sm">Tên trạm<input className="h-10 rounded-md border border-slate-300 px-3" onChange={(event) => updateField("name", event.target.value)} required value={form.name} /></label><label className="grid gap-1 text-sm md:col-span-2">Địa chỉ<input className="h-10 rounded-md border border-slate-300 px-3" onChange={(event) => updateField("address", event.target.value)} value={form.address} /></label><label className="grid gap-1 text-sm">Loại hình quan trắc<select className="h-10 rounded-md border border-slate-300 px-3" onChange={(event) => updateField("type", event.target.value)} value={form.type}><option>Không khí xung quanh</option><option>Nước mặt</option><option>Nước thải</option><option>Khí thải</option></select></label>{editingStation && <label className="grid gap-1 text-sm">Trạng thái<select className="h-10 rounded-md border border-slate-300 px-3" onChange={(event) => updateField("status", event.target.value)} value={form.status}><option value="active">Đang hoạt động</option><option value="maintenance">Bảo trì</option></select></label>}
        <label className="grid gap-1 text-sm">Vĩ độ <span className="text-xs text-slate-500">-90 đến 90</span><input className="h-10 rounded-md border border-slate-300 px-3" max="90" min="-90" onChange={(event) => updateField("latitude", event.target.value)} required step="any" type="number" value={form.latitude} /></label><label className="grid gap-1 text-sm">Kinh độ <span className="text-xs text-slate-500">-180 đến 180</span><input className="h-10 rounded-md border border-slate-300 px-3" max="180" min="-180" onChange={(event) => updateField("longitude", event.target.value)} required step="any" type="number" value={form.longitude} /></label>
        <fieldset className="space-y-3 rounded-md border border-slate-200 p-4 md:col-span-2"><legend className="px-1 text-sm font-semibold text-slate-800">Nguồn dữ liệu FTP</legend><div className="grid gap-3 md:grid-cols-2"><label className="grid gap-1 text-sm">Máy chủ FTP<select className="h-10 rounded-md border border-slate-300 bg-white px-3" onChange={(event) => { updateFtpAssignment("ftp_server_id", event.target.value); updateFtpAssignment("folder_path", ""); }} required value={form.ftp_assignment.ftp_server_id}><option value="">Chọn máy chủ FTP</option>{ftpConfigs.map((config) => <option key={config.id} value={config.id}>{config.name} — {config.host}:{config.port}</option>)}</select></label><label className="grid gap-1 text-sm">Folder dữ liệu<select className="h-10 rounded-md border border-slate-300 bg-white px-3" disabled={!form.ftp_assignment.ftp_server_id || ftpFoldersLoading} onChange={(event) => updateFtpAssignment("folder_path", event.target.value)} required value={form.ftp_assignment.folder_path}><option value="">{ftpFoldersLoading ? "Đang tải folder..." : "Chọn folder"}</option>{form.ftp_assignment.folder_path && !ftpFolders.some((entry) => entry.path === form.ftp_assignment.folder_path) && <option value={form.ftp_assignment.folder_path}>{form.ftp_assignment.folder_path}</option>}{ftpFolders.map((entry) => <option key={entry.path} value={entry.path}>{entry.name} — {entry.path}</option>)}</select></label></div><p className="text-xs text-slate-500">Mỗi folder chỉ được gán cho một trạm. Có thể đổi máy FTP hoặc folder trong chức năng Sửa trạm.</p></fieldset>
      </div><div className="flex justify-end gap-2 border-t border-slate-200 px-5 py-4">{formError && <p className="mr-auto self-center text-sm text-red-700">{formError}</p>}<button className="rounded-md border border-slate-300 px-4 py-2" onClick={() => setModalOpen(false)} type="button">Hủy</button><button className="rounded-md bg-cyan-700 px-4 py-2 font-semibold text-white disabled:opacity-50" disabled={saving} type="submit">{saving ? "Đang lưu..." : editingStation ? "Lưu thay đổi" : "Lưu trạm"}</button></div></form></div>}
    </section>
  );
}
