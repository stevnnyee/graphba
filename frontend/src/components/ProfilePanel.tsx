"use client";

import { AnimatePresence, motion } from "framer-motion";
import type { PlayerProfile } from "@/lib/api";

interface Props {
  profile: PlayerProfile | null;
}

export default function ProfilePanel({ profile }: Props) {
  return (
    <AnimatePresence mode="wait">
      {profile && (
        <motion.aside
          key={profile.id}
          initial={{ x: 40, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: 40, opacity: 0 }}
          transition={{ type: "spring", stiffness: 320, damping: 32 }}
          className="glass pointer-events-auto absolute right-4 top-28 z-10 w-72 rounded-2xl p-5"
        >
          <h2 className="text-lg font-semibold leading-tight">{profile.name}</h2>
          <p className="mt-0.5 text-xs text-white/40">{profile.active_years}</p>

          <div className="mt-4 flex items-baseline gap-2">
            <span className="text-3xl font-bold text-accent">
              {profile.connection_count}
            </span>
            <span className="text-xs text-white/50">teammates all-time</span>
          </div>

          <div className="mt-5">
            <p className="mb-2 text-[11px] uppercase tracking-wider text-white/35">
              Teams
            </p>
            <div className="flex flex-wrap gap-1.5">
              {profile.teams.map((t) => (
                <span
                  key={t.id}
                  title={t.name}
                  className="rounded-md bg-white/5 px-2 py-1 text-xs ring-1 ring-white/10"
                >
                  {t.abbreviation}
                </span>
              ))}
            </div>
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}
