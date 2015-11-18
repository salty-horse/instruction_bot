#!/usr/bin/env python
# encoding: utf-8

import os
import re
import random
from pattern.web import URL, Element, decode_entities
from pattern.en import parsetree

ROOT_PATH = os.path.dirname(os.path.abspath(__file__)) + '/'

RE_REPEATING_CHARS = re.compile(r'(.)\1{9,}')
RE_ENUMERATED_LIST = re.compile('([^.])\n(\\s*\\d+\\. )', re.MULTILINE)


bad_words = set(open(ROOT_PATH + 'badwords.txt').read().splitlines())
bad_words.add('faq')

def get_random_walkthrough_instruction():
    with open(ROOT_PATH + '/games.txt') as f:
        game_url = 'http://gamefaqs.com' + random.choice([
                g for
                g in f.readlines()
                if not g.startswith('#')
            ]).strip()
        print game_url

        game_page = URL(game_url).read()

        # Look for General FAQs
        general_faqs = Element(game_page)('h2.title:contains(General)')
        if not general_faqs:
            print 'No FAQs found for', game_page
            return None

        walkthroughs = [
            elem.href
            for elem
            in general_faqs[0].parent.parent('td:first-child a')
        ]

        walkthrough_url = 'http://gamefaqs.com{}?print=1'.format(random.choice(walkthroughs))
        print walkthrough_url
        walkthrough_page = URL(walkthrough_url).read()
        walkthrough_text = decode_entities(' '.join(
            span.content
            for span
            in Element(walkthrough_page)('pre > span'))) #.replace('\r\n', '\n')

        if 'bishoujo' in walkthrough_text.lower():
            print 'bishoujo found'
            return None

        # Cleanup
        clean_lines = []

        for line in walkthrough_text.splitlines():
            if RE_REPEATING_CHARS.search(line):
                continue

            # Try catch headings like this and terminate the top sentence.
            # "Headline
            #      Stuff about it"

            line_added = False

            if line.startswith('\t') or line.startswith('  '):
                if not clean_lines:
                    continue
                prev_line = clean_lines[-1]
                if not prev_line:
                    continue
                if not (prev_line.startswith('\t') or prev_line.startswith(' ')) and prev_line.strip()[-1].isalpha():
                    clean_lines[-1] = prev_line.strip() + '.'

                line = line.strip()
                clean_lines.append(line.strip())
                line_added = True

            if not line_added:
                clean_lines.append(line.strip())
        clean_text = '\n'.join(clean_lines)

        # Remove enumerations such as:
        # 1. hello        -> hello.
        # 2. world           world.
        clean_text = RE_ENUMERATED_LIST.sub('\\1.\n', clean_text)

        ptree = parsetree(clean_text)
        interesting_sentences = [
            s.string for s in ptree if \
            ((s[0].type == 'VB' and s[0].string.lower() != 'quit') or
             (len(s.words) >= 2 and (s.words[0].string.lower(), s.words[1].string.lower()) in [('do', "n't"), ('use', 'the')])) \
            and not any(w.lower() in bad_words for w in s.string.split())
        ]

        restored_sentences = [
            s.replace(' , ', ', '). \
              replace(u' ’ ', " ' "). \
              replace(' ; ', ', '). \
              replace(' .', '. '). \
              replace(" 's ", "'s "). \
              replace("s ' ", "s' "). \
              replace(u" ’ s ", "'s "). \
              replace(" 'll ", "'ll "). \
              replace(" n't", "n't"). \
              replace(" 're ", "'re "). \
              replace(" ( ", " ("). \
              replace(" )", ")"). \
              replace(' :', ':'). \
              replace(' ?', '?'). \
              # replace('* *', '**'). \
              # replace('*', ''). \
              replace(' !', '!').strip()
              for s in interesting_sentences
        ]

        short_sentences = list(set(s for s in restored_sentences if len(s) < 110 and len(s.split()) > 2))
        if not short_sentences:
            return None

        random_sentence = random.choice(short_sentences)

        return random_sentence
