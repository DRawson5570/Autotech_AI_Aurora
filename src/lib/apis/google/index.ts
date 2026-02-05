import { WEBUI_API_BASE_URL } from '$lib/constants';

export const getGoogleConfig = async (token: string = '') => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/google/config`, {
		method: 'GET',
		credentials: 'include',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			...(token && { authorization: `Bearer ${token}` })
		}
	})
		.then(async (res) => {
			if (!res.ok) {
				const contentType = res.headers.get('content-type') || '';
				let body: any = null;
				if (contentType.includes('application/json')) {
					try {
						body = await res.json();
					} catch (e) {
						body = { detail: `Invalid JSON response: ${String(e)}` };
					}
				} else {
					body = await res.text();
				}

				throw typeof body === 'string' ? { detail: body } : body;
			}
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			if (err && typeof err === 'object' && 'detail' in err) {
				error = err.detail;
			} else if (err && (typeof err === 'string' || err.message)) {
				error = err.message || String(err);
			} else {
				error = 'Server connection failed';
			}
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const updateGoogleConfig = async (token: string = '', config: any) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/google/config/update`, {
		method: 'POST',
		credentials: 'include',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			...(token && { authorization: `Bearer ${token}` })
		},
		body: JSON.stringify({
			...config
		})
	})
		.then(async (res) => {
			if (!res.ok) {
				const contentType = res.headers.get('content-type') || '';
				let body: any = null;
				if (contentType.includes('application/json')) {
					try {
						body = await res.json();
					} catch (e) {
						body = { detail: `Invalid JSON response: ${String(e)}` };
					}
				} else {
					body = await res.text();
				}

				throw typeof body === 'string' ? { detail: body } : body;
			}
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			if (err && typeof err === 'object' && 'detail' in err) {
				error = err.detail;
			} else if (err && (typeof err === 'string' || err.message)) {
				error = err.message || String(err);
			} else {
				error = 'Server connection failed';
			}
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const verifyGoogleConnection = async (token: string = '', connection: { url: string; key?: string }) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/google/verify`, {
		method: 'POST',
		credentials: 'include',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			...(token && { authorization: `Bearer ${token}` })
		},
		body: JSON.stringify(connection)
	})
		.then(async (res) => {
			if (!res.ok) {
				const contentType = res.headers.get('content-type') || '';
				let body: any = null;
				if (contentType.includes('application/json')) {
					try {
						body = await res.json();
					} catch (e) {
						body = { detail: `Invalid JSON response: ${String(e)}` };
					}
				} else {
					body = await res.text();
				}

				throw typeof body === 'string' ? { detail: body } : body;
			}
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			if (err && typeof err === 'object' && 'detail' in err) {
				error = err.detail;
			} else if (err && (typeof err === 'string' || err.message)) {
				error = err.message || String(err);
			} else {
				error = 'Server connection failed';
			}
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const setGoogleCredentials = async (token: string = '', provider: string = 'google', api_key: string | null = null) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/google/credentials/set`, {
		method: 'POST',
		credentials: 'include',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			...(token && { authorization: `Bearer ${token}` })
		},
		body: JSON.stringify({ provider, api_key })
	})
		.then(async (res) => {
			if (!res.ok) {
				const contentType = res.headers.get('content-type') || '';
				let body: any = null;
				if (contentType.includes('application/json')) {
					try {
						body = await res.json();
					} catch (e) {
						body = { detail: `Invalid JSON response: ${String(e)}` };
					}
				} else {
					body = await res.text();
				}

				throw typeof body === 'string' ? { detail: body } : body;
			}
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			if (err && typeof err === 'object' && 'detail' in err) {
				error = err.detail;
			} else if (err && (typeof err === 'string' || err.message)) {
				error = err.message || String(err);
			} else {
				error = 'Server connection failed';
			}
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};
