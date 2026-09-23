import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';
import type { HealthResponse, SessionDetail } from '$lib/types';

export const load: PageLoad = async ({ params, fetch }) => {
	const [sessionRes, healthRes] = await Promise.all([
		fetch(`/api/sessions/${encodeURIComponent(params.id)}`),
		fetch('/api/health')
	]);
	if (!sessionRes.ok) throw error(404, 'Session not found');
	const session = (await sessionRes.json()) as SessionDetail;
	const health = healthRes.ok ? ((await healthRes.json()) as HealthResponse) : null;
	return { session, health };
};
