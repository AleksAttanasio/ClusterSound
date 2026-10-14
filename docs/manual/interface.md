# Interface

![Settings](../assets/screenshots/settings.png){ .shot }

- **Navigation**: the panel on the left lists the sections; the button next to the logo collapses it to icons only.
  The Library shows the number of analysed samples; the Recorder a red dot while it records.
- **Settings**: the fine-tuning options of every section (folders, formats, devices, MIDI mappings…) are gathered
  in *Settings*, split by section and saved straight away. The **⋯** button at the top right of every screen
  opens the matching section directly.
- **The sections talk to each other**: a sample from the Library or the Store goes to the Sequencer or the
  Drum Rack with the **Send** menu (right-click on a 3D point or a row); the Drum Rack loads its samples into the
  Sequencer buses; the Recorder sends regions to the Drum Rack; Compose plays together with the Sequencer pattern;
  everything can be sent to Ableton Live.
- **No file is modified**: the app only writes in its own folders (data, cache, `~/Music/ClusterSound …`).

| Settings › General | |
|---|---|
| Language | interface language: English (default) or Italiano; the app reloads to apply it |
| Ableton Live bridge | port of the local server for the device (default 8770) |
| Temporary cache | limit of the online previews and of the samples tried (default 300 MB), *Clear* |

The other settings are described on the page of each section; the full list is in
[Reference › Settings](../reference/settings.md). The shortcuts are in
[Reference › Shortcuts](../reference/shortcuts.md).

!!! info "Windows"
    Everything works as on the Mac: shortcuts with `Ctrl` instead of `⌘`, *Show in folder* opens File
    Explorer, the window uses Edge WebView2. Reserved names (`CON`, `NUL`, `COM1`…) get a `_` in front.
