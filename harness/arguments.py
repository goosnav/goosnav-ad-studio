"""Shared CLI choices and actionable parse errors for both entrypoints."""
import argparse
import difflib
import sys

from .presets import EFFORTS, PROVIDERS


class HelpfulParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('allow_abbrev', False)
        super().__init__(*args, **kwargs)

    def error(self, message):
        self.print_help(sys.stderr)
        if 'unrecognized arguments:' in message:
            token = message.split('unrecognized arguments:', 1)[1].strip().split()[0]
            matches = difflib.get_close_matches(token, self._option_string_actions, n=1, cutoff=.65)
            if matches:
                message += f'\nDid you mean {matches[0]}?'
        self.exit(2, f'\nerror: {message}\n')


def add_model_options(parser):
    parser.add_argument('-e', '--effort', '-effort', choices=EFFORTS, type=str.lower,
                        help='model intensity preset (default medium): low, medium, high')
    parser.add_argument('-p', '--provider', '-provider', choices=PROVIDERS, type=str.lower,
                        help='preferred provider, with automatic failover (auto: high/low openai, medium anthropic)')


def model_overrides(args):
    selected = {key: getattr(args, key) for key in ('effort', 'provider') if getattr(args, key, None) is not None}
    return {'generation': selected} if selected else {}
