# First launch

1. Start the app (`python -m clustersound` or `ClusterSound.app`).
2. In the empty Library press **Choose folder…** and point to the sample folder (it is read recursively).
3. Wait for the analysis: the bar at the top shows the phases *Finding files → Analysis → Classification → 3D layout*.
   While the map is being computed a preview (PCA) appears straight away, then the final view (t-SNE).
4. Click a point of the cloud: the sample plays and the detail drawer opens.

![The library after the analysis](../assets/screenshots/library-3d.png){ .shot }

!!! tip "Timing"
    The first analysis uses every core and shows files/s live. The next ones are almost instant: unchanged files
    come from the cache and, if nothing changed, the whole library is restored from a snapshot.

!!! note "Your files are not touched"
    ClusterSound never modifies, moves or renames the original files. Classes, corrections and the map live in
    the app's data folder.

| | macOS | Windows |
|---|---|---|
| Data (settings, cache, snapshots, models) | `~/Library/Application Support/ClusterSound` | `%APPDATA%\ClusterSound` |
| Cache (online previews, helpers) | `~/Library/Caches/ClusterSound` | `%LOCALAPPDATA%\ClusterSound\Cache` |
| Downloads, Samples, Recordings, Patterns | `~/Music/ClusterSound …` | `~\Music\ClusterSound …` |

**No samples yet?** Press *Browse the free Store*: see [Store](../manual/store.md).

The interface is in English; to use it in Italian choose **Settings › General › Language**.
