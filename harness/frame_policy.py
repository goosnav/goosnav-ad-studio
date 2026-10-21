"""One controller-owned typography contract for production and review."""

LINK = {'font': 'sys-times', 'color': '#0000ee', 'underline': True}
CARD = {'retro': {'enabled': True, 'pixel': 2, 'aliased': True, 'rgb_split': 0,
                  'scanlines': 'off', 'shadow': False, 'jitter': False,
                  'typewriter': False, 'cursor': False},
        'media_fx': {'mode': 'ps1', 'pixel': 3, 'levels': 32}}
DESCRIPTION = ('Frame owns the early-web-2002 end card: black Helvetica Bold title; blue '
               '(#0000ee), underlined Times New Roman URL on white, like an old browser hyperlink. '
               'Use the installed Times New Roman face, or bundled Times-compatible Termes if unavailable. '
               'Steady aliased pixel type and ordered Bayer dithering on the closing end_card product picture. '
               'Full-ad framing uses the same type but keeps media processing clean. '
               'No jitter, scanlines, RGB splitting, shadows, blinking cursor or typewriter animation. '
               'The floating product picture may move; the story picture stays untouched. '
               'A director picture description cannot override this rendering contract.')
