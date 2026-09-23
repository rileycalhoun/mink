/** Small formatting helpers. */

/** 65.5 -> "1:05", 3661 -> "1:01:01" */
export function formatClock(totalSeconds: number): string {
	if (!Number.isFinite(totalSeconds) || totalSeconds < 0) return '0:00';
	const s = Math.floor(totalSeconds);
	const h = Math.floor(s / 3600);
	const m = Math.floor((s % 3600) / 60);
	const sec = s % 60;
	const mm = h > 0 ? String(m).padStart(2, '0') : String(m);
	return `${h > 0 ? h + ':' : ''}${mm}:${String(sec).padStart(2, '0')}`;
}

/** ISO string -> "Sep 22, 2026 · 9:41 PM" */
export function formatDate(iso: string): string {
	const d = new Date(iso);
	if (Number.isNaN(d.getTime())) return iso;
	return (
		d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) +
		' · ' +
		d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
	);
}

/** "mm:ss" (chapter timestamps from the summarizer) -> seconds. */
export function parseChapterTime(value: string): number {
	const parts = value.split(':').map(Number);
	if (parts.some((p) => Number.isNaN(p))) return 0;
	let total = 0;
	for (const p of parts) total = total * 60 + p;
	return total;
}
