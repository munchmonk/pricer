#!/Library/Frameworks/Python.framework/Versions/2.7/bin/python2.7

# threading to improve speed
# accept an output as input to update a few cards, keeping the rest intact
# bug: if a card has been printed in one set only, the page doesn't exist and it doesn't find it
# accept quantity as digit instead of digit + x (4 bolt instead of 4x bolt)

from __future__ import print_function
from bs4 import BeautifulSoup
import urllib2
import sys


def justify(s1, s2):
    MAXLEN = 70
    dashes = (MAXLEN - len(s1) - len(s2)) * '-'
    return s1 + dashes + s2


def manual_decode(cardname):
    cardname = cardname.replace('\xe2', '\'')
    cardname = cardname.replace('\x80', '')
    cardname = cardname.replace('\x99', '')
    return cardname


def parse_cardname(cardname):
    cardname = cardname.strip().lower()
    cardname = cardname.replace(',', '%2C')
    cardname = cardname.replace(' ', '+')
    cardname = cardname.replace('\'', '%27')
    return cardname


POOR = ('Poor', 6)
LIGHT_PLAYED = ('Light Played', 5)
PLAYED = ('Played', 4)
GOOD = ('Good', 3)
EXCELLENT = ('Excellent', 2)
NEAR_MINT = ('Near Mint', 1)
MINT = ('Mint', 0)

PAGENOTFOUND = -1
NOTENOUGH = -2

conditions_order = (NEAR_MINT, LIGHT_PLAYED, MINT, EXCELLENT, GOOD, PLAYED, POOR)


def get_card_price(cardname, copies=1, min_cond=POOR[1]):
    mkm = 'https://www.cardmarket.com/en/Magic/Cards/'
    cardname = parse_cardname(cardname)
    url = mkm + cardname
    page = urllib2.urlopen(url)
    soup = BeautifulSoup(page.read(), 'html.parser')
    table = soup.find('table', class_='MKMTable fullWidth mt-40')

    try:
        rows = table.select("tr")
    except AttributeError:
        return [PAGENOTFOUND]

    price_list = []

    for row in rows:
        price = None
        condition = None
        copies_found = 0

        # Price
        price_column = row.find('td', class_='st_price Price')
        if price_column:
            price = price_column.get_text()
            price = price[:-1]
            price = price.replace(',', '.')

            # Deal with playsets and multiples
            if 'PPU' in price:
                price = price[:-2]
                price = price.split(' ')
                playset_price = float(price[0])
                unit_price = float(price[2])
                price = unit_price
                copies_found += round(playset_price / unit_price)
            else:
                price = float(price)
                copies_found += 1

        # Condition
        condition_column = row.find('td', class_='Condition')
        if condition_column:
            condition_text = str(condition_column.select('div span')[0])
            for c in conditions_order:
                if c[0] in condition_text:
                    condition = c[1]
                    break

        # Only accept results with the specified condition
        if not(price and condition and condition <= min_cond):
            copies_found = 0

        # Add all results
        while len(price_list) < copies and copies_found > 0:
            price_list.append(price)
            copies_found -= 1

        # Return if applicable
        if len(price_list) == copies:
            return price_list

    return [NOTENOUGH]


def get_decklist(filename):
    ret = []

    try:
        f = open(filename, 'r')
    except IOError:
        print("Failed to open {}.".format(filename))
        return ret

    for line in f:
        word_list = line.strip().split(' ', 1)

        # Input sanity checks
        # Log comments and move to next line
        if len(word_list) < 2:
            ret.append((-1, line))
            continue

        # Ensure the firse word is a number, if not log it as a comment
        quantity = word_list[0]
        if quantity[-1] not in '0123456789':
            quantity = quantity[:-1]
            # quantity = word_list[0][:-1]
        try:
            quantity = int(quantity)
        except ValueError:
            ret.append((-1, line))
            continue

        # Line is legal, fix the apostrophe issue and add it to the return list
        cardname = word_list[1]
        cardname = manual_decode(cardname)
        ret.append((quantity, cardname))

    f.close()
    return ret


def get_owned_quantity(item, owned):
    for o in owned:
        if o[1].lower() == item[1].lower():
            return o[0]
    return 0


def get_deck_price(decklist, filename, min_cond=POOR[1], owned=None, comments=True):
    totprice = 0
    f = open(filename, 'w')

    for item in decklist:
        orig_quantity = item[0]
        quantity = orig_quantity
        cardname = item[1]

        # Print comments and move on
        if quantity == -1 and comments:
            f.write(item[1])
            continue

        # Check if I already have copies of the card in question
        if owned:
            owned_quantity = get_owned_quantity(item, owned)
            if owned_quantity > 0:
                quantity = orig_quantity - owned_quantity
                s1 = "{0}x {1}".format(min(orig_quantity, owned_quantity), cardname)
                s2 = "ALREADY OWNED"
                s = justify(s1, s2) + '\n'
                f.write(s)

        # Calculate cost of the remaining copies
        if quantity > 0:
            s1 = '{0}x {1}'.format(quantity, cardname)
            price_list = get_card_price(cardname, quantity, min_cond)

            if price_list[0] == PAGENOTFOUND:
                s2 = '*** FAILED TO FIND - CHECK SPELLING ***'

            elif price_list[0] == NOTENOUGH:
                s2 = '*** FAILED TO FIND - # OF COPIES / CONDITION ***'

            elif len(price_list) == quantity:
                playset_price = 0
                for price in price_list:
                    playset_price += price
                s2 = "{:.2f} euro".format(playset_price)
                totprice += playset_price
            else:
                s2 = "*** BUG, PLEASE REPORT IT ***"
            s = justify(s1, s2) + '\n'
            f.write(s)

    f.write('\n')
    s1 = 'Total deck price'
    s2 = '{:.2f} euro'.format(totprice)
    s = justify(s1, s2) + '\n'
    f.write(s)
    f.close()


def parse_commands(args):
    condition = PLAYED[1]
    copies = 1
    comments = True
    owned = True

    # Not enough arguments
    if len(args) == 1:
        print('Usage:')
        print('   ./price.py <cardname> [options]')
        print('   ./price.py <decklist> [options]')
        print('Options:')
        print('   -plain          only copies cards, leaving comments out')
        print('   -full           calculates the full price of the deck, regardless of owned cards')
        print('   -po             cards in any condition (default)')
        print('   -pl             only cards in played condition and above')
        print('   -lp             only cards in light played condition and above')
        print('   -g              only cards in good condition and above')
        print('   -ex             only cards in excellent condition and above')
        print('   -nm             only cards in near mint condition and above')
        print('   -m              only cards in mint condition')
        return

    args = args[1:]
    name = ''
    for arg in args:
        arg = arg.lower()
        if arg == '-po':
            condition = POOR[1]
        elif arg == '-pl':
            condition = PLAYED[1]
        elif arg == '-lp':
            condition = LIGHT_PLAYED[1]
        elif arg == '-g':
            condition = GOOD[1]
        elif arg == '-ex':
            condition = EXCELLENT[1]
        elif arg == '-nm':
            condition = NEAR_MINT[1]
        elif arg == '-m':
            condition = MINT[1]
        elif arg == '-plain':
            comments = False
        elif arg == '-full':
            owned = False
        else:
            name += arg + ' '

    name = name.strip()

    # Decklist
    if name[-4:] == '.txt':
        deck = get_decklist(name)
        if owned:
            owned = get_decklist('owned.txt')
            filename = name[:-4] + '_myprice.txt'
        else:
            owned = []
            filename = name[:-4] + '_fullprice.txt'
        print("Calculating total price for decklist...")
        get_deck_price(deck, filename, condition, owned, comments)
        print("Process completed! Results are in {}".format(filename))

    # Single card lookup
    else:
        print("Searching...")
        price = get_card_price(name, copies, condition)[0]
        if price == PAGENOTFOUND:
            print('Not found - check spelling.')
        elif price == NOTENOUGH:
            print('Not found - change # of copies / min. condition.')
        else:
            print('{:.2f} euro'.format(price))


if __name__ == '__main__':
    parse_commands(sys.argv)