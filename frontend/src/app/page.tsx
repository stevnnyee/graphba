"use client";

import { useEffect, useState } from "react";
import GraphCanvas from "@/components/GraphCanvas";
import SearchBar from "@/components/SearchBar";
import ProfilePanel from "@/components/ProfilePanel";
import PathPanel from "@/components/PathPanel";
import EraSlider from "@/components/EraSlider";
import {
  getConnections,
  getPath,
  getProfile,
  type Graph,
  type PathResponse,
  type PlayerProfile,
  type PlayerSearchResult,
} from "@/lib/api";

// Roster data starts in 1990; the slider spans that to the current season.
const MIN_SEASON = 1990;
const MAX_SEASON = 2025;
const FEATURED = 2544; // LeBron James — a dense, recognizable starting graph.

type Mode = "explore" | "path";

export default function Home() {
  const [mode, setMode] = useState<Mode>("explore");
  const [era, setEra] = useState<[number, number]>([MIN_SEASON, MAX_SEASON]);

  const [focusId, setFocusId] = useState<number | null>(FEATURED);
  const [profile, setProfile] = useState<PlayerProfile | null>(null);
  const [graph, setGraph] = useState<Graph>({ nodes: [], links: [] });

  const [pathFrom, setPathFrom] = useState<PlayerSearchResult | null>(null);
  const [pathTo, setPathTo] = useState<PlayerSearchResult | null>(null);
  const [path, setPath] = useState<PathResponse | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [reloadKey, setReloadKey] = useState(0); // bump to retry the last fetch

  // A full-range era is equivalent to "all-time", so only send a window when
  // the user has actually narrowed it.
  const windowed = era[0] !== MIN_SEASON || era[1] !== MAX_SEASON;
  const fromYear = windowed ? era[0] : undefined;
  const toYear = windowed ? era[1] : undefined;

  // Explore mode: load the focus player's ego network + profile.
  useEffect(() => {
    if (mode !== "explore" || focusId == null) return;
    let cancelled = false;
    setLoading(true);
    setError(false);
    (async () => {
      try {
        const [g, p] = await Promise.all([
          getConnections(focusId, { limit: 30, from: fromYear, to: toYear }),
          getProfile(focusId),
        ]);
        if (!cancelled) {
          setGraph(g);
          setProfile(p);
        }
      } catch {
        if (!cancelled) setError(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [mode, focusId, fromYear, toYear, reloadKey]);

  // Path mode: once both endpoints are chosen, compute the chain and render it.
  useEffect(() => {
    if (mode !== "path" || !pathFrom || !pathTo) return;
    let cancelled = false;
    setLoading(true);
    setError(false);
    (async () => {
      try {
        const r = await getPath(pathFrom.id, pathTo.id, {
          from: fromYear,
          to: toYear,
        });
        if (!cancelled) {
          setPath(r);
          setGraph({ nodes: r.nodes, links: r.links });
          setProfile(null);
        }
      } catch {
        if (!cancelled) setError(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [mode, pathFrom, pathTo, fromYear, toYear, reloadKey]);

  function handleNodeClick(id: number) {
    setMode("explore");
    setFocusId(id);
  }

  function switchMode(next: Mode) {
    setMode(next);
    if (next === "explore") {
      setPath(null);
    }
  }

  function retry() {
    setError(false);
    setReloadKey((k) => k + 1);
  }

  // Explore landed but the focus player has no teammates in the current view.
  const showEmpty =
    !loading &&
    !error &&
    mode === "explore" &&
    focusId != null &&
    graph.nodes.length <= 1;

  const pathIds =
    mode === "path" && path?.found
      ? new Set(path.nodes.map((n) => n.id))
      : undefined;
  const highlightFocus = mode === "explore" ? focusId : (pathFrom?.id ?? null);

  return (
    <main className="relative h-screen w-screen overflow-hidden">
      <GraphCanvas
        data={graph}
        focusId={highlightFocus}
        pathIds={pathIds}
        onNodeClick={handleNodeClick}
      />

      {/* Brand */}
      <div className="pointer-events-none absolute top-5 left-5 z-10">
        <h1 className="text-sm font-bold tracking-tight">
          Graph<span className="text-accent">BA</span>
        </h1>
        <p className="text-[11px] text-white/35">Six degrees of NBA</p>
      </div>

      {/* Top-center controls */}
      <div className="absolute top-5 left-1/2 z-20 w-[min(92vw,460px)] -translate-x-1/2">
        <div className="mb-3 flex justify-center">
          <div className="glass flex rounded-full p-1 text-xs">
            {(["explore", "path"] as Mode[]).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => switchMode(m)}
                className={`rounded-full px-4 py-1.5 capitalize transition ${
                  mode === m
                    ? "bg-accent/20 text-accent"
                    : "text-white/50 hover:text-white/80"
                }`}
              >
                {m === "path" ? "Find path" : "Explore"}
              </button>
            ))}
          </div>
        </div>

        {mode === "explore" ? (
          <SearchBar onSelect={(p) => setFocusId(p.id)} />
        ) : (
          <div className="flex flex-col gap-2">
            <SearchBar
              placeholder={pathFrom ? `From: ${pathFrom.name}` : "From player…"}
              onSelect={setPathFrom}
            />
            <SearchBar
              placeholder={pathTo ? `To: ${pathTo.name}` : "To player…"}
              onSelect={setPathTo}
            />
          </div>
        )}
      </div>

      {mode === "explore" && <ProfilePanel profile={profile} />}
      {mode === "path" && (
        <PathPanel path={path} onClear={() => switchMode("explore")} />
      )}

      <EraSlider
        min={MIN_SEASON}
        max={MAX_SEASON}
        from={era[0]}
        to={era[1]}
        onChange={(f, t) => setEra([f, t])}
      />

      {/* Loading — non-blocking spinner over the canvas */}
      {loading && (
        <div className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center">
          <div className="border-t-accent h-9 w-9 animate-spin rounded-full border-2 border-white/15" />
        </div>
      )}

      {/* Empty — focus player has no connections in this era */}
      {showEmpty && (
        <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center">
          <p className="glass rounded-xl px-4 py-2 text-xs text-white/60">
            No teammates found{windowed ? " in this era" : ""}.
          </p>
        </div>
      )}

      {/* Error — blocking card with retry */}
      {error && (
        <div className="absolute inset-0 z-30 flex items-center justify-center">
          <div className="glass max-w-xs rounded-2xl p-6 text-center">
            <p className="text-sm font-semibold">Couldn’t reach the server</p>
            <p className="mt-1 text-xs leading-relaxed text-white/55">
              The backend may be offline. Make sure it’s running, then try
              again.
            </p>
            <button
              type="button"
              onClick={retry}
              className="bg-accent/20 text-accent hover:bg-accent/30 mt-4 rounded-lg px-4 py-2 text-xs font-medium transition"
            >
              Retry
            </button>
          </div>
        </div>
      )}
    </main>
  );
}
