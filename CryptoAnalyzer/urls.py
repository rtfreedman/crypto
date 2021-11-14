"""CryptoAnalyzer URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import path
from Currency.views import CurrencyView


def temporary_redirect(to_path):
    def go_there(_):
        return redirect(to_path)
    return go_there


urlpatterns = [
    path('admin', admin.site.urls),
    path('', temporary_redirect('/currency')),
    path('currency', CurrencyView.as_view()),
    path('currency/refresh', CurrencyView.refresh_data),
    path('currency/target', CurrencyView.target_date)
]
