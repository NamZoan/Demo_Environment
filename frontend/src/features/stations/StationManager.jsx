import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { Edit2, MapPin, Plus, Trash2, X } from "lucide-react";
import { useMemo, useState } from "react";

import CoordinatePicker from "../../components/map/CoordinatePicker.jsx";

const statusOptions = [
  { value: "all", label: "Tat ca trang thai" },
  { value: "online", label: "Online" },
  { value: "offline", label: "Offline" },
  { value: "maintenance", label: "Bao tri" },
];

const statusStyles = {
  online: "bg-emerald-100 text-emerald-700",
  offline: "bg-slate-200 text-slate-700",
  maintenance: "bg-amber-100 text-amber-700",
};

const initialForm = {
  name: "",
  region: "Ha Noi",
  latitude: 21.0278,
  longitude: 105.8342,
};

export default function StationManager({ onCreateStation, onDeleteStation, onOpenDetails, stations }) {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState(initialForm);

  const filteredStations = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    return stations.filter((station) => {
      const matchesSearch =
        !normalized ||
        station.name.toLowerCase().includes(normalized) ||
        station.code.toLowerCase().includes(normalized) ||
        station.region.toLowerCase().includes(normalized);
      const matchesStatus = statusFilter === "all" || station.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [search, statusFilter, stations]);

  const columns = useMemo(
    () => [
      {
        accessorKey: "id",
        header: "ID",
        cell: ({ row }) => <span className="font-mono text-xs text-slate-500">#{row.original.id}</span>,
      },
      {
        accessorKey: "name",
        header: "Ten tram",
        cell: ({ row }) => (
          <button className="text-left" onClick={() => onOpenDetails(row.original)} type="button">
            <span className="block font-medium text-slate-900">{row.original.name}</span>
            <span className="block text-xs text-slate-500">{row.original.code}</span>
          </button>
        ),
      },
      {
        accessorKey: "coordinates",
        header: "Toa do",
        cell: ({ row }) => (
          <span className="text-xs text-slate-600">
            {row.original.latitude}, {row.original.longitude}
          </span>
        ),
      },
      {
        accessorKey: "status",
        header: "Trang thai",
        cell: ({ row }) => (
          <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${statusStyles[row.original.status]}`}>
            {statusOptions.find((item) => item.value === row.original.status)?.label || row.original.status}
          </span>
        ),
      },
      {
        id: "actions",
        header: "Hanh dong",
        cell: ({ row }) => (
          <div className="flex justify-end gap-2">
            <button
              className="rounded-md border border-slate-200 p-2 text-slate-600 hover:bg-slate-50"
              onClick={() => onOpenDetails(row.original)}
              title="Edit"
              type="button"
            >
              <Edit2 className="h-4 w-4" />
            </button>
            <button
              className="rounded-md border border-red-200 p-2 text-red-600 hover:bg-red-50"
              onClick={() => onDeleteStation(row.original.id)}
              title="Delete"
              type="button"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ),
      },
    ],
    [onDeleteStation, onOpenDetails],
  );

  const table = useReactTable({
    columns,
    data: filteredStations,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 12 } },
  });

  function handleSubmit(event) {
    event.preventDefault();
    onCreateStation(form);
    setModalOpen(false);
    setForm(initialForm);
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-center">
        <div>
          <h1 className="text-2xl font-semibold text-slate-950">Quan ly tram</h1>
          <p className="mt-1 text-sm text-slate-500">Quan ly 2000 tram quan trac ngoai troi theo khu vuc.</p>
        </div>
        <button
          className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-cyan-700 px-4 text-sm font-semibold text-white hover:bg-cyan-800"
          onClick={() => setModalOpen(true)}
          type="button"
        >
          <Plus className="h-4 w-4" />
          Them tram moi
        </button>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white">
        <div className="grid gap-3 border-b border-slate-200 p-4 md:grid-cols-[1fr_220px]">
          <input
            className="h-10 rounded-md border border-slate-300 px-3 text-sm outline-none focus:border-cyan-600"
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Tim theo ten tram, ma tram, khu vuc"
            value={search}
          />
          <select
            className="h-10 rounded-md border border-slate-300 px-3 text-sm outline-none focus:border-cyan-600"
            onChange={(event) => setStatusFilter(event.target.value)}
            value={statusFilter}
          >
            {statusOptions.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[780px] border-collapse text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              {table.getHeaderGroups().map((headerGroup) => (
                <tr key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <th className="border-b border-slate-200 px-4 py-3 text-left font-semibold" key={header.id}>
                      {flexRender(header.column.columnDef.header, header.getContext())}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row) => (
                <tr className="hover:bg-slate-50" key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <td className="border-b border-slate-100 px-4 py-3" key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex flex-col gap-3 p-4 text-sm text-slate-600 md:flex-row md:items-center md:justify-between">
          <span>
            Hien thi {table.getRowModel().rows.length} / {filteredStations.length} tram
          </span>
          <div className="flex items-center gap-2">
            <button
              className="rounded-md border border-slate-300 px-3 py-2 disabled:opacity-40"
              disabled={!table.getCanPreviousPage()}
              onClick={() => table.previousPage()}
              type="button"
            >
              Truoc
            </button>
            <span>
              Trang {table.getState().pagination.pageIndex + 1} / {table.getPageCount()}
            </span>
            <button
              className="rounded-md border border-slate-300 px-3 py-2 disabled:opacity-40"
              disabled={!table.getCanNextPage()}
              onClick={() => table.nextPage()}
              type="button"
            >
              Sau
            </button>
          </div>
        </div>
      </div>

      {modalOpen && (
        <div className="fixed inset-0 z-40 grid place-items-center bg-slate-950/50 p-4">
          <form className="w-full max-w-2xl rounded-lg bg-white shadow-xl" onSubmit={handleSubmit}>
            <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
              <h2 className="text-lg font-semibold">Them tram moi</h2>
              <button className="rounded-md p-2 text-slate-500 hover:bg-slate-100" onClick={() => setModalOpen(false)} type="button">
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="grid gap-4 p-5 md:grid-cols-2">
              <label className="grid gap-1 text-sm">
                Ten tram
                <input
                  className="h-10 rounded-md border border-slate-300 px-3"
                  onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                  required
                  value={form.name}
                />
              </label>
              <label className="grid gap-1 text-sm">
                Khu vuc
                <input
                  className="h-10 rounded-md border border-slate-300 px-3"
                  onChange={(event) => setForm((current) => ({ ...current, region: event.target.value }))}
                  value={form.region}
                />
              </label>
              <div className="md:col-span-2">
                <div className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-700">
                  <MapPin className="h-4 w-4" />
                  Chon toa do tren ban do
                </div>
                <CoordinatePicker
                  latitude={form.latitude}
                  longitude={form.longitude}
                  onChange={(coords) => setForm((current) => ({ ...current, ...coords }))}
                />
                <p className="mt-2 text-xs text-slate-500">
                  Lat {form.latitude}, Lng {form.longitude}
                </p>
              </div>
            </div>
            <div className="flex justify-end gap-2 border-t border-slate-200 px-5 py-4">
              <button className="rounded-md border border-slate-300 px-4 py-2" onClick={() => setModalOpen(false)} type="button">
                Huy
              </button>
              <button className="rounded-md bg-cyan-700 px-4 py-2 font-semibold text-white" type="submit">
                Luu tram
              </button>
            </div>
          </form>
        </div>
      )}
    </section>
  );
}
