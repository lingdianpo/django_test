from django.urls import path
from . import views

urlpatterns = [
    path('index',views.index,name='index'),
    path('catalogs/<int:id>',views.catalogs,name='catalogs'),
    path('detail/<int:id>',views.detail,name='detail'),

    path('sku',views.sku,name='sku'),
]