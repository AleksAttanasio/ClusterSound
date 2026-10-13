# Troubleshooting

??? question "The Recorder records silence or does not see the outputs (macOS)"
    Grant *System Audio Recording* in **System Settings → Privacy & Security**. The `cs-tap` helper needs
    macOS 14.2+; without it only *All outputs* through ScreenCaptureKit is left
    (`pip install -e ".[capture]"`). Apps that protect their stream record silence on purpose.

??? question "On Windows the window stays white"
    Install the **Microsoft Edge WebView2** runtime (already present on Windows 11).

??? question "On Windows the recording also contains ClusterSound's audio"
    It is a limit of WASAPI loopback: it cannot exclude a process. Stop the preview while you record.

??? question "Extract stems / Enhance say PyTorch is missing"
    Install the extra: `pip install -e ".[stems]"` or `pip install -e ".[enhance]"`. On first use the app asks to
    download the weights (55 MB / 66 MB).

??? question "The Live device does not find the app"
    The app must be open: the bridge listens on `127.0.0.1:8770` (port in Settings › General). Check
    `http://127.0.0.1:8770/live/ping` in the browser.

??? question "A rack does not load in Live"
    Make sure *ClusterSoundBridge* is the Control Surface and read Live's `Log.txt`
    (`~/Library/Preferences/Ableton/Live 10.x/Log.txt`, `ClusterSoundBridge` lines). After an update run
    `tools/install_live.sh` again and restart Live.

??? question "The library says to press Rescan"
    At startup the app only restores from a snapshot; if the files changed, or the analysis version changed, a
    rescan is needed. Unchanged files come from the cache anyway.

??? question "The cache takes too much space"
    The online previews have a limit (300 MB, Settings › General › Temporary cache, with *Clear*). `cache.sqlite`
    holds the analyses: deleting it forces a new full analysis.

??? question "I want the interface in Italian"
    **Settings › General › Language** → *Italiano*. The app reloads in Italian; the choice is saved in
    `settings.json`.
