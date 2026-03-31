from django.shortcuts import render
from django.http import HttpResponse
from django.http import JsonResponse
from django.conf import settings
from users.models import UserProfile
from django.db.models import F
from users.models import Address
from django_redis import get_redis_connection
from goods.models import SKU
import json
from .models import OrderInfo
from .models import OrderGoods
from django.views import View
from alipay import AliPay

def advance(request,username):
    '''
    地址栏中的settlement_type参数表示结算的来源
    其中0表示是结算购物车的数据，1表示结算立即购买的数据
    '''
    settlement_type = request.GET.get('settlement_type')
    # ********************************************************
    # 方法1:根据用户名来获取用户信息，然后再获取用户的地址信息
    # userprofile = UserProfile.objects.get(username=username)
    # address_queryset = userprofile.address_set.filter(is_delete=False).values('id','address',name=F('receiver'),mobile=F('receiver_mobile'),title=F('tag'))
    # print(address_queryset)
    # 方法2：根据用户信息来获取地址信息
    userprofile = UserProfile.objects.get(username=username)
    address_queryset = Address.objects.filter(
        user_profile=userprofile,
        is_delete=False).values(
        'id',
        'address',
        name=F('receiver'),
        mobile=F('receiver_mobile'),
        title=F('tag')
    )
    # ********************************************************
    if settlement_type == '0':
        #^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        # 获取的购物车中的被选定商品
        sku_list = []
        redis_conn = get_redis_connection(alias='carts')
        cache_key = f'buyer_{username}'
        product_in_carts = redis_conn.hgetall(name=cache_key)
        for key,json_string in product_in_carts.items():
            dict_value = json.loads(json_string)
            if(dict_value['status']):
                sku_object = SKU.objects.get(pk=key)
                sku_list.append({
                    'id':sku_object.pk,
                    'name':sku_object.name,
                    'count': dict_value['number'],
                    'selected': True,
                    'default_image_url': sku_object.default_image_url.name,
                    'price': sku_object.price,
                    'sku_sale_attr_name': ['尺寸', '颜色'],
                    'sku_sale_attr_val': ['18寸', '红色']
                })
        # ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        content = {
            'code':200,
            'base_url':request.build_absolute_uri(settings.MEDIA_URL),
            'data':{
                'addresses':list(address_queryset),
                'sku_list':sku_list
            }
        }
    ##########################################################################
    if settlement_type == '1':
        sku_id = request.GET.get('sku_id')
        buy_num = request.GET.get('buy_num')
        sku_object = SKU.objects.get(pk=sku_id)
        sku_list = [
            {
                'id': sku_object.pk,
                'name': sku_object.name,
                'count': buy_num,
                'selected': True,
                'default_image_url': sku_object.default_image_url.name,
                'price': sku_object.price,
                'sku_sale_attr_name': ['尺寸', '颜色'],
                'sku_sale_attr_val': ['18寸', '红色']
            }
        ]
        content = {
            'code': 200,
            'base_url': request.build_absolute_uri(settings.MEDIA_URL),
            'data': {
                'addresses': list(address_queryset),
                'sku_list': sku_list,
                'buy_count': buy_num,
                'sku_id': sku_id
            }
        }
    return JsonResponse(content)




def get_key(key_file):
    with open(key_file, 'r') as file:
        key_string = file.read()
    return key_string

def build_alipay_querystring(order_id,total_amount):
    app_private_key_string  = get_key('keys/app_private_key.pem')
    alipay_public_key_string = get_key('keys/alipay_public_key.pem')
    alipay_object = AliPay(
        appid='9021000128661963',
        app_notify_url=None,
        app_private_key_string=app_private_key_string,
        alipay_public_key_string=alipay_public_key_string,
    )
    # 调用PC页面支付方法
    querystring = alipay_object.api_alipay_trade_page_pay(
        subject='达达商城支付页面',
        out_trade_no=order_id,
        total_amount=float(total_amount),
        return_url='http://127.0.0.1:7000/dadashop/templates/pay_success.html',  # 同步通知地址,GET请求方式
        notify_url='http://127.0.0.1:8000/v1/pays/notify'  # 异步通知地址,POST请求方式
    )
    return querystring

def build_alipay_url(order_id,total_amount):
    querystring = build_alipay_querystring(order_id=order_id,total_amount=total_amount)
    return 'https://openapi-sandbox.dl.alipaydev.com/gateway.do?' + querystring

def result(request):
    #获取地址栏中的订单号及消费金额
    out_trade_no = request.GET.get('out_trade_no')
    total_amount = request.GET.get('total_amount')
    #根据订单号来更新订单的状态
    OrderInfo.objects.filter(pk=out_trade_no).update(status=2)
    #返需要返回信息
    content = {
        'code':200,
        'data':{
                'order_id':out_trade_no,
                'total_amount':total_amount
            }
    }
    return JsonResponse(content)

class OrderView(View):
    def post(self,request,username):
        data = json.loads(request.body)
        settlement_type = data.get('settlement_type')
        address_id = data.get('address_id')
        ##############################################################
        from datetime import datetime
        import random
        current_date = datetime.now()
        current_date_string = current_date.strftime('%Y%m%d%H%M%S')
        randominteger = random.randint(100000, 999999)
        order_id = current_date_string + str(randominteger)
        ##############################################################
        # 方法1根据用户去获取地址
        '''
        from users.models import  UserProfile
        #用户模型实例
        userprofile = UserProfile.objects.get(username=username)
        #用户地址 -- 反向关系
        address_object = userprofile.address_set.get(pk=address_id)
        print(address_object)
        '''
        # 方法2:根据地址去获取用户名
        from users.models import Address
        # 获取地址信息
        address_object = Address.objects.get(pk=address_id)
        # 获取拥有这个地址的用户信息 -- 正向关系
        userprofile = address_object.user_profile
        ##############################################################
        #现在是从购物车去结算
        if settlement_type == '0':
            ##########################################################
            total_amount = carts_count = 0
            #根据Redis中数据来计算的过程 -- 总价格及总数量
            redis_conn = get_redis_connection(alias='carts')
            cache_key = f'buyer_{username}'
            product_in_carts = redis_conn.hgetall(name=cache_key)
            for key,json_string in product_in_carts.items():
                dict_value = json.loads(json_string)
                if dict_value['status']:
                    sku_object = SKU.objects.get(pk=key)
                    total_amount += sku_object.price * dict_value['number']
                    carts_count += dict_value['number']
            ##################################################################
            #需要将相关的信息分别写入到订单信息表(一次)和订单商品表(N次，N>=1)

            #1.写入订单信息表(一次)



            OrderInfo.objects.create(
                order_id=order_id,
                total_amount=total_amount,
                total_count=carts_count,
                freight=0,#运费
                status=1,#代表是待付款
                receiver=address_object.receiver,
                address=address_object.address,
                receiver_mobile=address_object.receiver_mobile,
                tag=address_object.tag,
                user_profile=userprofile
            )
            #2.订单商品表(N次，N>=1)
            #从Redis获取到被选定的商品，将循环写入到订单商品表
            for key, json_string in product_in_carts.items():
                dict_value = json.loads(json_string)
                if dict_value['status']:
                    sku_object = SKU.objects.get(pk=key)
                    OrderGoods.objects.create(
                        order_info_id=order_id,
                        sku_id=key,
                        count=dict_value['number'],
                        price=sku_object.price
                    )
            ##################################################################
            '''
            from alipay import AliPay
            with open('keys/app_private_key.pem','r') as file:
                app_private_key_string = file.read()

            with open('keys/alipay_public_key.pem','r') as file:
                alipay_public_key_string = file.read()
            from alipay import AliPay
            alipay_object = AliPay(
                appid='9021000128661963',
                app_notify_url=None,
                app_private_key_string=app_private_key_string,
                alipay_public_key_string=alipay_public_key_string,
            )
            #调用PC页面支付方法
            querystring = alipay_object.api_alipay_trade_page_pay(
                subject='达达商城支付页面',
                out_trade_no=order_id,
                total_amount=float(total_amount),
                return_url='http://127.0.0.1:7000/dadashop/templates/pay_success.html', #同步通知地址,GET请求方式
                notify_url=None #异步通知地址,POST请求方式
            )
            '''
            ##################################################################
            content = {
                'code':200,
                'data':{
                    'saller': '达达商城', #商家的名称
                    'total_amount': total_amount, #总价格,公式 = 当前被选定的商品1的价格*数量+当前被选定的商品2的价格*数量+...
                    'order_id': order_id,#订单号,以YYYYMMDDHHMMSS+random.randint(100000,999999)
                    'pay_url': build_alipay_url(order_id,total_amount), #支付URL地址
                    'carts_count': carts_count #商品总数,每件商品的购买数量累加，如商品1购买了3件，商品2购买了2件，此时的结果为5
                }
            }
        ###############################################################################
        #现在是从立即购买去结算
        if settlement_type == '1':
            sku_id = data.get('sku_id')
            buy_count = int(data.get('buy_count')) #提交的数据类型为字符型，需要转换为整型才可以进行数学运算
            sku_object = SKU.objects.get(pk=sku_id)
            total_amount = sku_object.price * buy_count
            #################################################################
            OrderInfo.objects.create(
                order_id=order_id,
                total_amount=total_amount,
                total_count=buy_count,
                freight=0,  # 运费
                status=1,  # 代表是待付款
                receiver=address_object.receiver,
                address=address_object.address,
                receiver_mobile=address_object.receiver_mobile,
                tag=address_object.tag,
                user_profile=userprofile
            )
            #写入订单商品 -- 一次
            OrderGoods.objects.create(
                order_info_id=order_id,
                sku_id=sku_id,
                count=buy_count,
                price=sku_object.price
            )
            #################################################################
            content = {
                'code': 200,
                'data': {
                    'saller': '达达商城', #商家的名称
                    'total_amount': total_amount, #总价格,公式 = 当前商品的价格*数量
                    'order_id': order_id,#订单号,以YYYYMMDDHHMMSS+random.randint(100000,999999)
                    'pay_url': build_alipay_url(order_id,total_amount), #支付URL地址
                    'carts_count': buy_count #商品总数
                }
            }
        return JsonResponse(content)

    def get(self,request,username):
        type_str = request.GET.get('type')
        if type_str in ['0','1','2','3','4']:
            orderslist = []
            #用户模型实例
            userprofile = UserProfile.objects.get(username=username)
            #获取当前用户的所有订单信息
            orderinfo_queryset = userprofile.orderinfo_set.all()
            if type_str in ['1','2','3','4']:
                orderinfo_queryset = orderinfo_queryset.filter(status=type_str)
            for orderinfo_object in orderinfo_queryset:
                ########################################################
                #获取当前订单的所有商品形成列表
                ordergoods_queryset = orderinfo_object.ordergoods_set.all()
                order_sku = []
                for ordergoods_object in ordergoods_queryset:
                    order_sku.append({
                        'id': ordergoods_object.sku.pk,
                        'default_image_url': ordergoods_object.sku.default_image_url.name,
                        'name': ordergoods_object.sku.name,
                        'price': ordergoods_object.price,
                        'count': ordergoods_object.count,
                        'total_amount': ordergoods_object.count * ordergoods_object.price,
                        'sku_sale_attr_names': ['颜色', '尺寸'],
                        'sku_sale_attr_vals': ['红色', '15寸']
                    })
                ########################################################
                orderslist.append(
                    {
                        'order_id': orderinfo_object.pk,
                        'order_total_count': orderinfo_object.total_count,
                        'order_total_amount': orderinfo_object.total_amount,
                        'order_freight': orderinfo_object.freight,
                        'order_time': orderinfo_object.created_time,
                        'status': orderinfo_object.status,
                        #当前订单的所有商品
                        'order_sku':order_sku,
                        #当前订单的配送地址信息
                        'address': {
                            'title':orderinfo_object.tag,
                            'address':orderinfo_object.address,
                            'mobile':orderinfo_object.receiver_mobile,
                            'receiver':orderinfo_object.receiver
                        },
                    }
                )
            content = {
                'code':200,
                'base_url': request.build_absolute_uri(settings.MEDIA_URL),
                'data':{
                    'orders_list':orderslist
                }
            }
        if type_str == '5':
            order_id = request.GET.get('order_id')
            orderinfo_object = OrderInfo.objects.get(pk=order_id)
            content = {
                'code': 200,
                'data': {
                    'carts_count': orderinfo_object.total_count,
                    'total_amount': orderinfo_object.total_amount,
                    'order_id': order_id,
                    'saller': '达达商城',
                    'pay_url':build_alipay_url(order_id,orderinfo_object.total_amount)
                }
            }
        return JsonResponse(content)

    def put(self,request,username):
        data = json.loads(request.body)
        order_id = data.get('order_id')
        OrderInfo.objects.filter(pk=order_id).update(status=4)
        content = {
            'code':200
        }
        return  JsonResponse(content)
