import os
from datetime import datetime, timedelta

from django.http.response import HttpResponseBadRequest
import Currency.models as cm
from django.shortcuts import render
from django.views.generic import TemplateView
from django.http import HttpResponse, JsonResponse
from Currency.models import Currency
import logging
import settings

# Create your views here.
logger = logging.getLogger(__name__)

if settings.DEBUG:
    logger.setLevel(logging.DEBUG)


def authenticate():
    global __authenticated
    cm.authenticate('https://api.pro.coinbase.com/{}', os.getenv('CBAAPIKEY'), os.getenv('CBAAPISECRET'))
    __authenticated = True


class CurrencyView(TemplateView):
    template_name = 'currency.html'
    __authenticated = False
    data = {
        'template_script_url': '/static/scripts/currency.js',
        'all_currencies': [c.to_dict() for c in Currency.objects.all()],
        'allowed_currencies': [],
        'allowed_granularities': [
            {'name': '1 min', 'value': 60},
            {'name': '2 min', 'value': 120},
            {'name': '5 min', 'value': 300},
            {'name': '10 min', 'value': 600},
            {'name': '15 min', 'value': 900},
            {'name': '30 min', 'value': 1800},
            {'name': '1 hour', 'value': 3600},
            {'name': '6 hour', 'value': 21600},
            {'name': '1 day', 'value': 86400}
        ]
    }

    @classmethod
    def target_date(cls, request):
        # TODO: move this to middleware or smth
        if not cls.__authenticated:
            authenticate()
        try:
            currencies = [currency.strip().lower() for currency in request.headers['currencies'].split(',')]
            base_currency = request.headers['baseCurrency'].lower()
            start_date = datetime.fromisoformat(request.headers['startDate'])
            end_date = datetime.fromisoformat(request.headers['endDate'])
            granularity = int(request.headers['granularity'])
        except Exception as e:
            logger.warning(f'Exception raised when reading headers from request: {e}.')
            return HttpResponseBadRequest()
        return JsonResponse({
            'data': [
                rate.to_dict() for rate in Currency.collect_coinbase_rates(start_date, end_date, currencies, granularity=timedelta(seconds=granularity))
            ]
        })

    @classmethod
    def refresh_data(cls, request):
        if not cls.__authenticated:
            authenticate()
        cls.data['all_currencies'] = [
            c.to_dict() for c in Currency.collect_currency_info()
        ]
        return JsonResponse({
            'currencies': [
                c.to_dict() for c in Currency.collect_currency_info()
            ]
        })

    def get(self, request):
        if not self.__authenticated:
            authenticate()
        return render(request, 'currency.html', CurrencyView.data)
