#!/usr/bin/env python
# encoding: utf-8

import os
import sys
import random
import tweepy
from secret import TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_TOKEN_SECRET
from gamefaqs import get_random_walkthrough_instruction
from ikea import get_ikea_product

ROOT_PATH = os.path.dirname(os.path.abspath(__file__)) + '/'

FULLWIDTH_A_ORD = ord(u'Ａ')
ASCII_A_ORD = ord('A')
def convert_to_fullwidth(s):
    new_str = []
    for c in s:
        if ASCII_A_ORD <= ord(c) <= ASCII_A_ORD + 25:
            new_str.append(unichr(ord(c) - ASCII_A_ORD + FULLWIDTH_A_ORD))
        else:
            new_str.append(u' ' + c + ' ')
    return ''.join(new_str)

origmap = """!"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\]^_`abcdefghijklmnopqrstuvwxyz{|}"""
tinymap = u"""﹗"#﹩﹪﹠'⁽⁾﹡+,⁻⋅/⁰¹²³⁴⁵⁶⁷⁸⁹﹕﹔<⁼>﹖@ᴬᴮᶜᴰᴱᶠᴳᴴᴵᴶᴷᴸᴹᴺᴼᴾᑫᴿˢᵀᵁⱽᵂˣʸᶻ[\]^_`ᵃᵇᶜᵈᵉᶠᵍʰᶦʲᵏᶫᵐᶰᵒᵖᑫʳˢᵗᵘᵛʷˣʸᶻ{|}"""
tiny_translation = dict(zip(origmap, tinymap))
def convert_to_tiny(s):
    return ''.join(tiny_translation.get(c, c) for c in s)

def post_tweet():
    attempts = 0
    while attempts < 3:
        product_name, output_filename = get_ikea_product()
        if product_name is None:
            attempts += 1
            continue
        else:
            break
    else:
        print 'No suitable diagram found'
        sys.exit(1)
    formatted_product_name = convert_to_fullwidth(product_name)

    attempts = 0
    while attempts < 10:
        random_instruction = get_random_walkthrough_instruction()
        if not random_instruction:
            attempts += 1
            continue

        # random_instruction = random_instruction.lower().replace(',', '').replace('.', '')
        # message = message + '\n' + convert_to_tiny(random_instruction)

        if random_instruction.split(' ', 1)[0][-1].isalpha():
            random_instruction = 'Step {}: '.format(random.randint(5, 20)) + random_instruction

        message = formatted_product_name + '\n' + random_instruction
        if len(message) > 140:
            attempts += 1
        else:
            break
    else:
        print 'too many attempts to get a short message'
        sys.exit(1)

    print 'Tweeting:', message
    # Submit to Twitter
    auth = tweepy.OAuthHandler(TWITTER_API_KEY, TWITTER_API_SECRET)
    auth.secure = True
    auth.set_access_token(TWITTER_ACCESS_TOKEN, TWITTER_TOKEN_SECRET)
    api = tweepy.API(auth)
    print message
    print api.update_with_media(output_filename, status=message)

    # Delete temp files
    os.unlink(output_filename)

if __name__ == '__main__':
    post_tweet()
