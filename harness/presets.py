"""Release-independent role and provider presets; concrete models resolve per run."""

EFFORTS = ('low', 'medium', 'high')
PROVIDERS = ('auto', 'openai', 'anthropic')
DEFAULT_PROVIDERS = {'low': 'openai', 'medium': 'anthropic', 'high': 'openai'}
BACKENDS = {'openai': 'codex', 'anthropic': 'claude'}
CREATIVE = {'writer', 'animator', 'director'}
QA = {'researcher', 'critic', 'selector', 'reviewer'}
ROLES = ('researcher', 'writer', 'critic', 'selector', 'producer', 'animator', 'director', 'editor', 'reviewer')


def worker_presets(effort='medium', provider='auto'):
    primary = DEFAULT_PROVIDERS[effort] if provider == 'auto' else provider
    providers = [primary, 'anthropic' if primary == 'openai' else 'openai']
    workers = {}
    for role in ROLES:
        workers[role] = []
        for vendor in providers:
            if vendor == 'openai':
                if role in CREATIVE:
                    tier, thinking = {'high': ('quality', 'high'), 'medium': ('balanced', 'medium'),
                                      'low': ('economy', 'low')}[effort]
                elif role in QA:
                    tier, thinking = ('balanced', 'medium') if effort == 'high' else ('economy', 'low')
                else:
                    tier, thinking = ('economy', 'low') if effort == 'low' else ('balanced', 'medium')
            elif role in CREATIVE:
                tier, thinking = {'high': ('quality', 'max'), 'medium': ('quality', 'medium'),
                                  'low': ('balanced', 'low')}[effort]
            else:
                tier = 'economy' if role in QA and effort == 'low' else 'balanced'
                thinking = None if tier == 'economy' else 'low' if effort == 'low' else 'medium'
            profile = {'provider': BACKENDS[vendor], 'model': f'auto:{tier}'}
            if thinking:
                profile['effort'] = thinking
            workers[role].append(profile)
    return workers
