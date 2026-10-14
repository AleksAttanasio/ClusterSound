"""Typical drum + bass patterns per genre (hand-written on a 16th grid).

Step strings: one char per 16th, bars separated by "|" (a shorter string repeats):
    .  rest      x  hit      X  accent      o  ghost      2/3/4  roll of 2/3/4 hits in that 16th
Grid reference:  1 e & a 2 e & a 3 e & a 4 e & a  ->  index 0..15
Bass: "step:len:semitones" tokens (relative to the genre key), "g" = glide into the next note, "!" = accent.

Every genre gets its hand-written variants plus two derived ones (Fill, Breakdown).
"""
from . import model

GROUPS = ["Bass music UK", "Drum & Bass / Jungle", "Hip hop / Trap", "House / Techno", "Global / other"]


def V(name, drums, bass="", bars=1, **kw):
    return {"name": name, "drums": drums, "bass": bass, "bars": bars, **kw}


def G(id, name, group, bpm, rng, swing, key, variants, octave=1, half_time=False):
    return {"id": id, "name": name, "group": group, "bpm": bpm, "bpm_range": rng, "swing": swing, "key": key,
            "octave": octave, "half_time": half_time, "variants": variants}


GENRES = [
    # ------------------------------------------------------------------ Bass music UK
    G("ukg2step", "UK Garage (2-step)", "Bass music UK", 132, (128, 136), 62, "F", [
        V("Main", {"kick": "X.........x.....", "clap": "....X.......X...", "rim": ".......o......o.",
                   "chat": "..x..ox...x..ox.", "perc": "o.o.o.o.o.o.o.o."},
          "0:3:0 6:2:0 10:4:-2"),
        V("Skippy", {"kick": "X......x..x.....", "clap": "....X.......X...", "snare": "...........o..o.",
                     "chat": "..x.x.x...x.x.x.", "ohat": "..............x."},
          "0:2:0 7:2:0 10:3:3 14:2:-2"),
        V("Shuffle B", {"kick": "X.....x...x..x..", "clap": "....X.......X...", "rim": "..o....o..o.....",
                        "chat": "o.x.o.x.o.x.o.x.", "perc": "...x.......x...."},
          "0:2:0 6:2:0 10:2:5 13:3:3"),
    ]),
    G("speedgarage", "Speed Garage", "Bass music UK", 135, (130, 138), 58, "G", [
        V("Main", {"kick": "X...X...X...X...", "clap": "....X.......X...", "ohat": "..x...x...x...x.",
                   "chat": "o.o.o.o.o.o.o.o.", "rim": ".......x......x."},
          "0:2:0 3:1:12 6:2:0 8:2:0 11:1:12 14:2:-2"),
        V("Rolling", {"kick": "X...X...X...X...", "snare": "....X.......X..o", "ohat": "..x...x...x...x.",
                      "chat": "xxxxxxxxxxxxxxxx", "perc": "...x......x....."},
          "0:1:0 2:1:12 4:1:0 6:1:12 8:1:0 10:1:12 12:1:3 14:1:15"),
    ]),
    G("bassline", "UK Bassline (Niche)", "Bass music UK", 138, (135, 142), 54, "G", [
        V("Main", {"kick": "X...X...X...X...", "clap": "....X.......X...", "ohat": "..x...x...x...x.",
                   "chat": "x.x.x.x.x.x.x.x.", "perc": "...x...x...x...x"},
          "0:2:0 2:2:0 4:2:12 6:2:0 8:2:0 10:2:3 12:2:5 14:2:3"),
        V("Wobble", {"kick": "X...X...X...X...", "clap": "....X.......X...", "ohat": "..x...x...x...x.",
                     "rim": ".x.....x.x....x."},
          "0:3:0g 3:3:12 6:2:0 8:3:0g 11:3:10 14:2:7"),
    ]),
    G("ukfunky", "UK Funky", "Bass music UK", 130, (126, 132), 56, "A", [
        V("Main", {"kick": "X..x..x.X..x..x.", "clap": "....X.......X...", "perc": "..x..x.x..x..x.x",
                   "chat": "x.x.x.x.x.x.x.x.", "rim": ".x......x.x....."},
          "0:2:0 6:2:0 11:2:-2 14:2:3"),
        V("Tribal", {"kick": "X...X...X...X...", "clap": "....X.......X...", "perc": "x..x..x.x..x..x.",
                     "tom": "...........x.x.x", "chat": "..x...x...x...x."},
          "0:3:0 8:3:-2 12:2:3"),
    ]),
    G("grime", "Grime", "Bass music UK", 140, (138, 142), 50, "F#", [
        V("Main", {"kick": "X.....x...x.....", "snare": "....X.......X...", "chat": "x.x.x.x.x.x.x.x.",
                   "fx": "X..............."},
          "0:2:0 6:2:0 10:2:0 14:2:-5"),
        V("Eskibeat", {"kick": "X.......X.x.....", "clap": "....X.......X...", "snare": "............o..o",
                       "chat": "x.xxx.xxx.xxx.xx", "perc": "..x.....x.x....."},
          "0:1:0 3:1:0 6:1:12 8:1:0 10:1:7 13:1:5"),
    ]),
    G("dubstep", "Dubstep", "Bass music UK", 140, (138, 142), 50, "F", [
        V("Main", {"kick": "X.........x.....", "snare": "........X.......", "chat": "..x...x...x...x.",
                   "perc": "......o.......o."},
          "0:6:0 8:4:0 12:4:-2"),
        V("Variant B", {"kick": "X.....x...x.....", "snare": "........X.......", "clap": "........X.......",
                         "chat": "x.x.x.x.x.x.x.x.", "ohat": "..............x."},
          "0:3:0 6:2:0 10:6:3g"),
        V("Rolling", {"kick": "X.........x..x..", "snare": "......o.X.....o.", "chat": "x.xxx.xxx.xxx.xx",
                      "rim": "...o.......o...."},
          "0:2:0 2:2:0 4:2:12 10:2:0 12:4:-2"),
    ], half_time=True),
    G("riddim", "Riddim", "Bass music UK", 140, (140, 150), 50, "F", [
        V("Main", {"kick": "X.........X.....", "snare": "........X.......", "chat": "..x...x...x...x."},
          "0:2:0 3:2:0 6:2:0 10:2:0 13:2:0"),
        V("Triplet", {"kick": "X..x......X.....", "snare": "........X.......", "clap": "........X.......",
                      "chat": "x..x..x.x..x..x."},
          "0:2:0 3:2:0 6:2:0 8:2:1 11:2:0 14:2:0"),
    ], half_time=True),
    G("tearout", "Brostep / Tearout", "Bass music UK", 150, (145, 155), 50, "F#", [
        V("Main", {"kick": "X.....x.x.x.....", "snare": "........X.......", "chat": "x.x.x.x.x.x.x.x.",
                   "cymbal": "X..............."},
          "0:2:0 3:1:0 6:2:12 10:3:0 14:2:-1"),
        V("Heavy fill", {"kick": "X.x...x.x.x.x...", "snare": "........X...o.33", "tom": "............x.xx",
                           "chat": "x.x.x.x.x.x....."},
          "0:4:0 6:2:12 10:4:0"),
    ], half_time=True),
    G("halftime", "Halftime", "Bass music UK", 170, (160, 175), 52, "E", [
        V("Main", {"kick": "X.........x.....", "snare": "........X.......", "chat": "x.x.x.x.x.x.x.x.",
                   "rim": "..o.....o...o..."},
          "0:6:0 10:6:-2"),
        V("Shuffle", {"kick": "X......x..x.....", "snare": ".....o..X.....o.", "chat": "x.xxx.xxx.xxx.xx",
                      "perc": "...x.......x...."},
          "0:4:0 7:2:0 10:4:3"),
    ], half_time=True),
    G("breaks", "Breaks (Nu-skool)", "Bass music UK", 132, (125, 136), 52, "D", [
        V("Main", {"kick": "X.x.......x.....", "snare": "....X..o.o..X..o", "chat": "x.x.x.x.x.x.x.x.",
                   "ohat": "..............x."},
          "0:3:0 6:2:0 10:4:3 14:2:5"),
        V("Funky", {"kick": "X.....x...x..x..", "snare": "....X..o.o.oX..o", "chat": "xxxxxxxxxxxxxxxx",
                    "perc": "..x.......x....."},
          "0:2:0 6:2:0 10:2:-2 13:3:3"),
    ]),
    G("futuregarage", "Future Garage", "Bass music UK", 132, (128, 138), 64, "C#", [
        V("Main", {"kick": "X.......x.....x.", "clap": "....X.......X...", "chat": "..x..x.x..x...x.",
                   "perc": "o.o.o.o.o.o.o.o.", "fx": "........x......."},
          "0:4:0 8:3:-2 14:2:3"),
        V("Sparse", {"kick": "X.........x.....", "snare": "....x.......x..o", "rim": "...o...o.......o",
                     "chat": "..x...x...x...x."},
          "0:6:0 10:4:-4"),
    ]),
    # ------------------------------------------------------------------ Drum & Bass / Jungle
    G("dnb_liquid", "DnB Liquid", "Drum & Bass / Jungle", 174, (170, 176), 50, "F", [
        V("Main", {"kick": "X.........x.....", "snare": "....X.......X...", "chat": "x.x.x.x.x.x.x.x.",
                   "perc": "oooooooooooooooo", "cymbal": "..x...x...x...x."},
          "0:6:0 10:6:-2"),
        V("Ghost", {"kick": "X.........x.....", "snare": "....X..o.o..X...", "chat": "x.x.x.x.x.x.x.x.",
                    "ohat": "......x.......x.", "perc": "o.oo..o.o.oo..o."},
          "0:4:0 6:2:3 10:6:-2"),
    ]),
    G("dnb_rollers", "DnB Rollers", "Drum & Bass / Jungle", 174, (172, 176), 50, "F", [
        V("Main", {"kick": "X.........x.....", "snare": "....X.......X...", "rim": "..o.....o.o.....",
                   "chat": "..x...x...x...x.", "perc": "o.o.o.o.o.o.o.o."},
          "0:2:0 2:2:0 6:2:0 10:2:0 12:2:3 14:2:0"),
        V("Two-step", {"kick": "X.........x.....", "snare": "....X.......X...", "clap": "....x.......x...",
                       "chat": "x.xxx.xxx.xxx.xx"},
          "0:3:0 3:3:0 10:3:-2 13:3:0"),
    ]),
    G("dnb_jumpup", "DnB Jump-up", "Drum & Bass / Jungle", 174, (172, 176), 50, "F#", [
        V("Main", {"kick": "X.........x.....", "snare": "....X.......X...", "chat": "..x...x...x...x.",
                   "fx": "X..............."},
          "0:2:0 3:1:0 6:2:5 10:2:0 13:1:0 14:2:7"),
        V("Wobble", {"kick": "X.........x..x..", "snare": "....X.......X...", "clap": "....X.......X...",
                     "chat": "x.x.x.x.x.x.x.x."},
          "0:3:0g 3:3:12 6:2:0 10:3:0g 13:3:7"),
    ]),
    G("dnb_neuro", "Neurofunk", "Drum & Bass / Jungle", 174, (172, 176), 50, "E", [
        V("Main", {"kick": "X.........x..x..", "snare": "....X.......X...", "chat": "x.x.x.x.x.x.x.x.",
                   "rim": "......o.......o."},
          "0:4:0 6:2:1 10:3:0 13:3:-2"),
        V("Tight", {"kick": "X.x.......x.....", "snare": "....X..o....X.o.", "chat": "xxxxxxxxxxxxxxxx",
                    "perc": "..x.....x.x....."},
          "0:2:0 2:2:12 4:2:0 10:2:1 12:4:0"),
    ]),
    G("dnb_dancefloor", "DnB Dancefloor", "Drum & Bass / Jungle", 174, (172, 176), 50, "G", [
        V("Main", {"kick": "X.........x.....", "snare": "....X.......X...", "clap": "....X.......X...",
                   "ohat": "..x...x...x...x.", "chat": "x...x...x...x..."},
          "0:2:0 2:2:12 6:2:0 10:2:0 12:2:12 14:2:5"),
        V("Drop", {"kick": "X.........x.....", "snare": "....X.......X...", "chat": "x.x.x.x.x.x.x.x.",
                   "cymbal": "X...............", "fx": "X..............."},
          "0:1:0 1:1:0 2:2:12 6:2:0 8:1:0 10:2:3 12:2:5 14:2:7"),
    ]),
    G("jungle", "Jungle (Amen)", "Drum & Bass / Jungle", 165, (160, 170), 50, "D", [
        V("Amen", {"kick": "X.X.......XX....|..X.......XX....",
                   "snare": "....X..o.o..X..o|.o..X..o.o..X..o",
                   "cymbal": "x.x.x.x.x.x.x.x.|x.x.x.x.x.x.x.x."},
          "0:8:0 10:6:5 16:8:3 26:6:-2", bars=2),
        V("Chopped", {"kick": "X.........X.....|X.X.......x.....",
                      "snare": "....X..o.o..X.o.|....X.o..o..X.3.",
                      "chat": "x.x.x.x.x.x.x.x.|x.x.x.x.x.x.x.x.", "ohat": "..............x.|................"},
          "0:6:0 10:6:-2 16:6:0 26:6:3", bars=2),
    ]),
    G("dnb_minimal", "Minimal / Autonomic", "Drum & Bass / Jungle", 172, (168, 174), 52, "D#", [
        V("Main", {"kick": "X.........x.....", "snare": "........X.......", "chat": "x..x..x...x..x..",
                   "rim": "...o.......o...."},
          "0:8:0 10:6:-2"),
        V("Halftime", {"kick": "X.....x.........", "snare": "........X.......", "perc": "..o..o..o..o..o.",
                       "chat": "x.......x......."},
          "0:6:0 6:4:-2 12:4:3"),
    ], half_time=True),
    G("drumfunk", "Drumfunk", "Drum & Bass / Jungle", 170, (165, 174), 52, "A", [
        V("Main", {"kick": "X.x.......x..x..", "snare": "....X.oo.o.oX.oo", "chat": "x.x.x.x.x.x.x.x.",
                   "cymbal": "x...x...x...x..."},
          "0:6:0 10:6:3"),
        V("Busy", {"kick": "X.x...x...x.x...", "snare": ".o..X.o..oo.X.o.", "chat": "xoxoxoxoxoxoxoxo"},
          "0:4:0 6:2:-2 10:4:3"),
    ]),
    G("footwork", "Footwork / Juke", "Drum & Bass / Jungle", 160, (155, 165), 50, "C", [
        V("Main", {"kick": "X..X..X.X..X..X.|X..X..X...X.X.X.", "clap": "....X.......X...|....X.......X...",
                   "chat": "x.x.x.x.x.x.x.x.", "fx": "X...............|................"},
          "0:3:0 3:3:0 6:2:0 16:3:-2 19:3:-2 22:2:3", bars=2),
        V("Triplet", {"kick": "X..X..X..X..X..X", "clap": "........X.......", "snare": "............X..x",
                      "chat": "x..x..x..x..x..x"},
          "0:3:0 6:3:0 12:3:-2"),
    ]),
    # ------------------------------------------------------------------ Hip hop / Trap
    G("boombap", "Boom bap", "Hip hop / Trap", 90, (85, 95), 58, "A", [
        V("Main", {"kick": "X......x.xX.....", "snare": "....X.......X...", "chat": "x.x.x.x.x.x.x.x."},
          "0:4:0 7:2:0 9:2:0 10:4:-2"),
        V("Laid back", {"kick": "X.x.......x..x..", "snare": "....X.......X..o", "chat": "x.x.x.xox.x.x.xo",
                        "ohat": "......x........."},
          "0:3:0 10:3:3 13:3:-2"),
    ]),
    G("lofi", "Lo-fi hip hop", "Hip hop / Trap", 80, (70, 90), 60, "D#", [
        V("Main", {"kick": "X.......X.x.....", "snare": "....X.......X...", "chat": "x.xox.xox.xox.xo",
                   "perc": "......o.......o."},
          "0:6:0 8:4:5 12:4:3"),
        V("Rim", {"kick": "X......x..x.....", "rim": "....x.......x...", "chat": "x.x.x.x.x.x.x.x.",
                  "snare": "...............o"},
          "0:4:0 7:3:-2 10:6:-4"),
    ]),
    G("trap", "Trap", "Hip hop / Trap", 140, (130, 160), 50, "C#", [
        V("Main", {"kick": "X......x..x.....", "clap": "........X.......", "snare": "........X.......",
                   "chat": "x.x.x.x.x.x.3.x.", "ohat": "..............x."},
          "0:6:0 7:3:0g 10:6:-2"),
        V("Rolls", {"kick": "X.....x...x..x..", "clap": "........X.......", "chat": "x.x.4.x.x.x.x.33",
                    "perc": "...x.......x...."},
          "0:3:0 6:2:0g 10:4:12g 14:2:0"),
        V("Bounce", {"kick": "X..x....X.x.....", "clap": "........X.......", "snare": "...............o",
                     "chat": "x.x.x.x.x.x.x.x.", "ohat": "......x.......x."},
          "0:3:0 3:3:3 8:2:0 10:6:-2"),
    ], half_time=True),
    G("ukdrill", "UK Drill", "Hip hop / Trap", 142, (138, 145), 50, "F#", [
        V("Main", {"kick": "X.........x.....|X.......x.......",
                   "snare": "........X.......|......X.....X...",
                   "chat": "x..x..x.x..x..x.|x..x..x.x.3x..x."},
          "0:6:0 6:4:1g 10:6:0 16:6:-2g 22:4:0 26:6:-1", bars=2),
        V("Sliding 808", {"kick": "X.......x.......|X.....x.........",
                          "snare": "........X.......|......X...X.....",
                          "chat": "x..x..x.x..x..x.|x..x..x.x..x.3.."},
          "0:4:0g 4:4:12g 8:6:0 16:4:0g 20:4:-2g 24:8:-5", bars=2),
    ], half_time=True),
    G("nydrill", "NY / Brooklyn Drill", "Hip hop / Trap", 144, (140, 148), 50, "G", [
        V("Main", {"kick": "X.........x.....|X.....x.........",
                   "snare": "........X.......|........X.....x.",
                   "chat": "x..x..x.x..x..x.|x..x..x.3..x..x.", "perc": "..............x.|................"},
          "0:3:0g 3:3:12g 6:4:0 10:6:-2 16:6:0g 22:4:3g 26:6:-2", bars=2),
        V("Choppy", {"kick": "X.....x...x.....", "snare": "........X.....o.", "chat": "x..x..x.x.3..x..",
                     "ohat": "......x........."},
          "0:6:0g 6:4:5g 10:6:0"),
    ], half_time=True),
    G("phonk", "Phonk", "Hip hop / Trap", 135, (125, 145), 54, "G#", [
        V("Main", {"kick": "X.....x...x.....", "snare": "....X.......X...", "chat": "xxxxxxxxxxxxxxxx",
                   "perc": "x..x..x.x..x..x."},
          "0:3:0 6:2:0 10:4:-2 14:2:3"),
        V("Drift", {"kick": "X.X...x...x.x...", "clap": "....X.......X...", "chat": "x.x.x.x.x.x.x.x.",
                    "perc": "x..x..x...x.x..."},
          "0:2:0 2:2:0 6:2:12 10:2:0 12:4:-2"),
    ]),
    G("memphis", "Memphis rap", "Hip hop / Trap", 70, (65, 80), 52, "D#", [
        V("Main", {"kick": "X..X..X...X.....", "clap": "....X.......X...", "chat": "xxxxxxxxxxxxxxxx",
                   "perc": ".......x.......x"},
          "0:3:0 3:3:0 6:4:-2 10:4:3"),
        V("Cowbell", {"kick": "X.....X...X..X..", "snare": "....X.......X...", "chat": "x.x.x.x.x.x.x.x.",
                      "perc": "x..x..x.x..x..x."},
          "0:4:0 6:4:-2 10:6:0"),
    ]),
    G("jerseyclub", "Jersey Club", "Hip hop / Trap", 140, (135, 145), 50, "A", [
        V("Main", {"kick": "X...X...X.X.X...", "clap": "....X.......X...", "chat": "..x...x...x...x.",
                   "fx": "........x.x.x..."},
          "0:3:0 8:2:0 10:2:0 12:4:-2"),
        V("Bed squeak", {"kick": "X..X..X.X.X.X...", "snare": "....X.......X..x", "perc": "..x...x...x...x.",
                         "chat": "x.x.x.x.x.x.x.x."},
          "0:2:0 3:2:0 6:2:0 8:2:3 10:2:3 12:2:5"),
    ]),
    G("baltimore", "Baltimore Club", "Hip hop / Trap", 130, (125, 135), 50, "G", [
        V("Main", {"kick": "X..X..X.X...X...", "snare": "....X.......X...", "chat": "x.x.x.x.x.x.x.x.",
                   "perc": "......x.......x."},
          "0:2:0 3:2:0 6:2:0 8:4:-2 12:4:3"),
        V("Think break", {"kick": "X...X..XX...X...", "snare": "....X..o....X.o.", "ohat": "..x...x...x...x.",
                          "chat": "xxxxxxxxxxxxxxxx"},
          "0:4:0 7:2:0 8:4:3 12:4:5"),
    ]),
    # ------------------------------------------------------------------ House / Techno
    G("house", "House", "House / Techno", 124, (120, 128), 54, "A", [
        V("Main", {"kick": "X...X...X...X...", "clap": "....X.......X...", "ohat": "..x...x...x...x.",
                   "chat": "o.o.o.o.o.o.o.o.", "perc": ".....x.......x.."},
          "2:1:0 6:1:0 10:1:3 14:1:5"),
        V("Shuffle", {"kick": "X...X...X...X...", "clap": "....X.......X...", "ohat": "..x...x...x...x.",
                      "chat": "xxxxxxxxxxxxxxxx", "rim": "...x..x....x..x."},
          "2:2:0 6:2:0 10:2:0 14:1:7 15:1:5"),
    ]),
    G("deephouse", "Deep House", "House / Techno", 120, (118, 124), 56, "D#", [
        V("Main", {"kick": "X...X...X...X...", "clap": "....X.......X...", "ohat": "..x...x...x...x.",
                   "rim": ".x.....x..x.....", "perc": "o.o.o.o.o.o.o.o."},
          "0:2:0 3:1:0 6:2:-2 10:2:3 14:2:-2"),
        V("Laid back", {"kick": "X...X...X...X...", "snare": "....x.......x...", "chat": "..x...x...x...x.",
                        "perc": "..x..x....x..x.."},
          "0:4:0 6:2:5 10:4:3"),
    ]),
    G("techhouse", "Tech House", "House / Techno", 126, (124, 128), 54, "G", [
        V("Main", {"kick": "X...X...X...X...", "clap": "....X.......X...", "ohat": "..x...x...x...x.",
                   "chat": "xxxxxxxxxxxxxxxx", "perc": "..o..o....o..o.."},
          "2:1:0 3:1:0 6:1:0 7:1:0 10:1:0 11:1:3 14:1:0 15:1:-2"),
        V("Groove", {"kick": "X...X...X...X...", "clap": "....X.......X...", "rim": ".x..x..x.x..x..x",
                     "ohat": "..x...x...x...x.", "perc": "x..x..x...x..x.."},
          "1:1:0 3:1:0 5:1:0 7:1:12 9:1:0 11:1:0 13:1:-2 15:1:0"),
    ]),
    G("techno", "Techno", "House / Techno", 132, (128, 138), 50, "F", [
        V("Main", {"kick": "X...X...X...X...", "clap": "....x.......x...", "chat": "o.x.o.x.o.x.o.x.",
                   "cymbal": "..x...x...x...x.", "perc": "...o.......o...."},
          "2:1:0 6:1:0 10:1:0 14:1:0"),
        V("Rumble", {"kick": "X...X...X...X...", "rim": "...x..x...x..x..", "chat": "xxxxxxxxxxxxxxxx",
                     "ohat": "..x...x...x...x."},
          "1:1:0 2:1:0 3:1:0 5:1:0 6:1:0 7:1:0 9:1:0 10:1:0 11:1:0 13:1:0 14:1:0 15:1:0"),
    ]),
    G("minimal", "Minimal", "House / Techno", 125, (122, 128), 56, "A", [
        V("Main", {"kick": "X...X...X...X...", "rim": "...x...x..x...x.", "chat": "..x...x...x...x.",
                   "perc": "o..o..o..o..o..."},
          "3:1:0 7:1:0 11:1:-2 14:1:0"),
        V("Clicks", {"kick": "X...X...X...X...", "clap": "............x...", "rim": ".x...x.x.x...x..",
                     "chat": "x.x.x.x.x.x.x.x."},
          "2:1:0 10:1:0 13:1:3"),
    ]),
    G("electro", "Electro", "House / Techno", 128, (120, 132), 52, "E", [
        V("Main", {"kick": "X.....X...X.....", "snare": "....X.......X...", "chat": "xxxxxxxxxxxxxxxx",
                   "clap": "....x.......x..."},
          "0:2:0 6:2:0 10:2:3 12:2:5 14:2:3"),
        V("Planet", {"kick": "X.....X...X...X.", "snare": "....X.......X...", "chat": "x.x.x.x.x.x.x.x.",
                     "perc": "x..x..x...x..x.."},
          "0:3:0 6:3:-2 10:3:3 14:2:0"),
    ]),
    G("trance", "Trance", "House / Techno", 138, (134, 142), 50, "A", [
        V("Main", {"kick": "X...X...X...X...", "clap": "....X.......X...", "ohat": "..x...x...x...x.",
                   "chat": "xxxxxxxxxxxxxxxx", "cymbal": "X..............."},
          "1:1:0 2:1:0 3:1:0 5:1:0 6:1:0 7:1:0 9:1:0 10:1:0 11:1:0 13:1:0 14:1:0 15:1:0"),
        V("Offbeat", {"kick": "X...X...X...X...", "clap": "....X.......X...", "ohat": "..x...x...x...x.",
                      "perc": "...x...x...x...x"},
          "2:2:0 6:2:0 10:2:-4 14:2:-2"),
    ]),
    G("hardstyle", "Hardstyle", "House / Techno", 150, (145, 155), 50, "F", [
        V("Main", {"kick": "X...X...X...X...", "clap": "....X.......X...", "ohat": "..x...x...x...x.",
                   "chat": "x.x.x.x.x.x.x.x."},
          "2:2:0 6:2:0 10:2:0 14:2:0"),
        V("Reverse bass", {"kick": "X...X...X...X...", "snare": "............X.33", "ohat": "..x...x...x...x."},
          "2:2:0 6:2:12 10:2:0 14:2:7"),
    ]),
    G("disco", "Disco / Nu-disco", "House / Techno", 118, (112, 124), 54, "E", [
        V("Main", {"kick": "X...X...X...X...", "snare": "....X.......X...", "ohat": "..x...x...x...x.",
                   "chat": "xxxxxxxxxxxxxxxx", "perc": "x.x.x.x.x.x.x.x."},
          "0:1:0 2:1:12 4:1:0 6:1:12 8:1:5 10:1:17 12:1:7 14:1:19"),
        V("Funky", {"kick": "X...X...X...X...", "clap": "....X.......X...", "ohat": "..x...x...x...x.",
                    "chat": "x.x.x.x.x.x.x.x.", "tom": "............x.x."},
          "0:1:0 3:1:0 4:1:12 7:1:0 8:1:3 11:1:5 12:1:7 14:1:5"),
    ]),
    # ------------------------------------------------------------------ Global / other
    G("afrobeats", "Afrobeats", "Global / other", 104, (98, 110), 56, "A", [
        V("Main", {"kick": "X..x..x...X.....", "rim": "...x..x....x..x.", "clap": "............x...",
                   "chat": "x.xxx.xxx.xxx.xx", "perc": "o.o.o.o.o.o.o.o."},
          "0:3:0 6:2:0 10:4:-2 14:2:3"),
        V("Shaker", {"kick": "X......x..x.....", "snare": "....x.......x...", "rim": "...x..x....x..x.",
                     "perc": "xxxxxxxxxxxxxxxx"},
          "0:4:0 7:2:0 10:4:3"),
    ]),
    G("amapiano", "Amapiano", "Global / other", 113, (110, 116), 58, "F", [
        V("Main", {"kick": "X...X...X...X...", "clap": "....X.......X...", "perc": "xxxxxxxxxxxxxxxx",
                   "rim": "..x..x..x..x..x.", "chat": "..x...x...x...x."},
          "3:2:0! 6:1:0 10:2:-5! 13:2:0"),
        V("Log drum", {"kick": "X.......X.......", "clap": "....X.......X...", "perc": "o.o.o.o.o.o.o.o.",
                       "rim": "..x...x...x..x.."},
          "0:1:0! 3:1:0 6:2:7! 10:1:5 11:1:3 14:2:0!"),
    ]),
    G("reggaeton", "Reggaeton / Dembow", "Global / other", 95, (88, 100), 50, "C#", [
        V("Main", {"kick": "X...X...X...X...", "snare": "...x..x....x..x.", "chat": "x.x.x.x.x.x.x.x."},
          "0:3:0 3:3:0 6:2:-2 8:3:0 11:3:3 14:2:5"),
        V("Perreo", {"kick": "X...X...X...X...", "snare": "...x..x....x..x.", "clap": "...x..x....x..x.",
                     "perc": "x..x..x.x..x..x.", "chat": "xxxxxxxxxxxxxxxx"},
          "0:3:0 3:3:0 6:2:0 8:3:-2 11:3:-2 14:2:-4"),
    ]),
    G("dancehall", "Dancehall", "Global / other", 98, (90, 105), 54, "G", [
        V("Main", {"kick": "X..x..x...X.....", "snare": "....X.......X...", "rim": "...x..x....x..x.",
                   "chat": "x.x.x.x.x.x.x.x."},
          "0:3:0 6:2:0 10:4:-2"),
        V("Riddim", {"kick": "X...X...X...X...", "rim": "...x..x....x..x.", "clap": "....X.......X...",
                     "perc": "..x...x...x...x."},
          "0:3:0 3:3:5 8:3:0 11:3:3"),
    ]),
    G("moombahton", "Moombahton", "Global / other", 108, (105, 112), 50, "F#", [
        V("Main", {"kick": "X...X...X...X...", "snare": "...x..x....x..x.", "ohat": "..x...x...x...x.",
                   "chat": "x.x.x.x.x.x.x.x.", "perc": "x..x..x...x..x.."},
          "0:3:0 3:3:0 6:2:5 8:3:0 11:3:3 14:2:-2"),
        V("Dutch", {"kick": "X...X...X...X...", "clap": "...x..x....x..x.", "tom": "x..x..x...x..x..",
                    "chat": "..x...x...x...x."},
          "0:3:0g 3:3:12 8:3:0 11:3:7"),
    ]),
    G("pop", "Pop", "Global / other", 110, (95, 125), 52, "C", [
        V("Main", {"kick": "X.......x.x.....", "snare": "....X.......X...", "clap": "....X.......X...",
                   "chat": "x.x.x.x.x.x.x.x."},
          "0:4:0 8:4:-3 12:4:-5"),
        V("Four", {"kick": "X...X...X...X...", "clap": "....X.......X...", "chat": "x.x.x.x.x.x.x.x.",
                   "ohat": "..............x."},
          "0:2:0 4:2:0 8:2:-3 12:2:-5"),
    ]),
    G("funk", "Funk", "Global / other", 100, (90, 110), 55, "E", [
        V("Main", {"kick": "X..x..x...x..x..", "snare": "....X..o.o..X..o", "chat": "xxxxxxxxxxxxxxxx",
                   "ohat": "......x........."},
          "0:2:0 3:1:12 6:2:0 10:1:3 11:1:5 13:2:7"),
        V("Funky Drummer", {"kick": "X.x...x...x..x..", "snare": "....X..o.o.oX..o", "chat": "xxxxxxxoxxxxxxxx",
                            "ohat": ".......x........"},
          "0:2:0 2:1:0 6:2:-2 10:2:3 13:2:5"),
    ]),
    G("rock", "Rock", "Global / other", 120, (100, 140), 50, "E", [
        V("Main", {"kick": "X.......X.X.....", "snare": "....X.......X...", "chat": "x.x.x.x.x.x.x.x.",
                   "cymbal": "X..............."},
          "0:2:0 2:2:0 4:2:0 6:2:0 8:2:5 10:2:5 12:2:7 14:2:7"),
        V("Half time", {"kick": "X.....x...x.....", "snare": "........X.......", "cymbal": "x.x.x.x.x.x.x.x.",
                        "tom": "............xxxx"},
          "0:4:0 6:4:0 10:6:-2"),
    ]),
    G("breakbeat", "Classic breakbeat", "Global / other", 100, (90, 110), 54, "A", [
        V("Main", {"kick": "X.x...x...x..x..", "snare": "....X..o.o.oX..o", "chat": "x.x.x.x.x.x.x.x.",
                   "ohat": "..............x."},
          "0:3:0 6:2:0 10:3:3 13:3:-2"),
        V("Apache", {"kick": "X.......X.x.....", "snare": "....X.......X...", "perc": "x.xxx.xxx.xxx.xx",
                     "tom": "......x.......x."},
          "0:4:0 8:2:5 10:6:3"),
    ]),
]

GENRE_BY_ID = {g["id"]: g for g in GENRES}


# ------------------------------------------------------------------ building patterns
def _bars(text: str) -> str:
    return "|".join(text[i:i + 16] for i in range(0, len(text), 16))


def _derive(genre: dict) -> list[dict]:
    """Hand-written variants + an automatic Fill and Breakdown based on the first one."""
    main = genre["variants"][0]
    out = list(genre["variants"])
    fill = {**main, "name": "Fill", "drums": dict(main["drums"])}
    bars = main.get("bars", 1)
    # last beat of the last bar: snare roll + tom run
    n = bars * 16
    snare = model.parse_steps(main["drums"].get("snare") or main["drums"].get("clap") or "", n)[0]
    fill_snare = "".join("X" if v >= 127 else "x" if v >= 90 else "o" if v else "." for v in snare)
    fill_snare = fill_snare[: n - 4] + ("3" if genre["half_time"] else "x") + "x33"
    fill["drums"]["snare"] = _bars(fill_snare)
    fill["drums"]["tom"] = _bars("." * (n - 4) + "..xx")
    if "cymbal" not in fill["drums"]:
        fill["drums"]["cymbal"] = _bars("X" + "." * (n - 1))  # crash on the downbeat
    out.append(fill)
    brk = {"name": "Breakdown", "bass": "", "bars": bars,
           "drums": {k: v for k, v in main["drums"].items() if k not in ("kick", "snare", "tom")}}
    if not brk["drums"]:
        brk["drums"] = {"chat": "..x...x...x...x."}
    brk["drums"]["fx"] = _bars("X" + "." * (n - 1))
    out.append(brk)
    return out


def variants(genre_id: str) -> list[dict]:
    return _derive(GENRE_BY_ID[genre_id])


def build(genre_id: str, variant_index: int = 0) -> dict:
    """Full pattern JSON for a genre variant (no samples assigned yet)."""
    g = GENRE_BY_ID[genre_id]
    v = variants(genre_id)[variant_index]
    bars = v.get("bars", 1)
    p = {"id": f"{genre_id}:{variant_index}", "genre": genre_id, "name": v["name"], "bpm": g["bpm"],
         "swing": g["swing"], "bars": bars, "key": g["key"], "octave": g["octave"], "buses": {}}
    n = bars * model.STEPS_PER_BAR
    for bid, *_ in model.ALL_BUSES:
        p["buses"][bid] = model.empty_bus(bid, n)
    for bid, text in v["drums"].items():
        vel, rat = model.parse_steps(text, n)
        p["buses"][bid]["steps"], p["buses"][bid]["ratchet"] = vel, rat
    bass = v.get("bass")
    if bass is None:
        bass = g["variants"][0].get("bass", "")
    p["buses"]["bass"]["notes"] = model.parse_bass(bass)
    return model.validate(p)


def catalog() -> list[dict]:
    """Genre list for the UI (variants by name only)."""
    return [{"id": g["id"], "name": g["name"], "group": g["group"], "bpm": g["bpm"], "bpm_range": g["bpm_range"],
             "swing": g["swing"], "key": g["key"], "half_time": g["half_time"],
             "variants": [v["name"] for v in variants(g["id"])]} for g in GENRES]
