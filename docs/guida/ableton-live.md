# Ableton Live

Serve **Live 10.1 Suite** o successivo (Max for Live). Da fare una volta sola.

1. Installa device e Remote Script nella User Library:

    === "macOS"

        ```bash
        tools/install_live.sh
        ```

    === "Windows"

        ```powershell
        python tools\install_live.py
        ```

    Se la User Library non è nel percorso predefinito, passala come argomento.

2. Riavvia Live. In **Preferenze → Link/MIDI** scegli **ClusterSoundBridge** come *Control Surface*, con Input e
   Output su *Nessuno*.
3. Trascina il device **ClusterSound** (browser → *Max MIDI Effect*) su una traccia MIDI.

Con l'app aperta il device mostra il catalogo; prova *Invia a Live* dal Sequencer. Uso completo in
[Max for Live](../manuale/max-for-live.md), protocollo in [Integrazione con Live](../tecnica/integrazione-live.md).

!!! tip
    Per un device autonomo: aprilo in Max, *Freeze Device*, salva.
