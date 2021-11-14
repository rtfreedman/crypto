from __future__ import annotations
from django.db import models
from itertools import permutations
from typing import Tuple, List, DefaultDict
from hashlib import sha256
from django.http import HttpResponseNotAllowed
from django.utils import timezone
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
        r = cls.__get_nice(request_url, headers={
            'Content-Type': 'application/json',
            # 'CB-ACCESS-TIMESTAMP': str(timestamp),
            # 'CB-ACCESS-KEY': api_key,
            # 'CB-ACCESS-SIGN': access_sign,
        })
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
        for from_elem, to_elem in permutations(currencies, 2):
            print(f'Running {from_elem.short_name}-{to_elem.short_name}')
            for start_date, end_date in cls.__datetime_generator(date_start, date_end, granularity):
                req_url = base_url.format(
                    f'products/{from_elem.short_name.upper()}-{to_elem.short_name.upper()}/candles?start={start_date.strftime("%Y-%m-%dT%H:%M:%S")}&end={end_date.strftime("%Y-%m-%dT%H:%M:%S")}&granularity={int(granularity.total_seconds())}')
                resp = cls.__get_nice(req_url, headers={
                    'content-type': 'application/json',
                })
                if resp.status_code == 404:
                    # we've got a bad currency combo
                    # try the next one
                    logger.warning(f'GET {req_url} not found {resp.status_code}: {resp.text}')
                    logger.warning(json.dumps({
                        'start_date': start_date.strftime("%Y-%m-%d, %H:%M:%S"),
                        'date_start': date_start.strftime("%Y-%m-%d, %H:%M:%S"),
                        'end_date': end_date.strftime("%Y-%m-%d, %H:%M:%S"),
                        'date_end': date_end.strftime("%Y-%m-%d, %H:%M:%S"),
                        'granularity': granularity.total_seconds()
                    }))
                    break
                if resp.status_code != 200:
                    logger.warning(f'GET {req_url} bad status code {resp.status_code}: {resp.text}')
                    logger.warning(json.dumps({
                        'start_date': start_date.strftime("%Y-%m-%d, %H:%M:%S"),
                        'date_start': date_start.strftime("%Y-%m-%d, %H:%M:%S"),
                        'end_date': end_date.strftime("%Y-%m-%d, %H:%M:%S"),
                        'date_end': date_end.strftime("%Y-%m-%d, %H:%M:%S"),
                        'granularity': granularity.total_seconds()
                    }))
                    continue
                for rate_obj in resp.json():
                    try:
                        unix_timestamp, low_rate, high_rate, open_rate, close_rate, volume = rate_obj
                        defaults = {
                            'low_rate': Decimal(low_rate),
                            'high_rate': Decimal(high_rate),
                            'open_rate': Decimal(open_rate),
                            'close_rate': Decimal(close_rate),
                            'volume': Decimal(volume),
                        }
                        rate, _ = Rate.objects.get_or_create(
                            from_currency=from_elem,
                            to_currency=to_elem,
                            timestamp=make_aware(datetime.datetime.fromtimestamp(unix_timestamp)),
                            source=req_url,
                            defaults=defaults)
                        rates.append(rate)
                    except Exception as e:
                        logger.warning(f'{defaults}, {rate_obj} : {e}')
            print(start_date, end_date)
        return rates

    @ classmethod
    def __get_nice(cls, url, **kwargs):
        if time.time() - cls.last_request_time < 0.1:
            time.sleep(0.1 - (time.time() - cls.last_request_time))
        cls.last_request_time = time.time()
        resp = requests.get(url, **kwargs)
        logger.info(f'GET {url} {resp.status_code}: {resp.reason}')
        if resp.status_code == 429:
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

    def to_dict(self):
        return {
            'from_sn': self.from_currency.short_name,
            'from_id': self.from_currency.id,
            'to_sn': self.to_currency.short_name,
            'to_id': self.to_currency.id,
            'timestamp': self.timestamp,
            'rate': self.low_rate,
            'high_rate': self.high_rate,
            'open_rate': self.open_rate,
            'close_rate': self.close_rate,
            'volume': self.volume,
        }

    class Meta:
        unique_together = [['from_currency', 'to_currency', 'timestamp', 'source']]
