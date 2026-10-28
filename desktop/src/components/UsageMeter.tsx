import { memo, type CSSProperties } from "react";
import type { UsageSnapshot } from "../lib/api";

interface UsageMeterProps {
  snapshot: UsageSnapshot | null;
  online: boolean;
}

function compact(value: number): string {
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

function remainingLabel(percent: number): string {
  if (percent >= 99.95) {
    return "100%";
  }
  return `${percent.toFixed(1)}%`;
}

export const UsageMeter = memo(function UsageMeter({ snapshot, online }: UsageMeterProps) {
  const remainingPercent = snapshot
    ? Math.max(0, Math.min(100, 100 - snapshot.percent_used))
    : 0;
  const ringStyle = {
    "--usage-angle": `${remainingPercent * 3.6}deg`,
  } as CSSProperties;
  const title = snapshot?.note ?? "Waiting for the local token ledger.";

  return (
    <div
      className={`usage-meter${snapshot ? "" : " usage-meter--empty"}`}
      title={title}
      aria-live="polite"
    >
      <div className="usage-meter__ring" style={ringStyle} aria-hidden="true">
        <span>{snapshot ? remainingLabel(remainingPercent) : "—"}</span>
      </div>
      <div className="usage-meter__copy">
        <span className="usage-meter__label">
          Tokens / local day
          <em>LOCAL</em>
        </span>
        <strong>
          {snapshot ? compact(snapshot.total_tokens) : "—"}
          <small> / {snapshot ? compact(snapshot.budget_tokens) : "—"}</small>
        </strong>
        <span className="usage-meter__remaining">
          {snapshot
            ? `${compact(snapshot.remaining_tokens)} left`
            : online
              ? "usage unavailable"
              : "backend offline"}
        </span>
      </div>
    </div>
  );
});
