/**
 * All times are shown in PST (America/Los_Angeles).
 * API returns ISO strings with offset, e.g. "2026-02-18T14:00:00-08:00".
 */

export const PST_TZ = "America/Los_Angeles";

/** Today's date in PST (YYYY-MM-DD) for "today" counts and filtering. */
export function todayKeyPST() {
  return new Date().toLocaleDateString("en-CA", { timeZone: PST_TZ });
}

/** Short label for chart x-axis: "2025-02-07" -> "2/7". */
export function shortChartLabel(dateKey) {
  if (!dateKey || typeof dateKey !== "string") return "";
  const parts = dateKey.split("-");
  if (parts.length < 3) return dateKey;
  return `${parseInt(parts[1], 10)}/${parseInt(parts[2], 10)}`;
}

/** Last n days (including today) in PST, ordered oldest to newest. */
export function lastNDaysKeysPST(n) {
  const keys = [];
  const now = new Date();
  const msPerDay = 24 * 60 * 60 * 1000;
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date(now.getTime() - i * msPerDay);
    keys.push(d.toLocaleDateString("en-CA", { timeZone: PST_TZ }));
  }
  return keys;
}

/**
 * Parse API datetime string (ISO with offset, or "YYYY-MM-DD HH:MM:SS") to a Date.
 * Use this plus timeZone: PST_TZ when formatting so date/time are correct in PST.
 * Strings without timezone (e.g. "2026-02-18T14:00:00") are treated as UTC since
 * the backend stores datetimes in UTC; otherwise they would be parsed as local time
 * and give wrong dates for users outside PST.
 */
export function toDate(dateStr) {
  if (!dateStr) return new Date(NaN);
  let s = String(dateStr).trim().replace(" ", "T");
  // If no timezone designator, treat as UTC to avoid local-time parsing (wrong for non-PST users)
  const hasTz = /Z$|[+-]\d{2}:?\d{2}$/.test(s);
  if (!hasTz && s.length > 10) {
    s += "Z";
  }
  return new Date(s);
}

/** PST date (YYYY-MM-DD) for the given API datetime string. */
export function dateKey(dateStr) {
  if (!dateStr) return "";
  const d = toDate(dateStr);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("en-CA", { timeZone: PST_TZ });
}

/** Display date (YYYY-MM-DD) in PST from API string. */
export function formatDatePST(dateStr) {
  if (!dateStr) return "";
  const d = toDate(dateStr);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("en-CA", { timeZone: PST_TZ });
}

/** Display time (HH:mm) in PST from API string. */
export function formatTimePST(dateStr) {
  if (!dateStr) return "";
  const d = toDate(dateStr);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString(undefined, {
    timeZone: PST_TZ,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  });
}

/** Format for photo/detail display: "Feb 18, 2026, 2:00 PM" in PST. */
export function formatDateTimePST(dateStr) {
  if (!dateStr) return "";
  const d = toDate(dateStr);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString(undefined, {
    timeZone: PST_TZ,
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  });
}
