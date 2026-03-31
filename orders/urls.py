from django.urls import path
from . import views

urlpatterns = [
    path('<slug:username>/advance',views.advance,name='advance'),
    path('<slug:username>',views.OrderView.as_view(),name='confirm_order'),
    path('result/',views.result,name='result'),
]