import { Edit3, Plus, UserX, X } from "lucide-react";
import { useEffect, useState } from "react";

import { createRbacUser, disableRbacUser, fetchRbacOptions, fetchRbacUsers, updateRbacUser } from "../../api.js";

const emptyForm = { username: "", password: "", full_name: "", role: "viewer", status: "active", region_ids: [] };

function roleName(options, code) {
  return options.roles.find((role) => role.code === code)?.name || code;
}

function regionNames(options, ids) {
  return ids.map((id) => options.regions.find((region) => region.id === id)?.name || id).join(", ") || "Toàn hệ thống";
}

export default function RbacManagement({ currentUser }) {
  const [users, setUsers] = useState([]);
  const [options, setOptions] = useState({ roles: [], regions: [] });
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [message, setMessage] = useState(null);

  async function load() {
    setLoading(true);
    try {
      const [loadedUsers, loadedOptions] = await Promise.all([fetchRbacUsers(currentUser), fetchRbacOptions(currentUser)]);
      setUsers(loadedUsers);
      setOptions(loadedOptions);
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
    setEditingUser(null);
    setForm(emptyForm);
    setModalOpen(true);
  }

  function openEdit(user) {
    setEditingUser(user);
    setForm({ username: user.username, password: "", full_name: user.full_name || "", role: user.roles[0] || user.role || "viewer", status: user.status, region_ids: user.region_ids || [] });
    setModalOpen(true);
  }

  function updateField(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function toggleRegion(regionId) {
    setForm((current) => ({
      ...current,
      region_ids: current.region_ids.includes(regionId) ? current.region_ids.filter((id) => id !== regionId) : [...current.region_ids, regionId],
    }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    try {
      const payload = { full_name: form.full_name, role: form.role, status: form.status, region_ids: form.region_ids };
      if (!editingUser) Object.assign(payload, { username: form.username, password: form.password });
      if (editingUser && form.password) payload.password = form.password;
      if (editingUser) {
        await updateRbacUser(editingUser.id, payload, currentUser);
      } else {
        await createRbacUser(payload, currentUser);
      }
      setModalOpen(false);
      setMessage({ tone: "success", text: editingUser ? "Đã cập nhật người dùng" : "Đã tạo người dùng" });
      await load();
    } catch (error) {
      setMessage({ tone: "error", text: error.message });
    }
  }

  async function handleDisable(user) {
    if (!window.confirm(`Vô hiệu hóa tài khoản ${user.username}?`)) return;
    try {
      await disableRbacUser(user.id, currentUser);
      setMessage({ tone: "success", text: "Đã vô hiệu hóa tài khoản" });
      await load();
    } catch (error) {
      setMessage({ tone: "error", text: error.message });
    }
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-end">
        <div>
          <h1 className="text-2xl font-semibold text-slate-950">Phân quyền</h1>
          <p className="mt-1 text-sm text-slate-500">Quản lý tài khoản, vai trò và phạm vi khu vực được phép truy cập.</p>
        </div>
        <button className="inline-flex items-center justify-center gap-2 rounded-md bg-cyan-700 px-3 py-2 text-sm font-semibold text-white" onClick={openCreate} type="button">
          <Plus className="h-4 w-4" /> Thêm người dùng
        </button>
      </div>

      {message && <p className={`rounded-md px-3 py-2 text-sm ${message.tone === "error" ? "bg-red-50 text-red-700" : "bg-emerald-50 text-emerald-700"}`}>{message.text}</p>}

      <section className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr><th className="px-4 py-3">Tài khoản</th><th className="px-4 py-3">Vai trò</th><th className="px-4 py-3">Khu vực</th><th className="px-4 py-3">Trạng thái</th><th className="px-4 py-3 text-right">Hành động</th></tr></thead>
            <tbody>
              {loading ? <tr><td className="px-4 py-8 text-center text-slate-500" colSpan="5">Đang tải danh sách...</td></tr> : users.length === 0 ? <tr><td className="px-4 py-8 text-center text-slate-500" colSpan="5">Chưa có người dùng hoặc tài khoản hiện tại không có quyền quản trị.</td></tr> : users.map((user) => (
                <tr className="border-t border-slate-100" key={user.id}>
                  <td className="px-4 py-3"><p className="font-medium text-slate-900">{user.username}</p><p className="text-xs text-slate-500">{user.full_name || "Chưa cập nhật"}</p></td>
                  <td className="px-4 py-3">{roleName(options, user.roles[0] || user.role)}</td>
                  <td className="max-w-xs px-4 py-3 text-slate-600">{regionNames(options, user.region_ids)}</td>
                  <td className="px-4 py-3"><span className={`rounded-full px-2 py-1 text-xs font-medium ${user.status === "active" ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>{user.status === "active" ? "Đang hoạt động" : "Đã vô hiệu hóa"}</span></td>
                  <td className="px-4 py-3 text-right"><div className="inline-flex gap-2"><button className="rounded-md border border-slate-300 p-2 text-slate-600 hover:bg-slate-50" onClick={() => openEdit(user)} title="Sửa" type="button"><Edit3 className="h-4 w-4" /></button>{user.status === "active" && user.id !== currentUser?.id && <button className="rounded-md border border-red-200 p-2 text-red-600 hover:bg-red-50" onClick={() => handleDisable(user)} title="Vô hiệu hóa" type="button"><UserX className="h-4 w-4" /></button>}</div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {modalOpen && <div className="fixed inset-0 z-40 grid place-items-center bg-slate-950/50 p-4"><form className="w-full max-w-2xl rounded-lg bg-white shadow-xl" onSubmit={handleSubmit}><div className="flex items-center justify-between border-b border-slate-200 px-5 py-4"><h2 className="text-lg font-semibold">{editingUser ? "Sửa người dùng" : "Thêm người dùng"}</h2><button className="rounded-md p-2 text-slate-500" onClick={() => setModalOpen(false)} type="button"><X className="h-5 w-5" /></button></div><div className="grid gap-3 p-5 md:grid-cols-2">
        {!editingUser && <label className="grid gap-1 text-sm">Tên đăng nhập<input className="h-10 rounded-md border border-slate-300 px-3" onChange={(event) => updateField("username", event.target.value)} required value={form.username} /></label>}
        <label className="grid gap-1 text-sm">Họ và tên<input className="h-10 rounded-md border border-slate-300 px-3" onChange={(event) => updateField("full_name", event.target.value)} value={form.full_name} /></label>
        <label className="grid gap-1 text-sm">Mật khẩu{editingUser && <span className="text-xs text-slate-400">Để trống nếu không đổi</span>}<input className="h-10 rounded-md border border-slate-300 px-3" minLength="8" onChange={(event) => updateField("password", event.target.value)} required={!editingUser} type="password" value={form.password} /></label>
        <label className="grid gap-1 text-sm">Vai trò<select className="h-10 rounded-md border border-slate-300 px-3" onChange={(event) => updateField("role", event.target.value)} value={form.role}>{options.roles.map((role) => <option key={role.code} value={role.code}>{role.name}</option>)}</select></label>
        {editingUser && <label className="grid gap-1 text-sm">Trạng thái<select className="h-10 rounded-md border border-slate-300 px-3" onChange={(event) => updateField("status", event.target.value)} value={form.status}><option value="active">Đang hoạt động</option><option value="inactive">Đã vô hiệu hóa</option></select></label>}
        <fieldset className="md:col-span-2"><legend className="text-sm font-medium">Khu vực được truy cập</legend><div className="mt-2 grid gap-2 sm:grid-cols-2">{options.regions.map((region) => <label className="flex items-center gap-2 text-sm text-slate-700" key={region.id}><input checked={form.region_ids.includes(region.id)} onChange={() => toggleRegion(region.id)} type="checkbox" />{region.name} ({region.code})</label>)}</div><p className="mt-2 text-xs text-slate-500">Super Admin vẫn xem được toàn bộ khu vực.</p></fieldset>
      </div><div className="flex justify-end gap-2 border-t border-slate-200 px-5 py-4"><button className="rounded-md border border-slate-300 px-3 py-2 text-sm" onClick={() => setModalOpen(false)} type="button">Hủy</button><button className="rounded-md bg-cyan-700 px-3 py-2 text-sm font-semibold text-white" type="submit">Lưu</button></div></form></div>}
    </section>
  );
}
