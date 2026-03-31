from django.shortcuts import render
from django.http import HttpResponse
from django.http import JsonResponse
from django.views import View
from django_redis import get_redis_connection
import json
from django.conf import settings
from goods.models import SKU


class CartsView(View):
    redis_conn = get_redis_connection(alias='carts')

    def post(self, request, username):
        # 获取提交数据
        data = json.loads(request.body)
        sku_id = data.get('sku_id')
        count = int(data.get('count'))
        # 将数据写入到Redis  -- 新增或更新操作
        cache_key = f'buyer_{username}'
        # print(cache_key)
        # 只需要判断field是否存在即可，只要field不存在，则一定为新增
        if not self.redis_conn.hexists(name=cache_key, key=sku_id):
            # 字典
            dict_value = {
                'number': count,  # 商品的数量
                'status': True,  # 商品的状态(默认为True)
            }
            # 将字典转换为JSON格式的字符串
            json_string = json.dumps(dict_value)
            self.redis_conn.hset(name=cache_key, key=sku_id, value=json_string)
        else:
            # 1.获取出原来的field对应的值 -- JSON格式的字符串
            json_string = self.redis_conn.hget(name=cache_key, key=sku_id)
            # 2.将JSON格式的字符串转换为Python中的字典
            dict_value = json.loads(json_string)
            # 3.更新字典中的number的值为原来的基础上加count
            dict_value['number'] += count
            # 4.将Python中的字典转换为JSON格式的字符串
            json_string = json.dumps(dict_value)
            # 5.按原来的field重新写入到redis中
            self.redis_conn.hset(name=cache_key, key=sku_id, value=json_string)
        content = {
            'code': 200,
            'data':
                {
                    'carts_count': count
                },
            'base_url': request.build_absolute_uri(settings.MEDIA_URL)
        }
        return JsonResponse(content)

    def get(self, request, username):
        cache_key = f'buyer_{username}'
        product_id_list = self.redis_conn.hkeys(name=cache_key)
        sku_queryset = SKU.objects.filter(id__in=product_id_list)
        sku_list = []
        for sku_object in sku_queryset:
            json_string = self.redis_conn.hget(name=cache_key, key=sku_object.id)
            dict_value = json.loads(json_string)
            sku_list.append({
                'id': sku_object.id,
                'name': sku_object.name,
                'count': dict_value['number'],
                'selected': dict_value['status'],
                'default_image_url': sku_object.default_image_url.name,
                'price': sku_object.price,
                'sku_sale_attr_name': ['颜色', '尺寸'],
                'sku_sale_attr_val': ['红色', '18寸']
            })
        content = {
            'code': 200,
            'base_url': request.build_absolute_uri(settings.MEDIA_URL),
            'data': sku_list
        }
        return JsonResponse(content)

    def delete(self, request, username):
        cache_key = f'buyer_{username}'
        data = json.loads(request.body)
        sku_id = data.get('sku_id')
        self.redis_conn.hdel(cache_key, sku_id)
        content = {
            'code': 200,
            'data': {
                'carts_count': self.redis_conn.hlen(name=cache_key)
            },
            'base_url': request.build_absolute_uri(settings.MEDIA_URL)
        }
        return JsonResponse(content)

    def put(self, request, username):
        cache_key = f'buyer_{username}'
        data = json.loads(request.body)
        state = data.get('state')
        '''
        #数量增加
        if state == 'add':
            sku_id = data.get('sku_id')
            #1.从Redis中获取指定field的值 -- JSON格式的字符串
            json_string = self.redis_conn.hget(name=cache_key,key=sku_id)
            #2.将JSON格式的字符串转换为Python中的字典
            dict_value = json.loads(json_string)
            #3.将字典中的number进行累加
            dict_value['number'] += 1
            #4.将Python中的字典转换为JSON格式的字符串
            json_string = json.dumps(dict_value)
            #5.重新写入field的值为转换后的值
            self.redis_conn.hset(name=cache_key,key=sku_id,value=json_string)
        #数量减少
        if state == 'del':
            sku_id = data.get('sku_id')
            # 1.从Redis中获取指定field的值 -- JSON格式的字符串
            json_string = self.redis_conn.hget(name=cache_key, key=sku_id)
            # 2.将JSON格式的字符串转换为Python中的字典
            dict_value = json.loads(json_string)
            # 3.将字典中的number进行累加
            dict_value['number'] -= 1
            # 4.将Python中的字典转换为JSON格式的字符串
            json_string = json.dumps(dict_value)
            # 5.重新写入field的值为转换后的值
            self.redis_conn.hset(name=cache_key, key=sku_id, value=json_string)
        #单选
        if state == 'select':
            sku_id = data.get('sku_id')
            # 1.从Redis中获取指定field的值 -- JSON格式的字符串
            json_string = self.redis_conn.hget(name=cache_key, key=sku_id)
            # 2.将JSON格式的字符串转换为Python中的字典
            dict_value = json.loads(json_string)
            # 3.将字典中的status修改为True
            dict_value['status'] = True
            # 4.将Python中的字典转换为JSON格式的字符串
            json_string = json.dumps(dict_value)
            # 5.重新写入field的值为转换后的值
            self.redis_conn.hset(name=cache_key, key=sku_id, value=json_string)

        #取消单选
        if state == 'unselect':
            sku_id = data.get('sku_id')
            # 1.从Redis中获取指定field的值 -- JSON格式的字符串
            json_string = self.redis_conn.hget(name=cache_key, key=sku_id)
            # 2.将JSON格式的字符串转换为Python中的字典
            dict_value = json.loads(json_string)
            # 3.将字典中的status修改为False
            dict_value['status'] = False
            # 4.将Python中的字典转换为JSON格式的字符串
            json_string = json.dumps(dict_value)
            # 5.重新写入field的值为转换后的值
            self.redis_conn.hset(name=cache_key, key=sku_id, value=json_string)
        #全选
        if state == 'selectall':
            # 需要将Redis中的所有field值内的status依次修改为True
            all_products = self.redis_conn.hgetall(name=cache_key)
            for product_id,json_string in all_products.items():
                dict_value = json.loads(json_string)
                dict_value['status'] = True
                json_string = json.dumps(dict_value)
                self.redis_conn.hset(name=cache_key,key=product_id,value=json_string)

        # 取消全选
        if state == 'unselectall':
            # 需要将Redis中的所有field值内的status依次修改为False
            all_products = self.redis_conn.hgetall(name=cache_key)
            for product_id, json_string in all_products.items():
                dict_value = json.loads(json_string)
                dict_value['status'] = False
                json_string = json.dumps(dict_value)
                self.redis_conn.hset(name=cache_key, key=product_id, value=json_string)
        '''
        ######################################################################
        # 数量增加
        if state == 'add' or state == 'del':
            sku_id = data.get('sku_id')
            # 1.从Redis中获取指定field的值 -- JSON格式的字符串
            json_string = self.redis_conn.hget(name=cache_key, key=sku_id)
            # 2.将JSON格式的字符串转换为Python中的字典
            dict_value = json.loads(json_string)
            # 3.将字典中的number进行累加
            dict_value['number'] += 1 if state == 'add' else -1
            # 4.将Python中的字典转换为JSON格式的字符串
            json_string = json.dumps(dict_value)
            # 5.重新写入field的值为转换后的值
            self.redis_conn.hset(name=cache_key, key=sku_id, value=json_string)
        # 单选
        if state == 'select' or state == 'unselect':
            sku_id = data.get('sku_id')
            # 1.从Redis中获取指定field的值 -- JSON格式的字符串
            json_string = self.redis_conn.hget(name=cache_key, key=sku_id)
            # 2.将JSON格式的字符串转换为Python中的字典
            dict_value = json.loads(json_string)
            # 3.将字典中的status修改为True
            dict_value['status'] = state == 'select'
            # 4.将Python中的字典转换为JSON格式的字符串
            json_string = json.dumps(dict_value)
            # 5.重新写入field的值为转换后的值
            self.redis_conn.hset(name=cache_key, key=sku_id, value=json_string)
        # 全选
        if state == 'selectall' or state == 'unselectall':
            # 需要将Redis中的所有field值内的status依次修改为True
            all_products = self.redis_conn.hgetall(name=cache_key)
            for product_id, json_string in all_products.items():
                dict_value = json.loads(json_string)
                dict_value['status'] = state == 'selectall'
                json_string = json.dumps(dict_value)
                self.redis_conn.hset(name=cache_key, key=product_id, value=json_string)

            #######################################################################
        cache_key = f'buyer_{username}'
        product_id_list = self.redis_conn.hkeys(name=cache_key)
        sku_queryset = SKU.objects.filter(id__in=product_id_list)
        sku_list = []
        for sku_object in sku_queryset:
            json_string = self.redis_conn.hget(name=cache_key, key=sku_object.id)
            dict_value = json.loads(json_string)
            sku_list.append({
                'id': sku_object.id,
                'name': sku_object.name,
                'count': dict_value['number'],
                'selected': dict_value['status'],
                'default_image_url': sku_object.default_image_url.name,
                'price': sku_object.price,
                'sku_sale_attr_name': ['颜色', '尺寸'],
                'sku_sale_attr_val': ['红色', '18寸']
            })

        #######################################################################

        content = {
            'code': 200,
            'base_url': request.build_absolute_uri(settings.MEDIA_URL),
            'data': sku_list
        }
        return JsonResponse(content)
