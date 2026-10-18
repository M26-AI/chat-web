import { WEBUI_API_BASE_URL } from '$lib/constants';
const headers = (token: string) => ({ Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' });
export const getUsageDashboard = async (token: string) => fetch(`${WEBUI_API_BASE_URL}/usage/dashboard`, { headers: headers(token) }).then(async r => { if (!r.ok) throw new Error((await r.json()).detail); return r.json(); });
export const redeemCoupon = async (token: string, code: string) => fetch(`${WEBUI_API_BASE_URL}/usage/coupons/redeem`, { method: 'POST', headers: headers(token), body: JSON.stringify({ code }) }).then(async r => { if (!r.ok) throw new Error((await r.json()).detail); return r.json(); });
