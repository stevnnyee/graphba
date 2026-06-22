"use client";

interface Props {
  min: number;
  max: number;
  from: number;
  to: number;
  onChange: (from: number, to: number) => void;
}

export default function EraSlider({ min, max, from, to, onChange }: Props) {
  const pct = (v: number) => ((v - min) / (max - min)) * 100;

  return (
    <div className="glass pointer-events-auto absolute bottom-5 left-1/2 z-10 w-[min(90vw,560px)] -translate-x-1/2 rounded-2xl px-6 py-4">
      <div className="mb-2.5 flex items-center justify-between text-xs">
        <span className="uppercase tracking-wider text-white/40">Era</span>
        <span className="font-semibold text-accent">
          {from} – {to}
        </span>
      </div>

      <div className="relative h-5">
        <div className="absolute top-1/2 h-1 w-full -translate-y-1/2 rounded-full bg-white/10" />
        <div
          className="absolute top-1/2 h-1 -translate-y-1/2 rounded-full bg-accent"
          style={{ left: `${pct(from)}%`, right: `${100 - pct(to)}%` }}
        />
        <input
          type="range"
          className="era absolute inset-0 w-full"
          min={min}
          max={max}
          value={from}
          onChange={(e) => onChange(Math.min(Number(e.target.value), to), to)}
        />
        <input
          type="range"
          className="era absolute inset-0 w-full"
          min={min}
          max={max}
          value={to}
          onChange={(e) => onChange(from, Math.max(Number(e.target.value), from))}
        />
      </div>
    </div>
  );
}
