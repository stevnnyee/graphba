"use client";

import { AnimatePresence, motion } from "framer-motion";
import { seasonSpan, type PathResponse } from "@/lib/api";

interface Props {
  path: PathResponse | null;
  onClear: () => void;
}

export default function PathPanel({ path, onClear }: Props) {
  return (
    <AnimatePresence>
      {path && (
        <motion.div
          initial={{ y: 24, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 24, opacity: 0 }}
          transition={{ type: "spring", stiffness: 300, damping: 30 }}
          className="glass pointer-events-auto absolute left-4 top-28 z-10 w-80 rounded-2xl p-5"
        >
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold">
              {path.found
                ? `${path.links.length} ${path.links.length === 1 ? "degree" : "degrees"} of separation`
                : "No connection"}
            </h2>
            <button
              type="button"
              onClick={onClear}
              className="text-xs text-white/40 transition hover:text-white"
            >
              clear
            </button>
          </div>

          {!path.found ? (
            <p className="mt-3 text-xs leading-relaxed text-white/50">
              No teammate chain links these two players within the current era.
              Try widening the year range.
            </p>
          ) : (
            <ol className="mt-4">
              {path.nodes.map((n, i) => (
                <li key={n.id}>
                  <div className="flex items-center gap-3">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent/15 text-xs font-semibold text-accent">
                      {i + 1}
                    </span>
                    <span className="text-sm font-medium">{n.name as string}</span>
                  </div>
                  {i < path.links.length && (
                    <div className="ml-3.5 flex items-center py-1.5 pl-5 text-[11px] text-white/40">
                      <span className="border-l border-white/15 pl-3">
                        teammates · {seasonSpan(path.links[i].seasons)}
                      </span>
                    </div>
                  )}
                </li>
              ))}
            </ol>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
