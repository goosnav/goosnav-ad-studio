"""The product content inventory handed to writers and animators.

harness/product_content.json lists real, viewable content for each product (pages, cards,
cover details, the current offer), each with a locator and a membership status. Workers build
ads around a specific item from it instead of a cover and a slogan. Editing that file (for
example, marking printed pages "confirmed") is how the owner widens what ads may claim.
"""
import json
from pathlib import Path

INVENTORY = Path(__file__).with_name('product_content.json')


def product_content(config, path=INVENTORY, *, compact=False):
    """Inventory entries for the configured products, matched by name prefix (case-insensitive).

    compact replaces long card ID lists with their count and the inventory path, for briefs
    with a tight prompt budget; the full list stays in the file.
    """
    entries = json.loads(Path(path).read_text())['products']
    names = [p['name'] if isinstance(p, dict) else str(p) for p in config.get('products', [])]
    chosen = []
    for entry in entries:
        key = entry['match'].casefold()
        matched = [n for n in names if n.casefold().startswith(key) or key.startswith(n.casefold())]
        if matched:
            item = {'product': matched[0], **{k: v for k, v in entry.items() if k != 'match'}}
            if compact and 'cards' in item:
                item['cards'] = {**{k: v for k, v in item['cards'].items() if k != 'ids'},
                                 'count': len(item['cards']['ids']),
                                 'ids': f'{len(item["cards"]["ids"])} card IDs in {INVENTORY}'}
            chosen.append(item)
    return chosen
