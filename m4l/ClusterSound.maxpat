{
 "patcher": {
  "fileversion": 1,
  "appversion": {
   "major": 8,
   "minor": 1,
   "revision": 11,
   "architecture": "x64",
   "modernui": 1
  },
  "classnamespace": "box",
  "rect": [
   100.0,
   100.0,
   760.0,
   520.0
  ],
  "openinpresentation": 1,
  "default_fontsize": 10.0,
  "default_fontname": "Arial Bold",
  "gridsize": [
   8.0,
   8.0
  ],
  "description": "ClusterSound: importa pattern, drum rack e progressioni Compose nel set.",
  "boxes": [
   {
    "box": {
     "id": "card_import",
     "maxclass": "panel",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      20,
      480,
      60,
      30
     ],
     "presentation": 1,
     "presentation_rect": [
      4,
      4,
      276,
      132
     ],
     "background": 1,
     "ignoreclick": 1,
     "rounded": 8,
     "border": 1,
     "bgcolor": [
      0.16,
      0.16,
      0.16,
      1.0
     ],
     "bordercolor": [
      0.3,
      0.3,
      0.3,
      1.0
     ]
    }
   },
   {
    "box": {
     "id": "card_sounds",
     "maxclass": "panel",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      90,
      480,
      60,
      30
     ],
     "presentation": 1,
     "presentation_rect": [
      284,
      4,
      272,
      132
     ],
     "background": 1,
     "ignoreclick": 1,
     "rounded": 8,
     "border": 1,
     "bgcolor": [
      0.16,
      0.16,
      0.16,
      1.0
     ],
     "bordercolor": [
      0.3,
      0.3,
      0.3,
      1.0
     ]
    }
   },
   {
    "box": {
     "id": "card_status",
     "maxclass": "panel",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      160,
      480,
      60,
      30
     ],
     "presentation": 1,
     "presentation_rect": [
      4,
      142,
      552,
      22
     ],
     "background": 1,
     "ignoreclick": 1,
     "rounded": 8,
     "border": 1,
     "bgcolor": [
      0.16,
      0.16,
      0.16,
      1.0
     ],
     "bordercolor": [
      0.3,
      0.3,
      0.3,
      1.0
     ]
    }
   },
   {
    "box": {
     "id": "thisdevice",
     "maxclass": "newobj",
     "numinlets": 1,
     "numoutlets": 3,
     "patching_rect": [
      20,
      20,
      90,
      22
     ],
     "outlettype": [
      "bang",
      "int",
      "int"
     ],
     "text": "live.thisdevice"
    }
   },
   {
    "box": {
     "id": "js",
     "maxclass": "newobj",
     "numinlets": 1,
     "numoutlets": 7,
     "patching_rect": [
      20,
      330,
      260,
      22
     ],
     "outlettype": [
      "",
      "",
      "",
      "",
      "",
      "",
      ""
     ],
     "text": "js ClusterSound.js"
    }
   },
   {
    "box": {
     "id": "udpsend",
     "maxclass": "newobj",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      420,
      380,
      150,
      22
     ],
     "text": "udpsend 127.0.0.1 9101"
    }
   },
   {
    "box": {
     "id": "udprecv",
     "maxclass": "newobj",
     "numinlets": 1,
     "numoutlets": 1,
     "patching_rect": [
      420,
      280,
      110,
      22
     ],
     "outlettype": [
      ""
     ],
     "text": "udpreceive 9102"
    }
   },
   {
    "box": {
     "id": "midiin",
     "maxclass": "newobj",
     "numinlets": 1,
     "numoutlets": 1,
     "patching_rect": [
      620,
      20,
      50,
      22
     ],
     "outlettype": [
      "int"
     ],
     "text": "midiin"
    }
   },
   {
    "box": {
     "id": "midiout",
     "maxclass": "newobj",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      620,
      60,
      55,
      22
     ],
     "text": "midiout"
    }
   },
   {
    "box": {
     "id": "title",
     "maxclass": "comment",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      20,
      450,
      100,
      20
     ],
     "presentation": 1,
     "presentation_rect": [
      12,
      8,
      200,
      18
     ],
     "text": "ClusterSound",
     "fontface": 1,
     "fontsize": 12.0
    }
   },
   {
    "box": {
     "id": "kinds",
     "maxclass": "umenu",
     "numinlets": 1,
     "numoutlets": 3,
     "patching_rect": [
      20,
      120,
      130,
      22
     ],
     "outlettype": [
      "int",
      "",
      ""
     ],
     "presentation": 1,
     "presentation_rect": [
      12,
      30,
      184,
      20
     ],
     "items": [],
     "parameter_enable": 0
    }
   },
   {
    "box": {
     "id": "items",
     "maxclass": "umenu",
     "numinlets": 1,
     "numoutlets": 3,
     "patching_rect": [
      180,
      120,
      250,
      22
     ],
     "outlettype": [
      "int",
      "",
      ""
     ],
     "presentation": 1,
     "presentation_rect": [
      12,
      56,
      260,
      20
     ],
     "items": [],
     "parameter_enable": 0
    }
   },
   {
    "box": {
     "id": "pkind",
     "maxclass": "newobj",
     "numinlets": 1,
     "numoutlets": 1,
     "patching_rect": [
      20,
      160,
      80,
      22
     ],
     "outlettype": [
      ""
     ],
     "text": "prepend kind"
    }
   },
   {
    "box": {
     "id": "pitem",
     "maxclass": "newobj",
     "numinlets": 1,
     "numoutlets": 1,
     "patching_rect": [
      180,
      160,
      80,
      22
     ],
     "outlettype": [
      ""
     ],
     "text": "prepend item"
    }
   },
   {
    "box": {
     "id": "bref",
     "maxclass": "textbutton",
     "numinlets": 1,
     "numoutlets": 3,
     "patching_rect": [
      300,
      20,
      80,
      22
     ],
     "outlettype": [
      "",
      "",
      "int"
     ],
     "presentation": 1,
     "presentation_rect": [
      200,
      30,
      72,
      20
     ],
     "text": "Aggiorna",
     "mode": 0
    }
   },
   {
    "box": {
     "id": "breft",
     "maxclass": "newobj",
     "numinlets": 1,
     "numoutlets": 1,
     "patching_rect": [
      300,
      50,
      30,
      22
     ],
     "outlettype": [
      "bang"
     ],
     "text": "t b"
    }
   },
   {
    "box": {
     "id": "brefm",
     "maxclass": "message",
     "numinlets": 2,
     "numoutlets": 1,
     "patching_rect": [
      300,
      80,
      60,
      22
     ],
     "outlettype": [
      ""
     ],
     "text": "refresh"
    }
   },
   {
    "box": {
     "id": "bimp",
     "maxclass": "textbutton",
     "numinlets": 1,
     "numoutlets": 3,
     "patching_rect": [
      420,
      20,
      80,
      22
     ],
     "outlettype": [
      "",
      "",
      "int"
     ],
     "presentation": 1,
     "presentation_rect": [
      12,
      82,
      128,
      22
     ],
     "text": "Importa",
     "mode": 0
    }
   },
   {
    "box": {
     "id": "bimpt",
     "maxclass": "newobj",
     "numinlets": 1,
     "numoutlets": 1,
     "patching_rect": [
      420,
      50,
      30,
      22
     ],
     "outlettype": [
      "bang"
     ],
     "text": "t b"
    }
   },
   {
    "box": {
     "id": "bimpm",
     "maxclass": "message",
     "numinlets": 2,
     "numoutlets": 1,
     "patching_rect": [
      420,
      80,
      60,
      22
     ],
     "outlettype": [
      ""
     ],
     "text": "importa"
    }
   },
   {
    "box": {
     "id": "tg_newtracks",
     "maxclass": "toggle",
     "numinlets": 1,
     "numoutlets": 1,
     "patching_rect": [
      20,
      220,
      20,
      20
     ],
     "outlettype": [
      "int"
     ],
     "presentation": 1,
     "presentation_rect": [
      12,
      112,
      14,
      14
     ],
     "parameter_enable": 0
    }
   },
   {
    "box": {
     "id": "lb_newtracks",
     "maxclass": "comment",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      44,
      220,
      90,
      20
     ],
     "presentation": 1,
     "presentation_rect": [
      28,
      110,
      72,
      18
     ],
     "text": "Nuove tracce"
    }
   },
   {
    "box": {
     "id": "pp_newtracks",
     "maxclass": "newobj",
     "numinlets": 1,
     "numoutlets": 1,
     "patching_rect": [
      20,
      260,
      100,
      22
     ],
     "outlettype": [
      ""
     ],
     "text": "prepend newtracks"
    }
   },
   {
    "box": {
     "id": "lm_newtracks",
     "maxclass": "newobj",
     "numinlets": 1,
     "numoutlets": 1,
     "patching_rect": [
      20,
      190,
      70,
      22
     ],
     "outlettype": [
      ""
     ],
     "text": "loadmess 1"
    }
   },
   {
    "box": {
     "id": "tg_tempo",
     "maxclass": "toggle",
     "numinlets": 1,
     "numoutlets": 1,
     "patching_rect": [
      160,
      220,
      20,
      20
     ],
     "outlettype": [
      "int"
     ],
     "presentation": 1,
     "presentation_rect": [
      104,
      112,
      14,
      14
     ],
     "parameter_enable": 0
    }
   },
   {
    "box": {
     "id": "lb_tempo",
     "maxclass": "comment",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      184,
      220,
      90,
      20
     ],
     "presentation": 1,
     "presentation_rect": [
      120,
      110,
      48,
      18
     ],
     "text": "Tempo"
    }
   },
   {
    "box": {
     "id": "pp_tempo",
     "maxclass": "newobj",
     "numinlets": 1,
     "numoutlets": 1,
     "patching_rect": [
      160,
      260,
      100,
      22
     ],
     "outlettype": [
      ""
     ],
     "text": "prepend tempo"
    }
   },
   {
    "box": {
     "id": "tg_receive",
     "maxclass": "toggle",
     "numinlets": 1,
     "numoutlets": 1,
     "patching_rect": [
      300,
      220,
      20,
      20
     ],
     "outlettype": [
      "int"
     ],
     "presentation": 1,
     "presentation_rect": [
      172,
      112,
      14,
      14
     ],
     "parameter_enable": 0
    }
   },
   {
    "box": {
     "id": "lb_receive",
     "maxclass": "comment",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      324,
      220,
      90,
      20
     ],
     "presentation": 1,
     "presentation_rect": [
      188,
      110,
      60,
      18
     ],
     "text": "Ricevi"
    }
   },
   {
    "box": {
     "id": "pp_receive",
     "maxclass": "newobj",
     "numinlets": 1,
     "numoutlets": 1,
     "patching_rect": [
      300,
      260,
      100,
      22
     ],
     "outlettype": [
      ""
     ],
     "text": "prepend receive"
    }
   },
   {
    "box": {
     "id": "lm_receive",
     "maxclass": "newobj",
     "numinlets": 1,
     "numoutlets": 1,
     "patching_rect": [
      300,
      190,
      70,
      22
     ],
     "outlettype": [
      ""
     ],
     "text": "loadmess 1"
    }
   },
   {
    "box": {
     "id": "snd_title",
     "maxclass": "comment",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      480,
      450,
      100,
      20
     ],
     "presentation": 1,
     "presentation_rect": [
      292,
      8,
      256,
      18
     ],
     "text": "Strumenti di Live da provare",
     "fontface": 1,
     "fontsize": 12.0
    }
   },
   {
    "box": {
     "id": "lbl_sndtrack",
     "maxclass": "comment",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      700,
      120,
      60,
      20
     ],
     "presentation": 1,
     "presentation_rect": [
      292,
      31,
      56,
      18
     ],
     "text": "Traccia"
    }
   },
   {
    "box": {
     "id": "m_sndtrack",
     "maxclass": "umenu",
     "numinlets": 1,
     "numoutlets": 3,
     "patching_rect": [
      480,
      120,
      200,
      22
     ],
     "outlettype": [
      "int",
      "",
      ""
     ],
     "presentation": 1,
     "presentation_rect": [
      352,
      30,
      196,
      20
     ],
     "items": [],
     "parameter_enable": 0
    }
   },
   {
    "box": {
     "id": "p_sndtrack",
     "maxclass": "newobj",
     "numinlets": 1,
     "numoutlets": 1,
     "patching_rect": [
      480,
      150,
      100,
      22
     ],
     "outlettype": [
      ""
     ],
     "text": "prepend sndtrack"
    }
   },
   {
    "box": {
     "id": "lbl_sndtype",
     "maxclass": "comment",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      700,
      280,
      60,
      20
     ],
     "presentation": 1,
     "presentation_rect": [
      292,
      57,
      56,
      18
     ],
     "text": "Tipo"
    }
   },
   {
    "box": {
     "id": "m_sndtype",
     "maxclass": "umenu",
     "numinlets": 1,
     "numoutlets": 3,
     "patching_rect": [
      480,
      280,
      200,
      22
     ],
     "outlettype": [
      "int",
      "",
      ""
     ],
     "presentation": 1,
     "presentation_rect": [
      352,
      56,
      196,
      20
     ],
     "items": [],
     "parameter_enable": 0
    }
   },
   {
    "box": {
     "id": "p_sndtype",
     "maxclass": "newobj",
     "numinlets": 1,
     "numoutlets": 1,
     "patching_rect": [
      480,
      310,
      100,
      22
     ],
     "outlettype": [
      ""
     ],
     "text": "prepend sndtype"
    }
   },
   {
    "box": {
     "id": "lbl_sndpick",
     "maxclass": "comment",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      700,
      200,
      60,
      20
     ],
     "presentation": 1,
     "presentation_rect": [
      292,
      83,
      56,
      18
     ],
     "text": "Strumento"
    }
   },
   {
    "box": {
     "id": "m_sndpick",
     "maxclass": "umenu",
     "numinlets": 1,
     "numoutlets": 3,
     "patching_rect": [
      480,
      200,
      200,
      22
     ],
     "outlettype": [
      "int",
      "",
      ""
     ],
     "presentation": 1,
     "presentation_rect": [
      352,
      82,
      196,
      20
     ],
     "items": [],
     "parameter_enable": 0,
     "hint": "Scegli uno strumento: si carica e la clip suona in loop."
    }
   },
   {
    "box": {
     "id": "p_sndpick",
     "maxclass": "newobj",
     "numinlets": 1,
     "numoutlets": 1,
     "patching_rect": [
      480,
      230,
      100,
      22
     ],
     "outlettype": [
      ""
     ],
     "text": "prepend sndpick"
    }
   },
   {
    "box": {
     "id": "bprev",
     "maxclass": "textbutton",
     "numinlets": 1,
     "numoutlets": 3,
     "patching_rect": [
      760,
      20,
      80,
      22
     ],
     "outlettype": [
      "",
      "",
      "int"
     ],
     "presentation": 1,
     "presentation_rect": [
      292,
      108,
      32,
      22
     ],
     "text": "◀",
     "mode": 0,
     "hint": "Strumento precedente / successivo"
    }
   },
   {
    "box": {
     "id": "bprevt",
     "maxclass": "newobj",
     "numinlets": 1,
     "numoutlets": 1,
     "patching_rect": [
      760,
      50,
      30,
      22
     ],
     "outlettype": [
      "bang"
     ],
     "text": "t b"
    }
   },
   {
    "box": {
     "id": "bprevm",
     "maxclass": "message",
     "numinlets": 2,
     "numoutlets": 1,
     "patching_rect": [
      760,
      80,
      60,
      22
     ],
     "outlettype": [
      ""
     ],
     "text": "prev"
    }
   },
   {
    "box": {
     "id": "bprova",
     "maxclass": "textbutton",
     "numinlets": 1,
     "numoutlets": 3,
     "patching_rect": [
      850,
      20,
      80,
      22
     ],
     "outlettype": [
      "",
      "",
      "int"
     ],
     "presentation": 1,
     "presentation_rect": [
      328,
      108,
      112,
      22
     ],
     "text": "Prova ▶",
     "mode": 0,
     "hint": "Carica lo strumento scelto e suona la clip in loop. Doppio clic: vai alla traccia."
    }
   },
   {
    "box": {
     "id": "bprovat",
     "maxclass": "newobj",
     "numinlets": 1,
     "numoutlets": 1,
     "patching_rect": [
      850,
      50,
      30,
      22
     ],
     "outlettype": [
      "bang"
     ],
     "text": "t b"
    }
   },
   {
    "box": {
     "id": "bprovam",
     "maxclass": "message",
     "numinlets": 2,
     "numoutlets": 1,
     "patching_rect": [
      850,
      80,
      60,
      22
     ],
     "outlettype": [
      ""
     ],
     "text": "prova"
    }
   },
   {
    "box": {
     "id": "bnext",
     "maxclass": "textbutton",
     "numinlets": 1,
     "numoutlets": 3,
     "patching_rect": [
      940,
      20,
      80,
      22
     ],
     "outlettype": [
      "",
      "",
      "int"
     ],
     "presentation": 1,
     "presentation_rect": [
      444,
      108,
      32,
      22
     ],
     "text": "▶",
     "mode": 0,
     "hint": "Strumento precedente / successivo"
    }
   },
   {
    "box": {
     "id": "bnextt",
     "maxclass": "newobj",
     "numinlets": 1,
     "numoutlets": 1,
     "patching_rect": [
      940,
      50,
      30,
      22
     ],
     "outlettype": [
      "bang"
     ],
     "text": "t b"
    }
   },
   {
    "box": {
     "id": "bnextm",
     "maxclass": "message",
     "numinlets": 2,
     "numoutlets": 1,
     "patching_rect": [
      940,
      80,
      60,
      22
     ],
     "outlettype": [
      ""
     ],
     "text": "next"
    }
   },
   {
    "box": {
     "id": "bferma",
     "maxclass": "textbutton",
     "numinlets": 1,
     "numoutlets": 3,
     "patching_rect": [
      1030,
      20,
      80,
      22
     ],
     "outlettype": [
      "",
      "",
      "int"
     ],
     "presentation": 1,
     "presentation_rect": [
      480,
      108,
      68,
      22
     ],
     "text": "Stop",
     "mode": 0
    }
   },
   {
    "box": {
     "id": "bfermat",
     "maxclass": "newobj",
     "numinlets": 1,
     "numoutlets": 1,
     "patching_rect": [
      1030,
      50,
      30,
      22
     ],
     "outlettype": [
      "bang"
     ],
     "text": "t b"
    }
   },
   {
    "box": {
     "id": "bfermam",
     "maxclass": "message",
     "numinlets": 2,
     "numoutlets": 1,
     "patching_rect": [
      1030,
      80,
      60,
      22
     ],
     "outlettype": [
      ""
     ],
     "text": "ferma"
    }
   },
   {
    "box": {
     "id": "snd_hint",
     "maxclass": "comment",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      760,
      120,
      250,
      34
     ],
     "presentation": 0,
     "linecount": 2,
     "text": "Scegli uno strumento o usa ◀ ▶: si carica e la clip suona in loop. Doppio clic su Prova: vai alla traccia."
    }
   },
   {
    "box": {
     "id": "status",
     "maxclass": "comment",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      20,
      400,
      300,
      34
     ],
     "presentation": 1,
     "presentation_rect": [
      12,
      144,
      536,
      18
     ],
     "text": "Avvio…",
     "linecount": 1
    }
   },
   {
    "box": {
     "id": "bclip",
     "maxclass": "textbutton",
     "numinlets": 1,
     "numoutlets": 3,
     "patching_rect": [
      520,
      20,
      80,
      22
     ],
     "outlettype": [
      "",
      "",
      "int"
     ],
     "presentation": 1,
     "presentation_rect": [
      144,
      82,
      128,
      22
     ],
     "text": "Clip → Melodia",
     "mode": 0
    }
   },
   {
    "box": {
     "id": "bclipt",
     "maxclass": "newobj",
     "numinlets": 1,
     "numoutlets": 1,
     "patching_rect": [
      520,
      50,
      30,
      22
     ],
     "outlettype": [
      "bang"
     ],
     "text": "t b"
    }
   },
   {
    "box": {
     "id": "bclipm",
     "maxclass": "message",
     "numinlets": 2,
     "numoutlets": 1,
     "patching_rect": [
      520,
      80,
      60,
      22
     ],
     "outlettype": [
      ""
     ],
     "text": "inviaclip"
    }
   }
  ],
  "lines": [
   {
    "patchline": {
     "source": [
      "midiin",
      0
     ],
     "destination": [
      "midiout",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "thisdevice",
      0
     ],
     "destination": [
      "js",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "js",
      3
     ],
     "destination": [
      "udpsend",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "udprecv",
      0
     ],
     "destination": [
      "js",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "js",
      0
     ],
     "destination": [
      "kinds",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "kinds",
      0
     ],
     "destination": [
      "pkind",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "pkind",
      0
     ],
     "destination": [
      "js",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "js",
      1
     ],
     "destination": [
      "items",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "items",
      0
     ],
     "destination": [
      "pitem",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "pitem",
      0
     ],
     "destination": [
      "js",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "bref",
      0
     ],
     "destination": [
      "breft",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "breft",
      0
     ],
     "destination": [
      "brefm",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "brefm",
      0
     ],
     "destination": [
      "js",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "bimp",
      0
     ],
     "destination": [
      "bimpt",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "bimpt",
      0
     ],
     "destination": [
      "bimpm",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "bimpm",
      0
     ],
     "destination": [
      "js",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "tg_newtracks",
      0
     ],
     "destination": [
      "pp_newtracks",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "pp_newtracks",
      0
     ],
     "destination": [
      "js",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "lm_newtracks",
      0
     ],
     "destination": [
      "tg_newtracks",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "tg_tempo",
      0
     ],
     "destination": [
      "pp_tempo",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "pp_tempo",
      0
     ],
     "destination": [
      "js",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "tg_receive",
      0
     ],
     "destination": [
      "pp_receive",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "pp_receive",
      0
     ],
     "destination": [
      "js",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "lm_receive",
      0
     ],
     "destination": [
      "tg_receive",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "js",
      4
     ],
     "destination": [
      "m_sndtrack",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "m_sndtrack",
      0
     ],
     "destination": [
      "p_sndtrack",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "p_sndtrack",
      0
     ],
     "destination": [
      "js",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "js",
      6
     ],
     "destination": [
      "m_sndtype",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "m_sndtype",
      0
     ],
     "destination": [
      "p_sndtype",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "p_sndtype",
      0
     ],
     "destination": [
      "js",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "js",
      5
     ],
     "destination": [
      "m_sndpick",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "m_sndpick",
      0
     ],
     "destination": [
      "p_sndpick",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "p_sndpick",
      0
     ],
     "destination": [
      "js",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "bprev",
      0
     ],
     "destination": [
      "bprevt",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "bprevt",
      0
     ],
     "destination": [
      "bprevm",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "bprevm",
      0
     ],
     "destination": [
      "js",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "bprova",
      0
     ],
     "destination": [
      "bprovat",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "bprovat",
      0
     ],
     "destination": [
      "bprovam",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "bprovam",
      0
     ],
     "destination": [
      "js",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "bnext",
      0
     ],
     "destination": [
      "bnextt",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "bnextt",
      0
     ],
     "destination": [
      "bnextm",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "bnextm",
      0
     ],
     "destination": [
      "js",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "bferma",
      0
     ],
     "destination": [
      "bfermat",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "bfermat",
      0
     ],
     "destination": [
      "bfermam",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "bfermam",
      0
     ],
     "destination": [
      "js",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "js",
      2
     ],
     "destination": [
      "status",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "bclip",
      0
     ],
     "destination": [
      "bclipt",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "bclipt",
      0
     ],
     "destination": [
      "bclipm",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "bclipm",
      0
     ],
     "destination": [
      "js",
      0
     ]
    }
   }
  ],
  "autosave": 0,
  "devicewidth": 560.0
 }
}
