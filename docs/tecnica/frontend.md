# Frontend

L'interfaccia (`clustersound/ui/`) è una single page in **JavaScript moderno senza bundler né build**: `index.html`
carica moduli ES nativi e librerie vendorizzate. Funziona offline, identica nella WebView di macOS, in WebView2 su
Windows e in un browser normale con il [dev server](sviluppo.md#dev-server).

## Moduli

| Modulo | Righe | Ruolo |
|---|---|---|
| `app.js` | ~730 | boot, stato globale, Libreria (sidebar, filtri, lista, vista simili), routing tra sezioni |
| `nav.js` | ~70 | pannello di navigazione (sezioni, badge, versione compatta) |
| `scene3d.js` | ~650 | nuvola 3D con Three.js: shader dei punti, picking, vista simili, animazioni |
| `panel.js` | ~260 | tendina di dettaglio (dinamica, spettrogramma, misure, classe) |
| `player.js` | ~75 | riproduzione Web Audio con cache LRU dei buffer |
| `online.js` | ~950 | Store: home, risultati, pagine pack e provider, download |
| `pattern.js` | ~900 | Sequencer: generi, bus, layer, kit casuale, export |
| `sequencer.js` | ~300 | motore di step Web Audio, specchio di `patterns/render.py` |
| `arranger.js` | ~500 | timeline della sequenza di pattern |
| `drumrack.js` | ~1000 | Drum Rack 8×8 e SPD-SX |
| `compose.js` | ~2500 | Compose: browser, timeline, suggerimenti, variazioni, piano roll, synth |
| `sampler.js` | ~1230 | Recorder: dispositivi, editor, regioni, stem, Migliora |
| `settings.js` | ~140 | pagina Impostazioni divisa per sezione |
| `sendmenu.js`, `live.js` | | menu *Invia*, toast, invio a Live |
| `kit.js`, `icons.js` | | helper HTML per i componenti `wa-*`, icone SVG inline |

## Librerie (in `ui/vendor/`)

- **[Web Awesome](https://webawesome.com/) 3.14** — web component (`wa-button`, `wa-select`, `wa-slider`,
  `wa-checkbox`…) con le icone **Lucide** registrate come libreria offline (~50 SVG).
- **[Three.js](https://threejs.org/)** + `OrbitControls` — la vista 3D.
- Font **Inter** (UI) e **JetBrains Mono** (numeri, tempi, percorsi).

## Stato e comunicazione

- Ogni modulo riceve `api` (`window.pywebview.api`) nel costruttore e chiama `await api.metodo(...)`. Non c'è un
  framework né uno store reattivo: `app.js` tiene un oggetto `state` (classi, dati della libreria, filtri,
  selezione, vista simili) e ogni editor ha il proprio stato interno.
- I risultati della libreria arrivano **colonnari** (`name[]`, `cls[]`, `conf[]`, `xyz[]`…) per gestire decine di
  migliaia di punti senza oggetti per item.
- I lavori lunghi si seguono con **polling** dei metodi di stato (vedi [Architettura](architettura.md)).
- Preferenze di interfaccia (sezione attiva, nav compatta, quanti simili mostrare…) in `localStorage` con chiavi
  `cs.*`; le impostazioni vere sono in Python.
- `window.__cs` espone stato e editor per il debug dall'inspector (`--debug`).

## Vista 3D

Un unico `THREE.Points` con uno `ShaderMaterial`: colore, dimensione e alpha sono attributi per punto, così filtri
e selezione aggiornano solo dei buffer, senza ricreare geometria. Il **picking** non usa il raycaster: proietta i
punti visibili sullo schermo e sceglie il più vicino al cursore entro un raggio, preferendo quelli più vicini alla
camera. Le etichette delle classi sono div HTML posizionati sui centroidi a ogni frame. La vista *simili* anima i
punti verso un layout radiale attorno al centro e disegna il percorso.

## Audio

- **Player**: un solo `AudioContext`, sbloccato al primo gesto dell'utente (WKWebView bloccherebbe `<audio>.play()`
  nei callback asincroni); i buffer decodificati restano in una piccola cache LRU.
- **Sequencer**: scheduler classico "a lookahead" — un timer ogni **25 ms** programma le note dei prossimi
  **120 ms** sul clock di Web Audio. Guadagni (`(v/127)^1.5`), swing, roll, choke e l'hash dell'alternanza dei
  layer sono identici a quelli di `render.py`, quindi ciò che senti è ciò che esporti.
- **Compose**: un piccolo synth con oscillatori Web Audio suona gli eventi calcolati da `perform.py` (stessi
  eventi del MIDI esportato).

## Tema

`theme.css` è l'unico punto in cui si ridefiniscono i token `--wa-*` di Web Awesome: grigi neutri con un solo
accento **teal** (`#00b09f`, `#2fd1bd` per il testo), lo stesso della goccia del logo. L'app è solo scura.
`style.css` definisce alias brevi (`--bg`, `--line`, `--accent`, `--mono`…) e il layout delle sezioni.
