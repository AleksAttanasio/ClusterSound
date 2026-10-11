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
     "numoutlets": 6,
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
      8,
      4,
      120,
      20
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
      8,
      26,
      130,
      22
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
      8,
      52,
      260,
      22
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
      144,
      26,
      60,
      22
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
      8,
      80,
      120,
      24
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
      8,
      112,
      18,
      18
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
      111,
      80,
      20
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
      110,
      112,
      18,
      18
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
      130,
      111,
      80,
      20
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
      180,
      112,
      18,
      18
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
      200,
      111,
      80,
      20
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
      300,
      4,
      200,
      20
     ],
     "text": "Suoni da provare",
     "fontface": 1,
     "fontsize": 12.0
    }
   },
   {
    "box": {
     "id": "sndtracks",
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
      300,
      26,
      250,
      22
     ],
     "items": [],
     "parameter_enable": 0
    }
   },
   {
    "box": {
     "id": "snditems",
     "maxclass": "umenu",
     "numinlets": 1,
     "numoutlets": 3,
     "patching_rect": [
      480,
      200,
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
      300,
      52,
      250,
      22
     ],
     "items": [],
     "parameter_enable": 0
    }
   },
   {
    "box": {
     "id": "psndt",
     "maxclass": "newobj",
     "numinlets": 1,
     "numoutlets": 1,
     "patching_rect": [
      480,
      160,
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
     "id": "psndp",
     "maxclass": "newobj",
     "numinlets": 1,
     "numoutlets": 1,
     "patching_rect": [
      480,
      240,
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
     "id": "bprova",
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
      300,
      80,
      80,
      24
     ],
     "text": "Prova ▶",
     "mode": 0
    }
   },
   {
    "box": {
     "id": "bprovat",
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
     "id": "bprovam",
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
     "text": "prova"
    }
   },
   {
    "box": {
     "id": "baltri",
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
      386,
      80,
      80,
      24
     ],
     "text": "Altri",
     "mode": 0
    }
   },
   {
    "box": {
     "id": "baltrit",
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
     "id": "baltrim",
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
     "text": "altri"
    }
   },
   {
    "box": {
     "id": "bferma",
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
      472,
      80,
      78,
      24
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
     "id": "bfermam",
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
     "presentation": 1,
     "presentation_rect": [
      300,
      110,
      250,
      50
     ],
     "linecount": 3,
     "text": "Prova carica lo strumento sulla traccia e suona la clip in loop. Altri: nuove proposte dalla libreria di Live."
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
      8,
      134,
      280,
      32
     ],
     "text": "Avvio…",
     "linecount": 2
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
      "sndtracks",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "sndtracks",
      0
     ],
     "destination": [
      "psndt",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "psndt",
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
      "snditems",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "snditems",
      0
     ],
     "destination": [
      "psndp",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "psndp",
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
      "baltri",
      0
     ],
     "destination": [
      "baltrit",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "baltrit",
      0
     ],
     "destination": [
      "baltrim",
      0
     ]
    }
   },
   {
    "patchline": {
     "source": [
      "baltrim",
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
   }
  ],
  "autosave": 0,
  "devicewidth": 560.0
 }
}
