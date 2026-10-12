// "Invia a Live": hands what is open to the ClusterSound Max for Live device through the app's localhost bridge.
import { toast } from './sendmenu.js';

export async function sendToLive(api, kind, data, opts = {}) {
  toast('Preparo per Live…');
  return liveToast(await api.live_send(kind, data, opts));
}

// The toast for a reply of live_send / sampler_send_to_live.
export function liveToast(r) {
  if (r.error) { toast(`Errore: ${r.error}`); return r; }
  if (!r.running) { toast(`Bridge per Live non attivo: ${r.error || `porta ${r.port}`}`); return r; }
  toast(`Inviato a Live: ${r.tracks.join(', ')} — il device ClusterSound lo importa${r.pending > 1 ? ` (${r.pending} in coda)` : ''}`);
  return r;
}
