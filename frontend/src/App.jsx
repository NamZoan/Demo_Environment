import { Activity, AlertTriangle, MapPinned, ServerCog } from "lucide-react";
import { useMemo, useState } from "react";

import AdminLayout from "./components/layout/AdminLayout.jsx";
import StationManager from "./features/stations/StationManager.jsx";
import StationParameters from "./features/stations/StationParameters.jsx";
import { addStation, createMockStations } from "./services/mockApi.js";

function Dashboard({ stations, onOpenStations }) {
  const counts = useMemo(
    () =>
      stations.reduce(
        (summary, station) => {
          summary[station.status] += 1;
          return summary;
        },
        { total: stations.length, online: 0, offline: 0, maintenance: 0 },
      ),
    [stations],
  );

  const cards = [
    { label: "Tong tram", value: counts.total, icon: MapPinned, tone: "bg-cyan-50 text-cyan-800" },
    { label: "Dang online", value: counts.online, icon: Activity, tone: "bg-emerald-50 text-emerald-800" },
    { label: "Mat tin hieu", value: counts.offline, icon: AlertTriangle, tone: "bg-red-50 text-red-800" },
    { label: "Bao tri", value: counts.maintenance, icon: ServerCog, tone: "bg-amber-50 text-amber-800" },
  ];

  return (
    <section className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold text-slate-950">Dashboard</h1>
        <p className="mt-1 text-sm text-slate-500">Tong quan van hanh he thong quan trac moi truong.</p>
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => {
          const Icon = card.icon;
          return (
            <article className={`rounded-lg border border-slate-200 p-4 ${card.tone}`} key={card.label}>
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">{card.label}</span>
                <Icon className="h-5 w-5" />
              </div>
              <strong className="mt-4 block text-3xl">{card.value}</strong>
            </article>
          );
        })}
      </div>
      <button className="rounded-md bg-cyan-700 px-4 py-2 text-sm font-semibold text-white" onClick={onOpenStations} type="button">
        Mo trang quan ly tram
      </button>
    </section>
  );
}

function PlaceholderPage({ title }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-8">
      <h1 className="text-2xl font-semibold text-slate-950">{title}</h1>
      <p className="mt-2 text-sm text-slate-500">Module nay da co vi tri trong layout CMS va san sang noi API that.</p>
    </section>
  );
}

export default function App() {
  const [activePage, setActivePage] = useState("dashboard");
  const [globalSearch, setGlobalSearch] = useState("");
  const [selectedStation, setSelectedStation] = useState(null);
  const [stations, setStations] = useState(() => createMockStations());

  const visibleStations = useMemo(() => {
    const normalized = globalSearch.trim().toLowerCase();
    if (!normalized) return stations;
    return stations.filter(
      (station) =>
        station.name.toLowerCase().includes(normalized) ||
        station.code.toLowerCase().includes(normalized) ||
        station.region.toLowerCase().includes(normalized),
    );
  }, [globalSearch, stations]);

  const alertCount = stations.filter((station) => station.status === "offline" || station.metrics.pm25 >= 80).length;

  function openDetails(station) {
    setSelectedStation(station);
    setActivePage("parameters");
  }

  function createStation(payload) {
    setStations((current) => addStation(current, payload));
  }

  function deleteStation(stationId) {
    setStations((current) => current.filter((station) => station.id !== stationId));
    if (selectedStation?.id === stationId) {
      setSelectedStation(null);
    }
  }

  function renderPage() {
    if (activePage === "dashboard") {
      return <Dashboard onOpenStations={() => setActivePage("stations")} stations={stations} />;
    }
    if (activePage === "stations") {
      return (
        <StationManager
          onCreateStation={createStation}
          onDeleteStation={deleteStation}
          onOpenDetails={openDetails}
          stations={visibleStations}
        />
      );
    }
    if (activePage === "parameters") {
      return selectedStation ? (
        <StationParameters onBack={() => setActivePage("stations")} station={selectedStation} />
      ) : (
        <StationManager
          onCreateStation={createStation}
          onDeleteStation={deleteStation}
          onOpenDetails={openDetails}
          stations={visibleStations}
        />
      );
    }
    if (activePage === "settings") return <PlaceholderPage title="Cai dat he thong" />;
    if (activePage === "rbac") return <PlaceholderPage title="Phan quyen" />;
    return <PlaceholderPage title="Du lieu thong so" />;
  }

  return (
    <AdminLayout
      activePage={activePage}
      alertCount={alertCount}
      globalSearch={globalSearch}
      onGlobalSearch={setGlobalSearch}
      onNavigate={setActivePage}
    >
      {renderPage()}
    </AdminLayout>
  );
}
