# Ableton Live

You need **Live 10.1 Suite** or later (Max for Live). To do only once.

1. Install the device and the Remote Script into the User Library:

    === "macOS"

        ```bash
        tools/install_live.sh
        ```

    === "Windows"

        ```powershell
        python tools\install_live.py
        ```

    If the User Library is not in the default location, pass it as an argument.

2. Restart Live. In **Preferences → Link/MIDI** (**Settings → Link, Tempo & MIDI** in Live 12) choose **ClusterSoundBridge** as *Control Surface*, with
   Input and Output set to *None*.
3. Drag the **ClusterSound** device (browser → *Max MIDI Effect*) onto a MIDI track.

With the app open the device shows the catalogue; try *Send to Live* from the Sequencer. Full usage in
[Max for Live](../manual/max-for-live.md), protocol in [Live integration](../technical/live-integration.md).

!!! tip
    For a self-contained device: open it in Max, *Freeze Device*, save.
