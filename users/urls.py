from django.urls import path, include
from . import views

urlpatterns = [
    path('register', views.register, name='register'),
    path('login', views.login, name='login'),
    path('activation', views.activation, name='activation'),
    path('sms/code', views.sms_code, name='sms_code'),
    path('password/sms', views.password_sms, name='password_sms'),
    path('password/verification', views.password_verification, name='password_verification'),
    path('password/new', views.password_new, name='password_new'),
    path('<slug:username>/password', views.change_password, name='change_password'),
    path('<slug:username>/address', views.AddressView.as_view(), name='address1'),  # GET,POST
    path('<slug:username>/address/<int:id>', views.AddressView.as_view(), name='address2'),  # PUT,DELETE
    path('<slug:username>/address/default', views.address_default, name='address_default'),
    path('weibo/authorization', views.weibo_authorization, name='weibo_authorization'),
    path('weibo/users', views.WeiboView.as_view(), name='weibo_users'),
    path('weibo/users/binduser', views.weibo_binduser, name='weibo_binduser'),
]