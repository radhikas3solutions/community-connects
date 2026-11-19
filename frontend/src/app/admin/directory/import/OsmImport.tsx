"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import type { Dictionary } from "@/i18n/dictionaries";
import { BrowserApiError, browserApi } from "@/lib/browser-api";
import type { Language } from "@/lib/types";

export type OsmOptions = { areas: { key: string; label: string }[] };

type Result = {
  area: string;
  places: number;
  created: number;
  updated: number;
  already_listed: number;
  skipped_removed: number;
};
type Row = { area: string; result?: Result; error?: string };
type Counts = Omit<Result, "area">;

export function OsmImport({
  options,
  t,
  common,
  lang,
}: {
  options: OsmOptions;
  t: Dictionary["osmImport"];
  common: Dictionary["npiImport"];
  lang: Language;
}) {
  const [areas, setAreas] = useState(options.areas.map((a) => a.key));
  const [rows, setRows] = useState<Row[]>([]);
  const [running, setRunning] = useState(false);
  const stop = useRef(false);
  const label = (key: string) => options.areas.find((a) => a.key === key)?.label ?? key;

  async function run() {
    const jobs: Row[] = areas.map((area) => ({ area }));
    setRows(jobs);
    setRunning(true);
    stop.current = false;
    // One area per request, one at a time: the public Overpass server allows few parallel queries.
    for (let i = 0; i < jobs.length && !stop.current; i++) {
      const { area } = jobs[i]!;
      let row: Row;
      try {
        const result = await browserApi<Result>("/api/v1/admin/import/osm", {
          method: "POST",
          body: JSON.stringify({ area }),
        });
        row = { area, result };
      } catch (err) {
        row = { area, error: err instanceof BrowserApiError ? err.message : common.failed };
      }
      setRows((prev) => prev.map((r, j) => (j === i ? row : r)));
    }
    setRunning(false);
  }

  const sum = (k: keyof Counts) => rows.reduce((n, r) => n + (r.result?.[k] ?? 0), 0);
  const finished = rows.filter((r) => r.result || r.error).length;
  const cell = "px-2 py-1 text-right tabular-nums";
  const cols: (keyof Counts)[] = ["places", "created", "updated", "already_listed", "skipped_removed"];

  return (
    <div className="mt-4 space-y-4" lang={lang}>
      <fieldset>
        <legend className="mb-1 text-sm font-semibold">{t.areas}</legend>
        <div className="flex flex-wrap gap-4">
          {options.areas.map((a) => (
            <label key={a.key} className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={areas.includes(a.key)}
                disabled={running}
                onChange={(e) =>
                  setAreas((prev) => (e.target.checked ? [...prev, a.key] : prev.filter((k) => k !== a.key)))
                }
              />
              {a.label}
            </label>
          ))}
        </div>
      </fieldset>

      <div className="flex flex-wrap items-center gap-3">
        {running ? (
          <Button type="button" variant="secondary" onClick={() => (stop.current = true)}>
            {common.stop}
          </Button>
        ) : (
          <Button type="button" onClick={run} disabled={!areas.length}>
            {common.start} ({areas.length})
          </Button>
        )}
        {rows.length > 0 && (
          <span className="text-sm text-muted" role="status">
            {running ? common.running : common.done} {finished}/{rows.length}
          </span>
        )}
        {!running && sum("created") > 0 && (
          <Link href="/directory?category=restaurants" className="text-sm font-semibold text-brand-700 hover:underline">
            {t.open} →
          </Link>
        )}
      </div>

      {rows.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-line bg-surface">
          <table className="w-full text-sm">
            <thead className="bg-canvas text-left">
              <tr>
                <th className="px-2 py-1">{t.areas}</th>
                <th className={cell}>{t.places}</th>
                <th className={cell}>{common.columns.created}</th>
                <th className={cell}>{common.columns.updated}</th>
                <th className={cell}>{common.columns.already}</th>
                <th className={cell}>{common.columns.removed}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.area} className="border-t border-line">
                  <td className="px-2 py-1">{label(r.area)}</td>
                  {r.result ? (
                    cols.map((k) => (
                      <td key={k} className={cell}>
                        {r.result![k]}
                      </td>
                    ))
                  ) : (
                    <td colSpan={5} className="px-2 py-1 text-muted">
                      {r.error ? `⚠️ ${r.error}` : running ? "…" : ""}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
            {rows.length > 1 && (
              <tfoot className="border-t-2 border-line font-semibold">
                <tr>
                  <td className="px-2 py-1">{common.total}</td>
                  {cols.map((k) => (
                    <td key={k} className={cell}>
                      {sum(k)}
                    </td>
                  ))}
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      )}
    </div>
  );
}
