import { Bell, Menu, Search, UserCircle } from "lucide-react";

import Sidebar from "./Sidebar.jsx";

export default function AdminLayout({ activePage, alertCount, children, globalSearch, onGlobalSearch, onNavigate }) {
  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      <div className="flex min-h-screen">
        <Sidebar activePage={activePage} onNavigate={onNavigate} />

        <div className="min-w-0 flex-1">
          <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-slate-200 bg-white px-4 shadow-sm lg:px-6">
            <div className="flex items-center gap-3">
              <button className="rounded-md border border-slate-200 p-2 text-slate-600 lg:hidden" type="button">
                <Menu className="h-5 w-5" />
              </button>
              <div className="relative w-[min(48vw,520px)] min-w-56">
                <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <input
                  className="h-10 w-full rounded-md border border-slate-300 bg-slate-50 pl-9 pr-3 text-sm outline-none focus:border-cyan-600 focus:bg-white"
                  onChange={(event) => onGlobalSearch(event.target.value)}
                  placeholder="Tim kiem tram, khu vuc, ma thiet bi"
                  value={globalSearch}
                />
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button className="relative rounded-md border border-slate-200 p-2 text-slate-600" type="button">
                <Bell className="h-5 w-5" />
                {alertCount > 0 && (
                  <span className="absolute -right-1 -top-1 grid h-5 min-w-5 place-items-center rounded-full bg-red-600 px-1 text-[11px] font-semibold text-white">
                    {alertCount}
                  </span>
                )}
              </button>
              <div className="hidden items-center gap-2 rounded-md border border-slate-200 px-3 py-2 md:flex">
                <UserCircle className="h-5 w-5 text-slate-500" />
                <div className="text-sm">
                  <p className="font-medium leading-none">Admin</p>
                  <p className="mt-1 text-xs text-slate-500">Super Admin</p>
                </div>
              </div>
            </div>
          </header>

          <main className="p-4 lg:p-6">{children}</main>
        </div>
      </div>
    </div>
  );
}
