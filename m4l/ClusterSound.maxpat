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
  "default_fontname": "Ableton Sans Medium",
  "gridsize": [
   8.0,
   8.0
  ],
  "description": "ClusterSound: importa pattern, drum rack e progressioni Compose nel set.",
  "boxes": [
   {
    "box": {
     "id": "lcd_status",
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
      4,
      134,
      552,
      30
     ],
     "background": 1,
     "ignoreclick": 1,
     "rounded": 6,
     "border": 0,
     "bgcolor": [
      0.0,
      0.0,
      0.0,
      1.0
     ],
     "saved_attribute_attributes": {
      "bgcolor": {
       "expression": "themecolor.live_lcd_bg"
      }
     }
    }
   },
   {
    "box": {
     "id": "ol_kinds",
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
      8,
      26,
      264,
      20
     ],
     "background": 1,
     "ignoreclick": 1,
     "rounded": 6,
     "border": 1,
     "bgcolor": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "bordercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "saved_attribute_attributes": {
      "bordercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      }
     }
    }
   },
   {
    "box": {
     "id": "ol_items",
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
      8,
      50,
      264,
      20
     ],
     "background": 1,
     "ignoreclick": 1,
     "rounded": 6,
     "border": 1,
     "bgcolor": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "bordercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "saved_attribute_attributes": {
      "bordercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      }
     }
    }
   },
   {
    "box": {
     "id": "ol_m_sndtrack",
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
      348,
      30,
      200,
      20
     ],
     "background": 1,
     "ignoreclick": 1,
     "rounded": 6,
     "border": 1,
     "bgcolor": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "bordercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "saved_attribute_attributes": {
      "bordercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      }
     }
    }
   },
   {
    "box": {
     "id": "ol_m_sndtype",
     "maxclass": "panel",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      230,
      480,
      60,
      30
     ],
     "presentation": 1,
     "presentation_rect": [
      348,
      54,
      200,
      20
     ],
     "background": 1,
     "ignoreclick": 1,
     "rounded": 6,
     "border": 1,
     "bgcolor": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "bordercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "saved_attribute_attributes": {
      "bordercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      }
     }
    }
   },
   {
    "box": {
     "id": "ol_m_sndpick",
     "maxclass": "panel",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      300,
      480,
      60,
      30
     ],
     "presentation": 1,
     "presentation_rect": [
      348,
      78,
      200,
      20
     ],
     "background": 1,
     "ignoreclick": 1,
     "rounded": 6,
     "border": 1,
     "bgcolor": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "bordercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "saved_attribute_attributes": {
      "bordercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      }
     }
    }
   },
   {
    "box": {
     "id": "ol_bref",
     "maxclass": "panel",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      20,
      520,
      60,
      30
     ],
     "presentation": 1,
     "presentation_rect": [
      208,
      5,
      64,
      18
     ],
     "background": 1,
     "ignoreclick": 1,
     "rounded": 6,
     "border": 1,
     "bgcolor": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "bordercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "saved_attribute_attributes": {
      "bordercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      }
     }
    }
   },
   {
    "box": {
     "id": "ol_bimp",
     "maxclass": "panel",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      90,
      520,
      60,
      30
     ],
     "presentation": 1,
     "presentation_rect": [
      8,
      76,
      130,
      22
     ],
     "background": 1,
     "ignoreclick": 1,
     "rounded": 6,
     "border": 1,
     "bgcolor": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "bordercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "saved_attribute_attributes": {
      "bordercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      }
     }
    }
   },
   {
    "box": {
     "id": "ol_tg_newtracks",
     "maxclass": "panel",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      160,
      520,
      60,
      30
     ],
     "presentation": 1,
     "presentation_rect": [
      8,
      104,
      92,
      20
     ],
     "background": 1,
     "ignoreclick": 1,
     "rounded": 6,
     "border": 1,
     "bgcolor": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "bordercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "saved_attribute_attributes": {
      "bordercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      }
     }
    }
   },
   {
    "box": {
     "id": "ol_tg_tempo",
     "maxclass": "panel",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      230,
      520,
      60,
      30
     ],
     "presentation": 1,
     "presentation_rect": [
      104,
      104,
      80,
      20
     ],
     "background": 1,
     "ignoreclick": 1,
     "rounded": 6,
     "border": 1,
     "bgcolor": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "bordercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "saved_attribute_attributes": {
      "bordercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      }
     }
    }
   },
   {
    "box": {
     "id": "ol_tg_receive",
     "maxclass": "panel",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      300,
      520,
      60,
      30
     ],
     "presentation": 1,
     "presentation_rect": [
      188,
      104,
      84,
      20
     ],
     "background": 1,
     "ignoreclick": 1,
     "rounded": 6,
     "border": 1,
     "bgcolor": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "bordercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "saved_attribute_attributes": {
      "bordercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      }
     }
    }
   },
   {
    "box": {
     "id": "ol_bprev",
     "maxclass": "panel",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      370,
      520,
      60,
      30
     ],
     "presentation": 1,
     "presentation_rect": [
      288,
      104,
      32,
      20
     ],
     "background": 1,
     "ignoreclick": 1,
     "rounded": 6,
     "border": 1,
     "bgcolor": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "bordercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "saved_attribute_attributes": {
      "bordercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      }
     }
    }
   },
   {
    "box": {
     "id": "ol_bprova",
     "maxclass": "panel",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      440,
      520,
      60,
      30
     ],
     "presentation": 1,
     "presentation_rect": [
      324,
      104,
      120,
      20
     ],
     "background": 1,
     "ignoreclick": 1,
     "rounded": 6,
     "border": 1,
     "bgcolor": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "bordercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "saved_attribute_attributes": {
      "bordercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      }
     }
    }
   },
   {
    "box": {
     "id": "ol_bnext",
     "maxclass": "panel",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      510,
      520,
      60,
      30
     ],
     "presentation": 1,
     "presentation_rect": [
      448,
      104,
      32,
      20
     ],
     "background": 1,
     "ignoreclick": 1,
     "rounded": 6,
     "border": 1,
     "bgcolor": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "bordercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "saved_attribute_attributes": {
      "bordercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      }
     }
    }
   },
   {
    "box": {
     "id": "ol_bferma",
     "maxclass": "panel",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      20,
      560,
      60,
      30
     ],
     "presentation": 1,
     "presentation_rect": [
      484,
      104,
      64,
      20
     ],
     "background": 1,
     "ignoreclick": 1,
     "rounded": 6,
     "border": 1,
     "bgcolor": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "bordercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "saved_attribute_attributes": {
      "bordercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      }
     }
    }
   },
   {
    "box": {
     "id": "ol_bclip",
     "maxclass": "panel",
     "numinlets": 1,
     "numoutlets": 0,
     "patching_rect": [
      90,
      560,
      60,
      30
     ],
     "presentation": 1,
     "presentation_rect": [
      142,
      76,
      130,
      22
     ],
     "background": 1,
     "ignoreclick": 1,
     "rounded": 6,
     "border": 1,
     "bgcolor": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "bordercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "saved_attribute_attributes": {
      "bordercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      }
     }
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
      8,
      6,
      180,
      16
     ],
     "text": "Da ClusterSound",
     "fontsize": 11.0,
     "fontname": "Ableton Sans Bold",
     "textcolor": [
      0.92,
      0.92,
      0.92,
      1.0
     ],
     "saved_attribute_attributes": {
      "textcolor": {
       "expression": "themecolor.live_control_fg"
      }
     }
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
      264,
      20
     ],
     "items": [],
     "parameter_enable": 0,
     "rounded": 6,
     "arrow": 1,
     "fontname": "Ableton Sans Bold",
     "fontsize": 10.0,
     "bgcolor": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "bgfillcolor_type": "color",
     "bgfillcolor_color": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "textcolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "saved_attribute_attributes": {
      "textcolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "color": {
       "expression": "themecolor.live_lcd_control_fg"
      }
     },
     "color": [
      1.0,
      0.709,
      0.196,
      1.0
     ]
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
      50,
      264,
      20
     ],
     "items": [],
     "parameter_enable": 0,
     "rounded": 6,
     "arrow": 1,
     "fontname": "Ableton Sans Bold",
     "fontsize": 10.0,
     "bgcolor": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "bgfillcolor_type": "color",
     "bgfillcolor_color": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "textcolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "saved_attribute_attributes": {
      "textcolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "color": {
       "expression": "themecolor.live_lcd_control_fg"
      }
     },
     "color": [
      1.0,
      0.709,
      0.196,
      1.0
     ]
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
      208,
      5,
      64,
      18
     ],
     "text": "Aggiorna",
     "mode": 0,
     "rounded": 6,
     "fontname": "Ableton Sans Bold",
     "fontsize": 10.0,
     "bgcolor": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "bgovercolor": [
      1.0,
      0.709,
      0.196,
      0.15
     ],
     "bgoncolor": [
      1.0,
      0.709,
      0.196,
      0.35
     ],
     "saved_attribute_attributes": {
      "bordercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "borderoncolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textcolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textovercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textoncolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textoveroncolor": {
       "expression": "themecolor.live_lcd_control_fg"
      }
     },
     "bgoveroncolor": [
      1.0,
      0.709,
      0.196,
      0.35
     ],
     "bordercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "borderoncolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textcolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textovercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textoncolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textoveroncolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "usebgoncolor": 1
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
      76,
      130,
      22
     ],
     "text": "Importa",
     "mode": 0,
     "rounded": 6,
     "fontname": "Ableton Sans Bold",
     "fontsize": 10.0,
     "bgcolor": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "bgovercolor": [
      1.0,
      0.709,
      0.196,
      0.15
     ],
     "bgoncolor": [
      1.0,
      0.709,
      0.196,
      0.35
     ],
     "saved_attribute_attributes": {
      "bordercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "borderoncolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textcolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textovercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textoncolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textoveroncolor": {
       "expression": "themecolor.live_lcd_control_fg"
      }
     },
     "bgoveroncolor": [
      1.0,
      0.709,
      0.196,
      0.35
     ],
     "bordercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "borderoncolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textcolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textovercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textoncolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textoveroncolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "usebgoncolor": 1
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
     "maxclass": "textbutton",
     "numinlets": 1,
     "numoutlets": 3,
     "patching_rect": [
      20,
      220,
      20,
      20
     ],
     "outlettype": [
      "",
      "",
      "int"
     ],
     "presentation": 1,
     "presentation_rect": [
      8,
      104,
      92,
      20
     ],
     "mode": 1,
     "text": "Nuove tracce",
     "texton": "Nuove tracce",
     "fontname": "Ableton Sans Bold",
     "fontsize": 10.0,
     "rounded": 6,
     "bgcolor": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "bgovercolor": [
      1.0,
      0.709,
      0.196,
      0.15
     ],
     "bgoncolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "saved_attribute_attributes": {
      "bgoncolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "bgoveroncolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "bordercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "borderoncolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textcolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textovercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textoncolor": {
       "expression": "themecolor.live_lcd_bg"
      },
      "textoveroncolor": {
       "expression": "themecolor.live_lcd_bg"
      }
     },
     "bgoveroncolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "bordercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "borderoncolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textcolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textovercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textoncolor": [
      0.0,
      0.0,
      0.0,
      1.0
     ],
     "textoveroncolor": [
      0.0,
      0.0,
      0.0,
      1.0
     ],
     "usebgoncolor": 1
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
     "presentation": 0,
     "text": "Nuove tracce",
     "fontname": "Ableton Sans Bold",
     "fontsize": 10.0,
     "textcolor": [
      0.92,
      0.92,
      0.92,
      1.0
     ],
     "saved_attribute_attributes": {
      "textcolor": {
       "expression": "themecolor.live_control_fg"
      }
     }
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
     "maxclass": "textbutton",
     "numinlets": 1,
     "numoutlets": 3,
     "patching_rect": [
      160,
      220,
      20,
      20
     ],
     "outlettype": [
      "",
      "",
      "int"
     ],
     "presentation": 1,
     "presentation_rect": [
      104,
      104,
      80,
      20
     ],
     "mode": 1,
     "text": "Tempo",
     "texton": "Tempo",
     "fontname": "Ableton Sans Bold",
     "fontsize": 10.0,
     "rounded": 6,
     "bgcolor": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "bgovercolor": [
      1.0,
      0.709,
      0.196,
      0.15
     ],
     "bgoncolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "saved_attribute_attributes": {
      "bgoncolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "bgoveroncolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "bordercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "borderoncolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textcolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textovercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textoncolor": {
       "expression": "themecolor.live_lcd_bg"
      },
      "textoveroncolor": {
       "expression": "themecolor.live_lcd_bg"
      }
     },
     "bgoveroncolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "bordercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "borderoncolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textcolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textovercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textoncolor": [
      0.0,
      0.0,
      0.0,
      1.0
     ],
     "textoveroncolor": [
      0.0,
      0.0,
      0.0,
      1.0
     ],
     "usebgoncolor": 1
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
     "presentation": 0,
     "text": "Tempo",
     "fontname": "Ableton Sans Bold",
     "fontsize": 10.0,
     "textcolor": [
      0.92,
      0.92,
      0.92,
      1.0
     ],
     "saved_attribute_attributes": {
      "textcolor": {
       "expression": "themecolor.live_control_fg"
      }
     }
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
     "maxclass": "textbutton",
     "numinlets": 1,
     "numoutlets": 3,
     "patching_rect": [
      300,
      220,
      20,
      20
     ],
     "outlettype": [
      "",
      "",
      "int"
     ],
     "presentation": 1,
     "presentation_rect": [
      188,
      104,
      84,
      20
     ],
     "mode": 1,
     "text": "Ricevi",
     "texton": "Ricevi",
     "fontname": "Ableton Sans Bold",
     "fontsize": 10.0,
     "rounded": 6,
     "bgcolor": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "bgovercolor": [
      1.0,
      0.709,
      0.196,
      0.15
     ],
     "bgoncolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "saved_attribute_attributes": {
      "bgoncolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "bgoveroncolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "bordercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "borderoncolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textcolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textovercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textoncolor": {
       "expression": "themecolor.live_lcd_bg"
      },
      "textoveroncolor": {
       "expression": "themecolor.live_lcd_bg"
      }
     },
     "bgoveroncolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "bordercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "borderoncolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textcolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textovercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textoncolor": [
      0.0,
      0.0,
      0.0,
      1.0
     ],
     "textoveroncolor": [
      0.0,
      0.0,
      0.0,
      1.0
     ],
     "usebgoncolor": 1
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
     "presentation": 0,
     "text": "Ricevi",
     "fontname": "Ableton Sans Bold",
     "fontsize": 10.0,
     "textcolor": [
      0.92,
      0.92,
      0.92,
      1.0
     ],
     "saved_attribute_attributes": {
      "textcolor": {
       "expression": "themecolor.live_control_fg"
      }
     }
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
      288,
      8,
      260,
      16
     ],
     "text": "Strumenti di Live",
     "fontsize": 11.0,
     "fontname": "Ableton Sans Bold",
     "textcolor": [
      0.92,
      0.92,
      0.92,
      1.0
     ],
     "saved_attribute_attributes": {
      "textcolor": {
       "expression": "themecolor.live_control_fg"
      }
     }
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
      288,
      31,
      56,
      18
     ],
     "text": "Traccia",
     "fontname": "Ableton Sans Bold",
     "fontsize": 10.0,
     "textcolor": [
      0.92,
      0.92,
      0.92,
      1.0
     ],
     "saved_attribute_attributes": {
      "textcolor": {
       "expression": "themecolor.live_control_fg"
      }
     }
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
      348,
      30,
      200,
      20
     ],
     "items": [],
     "parameter_enable": 0,
     "rounded": 6,
     "arrow": 1,
     "fontname": "Ableton Sans Bold",
     "fontsize": 10.0,
     "bgcolor": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "bgfillcolor_type": "color",
     "bgfillcolor_color": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "textcolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "saved_attribute_attributes": {
      "textcolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "color": {
       "expression": "themecolor.live_lcd_control_fg"
      }
     },
     "color": [
      1.0,
      0.709,
      0.196,
      1.0
     ]
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
      288,
      55,
      56,
      18
     ],
     "text": "Tipo",
     "fontname": "Ableton Sans Bold",
     "fontsize": 10.0,
     "textcolor": [
      0.92,
      0.92,
      0.92,
      1.0
     ],
     "saved_attribute_attributes": {
      "textcolor": {
       "expression": "themecolor.live_control_fg"
      }
     }
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
      348,
      54,
      200,
      20
     ],
     "items": [],
     "parameter_enable": 0,
     "rounded": 6,
     "arrow": 1,
     "fontname": "Ableton Sans Bold",
     "fontsize": 10.0,
     "bgcolor": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "bgfillcolor_type": "color",
     "bgfillcolor_color": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "textcolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "saved_attribute_attributes": {
      "textcolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "color": {
       "expression": "themecolor.live_lcd_control_fg"
      }
     },
     "color": [
      1.0,
      0.709,
      0.196,
      1.0
     ]
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
      288,
      79,
      56,
      18
     ],
     "text": "Strumento",
     "fontname": "Ableton Sans Bold",
     "fontsize": 10.0,
     "textcolor": [
      0.92,
      0.92,
      0.92,
      1.0
     ],
     "saved_attribute_attributes": {
      "textcolor": {
       "expression": "themecolor.live_control_fg"
      }
     }
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
      348,
      78,
      200,
      20
     ],
     "items": [],
     "parameter_enable": 0,
     "hint": "Scegli uno strumento: si carica e la clip suona in loop.",
     "rounded": 6,
     "arrow": 1,
     "fontname": "Ableton Sans Bold",
     "fontsize": 10.0,
     "bgcolor": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "bgfillcolor_type": "color",
     "bgfillcolor_color": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "textcolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "saved_attribute_attributes": {
      "textcolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "color": {
       "expression": "themecolor.live_lcd_control_fg"
      }
     },
     "color": [
      1.0,
      0.709,
      0.196,
      1.0
     ]
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
      288,
      104,
      32,
      20
     ],
     "text": "◀",
     "mode": 0,
     "hint": "Strumento precedente / successivo",
     "rounded": 6,
     "fontname": "Ableton Sans Bold",
     "fontsize": 10.0,
     "bgcolor": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "bgovercolor": [
      1.0,
      0.709,
      0.196,
      0.15
     ],
     "bgoncolor": [
      1.0,
      0.709,
      0.196,
      0.35
     ],
     "saved_attribute_attributes": {
      "bordercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "borderoncolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textcolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textovercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textoncolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textoveroncolor": {
       "expression": "themecolor.live_lcd_control_fg"
      }
     },
     "bgoveroncolor": [
      1.0,
      0.709,
      0.196,
      0.35
     ],
     "bordercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "borderoncolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textcolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textovercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textoncolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textoveroncolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "usebgoncolor": 1
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
      324,
      104,
      120,
      20
     ],
     "text": "Prova ▶",
     "mode": 0,
     "hint": "Carica lo strumento scelto e suona la clip in loop. Doppio clic: vai alla traccia.",
     "rounded": 6,
     "fontname": "Ableton Sans Bold",
     "fontsize": 10.0,
     "bgcolor": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "bgovercolor": [
      1.0,
      0.709,
      0.196,
      0.15
     ],
     "bgoncolor": [
      1.0,
      0.709,
      0.196,
      0.35
     ],
     "saved_attribute_attributes": {
      "bordercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "borderoncolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textcolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textovercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textoncolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textoveroncolor": {
       "expression": "themecolor.live_lcd_control_fg"
      }
     },
     "bgoveroncolor": [
      1.0,
      0.709,
      0.196,
      0.35
     ],
     "bordercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "borderoncolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textcolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textovercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textoncolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textoveroncolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "usebgoncolor": 1
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
      448,
      104,
      32,
      20
     ],
     "text": "▶",
     "mode": 0,
     "hint": "Strumento precedente / successivo",
     "rounded": 6,
     "fontname": "Ableton Sans Bold",
     "fontsize": 10.0,
     "bgcolor": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "bgovercolor": [
      1.0,
      0.709,
      0.196,
      0.15
     ],
     "bgoncolor": [
      1.0,
      0.709,
      0.196,
      0.35
     ],
     "saved_attribute_attributes": {
      "bordercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "borderoncolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textcolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textovercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textoncolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textoveroncolor": {
       "expression": "themecolor.live_lcd_control_fg"
      }
     },
     "bgoveroncolor": [
      1.0,
      0.709,
      0.196,
      0.35
     ],
     "bordercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "borderoncolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textcolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textovercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textoncolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textoveroncolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "usebgoncolor": 1
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
      484,
      104,
      64,
      20
     ],
     "text": "Stop",
     "mode": 0,
     "rounded": 6,
     "fontname": "Ableton Sans Bold",
     "fontsize": 10.0,
     "bgcolor": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "bgovercolor": [
      1.0,
      0.709,
      0.196,
      0.15
     ],
     "bgoncolor": [
      1.0,
      0.709,
      0.196,
      0.35
     ],
     "saved_attribute_attributes": {
      "bordercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "borderoncolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textcolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textovercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textoncolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textoveroncolor": {
       "expression": "themecolor.live_lcd_control_fg"
      }
     },
     "bgoveroncolor": [
      1.0,
      0.709,
      0.196,
      0.35
     ],
     "bordercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "borderoncolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textcolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textovercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textoncolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textoveroncolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "usebgoncolor": 1
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
     "text": "Scegli uno strumento o usa ◀ ▶: si carica e la clip suona in loop. Doppio clic su Prova: vai alla traccia.",
     "fontname": "Ableton Sans Bold",
     "fontsize": 10.0,
     "textcolor": [
      0.92,
      0.92,
      0.92,
      1.0
     ],
     "saved_attribute_attributes": {
      "textcolor": {
       "expression": "themecolor.live_control_fg"
      }
     }
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
      140,
      536,
      18
     ],
     "text": "Avvio…",
     "linecount": 1,
     "fontname": "Ableton Sans Medium",
     "fontsize": 10.0,
     "textcolor": [
      0.92,
      0.92,
      0.92,
      1.0
     ],
     "saved_attribute_attributes": {
      "textcolor": {
       "expression": "themecolor.live_lcd_title"
      }
     }
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
      142,
      76,
      130,
      22
     ],
     "text": "Clip → Melodia",
     "mode": 0,
     "rounded": 6,
     "fontname": "Ableton Sans Bold",
     "fontsize": 10.0,
     "bgcolor": [
      0.0,
      0.0,
      0.0,
      0.0
     ],
     "bgovercolor": [
      1.0,
      0.709,
      0.196,
      0.15
     ],
     "bgoncolor": [
      1.0,
      0.709,
      0.196,
      0.35
     ],
     "saved_attribute_attributes": {
      "bordercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "borderoncolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textcolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textovercolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textoncolor": {
       "expression": "themecolor.live_lcd_control_fg"
      },
      "textoveroncolor": {
       "expression": "themecolor.live_lcd_control_fg"
      }
     },
     "bgoveroncolor": [
      1.0,
      0.709,
      0.196,
      0.35
     ],
     "bordercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "borderoncolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textcolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textovercolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textoncolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "textoveroncolor": [
      1.0,
      0.709,
      0.196,
      1.0
     ],
     "usebgoncolor": 1
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
      2
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
      2
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
      2
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
