from django.urls import path
from . import views

urlpatterns = [
    path('<slug:username>',views.CartsView.as_view(),name='carts'),
]