"use client";

import { useEffect, useRef, useState } from "react";
import { searchPlayers, type PlayerSearchResult } from "@/lib/api";

interface Props {
  placeholder?: string;
  onSelect: (player: PlayerSearchResult) => void;
}

export default function SearchBar({
  placeholder = "Search a player…",
  onSelect,
}: Props) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<PlayerSearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const boxRef = useRef<HTMLDivElement>(null);

  // Debounced search; the backend guards a 2-char minimum, so we mirror it.
  useEffect(() => {
    if (q.trim().length < 2) {
      setResults([]);
      return;
    }
    const t = setTimeout(async () => {
      try {
        const r = await searchPlayers(q.trim());
        setResults(r);
        setOpen(true);
        setActive(0);
      } catch {
        setResults([]);
      }
    }, 180);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  function choose(player: PlayerSearchResult) {
    onSelect(player);
    setQ("");
    setResults([]);
    setOpen(false);
  }

  return (
    <div ref={boxRef} className="relative w-full">
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onFocus={() => results.length > 0 && setOpen(true)}
        onKeyDown={(e) => {
          if (!open) return;
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setActive((a) => Math.min(a + 1, results.length - 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((a) => Math.max(a - 1, 0));
          } else if (e.key === "Enter" && results[active]) {
            choose(results[active]);
          } else if (e.key === "Escape") {
            setOpen(false);
          }
        }}
        placeholder={placeholder}
        className="glass w-full rounded-xl px-4 py-3 text-sm text-foreground outline-none transition placeholder:text-white/45 focus:ring-2 focus:ring-accent/60"
      />
      {open && results.length > 0 && (
        <ul className="glass absolute z-30 mt-2 w-full overflow-hidden rounded-xl">
          {results.map((p, i) => (
            <li key={p.id}>
              <button
                type="button"
                onMouseEnter={() => setActive(i)}
                onClick={() => choose(p)}
                className={`flex w-full items-center justify-between px-4 py-2.5 text-left text-sm transition ${
                  i === active ? "bg-accent/15" : "hover:bg-white/5"
                }`}
              >
                <span className="font-medium">{p.name}</span>
                <span className="text-xs text-white/40">{p.active_years}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
