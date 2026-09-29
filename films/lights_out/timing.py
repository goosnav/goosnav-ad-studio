"""Shared timings for picture and sound (no bpy)."""
BEAT = 0.625
DUR = 90.0
# narration placement (seconds) -- shared with sound.py and the .srt
VO_AT = {'01': 3.1, '02': 5.4, '03': 10.6, '04': 16.6, '05': 22.7, '06': 28.2, '07': 33.1, '08': 35.7,
         '09': 39.0, '10': 44.1, '11': 47.7, '12': 52.8, '13': 59.3, '14': 62.1, '15': 65.0, '16': 68.8,
         '17': 72.6, '18': 77.6, '19': 80.7, '20': 86.0}
T = dict(
    BREAKER=0.6, LAMPS=1.0,
    REEL=10.0, PRESS=16.25, SHEETS=22.5, BIND=28.125, BIND_T0=28.3, BIND_SLAM=31.875, LINE=35.0,
    KILN=38.75, DICE_T0=39.2, QUENCH=45.0, SHUF=47.5, CRIMP=50.0,
    TUBE=52.5, FIRE=58.125, TUBEUP=58.75,
    ARMS=63.75, ARMS_T0=64.0, WAKE=71.25, ROW=76.25,
    DOCK=80.0, LAMPS_OFF=85.3, END=85.9,
)
