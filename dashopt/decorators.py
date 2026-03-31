from django.shortcuts import redirect
from django.http import JsonResponse
from .utils import jwt_decode

def login_required(func):
    def wrapper(request, *args, **kwargs):
        if request.headers['Authorization'] == 'null':
            content = {
                'code': 403
            }
            return JsonResponse(content)
        else:
            jwt_string = request.headers['Authorization']
            try:
                payload = jwt_decode(jwt_string)  # 只要是通过JWT正确解码后的数据一定是可信数据
                # Python允许动态为对象添加属性
                request.user_id = payload['id']  # 当前登录用户的ID
                request.username = payload['username']  # 当前登录用户的用户名
                return func(request,*args,**kwargs)
            except Exception as e:
                content = {
                    'code': 403
                }
                return JsonResponse(content)
    return wrapper
