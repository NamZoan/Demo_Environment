import { Activity, BarChart3, Camera, Database, FileCheck2, HardDrive, MapPinned, Settings, ShieldCheck, Siren } from "lucide-react";

const menuItems = [
  { id: "dashboard", label: "Điều hành tổng quan", icon: BarChart3 },
  { id: "stations", label: "WebGIS & Trạm", icon: MapPinned },
  { id: "parameters", label: "Dữ liệu quan trắc", icon: Activity },
  { id: "qcvn", label: "Cảnh báo QCVN", icon: Siren },
  { id: "approval", label: "Kiểm duyệt dữ liệu", icon: FileCheck2 },
  { id: "camera", label: "Camera & Lấy mẫu", icon: Camera },
  { id: "backend", label: "Backend & Database", icon: HardDrive },
  { id: "settings", label: "Cấu hình hệ thống", icon: Settings },
  { id: "rbac", label: "Phân quyền", icon: ShieldCheck },
];

export default function Sidebar({ activePage, onNavigate }) {
  return (
    <aside className="hidden w-72 shrink-0 border-r border-slate-200 bg-[#073b4c] text-white lg:block">
      <div className="flex h-20 items-center gap-3 border-b border-white/10 px-5">
        <div className="grid h-10 w-10 place-items-center rounded-md bg-white/10">
          <Database className="h-6 w-6 text-emerald-300" />
        </div>
        <div>
          <p className="text-sm font-semibold leading-tight">EnviSoft Control</p>
          <p className="text-xs text-cyan-100/75">Dữ liệu quan trắc tự động</p>
        </div>
      </div>

      <nav className="space-y-1 px-3 py-4">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const active = activePage === item.id;
          return (
            <button
              className={`flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-left text-sm transition ${
                active ? "bg-emerald-400 text-slate-950" : "text-cyan-50/80 hover:bg-white/10 hover:text-white"
              }`}
              key={item.id}
              onClick={() => onNavigate(item.id)}
              type="button"
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
