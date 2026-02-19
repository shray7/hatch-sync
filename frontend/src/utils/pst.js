/**
 * All times are shown in PST (America/Los_Angeles).
 * API returns ISO strings with offset, e.g. "2026-02-18T14:00:00-08:00".
 */

export const PST_TZ = "America/Los_Angeles";

/** Today's date in PST (YYYY-MM-DD) for "today" counts and filtering. */
export function todayKeyPST() {
  return new Date().toLocaleDateString("en-CA", { timeZone: PST_TZ });
}

/** Last n days (including today) in PST, ordered oldest to newest. */
export function lastNDaysKeysPST(n) {
  const keys = [];
  const now = new Date();
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    keys.push(d.toLocaleDateString("en-CA", { timeZone: PST_TZ }));
  }
  return keys;
}

/** Date part (YYYY-MM-DD) from API string; API sends times in PST so this is the PST date. */
export function dateKey(dateStr) {
  if (!dateStr) return "";
  return dateStr.slice(0, 10);
}

/** Parse API datetime string (ISO with offset or "YYYY-MM-DD HH:MM:SS"). */
export function toDate(dateStr) {
  if (!dateStr) return new Date(NaN);
  const s = dateStr.replace(" ", "T");
  return new Date(s);
}

/** Display date (YYYY-MM-DD) in PST from API string. */
export function formatDatePST(dateStr) {
  if (!dateStr) return "";
  return dateStr.slice(0, 10);
}

/** Display time (HH:mm) in PST from API string (assumes API sent PST). */
export function formatTimePST(dateStr) {
  if (!dateStr) return "";
  if (dateStr.includes("T") && dateStr.length >= 16) return dateStr.slice(11, 16);
  if (dateStr.length >= 16) return dateStr.slice(11, 16);
  return "";
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
