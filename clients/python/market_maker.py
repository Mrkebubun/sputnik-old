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
import urllib2
import json
from bs4 import BeautifulSoup
import logging

class MarketMakerBot(TradingBot):
    external_markets = {}

    def startAutomationAfterAuth(self):
        rate = 1

        self.get_external_market = task.LoopingCall(self.getExternalMarket)
        self.get_external_market.start(rate * 60)

        self.monitor_orders = task.LoopingCall(self.monitorOrders)
        self.monitor_orders.start(rate * 1)

        return True

    def startAutomation(self):
        self.authenticate()

    # See if we have any orders on a given side
    def cancelOrders(self, currency, side):
        for id, order in self.orders.items():
            if order['is_cancelled'] or order['quantity_left'] <= 0:
                continue

            if order['side'] == side and order['contract'] == 'BTC/%s' % currency:
                self.cancelOrder(id)

    def checkOrders(self, side):
        for id, order in self.orders.iteritems():
            if order['is_cancelled'] or order['quantity_left'] <= 0:
                continue

            if order['side'] == side:
                return True

        return False

    def getExternalMarket(self):
        try:
            url = "https://www.bitstamp.net/api/ticker/"
            file_handle = urllib2.urlopen(url)
            json_data = json.load(file_handle)
            btcusd_bid = float(json_data['bid'])
            btcusd_ask = float(json_data['ask'])
        except Exception as e:
            # Unable to get markets, just exit
            print "unable to get external market data: %s" % e
            return

        for currency in self.currency_list:
            try:
            # Get Yahoo quote
                url = "http://finance.yahoo.com/q?s=USD%s=X" % currency
                file_handle = urllib2.urlopen(url)
                soup = BeautifulSoup(file_handle)
                bid = float(soup.find(id="yfs_b00_usd%s=x" % currency.lower()).text)
                ask = float(soup.find(id="yfs_a00_usd%s=x" % currency.lower()).text)
            except Exception as e:
                # Unable to get markets, just exit
                print "unable to get external market data: %s" % e
                continue


            new_bid = int(btcusd_bid * bid)
            new_ask = int(btcusd_ask * ask)
            if currency in self.external_markets:
                if new_bid != self.external_markets[currency]['bid']:
                    self.external_markets[currency]['bid'] = new_bid
                    self.replaceBidAsk(currency, new_bid, 'BUY')
                if new_ask != self.external_markets[currency]['ask']:
                    self.external_markets[currency]['ask'] = new_ask
                    self.replaceBidAsk(currency, new_ask, 'SELL')
            else:
                self.external_markets[currency] = {'bid': new_bid, 'ask': new_ask}
                self.replaceBidAsk(currency, new_ask, 'SELL')
                self.replaceBidAsk(currency, new_bid, 'BUY')

    def replaceBidAsk(self, currency, new_ba, side):
        self.cancelOrders(currency, side)
        self.btcmxn_bid = new_ba

        self.placeOrder('BTC/%s' % currency, 25000000, int(new_ba) * 100, side)

    def monitorOrders(self):
        for currency, market in self.external_markets.iteritems():
            # Make sure we have orders open for both bid and ask
            for side in ['BUY', 'SELL']:
                total_qty = 0
                for id, order in self.orders.iteritems():
                    if order['side'] == side and order['is_cancelled'] is False and order['contract'] == 'BTC/%s' % currency:
                        total_qty += order['quantity_left']
                qty_to_add = 25000000 - total_qty
                if qty_to_add > 0:
                    if side == 'BUY':
                        price = int(market['bid']) * 100
                    else:
                        price = int(market['ask']) * 100

                    self.placeOrder('BTC/%s' % currency, qty_to_add, price, side)

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
    username = config.get("market_maker", "username")
    password = config.get("market_maker", "password")

    factory = BotFactory(uri, debugWamp=debug, username_password=(username, password))
    factory.protocol = MarketMakerBot

    # null -> ....
    if factory.isSecure:
        contextFactory = ssl.ClientContextFactory()
    else:
        contextFactory = None

    connectWS(factory, contextFactory)
    reactor.run()
