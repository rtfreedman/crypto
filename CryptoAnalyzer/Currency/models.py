from __future__ import annotations
from django.db import models
from itertools import permutations
from typing import Tuple, List, DefaultDict
from hashlib import sha256
from django.http import HttpResponseNotAllowed
from django.utils import timezone
from django.db.models import Q
import pytz
import datetime
from decimal import Decimal
from django.utils.timezone import make_aware
import requests
import os
import json
import time
import hmac
import logging
import settings
from itertools import islice

insert_batch_size = 100
__api_key = ''
__api_secret = ''
base_url = ''
__authenticated = False
__last_request = 0
__nice_time = 0.1

logger = logging.getLogger(__name__)

if settings.DEBUG:
    logger.setLevel(logging.DEBUG)


def __generate_access_sign_and_timestamp(request_path: str, method: str = 'GET', body: str = '') -> Tuple[str, int]:
    if not __authenticated:
        raise HttpResponseNotAllowed
    message = str(timestamp := round(time.time())) + method + request_path + body
    access_sign = hmac.new(__api_secret.encode('latin-1'), message.encode('latin-1'), sha256).hexdigest().upper()
    return access_sign, timestamp


def authenticate(url: str, api_key: str, api_secret: str):
    global __api_key, __api_secret, __authenticated, base_url
    base_url = url
    __api_key = api_key
    __api_secret = api_secret
    __authenticated = True


class Currency(models.Model):
    short_name = models.TextField(unique=True)
    min_size = models.DecimalField(max_digits=20, decimal_places=10)
    name = models.TextField(unique=True)
    last_request_time = 0

    @classmethod
    def collect_currency_info(cls) -> List[Currency]:
        request_url = base_url.format('currencies')
        # access_sign, timestamp = Currency.generate_access_sign_and_timestamp(request_url)
        try:
            r = cls.__get_nice(request_url, headers={
                'Content-Type': 'application/json',
                # 'CB-ACCESS-TIMESTAMP': str(timestamp),
                # 'CB-ACCESS-KEY': api_key,
                # 'CB-ACCESS-SIGN': access_sign,
            })
        except Exception as e:
            logger.warning(f'GET {request_url} exception {e}')
            return
        if not r:
            return
        currency_objects = []
        for currency in r.json():
            cur, _ = Currency.objects.get_or_create(short_name=currency["id"].lower(), defaults={
                'min_size': Decimal(currency['min_size']),
                'name': currency['name'].lower(),
            })
            currency_objects.append(cur)
        return currency_objects

    @staticmethod
    def __datetime_generator(start: datetime.datetime, end: datetime.datetime, granularity: datetime.timedelta) -> Tuple[datetime.datetime, datetime.datetime]:
        # TODO: test me!
        api_max_length = 300
        i = 0
        # TODO: calculate the number of total requests and turn this into a for loop
        while True:
            i += 1
            set_end = start + ((i+1) * granularity * api_max_length)
            set_start = start + (i * api_max_length * granularity)
            if set_end > end:
                yield (set_start, end)
                return
            yield (set_start, set_end)

    @classmethod
    def collect_coinbase_rates(cls, date_start: datetime.datetime, date_end: datetime.datetime, currencies_sn: List[str] = ['btc', 'usd', 'xau'], granularity: datetime.timedelta = datetime.timedelta(seconds=86400)) -> List[Rate]:
        try:
            currencies = [Currency.objects.get(short_name=currency) for currency in currencies_sn]
        except Currency.DoesNotExist:
            return
        rates = []
        # refactor me
        for from_elem, to_elem in permutations(currencies, 2):
            print(f'Running {from_elem.short_name}-{to_elem.short_name}')
            for start_date, end_date in cls.__datetime_generator(date_start, date_end, granularity):
                req_url = base_url.format(
                    f'products/{from_elem.short_name.upper()}-{to_elem.short_name.upper()}/candles?start={start_date.strftime("%Y-%m-%dT%H:%M:%S")}&end={end_date.strftime("%Y-%m-%dT%H:%M:%S")}&granularity={int(granularity.total_seconds())}')
                try:
                    resp = cls.__get_nice(req_url, headers={
                        'content-type': 'application/json',
                    })
                except Exception as e:
                    logger.warning(f'GET {req_url} exception {e}')
                    continue
                if resp.status_code == 404:
                    # we've got a bad currency combo
                    # try the next one
                    logger.warning(f'GET {req_url} not found {resp.status_code}: {resp.text}')
                    break
                if resp.status_code != 200:
                    logger.warning(f'GET {req_url} bad status code {resp.status_code}: {resp.text}')
                    continue
                for rate_obj in resp.json():
                    try:
                        unix_timestamp, low_rate, high_rate, open_rate, close_rate, volume = rate_obj
                        rate = Rate(
                            from_currency=from_elem,
                            to_currency=to_elem,
                            timestamp=make_aware(datetime.datetime.fromtimestamp(unix_timestamp)),
                            source=req_url,
                            low_rate=Decimal(low_rate),
                            high_rate=Decimal(high_rate),
                            open_rate=Decimal(open_rate),
                            close_rate=Decimal(close_rate),
                            volume=Decimal(volume))
                        rates.append(rate)
                    except Exception as e:
                        logger.warning(f'{rate_obj} : {e}')
                        raise
        Rate.objects.bulk_create(rates, batch_size=100, ignore_conflicts=True)
        return rates

    @ classmethod
    def __get_nice(cls, url, **kwargs):
        if time.time() - cls.last_request_time < 0.3:
            time.sleep(0.3 - (time.time() - cls.last_request_time))
        cls.last_request_time = time.time()
        resp = requests.get(url, **kwargs)
        if not resp or resp.status_code == 429:
            time.sleep(5)
            resp = requests.get(url, **kwargs)
        return resp

    def to_dict(self) -> DefaultDict:
        return {
            'short_name': self.short_name,
            'min_size': self.min_size,
            'name': self.name,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class Rate(models.Model):
    from_currency = models.ForeignKey(Currency, on_delete=models.CASCADE, related_name='idfrom')
    to_currency = models.ForeignKey(Currency, on_delete=models.CASCADE, related_name='idto')
    timestamp = models.DateTimeField()
    low_rate = models.DecimalField(default=Decimal(0), max_digits=20, decimal_places=10)
    high_rate = models.DecimalField(default=Decimal(0), max_digits=20, decimal_places=10)
    open_rate = models.DecimalField(default=Decimal(0), max_digits=20, decimal_places=10)
    close_rate = models.DecimalField(default=Decimal(0), max_digits=20, decimal_places=10)
    volume = models.DecimalField(default=Decimal(0), max_digits=20, decimal_places=10)
    source = models.TextField(default='system')

    def __create_via_rate(self, to_rate: Rate, from_currency: Currency, to_currency: Currency, via_currency: Currency):
        # called on from_rate - this is just for clarity
        from_rate = self
        # Overexplaining in case I ever need to debug this again, which I imagine would be a giant pain in the ass
        # rates are like this: from_currency => to_currency so BTC * Rate (usd/btc) = USD for from_sn=btc to_sn=usd
        # normally this would mean interpretting btc to eth via usd would mean:
        # from_rate [usd/btc] * (1 / to_rate) [eth/usd]
        # but because we may only have one rate (btc/usd in this contrived example) we may need to flip stuff

        # going from via for both currencies
        if (from_rate.from_currency.short_name == via_currency.short_name and
                to_rate.from_currency.short_name == via_currency.short_name):
            # our from_rate is coming from the via currency: from usd to btc i.e. (btc/usd)
            # our to_rate is coming from the via currency: from usd to eth i.e. (eth/usd)
            # flip from_rate: (eth/usd) / (btc/usd)  = eth/btc
            low_rate = to_rate.low_rate / from_rate.low_rate
            high_rate = to_rate.high_rate / from_rate.high_rate
            open_rate = to_rate.open_rate / from_rate.open_rate
            close_rate = to_rate.close_rate / from_rate.close_rate
        elif (from_rate.from_currency.short_name == via_currency.short_name and
                to_rate.from_currency.short_name == to_currency.short_name):
            # our from_rate is coming from the via currency: from usd to btc i.e. (btc/usd)
            # our to_rate is coming fom the to_currency: from eth to usd i.e. (usd/eth)
            # flip both: 1 / ((btc/usd) * (usd/eth)) = 1 / (btc/eth) = eth/btc
            low_rate = 1 / (from_rate.low_rate * to_rate.low_rate)
            high_rate = 1 / (from_rate.high_rate * to_rate.high_rate)
            open_rate = 1 / (from_rate.open_rate * to_rate.open_rate)
            close_rate = 1 / (from_rate.close_rate * to_rate.close_rate)
        elif (from_rate.from_currency.short_name == from_currency.short_name and
                to_rate.from_currency.short_name == via_currency.short_name):
            # our from_rate is coming from the from currency: from btc to usd i.e. (usd/btc)
            # our to_rate is coming from the via currency: from usd to eth i.e. (eth/usd)
            # flip nothing: (usd/btc) * (eth/usd) = eth/btc
            low_rate = from_rate.low_rate * to_rate.low_rate
            high_rate = from_rate.high_rate * to_rate.high_rate
            open_rate = from_rate.open_rate * to_rate.open_rate
            close_rate = from_rate.close_rate * to_rate.close_rate
        elif (from_rate.from_currency.short_name == from_currency.short_name and
                to_rate.from_currency.short_name == to_currency.short_name):
            # our from_rate is coming from the from currency: from btc to usd i.e. (usd/btc)
            # our to_rate is coming from the to_currency: from eth to usd i.e. (usd/eth)
            # flip to_rate:  (usd/btc) * (eth/usd) = eth/btc
            low_rate = from_rate.low_rate / to_rate.low_rate
            high_rate = from_rate.high_rate / to_rate.high_rate
            open_rate = from_rate.open_rate / to_rate.open_rate
            close_rate = from_rate.close_rate / to_rate.close_rate
        return Rate(
            from_currency=from_currency,
            to_currency=to_currency,
            timestamp=from_rate.timestamp,
            source=f'system via {via_currency.short_name}',
            low_rate=low_rate,
            high_rate=high_rate,
            open_rate=open_rate,
            close_rate=close_rate,
            volume=self.volume,
        )

    @classmethod
    def calculate(cls, from_currency: Currency, to_currency: Currency, via_currency: Currency):
        from_rates = Rate.objects.filter(
            Q(from_currency=from_currency, to_currency=via_currency) |
            Q(from_currency=via_currency, to_currency=from_currency)
        ).order_by('timestamp')
        via_rates = []

        def generate_rates():
            for from_rate in from_rates.iterator(1000):
                try:
                    to_rates = Rate.objects.filter(
                        Q(from_currency=to_currency, to_currency=via_currency, timestamp=from_rate.timestamp) |
                        Q(from_currency=via_currency, to_currency=to_currency, timestamp=from_rate.timestamp)
                    )
                except Rate.DoesNotExist:
                    continue
                for to_rate in to_rates:
                    yield from_rate.__create_via_rate(to_rate, from_currency, to_currency, via_currency)
        Rate.objects.bulk_create(generate_rates, batch_size=1000, ignore_conflicts=True)
        return

    @classmethod
    def get_data_from_range(cls, date_start: datetime.datetime, date_end: datetime.datetime, currencies: List[Currency], base_currency: Currency, max_returned: int = 100, as_dict=False) -> DefaultDict[str, List]:
        # grab the rates based on currency
        rate_data = {}
        for currency in currencies:
            currency_rates = Rate.objects.filter(
                Q(timestamp__range=(date_start, date_end), from_currency=base_currency, to_currency=currency) |
                Q(timestamp__range=(date_start, date_end), from_currency=currency, to_currency=base_currency)
            ).order_by("timestamp")
            # order by timestamp so we can adjust evenly-ish for the max_returned (provided data is evenly distributed)
            result_count = currency_rates.count()
            min_timedelta = None
            if result_count > max_returned:
                min_timedelta = (date_end - date_start) / max_returned
            last_rate_time = None
            yielded_rates = []
            for rate in currency_rates.iterator(chunk_size=1000):
                if last_rate_time and min_timedelta and (last_rate_time + min_timedelta) > rate.timestamp:
                    continue
                if last_rate_time:
                    print(f'Yield: {len(yielded_rates)}', end='\r')
                last_rate_time = rate.timestamp
                if as_dict:
                    yielded_rates.append(rate.to_dict(base_currency_sn=base_currency.short_name))
                else:
                    yielded_rates.append(rate)
            rate_data[currency.short_name] = yielded_rates
        return rate_data

    def to_dict(self, base_currency_sn: str = None):
        if base_currency_sn == self.from_currency.short_name:
            return {
                'from_sn': self.to_currency.short_name,
                'from_id': self.to_currency.id,
                'to_sn': self.from_currency.short_name,
                'to_id': self.from_currency.id,
                'timestamp': self.timestamp,
                'low_rate': 1/self.high_rate,
                'high_rate': 1/self.low_rate,
                'open_rate': 1/self.open_rate,
                'close_rate': 1/self.close_rate,
                'volume': self.volume,
            }
        return {
            'from_sn': self.from_currency.short_name,
            'from_id': self.from_currency.id,
            'to_sn': self.to_currency.short_name,
            'to_id': self.to_currency.id,
            'timestamp': self.timestamp,
            'low_rate': self.low_rate,
            'high_rate': self.high_rate,
            'open_rate': self.open_rate,
            'close_rate': self.close_rate,
            'volume': self.volume,
        }

    class Meta:
        indexes = [models.Index(fields=['timestamp'])]
        unique_together = [['from_currency', 'to_currency', 'timestamp', 'source']]
