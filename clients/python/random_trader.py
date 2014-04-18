#!/usr/bin/env python
# Copyright (c) 2014, Mimetic Markets, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
# 1. Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
# IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
# TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
# PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED
# TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

__author__ = 'sameer'

import sys

from twisted.python import log
from twisted.internet import reactor, ssl, task

from autobahn.twisted.websocket import connectWS
from ConfigParser import ConfigParser

from client import TradingBot, BotFactory
import random, string
import logging

class RandomBot(TradingBot):
    def startAutomationAfterAuth(self):
        rate = 10

        self.place_orders = task.LoopingCall(self.placeRandomOrder)
        self.place_orders.start(1.0 * rate)

        self.chatter = task.LoopingCall(self.saySomethingRandom)
        self.chatter.start(10.0 * rate)

        return True

    def startAutomation(self):
        self.authenticate()

    def placeRandomOrder(self):
        random_markets = []
        for ticker, contract in self.markets.iteritems():
            if contract['contract_type'] != "cash":
                random_markets.append(ticker)

        # Pick a market at random
        ticker = 'BTC/%s' % random.choice(self.currency_list)
        side = random.choice(["BUY", "SELL"])
        contract = self.markets[ticker]

        # Set a price/quantity that is reasonable for the market
        tick_size = contract['tick_size']
        lot_size = contract['lot_size']
        denominator = contract['denominator']


        # Look at best bid/ask
        try:
            best_bid = max([order['price'] for order in self.markets[ticker]['bids']])
            best_ask = min([order['price'] for order in self.markets[ticker]['asks']])

            # Hit the other side
            if side is 'BUY':
                price = best_ask
            else:
                price = best_bid

            price = int(price / (tick_size * denominator)) * tick_size * denominator
        except (ValueError, KeyError):
            # We don't have a best bid/ask, don't trade
            return

        # a qty somewhere between 0.5 and 2 BTC
        quantity = random.randint(50,200) * lot_size

        self.placeOrder(ticker, quantity, price, side)

    def saySomethingRandom(self):
        random_saying = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(8))
        self.chat(random_saying)

    def cancelRandomOrder(self):
        if len(self.orders.keys()) > 0:
            while True:
                order_to_cancel = random.choice(self.orders.keys())
                if not self.orders[order_to_cancel]['is_cancelled'] and self.orders[order_to_cancel]['quantity_left'] > 0:
                    break
            self.cancelOrder(order_to_cancel)

if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(funcName)s() %(lineno)d:\t %(message)s', level=logging.DEBUG)

    if len(sys.argv) > 1 and sys.argv[1] == 'debug':
        debug = True
    else:
        debug = False

    log.startLogging(sys.stdout)
    config = ConfigParser()
    config.read("client.ini")

    uri = config.get("client", "uri")
    username = config.get("random_trader", "username")
    password = config.get("random_trader", "password")

    factory = BotFactory(uri, debugWamp=debug, username_password=(username, password))
    factory.protocol = RandomBot

    # null -> ....
    if factory.isSecure:
        contextFactory = ssl.ClientContextFactory()
    else:
        contextFactory = None

    connectWS(factory, contextFactory)
    reactor.run()