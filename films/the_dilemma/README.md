# THE DILEMMA (reference film)

A 90 s, 24 fps film. A giant generic Book 2 stands like a monolith on a paper desert under three suns, then explodes. Its drawings become a tornado (hero pages: Foot Oiling Machine, Emotion Nullifier, Self-Filling Coffee Mug). The pages come down as Goosklerf cards and dice that build a fortress, 2026 comics fall from a slot in the sky (the Patreon), and everything rewinds into the book. It ends on the hero shot with prices, then the white card.

Rebuild from scratch (about 3 h of render in 4:5 on the studio machine):

```
python3 -m studio vo the_dilemma --voice en_US-norman-medium   # slow 0.93 (default); public-domain voice
python3 -m studio render the_dilemma --format 4x5
python3 -m studio sound the_dilemma --format 4x5
python3 -m studio type the_dilemma --format 4x5
python3 -m studio assemble the_dilemma --format 4x5 --name THE_DILEMMA
python3 -m studio qa the_dilemma --format 4x5 --name THE_DILEMMA
```

The VO is placed at the times in `sound.py` (`VO_AT`). Hard cuts are listed in `film.py` (`CUT_FRAMES`).

Textures used, from `<assets>/textures`:

- `gen_book_*`, `gen_card.png`, `gen_pack.png`
- `page_00..05`, `hero_*`, `comic_00..06`
- `die_*`
