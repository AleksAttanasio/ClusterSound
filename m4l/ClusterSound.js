// ClusterSound for Max for Live (Live 10.1+, Max 8 js = ES5).
// Lists what is saved in ClusterSound (HTTP bridge on 127.0.0.1) and imports it into the Live set: new MIDI
// tracks (or the selected one), clips with the notes, and the .adg rack loaded by the ClusterSoundBridge
// Remote Script (OSC/JSON over UDP: [udpsend 127.0.0.1 9101] / [udpreceive 9102]). With "Ricevi" on it also
// imports what the app sends with "Invia a Live".
//
// "Suoni": Live's library as the Remote Script sees it, by type (every Sounds folder with the installed Packs'
// presets, drum kits, each instrument's presets, the hits of a drum bus) with all the presets of the chosen
// type. Picking one (or ◀ ▶) loads it on the imported track and plays its clip in loop. Tracks that arrive
// without an instrument get the first preset of their type right away, so every import plays.
//
// "Clip → Melodia" sends the notes of the clip selected in Live (Detail view) to ClusterSound, where Compose
// imports it as the melody of the current version.
//
// inlet: bang (from live.thisdevice), refresh, kind <i>, item <i>, importa, inviaclip, newtracks/tempo/receive <0|1>,
//        port <n>, sndtrack <i>, sndtype <i>, sndpick <i>, prova, prev, next, ferma,
//        /clustersound <json> (Remote Script replies)
// outlets: 0 kinds umenu, 1 items umenu, 2 status comment, 3 udpsend, 4 sound tracks umenu, 5 sounds umenu,
//          6 sound types umenu

autowatch = 1;
inlets = 1;
outlets = 7;

var KINDS = [["pattern", "Pattern salvati"], ["sequence", "Sequenze"], ["rack", "Drum rack"], ["compose", "Progressioni"]];
var OUT_MENU_KINDS = 0, OUT_MENU_ITEMS = 1, OUT_STATUS = 2, OUT_UDP = 3, OUT_SND_TRACKS = 4, OUT_SND_ITEMS = 5,
    OUT_SND_TYPES = 6;
var PAGE = 60;
var ACK_TIMEOUT = 12000;  // the Remote Script retries for ~8 s while a new preset is indexed

var port = 8770;
var opts = { newtracks: 1, tempo: 0, receive: 1 };
var catalog = null;
var kindIdx = 0, itemIdx = 0;
var ready = false, busy = false, connected = false;
var bridgeOk = false, msgId = 0;
var steps = [], waiting = null, waitTask = null;
var poll = new Task(tick, this);
var pings = 0;
var imported = [], sndIdx = 0;  // entries of the last import: {name, role, pad, trackId, clipId, restore, cat, options, total, pick, hasSound}
var cats = null, catDefaults = {};  // instrument types of Live's library, and the starting one per role
var pending = null;   // entry to play as soon as the current loading ends (the last click wins)
var lastProva = 0;    // a second click on Prova within DOUBLE_CLICK ms selects the track
var DOUBLE_CLICK = 400;

// ------------------------------------------------------------------ inlet messages
function bang() {  // live.thisdevice: the Live API is usable from now on
    if (ready) return;
    ready = true;
    outlet(OUT_MENU_KINDS, "clear");
    for (var i = 0; i < KINDS.length; i++) outlet(OUT_MENU_KINDS, "append", KINDS[i][1]);
    outlet(OUT_MENU_KINDS, "set", kindIdx);
    refresh();
    poll.interval = 1000;
    poll.repeat();
}

function refresh() {
    http("/live/catalog", function (err, data) {
        if (err) return status(err);
        catalog = data;
        fillItems();
        status("Connesso a ClusterSound" + (bridgeOk ? " · Remote Script ok" : ""));
    });
    sendOsc({ cmd: "ping" });
}

function kind(i) { kindIdx = i; itemIdx = 0; fillItems(); }
function item(i) { itemIdx = i; }
function port_(n) { port = n; refresh(); }
function newtracks(v) { opts.newtracks = v ? 1 : 0; }
function tempo(v) { opts.tempo = v ? 1 : 0; }
function receive(v) { opts.receive = v ? 1 : 0; }

function importa() {
    var list = currentList();
    if (!list.length) return status("Niente da importare");
    var it = list[Math.min(itemIdx, list.length - 1)];
    var k = KINDS[kindIdx][0];
    status("Preparo «" + it.name + "»…");
    busy = true;
    http("/live/payload?kind=" + k + "&id=" + encodeURIComponent(it.id), function (err, data) {
        if (err) { busy = false; return status(err); }
        later(function () { importPayload(data); });
    });
}

function inviaclip() {
    var clip = new LiveAPI("live_set view detail_clip");
    if (!clip || Number(clip.id) === 0) return status("Seleziona una clip MIDI in Live (vista Detail)");
    if (!clip.get("is_midi_clip")[0]) return status("La clip selezionata è audio: serve una clip MIDI");
    var len = Number(clip.get("length")[0]);
    var notes = clipNotes(clip, len);
    if (!notes.length) return status("La clip selezionata non ha note");
    var name = String(clip.get("name")[0] || "Clip");
    var body = JSON.stringify({ name: name, length: len, notes: notes });
    dlog("clip «" + name + "»: " + notes.length + " note → ClusterSound");
    http("/live/clip?data=" + encodeURIComponent(body), function (err, data) {
        if (err) return status(err);
        if (!data || !data.ok) return status("ClusterSound non ha confermato la clip: aggiorna l'app");
        status("«" + name + "» inviata: in ClusterSound → Compose → Melodia → Importa → Clip da Ableton");
    });
}

function clipNotes(clip, len) {  // [[pitch, start, duration, velocity]] in beats, muted notes left out
    var out = [], i;
    try {  // Live 11+
        var res = JSON.parse(clip.call("get_notes_extended", 0, 128, 0, len));
        for (i = 0; i < res.notes.length; i++) {
            var n = res.notes[i];
            if (!n.mute) out.push([n.pitch, n.start_time, n.duration, n.velocity]);
        }
        return out;
    } catch (e) { /* Live 10: flat list "notes N note p t d v m … done" */ }
    var a = clip.call("get_notes", 0, 0, len, 128);
    for (i = 0; i < a.length; i++) {
        if (a[i] === "note" && !Number(a[i + 5])) out.push([Number(a[i + 1]), Number(a[i + 2]), Number(a[i + 3]), Number(a[i + 4])]);
    }
    return out;
}
clipNotes.local = 1;

function anything() {
    var a = arrayfromargs(messagename, arguments);
    if (messagename === "port") return port_(a[1]);
    if (messagename === "/clustersound") return onReply(a.slice(1).join(" "));
}

// ------------------------------------------------------------------ catalogue
function currentList() {
    return (catalog && catalog[KINDS[kindIdx][0]]) || [];
}

function fillItems() {
    var list = currentList();
    outlet(OUT_MENU_ITEMS, "clear");
    for (var i = 0; i < list.length; i++) outlet(OUT_MENU_ITEMS, "append", list[i].name);
    if (list.length) outlet(OUT_MENU_ITEMS, "set", Math.min(itemIdx, list.length - 1));
}

// ------------------------------------------------------------------ polling (push from the app)
function tick() {
    if (++pings % 5 === 0) sendOsc({ cmd: "ping" });
    if (busy || !opts.receive) return;
    http("/live/next", function (err, data) {
        if (err) {
            if (connected) status(err);
            connected = false;
            return;
        }
        if (!connected) { connected = true; refresh(); }
        if (data && data.tracks) { busy = true; later(function () { importPayload(data); }); }
    });
}
tick.local = 1;

// ------------------------------------------------------------------ HTTP
function http(path, cb) {
    var req = new XMLHttpRequest();
    req.open("GET", "http://127.0.0.1:" + port + path);
    req.onreadystatechange = function () {
        if (this.readyState !== 4) return;
        var text = this.responseText;
        if (this.status === 204 || (this.status === 200 && !text)) return cb(null, null);
        if (!this.status) return cb("ClusterSound non raggiungibile (porta " + port + "): apri l'app");
        var data = null;
        try { data = JSON.parse(text); } catch (e) { return cb("Risposta non valida da ClusterSound"); }
        if (data && data.error) return cb(data.error);
        cb(null, data);
    };
    req.send();
}
http.local = 1;

// ------------------------------------------------------------------ Remote Script (OSC)
function dlog(text) {  // to the Max console and, through the Remote Script, to Live's Log.txt
    post("ClusterSound: " + text + "\n");
    if (bridgeOk) outlet(OUT_UDP, "/clustersound", JSON.stringify({ cmd: "log", id: 0, text: String(text) }));
}
dlog.local = 1;

function sendOsc(obj) {
    obj.id = ++msgId;
    outlet(OUT_UDP, "/clustersound", JSON.stringify(obj));
    return obj.id;
}
sendOsc.local = 1;

function onReply(text) {
    var msg;
    try { msg = JSON.parse(text); } catch (e) { return; }
    if (msg.cmd === "ping" && msg.ok) bridgeOk = true;
    if (waiting && msg.id === waiting.id) {
        var w = waiting;
        waiting = null;
        if (waitTask) waitTask.cancel();
        w.done(msg);
        later(runSteps);
    }
}
onReply.local = 1;

// ------------------------------------------------------------------ import
function later(fn) {  // run outside the current (notification / network) context
    var t = new Task(fn, this);
    t.schedule(0);
}
later.local = 1;

function status(text) {
    outlet(OUT_STATUS, "set", text);
}
status.local = 1;

function pathIndex(api, key) {  // "live_set tracks 3" -> 3
    var parts = String(api.unquotedpath || api.path).replace(/"/g, "").split(" ");
    var i = parts.indexOf(key);
    return i >= 0 ? parseInt(parts[i + 1], 10) : -1;
}
pathIndex.local = 1;

function alive(id) {
    return id && Number(new LiveAPI("id " + id).id) === id;
}
alive.local = 1;

function trackIndex(trackId) {  // current index of a track in live_set tracks, -1 if it is gone
    return alive(trackId) ? pathIndex(new LiveAPI("id " + trackId), "tracks") : -1;
}
trackIndex.local = 1;

function importPayload(p) {
    var set = new LiveAPI("live_set");
    var selTrack = pathIndex(new LiveAPI("live_set view selected_track"), "tracks");
    var scene = Math.max(0, pathIndex(new LiveAPI("live_set view selected_scene"), "scenes"));
    var insertAt = selTrack >= 0 ? selTrack + 1 : -1;
    var notes = [], refs = [];

    if (opts.tempo && p.bpm) steps.push(function () { set.set("tempo", p.bpm); });

    for (var i = 0; i < p.tracks.length; i++) {
        (function (t, first) {
            // tracks and clips are kept by Live id: indices change as soon as tracks are added or moved
            var ref = { name: t.name, role: t.role || "chords", trackId: 0, clipId: 0, cat: null, options: [], total: 0,
                        pick: 0, hasSound: false, pad: null,
                        restore: t.adg_path ? { root: t.adg_root, path: t.adg_path } : null, buses: t.buses || [] };
            refs.push(ref);
            steps.push(function () {
                var index;
                if (first && !opts.newtracks && selTrack >= 0) {
                    index = selTrack;
                } else {
                    set.call("create_midi_track", insertAt);
                    index = insertAt >= 0 ? insertAt : set.getcount("tracks") - 1;
                    if (insertAt >= 0) insertAt++;
                    new LiveAPI("live_set tracks " + index).set("name", t.name);
                }
                ref.trackId = Number(new LiveAPI("live_set tracks " + index).id);
            });
            if (t.adg_path) {
                steps.push(function () {
                    if (!bridgeOk) { notes.push(t.name + ": Remote Script non attiva, trascina il rack dal browser → " + t.adg_path); return; }
                    var id = sendOsc({ cmd: "load", track: trackIndex(ref.trackId), root: t.adg_root, path: t.adg_path });
                    wait(id, function (msg) {
                        if (msg.ok) ref.hasSound = true;
                        else notes.push(t.name + ": " + msg.error);
                    });
                });
            }
            for (var c = 0; c < t.clips.length; c++) {
                (function (clip, slot) {
                    steps.push(function () {
                        if (!clip.notes.length) return;  // placeholder: keeps the next clips in their scene
                        var clipId = writeClip(set, trackIndex(ref.trackId), slot, clip);
                        if (!ref.clipId) ref.clipId = clipId;
                    });
                })(t.clips[c], scene + c);
            }
        })(p.tracks[i], i === 0);
    }
    steps.push(function () {
        busy = false;
        imported = entriesOf(refs);
        dlog("imported " + imported.length + " entries: " + imported.map(function (e) { return e.name; }).join(", "));
        sndIdx = 0;
        for (var k = 0; k < imported.length; k++) if (!imported[k].hasSound) { sndIdx = k; break; }
        fillSoundTracks();
        status("Importato «" + p.name + "»" + (notes.length ? " · " + notes.join(" · ") : ""));
        // a track without an instrument gets the first proposal from Live's library, so the import plays
        for (var j = 0; j < refs.length; j++) {
            (function (r) {
                if (r.hasSound || !bridgeOk) return;
                firstSound(r);
            })(refs[j]);
        }
    });
    runSteps();
}
importPayload.local = 1;

function wait(id, done) {
    waiting = { id: id, done: done };
    waitTask = new Task(function () {
        if (!waiting || waiting.id !== id) return;
        waiting = null;
        done({ ok: false, error: "nessuna risposta dalla Remote Script" });
        bridgeOk = false;
        runSteps();
    }, this);
    waitTask.schedule(ACK_TIMEOUT);
}
wait.local = 1;

function runSteps() {
    while (steps.length && !waiting) {
        var s = steps.shift();
        try { s(); } catch (e) { status("Errore: " + e); dlog("step error: " + e); }
    }
    if (steps.length || waiting) return;
    // idle: the menus show the current state, then the click that came in while loading is played
    fillSoundTypes();
    fillSoundItems();
    if (pending) {
        var r = pending;
        pending = null;
        play(r);
    }
}
runSteps.local = 1;

function writeClip(set, track, slot, clip) {
    // first empty slot from the wanted scene down: never overwrite a clip of the set
    var cs, path;
    for (;; slot++) {
        while (set.getcount("scenes") <= slot) set.call("create_scene", -1);
        path = "live_set tracks " + track + " clip_slots " + slot;
        cs = new LiveAPI(path);
        if (!cs.get("has_clip")[0]) break;
    }
    cs.call("create_clip", clip.length);
    var c = new LiveAPI(path + " clip");
    c.set("name", clip.name);
    c.call("set_notes");
    c.call("notes", clip.notes.length);
    for (var i = 0; i < clip.notes.length; i++) {
        var n = clip.notes[i];
        c.call("note", n[0], n[1].toFixed(6), n[2].toFixed(6), n[3], 0);
    }
    c.call("done");
    return Number(c.id);
}
writeClip.local = 1;

// ------------------------------------------------------------------ Suoni
function current() {
    return imported[Math.min(sndIdx, imported.length - 1)] || null;
}
current.local = 1;

// Entries of the "Traccia" menu: every imported track and, for a Drums track, every drum bus of the pattern or
// sequence (whatever is picked for it is loaded on that bus' pad of the Drum Rack).
function entriesOf(refs) {
    var out = [];
    for (var i = 0; i < refs.length; i++) {
        var r = refs[i];
        if (r.buses.length) r.name = r.name + " · kit intero";
        out.push(r);
        for (var j = 0; j < r.buses.length; j++) {
            var b = r.buses[j];
            out.push({ name: r.name.split(" · ")[0] + " › " + b.label, role: "bus:" + b.id, busLabel: b.label,
                       pad: b.note, trackId: r.trackId, clipId: r.clipId, cat: null, options: [], total: 0,
                       pick: 0, hasSound: r.hasSound, restore: r.restore, buses: [] });
        }
    }
    return out;
}
entriesOf.local = 1;

function typesFor(r) {
    var out = [];
    if (r.pad !== null) out.push({ key: r.role, name: "Colpi di " + r.busLabel });
    return out.concat(cats || []);
}
typesFor.local = 1;

// The instruments menu: the ClusterSound samples back (when the import had a rack), the presets of the type
// fetched so far and, if the type has more, an entry that fetches the next page.
function choices(r) {
    var out = [];
    if (r.restore) out.push({ label: r.pad !== null ? "★ Kit ClusterSound (ripristina tutto)" : "★ Sample ClusterSound", restore: true });
    for (var i = 0; i < r.options.length; i++) out.push({ label: r.options[i].name + "  ·  " + r.options[i].folder, opt: r.options[i] });
    if (r.options.length < r.total) out.push({ label: "… altri " + (r.total - r.options.length), more: true });
    return out;
}
choices.local = 1;

function firstChoice(r) {
    return r.restore ? 1 : 0;
}
firstChoice.local = 1;

function fillSoundTracks() {
    outlet(OUT_SND_TRACKS, "clear");
    for (var i = 0; i < imported.length; i++) outlet(OUT_SND_TRACKS, "append", imported[i].name);
    if (imported.length) outlet(OUT_SND_TRACKS, "set", sndIdx);
    fillSoundTypes();
    fillSoundItems();
}
fillSoundTracks.local = 1;

function fillSoundTypes() {
    var r = current();
    outlet(OUT_SND_TYPES, "clear");
    if (!r || !cats) return;
    var types = typesFor(r);
    for (var i = 0; i < types.length; i++) outlet(OUT_SND_TYPES, "append", types[i].name);
    for (var k = 0; k < types.length; k++) if (types[k].key === r.cat) outlet(OUT_SND_TYPES, "set", k);
}
fillSoundTypes.local = 1;

function fillSoundItems() {
    var r = current();
    outlet(OUT_SND_ITEMS, "clear");
    if (!r) return;
    var list = choices(r);
    dlog("menu " + r.name + ": type " + r.cat + ", " + list.length + " entries, pick " + r.pick);
    for (var i = 0; i < list.length; i++) outlet(OUT_SND_ITEMS, "append", list[i].label);
    if (list.length) outlet(OUT_SND_ITEMS, "set", Math.min(r.pick, list.length - 1));
}
fillSoundItems.local = 1;

function ensureTypes(then) {
    if (cats) return then();
    steps.push(function () {
        if (!bridgeOk) return status("Remote Script non attiva: niente strumenti di Live da provare");
        var id = sendOsc({ cmd: "categories" });
        wait(id, function (msg) {
            if (!msg.ok) return status(msg.error);
            cats = msg.items;
            catDefaults = msg.defaults || {};
            fillSoundTypes();
            then();
        });
    });
}
ensureTypes.local = 1;

function defaultType(r) {
    if (r.pad !== null) return r.role;
    return catDefaults[r.role] || (cats.length ? cats[0].key : null);
}
defaultType.local = 1;

function listType(r, offset, then) {  // fetch a page of the presets of r.cat
    steps.push(function () {
        var id = sendOsc({ cmd: "list", key: r.cat, offset: offset, limit: PAGE });
        wait(id, function (msg) {
            if (!msg.ok) { r.options = []; r.total = 0; fillSoundItems(); return status(r.name + ": " + msg.error); }
            if (msg.key !== r.cat) return;  // the type changed meanwhile
            r.options = offset ? r.options.concat(msg.items) : msg.items;
            r.total = msg.total;
            if (r === current()) fillSoundItems();
            status(r.name + ": " + r.total + " strumenti in «" + typeName(r) + "»");
            if (then) then();
        });
    });
}
listType.local = 1;

function typeName(r) {
    var types = typesFor(r);
    for (var i = 0; i < types.length; i++) if (types[i].key === r.cat) return types[i].name;
    return r.cat;
}
typeName.local = 1;

function firstSound(r) {  // a track imported without an instrument: the first preset of its type
    ensureTypes(function () {
        r.cat = defaultType(r);
        if (!r.cat) return;
        r.pick = firstChoice(r);
        listType(r, 0, function () { loadOption(r, false); });
    });
}
firstSound.local = 1;

function loadOption(r, play) {
    steps.push(function () {
        var c = choices(r)[r.pick];
        if (!c || c.more) return;
        var index = trackIndex(r.trackId);
        if (index < 0) return status(r.name + ": la traccia non c'è più");
        var cmd = c.restore ? { cmd: "load", track: index, root: r.restore.root, path: r.restore.path }
                            : { cmd: "load_item", track: index, item: c.opt.id };
        if (!c.restore && r.pad !== null) cmd.pad = r.pad;
        status(r.name + ": carico «" + c.label + "»…");
        var id = sendOsc(cmd);
        wait(id, function (msg) {
            if (!msg.ok) return status(r.name + ": " + msg.error);
            r.hasSound = true;
            status(r.name + ": " + c.label + (play ? "  ▶" : "") + "   (" + (r.pick + 1) + "/" + choices(r).length + ")");
            if (play) fire(r);
        });
    });
}
loadOption.local = 1;

function fire(r) {
    // fire the clip itself, never a slot: firing an empty slot of an armed track starts recording
    if (r.clipId && alive(r.clipId)) new LiveAPI("id " + r.clipId).call("fire");
}
fire.local = 1;

function play(r) {  // load the picked entry and play; "… altri" fetches the next page and plays its first preset
    var c = choices(r)[r.pick];
    if (c && c.more) listType(r, r.options.length, function () { fillSoundItems(); loadOption(r, true); });
    else loadOption(r, true);
    runSteps();
}
play.local = 1;

function sndtrack(i) {
    sndIdx = i;
    var r = current();
    if (!r) return;
    fillSoundTypes();
    fillSoundItems();
    if (!r.cat) {
        ensureTypes(function () {
            r.cat = defaultType(r);
            r.pick = firstChoice(r);
            fillSoundTypes();
            listType(r, 0);
        });
        runSteps();
    }
}

function sndtype(i) {
    var r = current();
    if (!r || !cats) return;
    var t = typesFor(r)[i];
    if (!t || t.key === r.cat) return;
    r.cat = t.key;
    r.options = [];
    r.total = 0;
    r.pick = firstChoice(r);
    fillSoundItems();
    listType(r, 0);
    runSteps();
}

function playOrQueue(r) {  // never drop a click: while something loads, the last choice waits its turn
    if (waiting || steps.length) {
        pending = r;
        var c = choices(r)[r.pick];
        return status("Dopo il caricamento: «" + (c ? c.label : "") + "»");
    }
    play(r);
}
playOrQueue.local = 1;

function sndpick(i) {  // choosing an instrument plays it on the clip right away
    var r = current();
    if (!r) return;
    r.pick = i;
    playOrQueue(r);
}

function prova() {
    var r = current();
    if (!r) return status("Importa prima qualcosa: gli strumenti si provano sulle tracce importate");
    var now = Date.now();
    if (now - lastProva < DOUBLE_CLICK) {  // double click: also go to the track
        lastProva = 0;
        return selectTrack(r);
    }
    lastProva = now;
    if (!r.cat) return sndtrack(sndIdx);
    playOrQueue(r);
}

function selectTrack(r) {
    if (alive(r.trackId)) new LiveAPI("live_set view").set("selected_track", "id", r.trackId);
}
selectTrack.local = 1;

function step_(delta) {
    var r = current();
    if (!r) return;
    var n = choices(r).length;
    if (!n) return;
    r.pick = (r.pick + delta + n) % n;
    outlet(OUT_SND_ITEMS, "set", r.pick);
    playOrQueue(r);
}
step_.local = 1;

function prev() { step_(-1); }
function next() { step_(1); }

function ferma() {
    var r = current();
    if (r && alive(r.trackId)) new LiveAPI("id " + r.trackId).call("stop_all_clips");
}
