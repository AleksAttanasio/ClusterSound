// "Invia a Live": hands what is open to the ClusterSound Max for Live device through the app's localhost bridge.
import { toast } from './sendmenu.js';

export async function sendToLive(api, kind, data, opts = {}) {
  toast('Preparo per Live…');
  const r = await api.live_send(kind, data, opts);
  if (r.error) { toast(`Errore: ${r.error}`); return r; }
  if (!r.running) { toast(`Bridge per Live non attivo: ${r.error || `porta ${r.port}`}`); return r; }
  toast(`Inviato a Live: ${r.tracks.join(', ')} — il device ClusterSound lo importa${r.pending > 1 ? ` (${r.pending} in coda)` : ''}`);
  return r;
}
