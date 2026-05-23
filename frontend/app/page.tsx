"use client";

import ActivityList from "./components/ActivityList";
import React, { useState, useEffect } from "react";
import Sidebar from "./components/Sidebar";
import StatCard from "./components/StatCard";
// import ActivityList from "./components/ActivityList";
// import Chat from "./components/Chat";

function MobileNav({ setShow }: { setShow: (v: boolean) => void }) {
  return (
    <div className="flex items-center bg-zinc-950 py-3 px-4 md:hidden shadow-lg">
      <button
        className="text-zinc-200 hover:text-white focus:outline-none mr-3"
        onClick={() => setShow(true)}
        aria-label="Open menu"
      >
        <svg className="w-7 h-7" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
          <path d="M4 6h16M4 12h16M4 18h16" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </button>
      <span className="font-extrabold text-lg tracking-tight text-white select-none">
        AI Coach
      </span>
    </div>
  );
}

export default function DashboardPage() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [stats, setStats] = useState<any>(null);

  useEffect(() => {
    fetch("http://13.233.55.51:8001/api/stats")
      .then((res) => res.json())
      .then((data) => {
        console.log("API Data:", data);
        setStats(data);
      })
      .catch((err) => {
        console.error("API Error:", err);
      });
  }, []);

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 flex font-sans transition-colors">
      <Sidebar show={sidebarOpen} setShow={setSidebarOpen} />

      <div className="flex-1 flex flex-col min-w-0">
        <MobileNav setShow={setSidebarOpen} />

        <main className="flex-1 flex flex-col py-6 px-4 md:py-8 md:px-10 w-full">
          <header className="mb-8">
            <h1 className="text-3xl md:text-4xl font-extrabold text-zinc-900 dark:text-zinc-50">
              Dashboard
            </h1>
            <p className="text-zinc-500 dark:text-zinc-300">
              Your AI-powered running insights
            </p>
          </header>

          {/* ✅ Stats Section */}
          <section className="grid gap-6 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 mb-6">
            {stats ? (
              <>
                <StatCard label="Total Distance (km)" value={stats.total_distance} />
                <StatCard label="Total Runs" value={stats.total_runs} />
                <StatCard label="Avg Pace" value={stats.avg_pace} />
              </>
            ) : (
              <p>Loading stats...</p>
            )}
          </section>

          {/* ❌ Disabled temporarily */}
           <ActivityList />
          {/* <Chat />*/}

        </main>
      </div>
    </div>
  );
}
