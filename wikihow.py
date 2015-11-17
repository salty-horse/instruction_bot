#!/usr/bin/env python

import random
from pattern.web import URL, Element, plaintext

def get_random_step(title=None):
    if title is not None and 'how to' in title.lower():
        title = title.lower().replace('how to', '', 1).strip()

    page = URL('http://www.wikihow.com/Special:Randomizer').read()

    steps = []
    e = Element(page)
    for s in e('.steps li'):
        try:
            main = s('b.whb')[0].string
            extra = s.string[s.string.index(main) + len(main) + 4:]

            if '<div class="clearall">' in extra:
                extra = extra[:extra.index('<div class="clearall">')]

            plain = plaintext(main)
            if len(plain) < 100:
                steps.append(plain)

        except Exception as e:
            pass

    return random.choice(steps)
