// ClusterSound for Max for Live (Live 10.1+, Max 8 js = ES5).
// Lists what is saved in ClusterSound (HTTP bridge on 127.0.0.1) and imports it into the Live set: new MIDI
// tracks (or the selected one), clips with the notes, and the .adg rack loaded by the ClusterSoundBridge
// Remote Script (OSC/JSON over UDP: [udpsend 127.0.0.1 9101] / [udpreceive 9102]). With "Ricevi" on it also
// imports what the app sends with "Invia a Live".
//
// "Suoni": for every imported track the Remote Script proposes a few presets from Live's library (Sounds,
// Drums, installed Packs); "Prova" loads one on the track and plays its clip in loop. Tracks that arrive
// without an instrument get the first proposal right away, so every import plays.
//
// inlet: bang (from live.thisdevice), refresh, kind <i>, item <i>, importa, newtracks/tempo/receive <0|1>,
//        port <n>, sndtrack <i>, sndpick <i>, prova, altri, ferma, /clustersound <json> (Remote Script replies)
// outlets: 0 kinds umenu, 1 items umenu, 2 status comment, 3 udpsend, 4 sound tracks umenu, 5 sounds umenu

autowatch = 1;
inlets = 1;
outlets = 6;

var KINDS = [["pattern", "Pattern salvati"], ["sequence", "Sequenze"], ["rack", "Drum rack"], ["compose", "Progressioni"]];
var OUT_MENU_KINDS = 0, OUT_MENU_ITEMS = 1, OUT_STATUS = 2, OUT_UDP = 3, OUT_SND_TRACKS = 4, OUT_SND_ITEMS = 5;
var SUGGESTIONS = 6;
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
var imported = [], sndIdx = 0;  // tracks of the last import: {name, role, index, slot, options, pick, seed, hasSound}

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

function importPayload(p) {
    var set = new LiveAPI("live_set");
    var selTrack = pathIndex(new LiveAPI("live_set view selected_track"), "tracks");
    var scene = Math.max(0, pathIndex(new LiveAPI("live_set view selected_scene"), "scenes"));
    var insertAt = selTrack >= 0 ? selTrack + 1 : -1;
    var notes = [], refs = [];

    if (opts.tempo && p.bpm) steps.push(function () { set.set("tempo", p.bpm); });

    for (var i = 0; i < p.tracks.length; i++) {
        (function (t, first) {
            var ref = { name: t.name, role: t.role || "chords", index: -1, slot: -1, options: [], pick: 0,
                        seed: Math.floor(Math.random() * 1000000), hasSound: false };
            refs.push(ref);
            steps.push(function () {
                if (first && !opts.newtracks && selTrack >= 0) { ref.index = selTrack; return; }
                set.call("create_midi_track", insertAt);
                ref.index = insertAt >= 0 ? insertAt : set.getcount("tracks") - 1;
                if (insertAt >= 0) insertAt++;
                new LiveAPI("live_set tracks " + ref.index).set("name", t.name);
            });
            if (t.adg_path) {
                steps.push(function () {
                    if (!bridgeOk) { notes.push(t.name + ": Remote Script non attiva, trascina il rack dal browser → " + t.adg_path); return; }
                    var id = sendOsc({ cmd: "load", track: ref.index, root: t.adg_root, path: t.adg_path });
                    wait(id, function (msg) {
                        if (msg.ok) ref.hasSound = true;
                        else notes.push(t.name + ": " + msg.error);
                    });
                });
            }
            for (var c = 0; c < t.clips.length; c++) {
                (function (clip, slot) {
                    steps.push(function () {
                        var at = writeClip(set, ref.index, slot, clip);
                        if (ref.slot < 0) ref.slot = at;
                    });
                })(t.clips[c], scene + c);
            }
        })(p.tracks[i], i === 0);
    }
    steps.push(function () {
        busy = false;
        imported = refs;
        sndIdx = 0;
        for (var k = 0; k < refs.length; k++) if (!refs[k].hasSound) { sndIdx = k; break; }
        fillSoundTracks();
        status("Importato «" + p.name + "»" + (notes.length ? " · " + notes.join(" · ") : ""));
        // a track without an instrument gets the first proposal from Live's library, so the import plays
        for (var j = 0; j < refs.length; j++) {
            (function (r) {
                if (r.hasSound || !bridgeOk) return;
                suggest(r, function () { loadOption(r, false); });
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
        try { s(); } catch (e) { status("Errore: " + e); }
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
    return slot;
}
writeClip.local = 1;

// ------------------------------------------------------------------ Suoni
function current() {
    return imported[Math.min(sndIdx, imported.length - 1)] || null;
}
current.local = 1;

function fillSoundTracks() {
    outlet(OUT_SND_TRACKS, "clear");
    for (var i = 0; i < imported.length; i++) outlet(OUT_SND_TRACKS, "append", imported[i].name);
    if (imported.length) outlet(OUT_SND_TRACKS, "set", sndIdx);
    fillSoundItems();
}
fillSoundTracks.local = 1;

function fillSoundItems() {
    var r = current();
    outlet(OUT_SND_ITEMS, "clear");
    if (!r) return;
    for (var i = 0; i < r.options.length; i++) outlet(OUT_SND_ITEMS, "append", r.options[i].name + " · " + r.options[i].folder);
    if (r.options.length) outlet(OUT_SND_ITEMS, "set", r.pick);
}
fillSoundItems.local = 1;

function suggest(r, then) {
    steps.push(function () {
        if (!bridgeOk) return status("Remote Script non attiva: impossibile proporre strumenti");
        var id = sendOsc({ cmd: "suggest", role: r.role, count: SUGGESTIONS, seed: r.seed });
        wait(id, function (msg) {
            if (!msg.ok) return status(r.name + ": " + msg.error);
            r.options = msg.items;
            r.pick = 0;
            if (r === current()) fillSoundItems();
            if (then) then();
        });
    });
}
suggest.local = 1;

function loadOption(r, play) {
    steps.push(function () {
        var opt = r.options[r.pick];
        if (!opt) return;
        var id = sendOsc({ cmd: "load_item", track: r.index, item: opt.id });
        wait(id, function (msg) {
            if (!msg.ok) return status(r.name + ": " + msg.error);
            r.hasSound = true;
            status(r.name + ": " + opt.name + (play ? " ▶" : ""));
            if (play) fire(r);
        });
    });
}
loadOption.local = 1;

function fire(r) {
    if (r.slot >= 0) new LiveAPI("live_set tracks " + r.index + " clip_slots " + r.slot).call("fire");
}
fire.local = 1;

function sndtrack(i) {
    sndIdx = i;
    var r = current();
    fillSoundItems();
    if (r && !r.options.length) { suggest(r); runSteps(); }
}

function sndpick(i) {
    var r = current();
    if (r) r.pick = i;
}

function prova() {
    var r = current();
    if (!r) return status("Importa prima qualcosa: le proposte sono per le tracce importate");
    if (!r.options.length) suggest(r, function () { loadOption(r, true); });
    else loadOption(r, true);
    runSteps();
}

function altri() {
    var r = current();
    if (!r) return;
    r.seed++;
    suggest(r);
    runSteps();
}

function ferma() {
    var r = current();
    if (r) new LiveAPI("live_set tracks " + r.index).call("stop_all_clips");
}
