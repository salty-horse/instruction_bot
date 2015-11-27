#!/usr/bin/env python
# encoding: utf-8

import os
import re
import random
from pattern.web import URL, Element, decode_entities
from pattern.en import parsetree

ROOT_PATH = os.path.dirname(os.path.abspath(__file__)) + '/'

RE_REPEATING_WHITESPACE = re.compile(r'([\w])( {2,})')
RE_LEADING_WHITESPACE = re.compile(r'^(\s+)')

RE_REPEATING_CHARS = re.compile(r'([^ ])\1{4,}')
RE_ENUMERATED_LIST = re.compile('([^.])\n(\\s*\\d+\\. )', re.MULTILINE)


bad_words = set(open(ROOT_PATH + 'badwords.txt').read().splitlines())
bad_words.add('faq')

filter_words = [
    'adult visual novel',
    'bishoujo',
    'eroge',
    'hentai',
]

filter_substrings = [
    'http',
    '.com',
    'copyright',
]

def get_random_walkthrough_instruction(char_limit=95):
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
            print 'No FAQs found for', game_url
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

        lower_walkthrough_text = walkthrough_text.lower()
        if any(word in lower_walkthrough_text for word in filter_words):
            print 'bishoujo/adult visual novel found'
            return None

        # Strip all blocks of multiple spaces, ignore space blocks in the
        # beginning of the line.
        clean_lines = []
        for line in walkthrough_text.splitlines():
            match = RE_LEADING_WHITESPACE.match(line)
            if match:
                leading_whitespace = match.groups()[0]
            else:
                leading_whitespace = ''
            line = leading_whitespace + RE_REPEATING_WHITESPACE.sub('\\1.\n\\2', line.lstrip())
            clean_lines.append(line)
        no_whitespace_text = '\n'.join(clean_lines)


        # Cleanup
        clean_lines = []

        for line in no_whitespace_text.splitlines():
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
                if not (prev_line.startswith('\t') or prev_line.startswith(' ')) and \
                        (prev_line.strip()[-1].isalpha() or prev_line.strip()[-1] == ':'):
                    prev_line = prev_line.rstrip()
                    if prev_line:
                        if prev_line[-1].isalpha():
                            prev_line += '.'
                        else:
                            prev_line = prev_line[:-1] + '.'

                    clean_lines[-1] = prev_line

                clean_lines.append(line.rstrip())
                line_added = True

            if not line_added:
                clean_lines.append(line.rstrip())
        clean_text = '\n'.join(clean_lines)

        # Remove enumerations such as:
        # 1. hello        -> hello.
        # 2. world           world.
        clean_text = RE_ENUMERATED_LIST.sub('\\1.\n', clean_text)

        ptree = parsetree(clean_text)

        interesting_sentences = []
        for s in ptree:
            sentence_string = s.string
            sentence_string_lower = sentence_string.lower()

            if sentence_string.startswith(('I', "I ' m", '(')):
                continue

            # Filter How/Why/What/Where...
            if s[0].type == 'WRB':
                continue

            if sentence_string_lower.startswith('will'):
                continue

            if any(w.lower() in bad_words for w in sentence_string.split()):
                continue

            if (s[0].type == 'VB' and s[0].string.lower() != 'quit'):
                interesting_sentences.append(sentence_string)
            elif (len(s.words) >= 2 and (s.words[0].string.lower(), s.words[1].string.lower()) in [('do', "n't"), ('use', 'the')]):
                interesting_sentences.append(sentence_string)
            else:
                # Allow for any sentence with a verb.
                if any(word.type == 'VB' for word in s.words):
                    interesting_sentences.append(sentence_string)

        restored_sentences = [
            s.replace(' , ', ', '). \
              replace('|', ''). \
              replace(u' ’ ', " ' "). \
              replace(' ; ', ', '). \
              replace(' .', '. '). \
              replace(" 's ", "'s "). \
              replace(" ' s ", "'s "). \
              replace("s ' ", "s' "). \
              replace(u" ’ s ", "'s "). \
              replace(" 'll ", "'ll "). \
              replace(" ' ll ", "'ll "). \
              replace(" n't", "n't"). \
              replace(" 're ", "'re "). \
              replace(" ' re ", "'re "). \
              replace(" 've ", "'ve "). \
              replace(" ' ve ", "'ve "). \
              replace('$ ', '$'). \
              replace(" ( ", " ("). \
              replace(" )", ")"). \
              replace(" [ ", " ["). \
              replace(" ]", "]"). \
              replace(" { ", " {"). \
              replace(" }", "}"). \
              replace(' :', ':'). \
              replace(' ?', '?'). \
              replace('. .', '.'). \
              # replace('* *', '**'). \
              # replace('*', ''). \
              replace(' !', '!').strip()
              for s in interesting_sentences
        ]

        restored_sentences = [
            s for s in restored_sentences
            if not any(substr in s for substr in filter_substrings)
        ]

        short_sentences = list(set(s for s in restored_sentences if len(s) <= char_limit and len(s.split()) > 2))
        if not short_sentences:
            return None

        random_sentence = random.choice(short_sentences)

        return random_sentence
