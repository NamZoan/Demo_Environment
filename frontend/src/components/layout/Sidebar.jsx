import { Activity, BarChart3, Database, MapPinned, Settings, ShieldCheck } from "lucide-react";

const menuItems = [
  { id: "dashboard", label: "Dashboard", icon: BarChart3 },
  { id: "stations", label: "Quan ly tram", icon: MapPinned },
  { id: "parameters", label: "Du lieu thong so", icon: Activity },
  { id: "settings", label: "Cai dat he thong", icon: Settings },
  { id: "rbac", label: "Phan quyen", icon: ShieldCheck },
];

export default function Sidebar({ activePage, onNavigate }) {
  return (
    <aside className="hidden w-72 shrink-0 border-r border-slate-200 bg-slate-950 text-white lg:block">
      <div className="flex h-16 items-center gap-3 border-b border-white/10 px-5">
        <Database className="h-6 w-6 text-cyan-300" />
        <div>
          <p className="text-sm font-semibold leading-tight">Enviro CMS</p>
          <p className="text-xs text-slate-400">Monitoring Operations</p>
        </div>
      </div>

      <nav className="space-y-1 px-3 py-4">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const active = activePage === item.id;
          return (
            <button
              className={`flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-left text-sm transition ${
                active ? "bg-cyan-500 text-slate-950" : "text-slate-300 hover:bg-white/10 hover:text-white"
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
