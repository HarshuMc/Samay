# -*- coding: utf-8 -*-
"""
SAMAY graphical UI notes
=========================
The entire SAMAY interface is drawn with Cairo on top of GTK 3.
There is no bitmap asset pipeline and no external UI theme files aside from
`samay/ui/samay.css`, which is used as a styling reference.

Key visual goals:
- Galaxy Watch / OneUI style
- Glassmorphism panels with dynamic opacity
- Clean traffic light buttons and compact opacity slider
- Live day/night background that reacts to weather data
- Weather particle overlays (rain, snow, thunderstorm)

This module is a placeholder for any future highly-custom UI pass.
"""
