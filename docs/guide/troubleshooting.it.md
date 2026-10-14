# Risoluzione problemi

??? question "Il Recorder registra silenzio o non vede le uscite (macOS)"
    Concedi *Registrazione audio di sistema* in **Impostazioni di Sistema → Privacy e sicurezza**. L'helper
    `cs-tap` richiede macOS 14.2+; senza, resta solo *Tutte le uscite* via ScreenCaptureKit
    (`pip install -e ".[capture]"`). Le app che proteggono il flusso registrano silenzio per scelta.

??? question "Su Windows la finestra resta bianca"
    Installa il runtime **Microsoft Edge WebView2** (già presente su Windows 11).

??? question "Su Windows nella registrazione c'è anche l'audio di ClusterSound"
    È un limite del loopback WASAPI: non può escludere un processo. Ferma l'anteprima mentre registri.

??? question "Estrai stem / Migliora dicono che manca PyTorch"
    Installa l'extra: `pip install -e ".[stems]"` o `pip install -e ".[enhance]"`. Al primo uso l'app chiede di
    scaricare i pesi (55 MB / 66 MB).

??? question "Il device di Live non trova l'app"
    L'app deve essere aperta: il bridge ascolta su `127.0.0.1:8770` (porta in Impostazioni › Generale). Controlla
    `http://127.0.0.1:8770/live/ping` nel browser.

??? question "Un rack non si carica in Live"
    Verifica che *ClusterSoundBridge* sia la Control Surface e leggi `Log.txt` di Live
    (`~/Library/Preferences/Ableton/Live 10.x/Log.txt`, righe `ClusterSoundBridge`). Dopo un aggiornamento
    rilancia `tools/install_live.sh` e riavvia Live.

??? question "La libreria dice di premere Riscansiona"
    All'avvio l'app ripristina solo da snapshot; se i file sono cambiati, o è cambiata la versione dell'analisi,
    serve una riscansione. I file invariati vengono comunque dalla cache.

??? question "La cache occupa troppo spazio"
    Le anteprime online hanno un limite (300 MB, Impostazioni › Store, con *Svuota cache*). `cache.sqlite`
    contiene le analisi: cancellarla forza una nuova analisi completa.
