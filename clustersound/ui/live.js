// "Send to Live": hands what is open to the ClusterSound Max for Live device through the app's localhost bridge.
import { toast } from './sendmenu.js';
import { t } from './i18n.js';

export async function sendToLive(api, kind, data, opts = {}) {
  toast(t('Preparing for Live…'));
  return liveToast(await api.live_send(kind, data, opts));
}

// The toast for a reply of live_send / sampler_send_to_live.
export function liveToast(r) {
  if (r.error) { toast(t('Error: {error}', { error: r.error })); return r; }
  if (!r.running) { toast(t('Live bridge not active: {error}', { error: r.error || t('port {port}', { port: r.port }) })); return r; }
  toast(t('Sent to Live: {tracks} — the ClusterSound device imports it', { tracks: r.tracks.join(', ') })
    + (r.pending > 1 ? t(' ({n} queued)', { n: r.pending }) : ''));
  return r;
}
