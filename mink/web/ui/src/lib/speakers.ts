/**
 * Speaker identity helpers. Diarization labels look like "SPEAKER_00";
 * we prettify them for display and hash them onto a small, distinct palette.
 */

const PALETTE = [
	'#22c55e', // green
	'#38bdf8', // sky
	'#a78bfa', // violet
	'#f472b6', // pink
	'#fbbf24', // amber
	'#fb7185', // rose
	'#2dd4bf', // teal
	'#f97316' // orange
] as const;

function hashLabel(label: string): number {
	let h = 2166136261;
	for (let i = 0; i < label.length; i++) {
		h ^= label.charCodeAt(i);
		h = Math.imul(h, 16777619);
	}
	return Math.abs(h);
}

/** Stable accent color for a speaker label. Never throws on odd payloads. */
export function speakerColor(label: string | number | null | undefined): string {
	if (label === null || label === undefined || label === '') return '#94a3b8';
	return PALETTE[hashLabel(String(label)) % PALETTE.length];
}

/** "SPEAKER_00" -> "Speaker 1"; anything else passes through trimmed. Never throws. */
export function prettySpeaker(label: string | number | null | undefined): string {
	if (label === null || label === undefined || label === '') return 'Unknown';
	const text = String(label).trim();
	const m = /^SPEAKER_(\d+)$/.exec(text);
	if (m) return `Speaker ${parseInt(m[1], 10) + 1}`;
	return text || 'Unknown';
}
