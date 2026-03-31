import json
import random
import requests
import logging

from django.http import JsonResponse
from django.conf import settings
from django.template.loader import render_to_string
from django.views import View
from django.db.models import F
from django.utils.decorators import method_decorator
from django.core.mail import send_mail
from django.utils.translation import gettext_lazy as _

from dashopt.utils import md5
from dashopt.utils import jwt_encode, jwt_decode
from django_redis import get_redis_connection
from dashopt.decorators import login_required
from .models import WeiboProfile
from .models import Address
from .models import UserProfile

def weibo_binduser(request):
    data = json.loads(request.body)
    username = data.get('username')
    password = md5(data.get('password'))
    uid = data.get('uid')
    # 1.以输入的用户名和密码进行查找
    user_profile_queryset = UserProfile.objects.filter(username=username,password=password)
    # 2.找到后，
    if user_profile_queryset:
        user_profile = user_profile_queryset.first() #当前登录用户模型的实例
        #更新微博用户模型的外键字段值为找到用户的ID
        WeiboProfile.objects.filter(wuid=uid).update(user_profile=user_profile)
        payload = {
            'id':user_profile.pk,
            'username':username
        }
        content = {
            'code':200,
            'username':username,
            'carts_count':0,
            'token':jwt_encode(payload=payload)
        }
    else:
        content = {
            'code':10017,
            'error':'对不起，用户名或密码错误'
        }
    return JsonResponse(content)

def weibo_authorization(request):
    content = {
        'code':200,
        'oauth_url':'https://api.weibo.com/oauth2/authorize?client_id=3291993783&response_type=code&redirect_uri=http://localhost:7000/dadashop/templates/callback.html'
    }
    return JsonResponse(content)

class WeiboView(View):
    def get(self,request):
        code = request.GET.get('code') #获取授权码
        #用授权码来换到访问令牌(AccessToken)
        #经过微博开发文档发现：用授权码来换到访问令牌的地址为：https://api.weibo.com/oauth2/access_token
        #但是需要向这个地址发送POST类型的请求,如何实现呢？ -- 其实无论是POST请求，还是GET请求，还是PUT请求，还DELETE请求
        #在Python中是完全一样的，都只能通过requests模块实现，只是调用的方法不同。
        data = {
            'client_id':'3291993783',
            'client_secret':'9f07c80d272124f9a095e1ad524bd0ad',
            'grant_type':'authorization_code',
            'code':code,
            'redirect_uri':'http://localhost:7000/dadashop/templates/callback.html'
        }
        response = requests.post(
            url='https://api.weibo.com/oauth2/access_token',
            data=data
        )
        # print(response.headers) #获取响应头
        # print('=====================================')
        # print(response.status_code) #获取响应的状态码
        #print(response.content) #获取响应的内容,Bytes对象
        #print('=====================================')
        #print(response.text) #获取响应的内容,str对象
        # print('=====================================')
        response_json_data = response.json() #获取响应的JSON格式的数据
        #获取响应的数据
        access_token = response_json_data.get('access_token') #访问令牌
        uid = response_json_data.get('uid') #微博用户ID
        #现在要以access_token和uid为条件在微博表中进行查找，如果没有找到的话，
        return JsonResponse({'code':200,'access_token':access_token,'uid':uid})
        weiboprofile_exists = WeiboProfile.objects.filter(wuid=uid,access_token=access_token).exists()
        if not weiboprofile_exists:
            # 则证明这个微博用户是第一次通过扫码进来的，则需要写将access_token和uid写入到微博表。
            WeiboProfile.objects.create(
                wuid=uid,
                access_token=access_token
            )
            content = {
                'code':201,
                'uid':uid
            }
            return  JsonResponse(content)
        else:
            # 如果可以找到的话，则证明这个微博用户是第N次通过扫码进来的，
            weibo_profile = WeiboProfile.objects.get(wuid=uid,access_token=access_token)
            #则再需要看一下这个用户是否与达达商城的用户表进行了绑定，即user_profile字段是否为空，
            if weibo_profile.user_profile :
                #证明已经绑定过达达商城的用户，现在可以以当前用户的身份进行登录
                payload = {
                    'id':weibo_profile.user_profile.pk,
                    'username':weibo_profile.user_profile.username
                }
                content = {
                    'code':200,
                    'username':weibo_profile.user_profile.username, #一对一的正向关系
                    'token':jwt_encode(payload=payload) #JWT字符串
                }
                return JsonResponse(content)
            else:
                # 暂时还没有绑定过，需要继续显示绑定信息的页面
                content = {
                    'code': 201,
                    'uid': uid
                }
                return JsonResponse(content)

    def post(self,request):
        data = json.loads(request.body)
        username = data.get('username')
        password = md5(data.get('password'))
        email = data.get('email')
        phone = data.get('phone')
        uid = data.get('uid') #微博用户的ID -- 将作为更新微博用户模型的条件来使用
        #将注册的信息写入到用户模型
        userprofile = UserProfile.objects.create(
            username=username,
            password=password,
            email=email,
            phone=phone
        )
        #更新微博用户模型的外键字段值为新注册用户的ID
        WeiboProfile.objects.filter(wuid=uid).update(user_profile=userprofile.pk)
        payload = {
            'id':userprofile.pk,
            'username':userprofile.username
        }
        content = {
            'code':200,
            'username':username,
            'token':jwt_encode(payload=payload)
        }
        return JsonResponse(content)



class AddressView(View):
    #针对于路由的GET请求
    @method_decorator(login_required)
    def get(self,request,username):
        #null是由于前端发送AJAX时没有对名称为'dada_token'的本地存储的键进行判断的原因的造成的

        #为了防止用户不登录的情况下就直接访问该函数对应的路由，所以
        #1.检测请求头是否存在authorization的KEY
        #2.检测该authorization的JWT字符串是否可以被解码
        '''
        #第一种方法:通过遍历才可以得到列表+字典的嵌套关系
        addresslist = []
        ##获取用户信息
        user_profile = UserProfile.objects.get(username=username)
        ##获取用户的所有正常地址信息
        addresses = user_profile.address_set.filter(is_delete=False)
        for item in addresses:
            addresslist.append({
                'id': item.id,  # 地址id
                'address': item.address,  # 地址
                'receiver': item.receiver,  # 收货人
                'receiver_mobile': item.receiver_mobile,  # 联系电话
                'tag': item.tag,  # 地址标签
                'postcode': item.postcode,  #
                'is_default': item.is_default,
            })
        content = {
            'code':200,
            'addresslist':addresslist
        }
        '''
        #第二种方法:通过values()方法即可返回字典，最终只需要再通过list()函数将结果集转换为列表即可
        addresslist = list(UserProfile.objects.get(username=username).address_set.values('id','receiver','receiver_mobile','postcode','address','is_default','tag').filter(is_delete=False))
        content = {
            'code':200,
            'addresslist':addresslist
        }
        return JsonResponse(content)
    #针对于路由的POST请求
    @method_decorator(login_required)
    def post(self,request,username):
        #获取提交数据
        data = json.loads(request.body)
        receiver=data.get('receiver')
        address = data.get('address')
        receiver_phone=data.get('receiver_phone')
        postcode=data.get('postcode')
        tag=data.get('tag')

        #以下方法的基本原理是：利用了RelatedManager的create()方法
        #UserProfile.objects.get(username=username)返回UserProfile的模型实例
        # UserProfile.objects.get(username=username).address_set返回UserProfile的模型实例
        #的所有地址形成管理器(反向管理器),反向管理器实质上是一种特殊的管理器，主要用于一对多的反向关系及多对多的关系
        #而反向管理器可以访问管理器的所有方法（当然它也有自己特有的方法），所以就可以通过
        #反向管理器.create()来创建子模型实例
        '''
        UserProfile.objects.get(username=username).address_set.create(
            receiver=receiver,
            address=address,
            postcode=postcode,
            tag=tag,
            receiver_mobile=receiver_phone
        )
        '''
        #以下方法是先直接创建了Address的模型实例，但需要注意的是：
        #Address模型中存在一个外键，如果该字段不允许为空或没有默认情况下，以下创建Address模型
        #实例的代码将产生错误。
        '''
        address = Address.objects.create(
            receiver=receiver,
            address=address,
            postcode=postcode,
            tag=tag,
            receiver_mobile=receiver_phone
        )
        '''
        #上述代码虽然可以创建了Address模型实例，但是还不知道它是谁的地址信息(在本案例中user_profile_id字段允许为空)
        #刚刚说过，反向管理器有它自己特有的方法，如add(),remove(),clear()等
        #其中add()方法就是添加一个子
        #UserProfile.objects.get(username=username).address_set.add(address)

        ########################################################
        try:
            # 模型实例
            user_profile = UserProfile.objects.get(username=username)
            Address.objects.create(
                receiver=receiver,
                address=address,
                postcode=postcode,
                tag=tag,
                receiver_mobile=receiver_phone,
                user_profile=user_profile,
                # user_profile_id = user_profile.id, #与上一行代码，两者都正确
                is_default = not user_profile.address_set.filter(is_delete=False).count()
            )
            content = {
                'code':200,
                'data':'地址添加成功'
            }
        except Exception as e:
            content = {
                'code':10014,
                'error':'地址添加失败'
            }
        return JsonResponse(content)

    @method_decorator(login_required)
    def put(self,request,username,id):
        data = json.loads(request.body)
        # id = data.get('id') #????
        receiver = data.get('receiver')
        receiver_mobile = data.get('receiver_mobile')
        tag = data.get('tag')
        address = data.get('address')
        '''
        #方法1
        Address.objects.filter(pk=id).update(
            receiver=receiver,
            receiver_mobile=receiver_mobile,
            tag=tag,
            address=address
        )
        '''
        try:
            address_object = Address.objects.get(pk=id) #模型实例
            address_object.receiver=receiver
            address_object.receiver_mobile=receiver_mobile
            address_object.tag=tag
            address_object.address = address
            address_object.save()
            content = {
                'code':200,
                'data':'地址修改成功'
            }
        except Exception as e:
            content = {
                'code': 10016,
                'data': '地址修改失败'
            }
        return JsonResponse(content)

    @method_decorator(login_required)
    def delete(self,request,username,id):
        # data = json.loads(request.body)
        # username = data.get('username')
        # id = data.get('id')
        try:
            #逻辑地址，同时将设置为非默认地址(无论原来是否为默认地址)
            Address.objects.filter(pk=id).update(is_delete=True,is_default=False)
            ####################################################################
            #查看当前用户的是否还存在默认地址
            has_default_address = UserProfile.objects.get(username=username).address_set.filter(is_default=True).exists()
            if not has_default_address: #如果没有默认地址
                #如果还有正常地址的话，则第一个正常地址为默认地址
                address_queryset = UserProfile.objects.get(username=username).address_set.filter(is_delete=False) #结果集
                if address_queryset:
                    address_object = address_queryset.first() # 获取结果集中的第一条记录
                    address_object.is_default = True
                    address_object.save()

                ####################################################################
            content = {
                'code':200,
                'data':'地址删除成功'
            }
        except Exception as e:
            content = {
                'code': 10015,
                'data': '地址删除失败'
            }
        return JsonResponse(content)

@login_required
def address_default(request,username):
    data = json.loads(request.body)
    id = data.get('id')
    try:
        #将用户地址中除了当前地址外的其他地址变为非默认地址
        #UserProfile.objects.get(username=username).address_set.exclude(pk=id).update(is_default=False)
        #将当前用户原来的地址变为非默认地址
        UserProfile.objects.get(username=username).address_set.filter(is_default=True).update(is_default=False)
        #将当前地址设置为默认地址
        Address.objects.filter(pk=id).update(is_default=True)
        content = {
            'code':200,
            'data':'设置默认地址成功'
        }
    except Exception as e:
        content = {
            'code':10016,
            'error':'设置默认地址失败'
        }
    return JsonResponse(content)

def register(request):
    redis_conn = get_redis_connection()
    # 表单虽然是POST提交，但是在本案例中不能使用request.POST.get()方法进行获取的原因是
    # 前端AJAX请求中设置了请求数据的类型为application/json
    # 而request.POST.get()只能获取请求类型为application/x-www-form-urlencoded的数据
    # 但是无论是哪一种的数据类型，只是POST提交，在Django中都是将数据呈现在请求体内的
    # request.POST.get()只是DJANGO提供了一种更加便捷的访问方式而已。
    # 1.获取提交数据
    data = json.loads(request.body)
    uname = data.get('uname')
    password = md5(data.get('password'))
    phone = data.get('phone')
    email = data.get('email')
    verify = data.get('verify')  # 输入的手机验证码
    cache_key = f'register_verify_{phone}'
    cache_value = redis_conn.get(cache_key)
    # 必须保证用户输入的验证码与应该输入的验证码保持一致

    if (verify != cache_value):
        content = {
            "code": 10009,
            "error": "手机验证码错误"
        }
        return JsonResponse(content)

    # 2.数据合法校验，如用户名的长度是否介于6~11位之间等。
    # 3.数据的唯一性校验,分别保证用户名，邮件及电话的唯一性
    user_exists = UserProfile.objects.filter(username=uname).exists()
    if user_exists:
        content = {
            'code': 10001,
            'error': '用户名称已经存在'
        }
        return JsonResponse(content)
    email_exists = UserProfile.objects.filter(email=email).exists()
    if email_exists:
        content = {
            'code': 10002,
            'error': '邮箱地址已经存在'
        }
        return JsonResponse(content)
    phone_exists = UserProfile.objects.filter(phone=phone).exists()
    if phone_exists:
        content = {
            'code': 10001,
            'error': '手机号码已经存在'
        }
        return JsonResponse(content)
    # 4.如果所有的唯一性校验都通过了，则将用户信息写入到UserProfile模型
    ##########################################################
    try:
        userprofile = UserProfile.objects.create(
            username=uname,
            password=password,
            email=email,
            phone=phone
        )
        # ******************************************* #
        # 随机数 -- 将与用户名拼接后再次进行MD5操作，并且为作为激活地址的参数出现
        rand = random.randint(10000, 99999)
        code = md5(uname + str(rand))
        # 为了保证在激活时使用正确的随机数，所以必须将其保存到服务务器一份 -- Redis
        redis_conn = get_redis_connection(alias='default')
        # 将随机数写入到Redis-> 键名是什么呢? -- 邮箱
        cache_key = f'activation_{uname}'
        redis_conn.set(cache_key, rand, 3 * 86400)
        # print(redis_conn.keys(pattern='*'))
        # 读取激活邮件的模板作为邮件的正文
        html_message = render_to_string('users/activation.html', {'username': uname, 'code': code})
        # 发送邮件
        send_mail(
            subject='达达商城::用户激活',
            message=None,
            html_message=html_message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[email]
        )
        # ******************************************* #
        payload = {
            'id': userprofile.id,
            'username': uname
        }
        content = {
            'code': 200,
            'username': uname,
            'token': jwt_encode(payload),
            'carts_count': 0
        }
    except Exception as e:
        content = {
            'code': 10004,
            'error': '未知原因导致用户注册失败'
        }
    ##########################################################
    return JsonResponse(content)


def login(request):
    print(settings.KEY_LOGIN)
    print(settings.KEY_LOGINS)
    print(settings.KEY_LOGIN)
    logger = logging.getLogger('django')
    logger.info('测试登录')
    data = json.loads(request.body)
    username = data.get('username')
    password = md5(data.get('password'))
    # 以当前的用户名和密码为条件进行查找，以证明用户是否存在
    user_queryset = UserProfile.objects.filter(username=username, password=password)
    if user_queryset:
        payload = {
            'id': user_queryset.first().id,
            'username': username
        }
        content = {
            'code': 200,
            'username': username,
            'token': jwt_encode(payload),
            'carts_count': 0
        }
    else:
        content = {
            'code': 10003,
            'error': _('PASSWD ERROR')
        }
    return JsonResponse(content)


def activation(request):
    username = request.GET.get('username')
    code = request.GET.get('code')
    # 从Redis中获取随机数，但是你要取值的话就需要KEY才行，KEY是多少呢?
    cache_key = f'activation_{username}'
    redis_conn = get_redis_connection(alias='default')
    if not redis_conn.exists(cache_key):  # 一种是用户名被修改了，二是数据过期了
        # 其中既使用户名被修改了，但是只能这个用户名存在于数据库中仍然要正常发送邮件
        # 这种情况无法通过技术手段来判别
        # 重新发送邮件的过程
        ##########################################
        ##########################################
        content = {
            'code': 10006,
            'error': '激活用户不存在或激活码过期,请查收邮件后重新激活'
        }
        return JsonResponse(content)
    cache_value = redis_conn.get(cache_key)
    # 再次将username和随机数进行一次MD5的操作
    code2 = md5(username + cache_value)
    if code != code2:
        content = {
            'code': 10007,
            'error': '验证哈希校验失败'
        }
        return JsonResponse(content)
    try:
        UserProfile.objects.filter(username=username).update(is_active=True)
        # 激活成功后，删除缓存中的激活随机数
        redis_conn.delete(cache_key)
        content = {
            'code': 200,
            'data': '激活成功'
        }
    except Exception as e:
        content = {
            'code': 10005,
            'error': '激活失败'
        }
    return JsonResponse(content)


def sms_code(request):
    redis_conn = get_redis_connection()
    # 获取提交数据
    data = json.loads(request.body)
    phone = data.get('phone')
    # 调用手机运营商的API
    # from ronglian_sms_sdk import SmsSDK
    # 构造函数
    # smssdk = SmsSDK(
    #     accId='2c94811c8a27cf2d018a9814bd2520a1',  # 主账号ID
    #     accToken='c2d4ee98fafd41bab4bb4689ceaaf0c0',  # 主账号令牌
    #     appId='2c94811c8a27cf2d018a9814be3120a8'  # 应用ID
    # )
    # 发送短信的方法
    # tid代表的模板ID -- 测试期间模板ID为1
    # mobile代表的接收短信的手机号码，多个手机号码之间以逗号进行分隔，如'13800138000,13800138001'
    # datas代表的向模板传递的实际数据，其第一个代表的内容，第二个代表的是时间 -- 前提是使用了默认的模板
    expires = 10
    rand = random.randint(1000, 9999)
    cache_key = f'register_verify_{phone}'
    redis_conn.set(cache_key, rand, expires * 60)
    # 返回JSON格式的字符串
    # text = smssdk.sendMessage(tid='1', mobile=phone, datas=(rand, expires))
    # 转换为字典
    # dict = json.loads(text)
    # dict['statusCode'] == '000000'
    if True:
        content = {
            'code': 200,
        }
    else:
        content = {
            'code': 10008,
            'error': '发送失败'
        }
    return JsonResponse(content)


def password_sms(request):
    # 1.获取数据
    data = json.loads(request.body)
    email = data.get('email')
    # 2.发送邮件
    # from django.core.mail import send_mail
    # from django.template.loader import render_to_string
    # import random
    verify = random.randint(1000, 9999)
    minutes = 10
    html_message = render_to_string('users/forget_password.html', {'verify': verify, 'minutes': minutes})
    try:
        #from django_redis import get_redis_connection
        redis_conn = get_redis_connection()
        cache_key = f'forget_password_{email}'
        redis_conn.set(cache_key,verify,minutes*60)
        send_mail(
            subject='达达商城::找回密码',
            message=None,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[email],
            html_message=html_message
        )
        content = {
            'code': 200,
            'data': '邮件发送成功，请查收'
        }
    except Exception as e:
        content = {
            'code': 10009,
            'error': '邮件发送失败'
        }
    return JsonResponse(content)


def password_verification(request):
    #from django_redis import get_redis_connection
    redis_conn = get_redis_connection()
    data = json.loads(request.body)
    # 获取用户输入的验证码
    email = data.get('email')
    code = data.get('code')
    #缓存的KEY
    cache_key = f'forget_password_{email}'
    # 缓存的VALUE
    cache_value = redis_conn.get(cache_key)
    # 用户输入的验证码与应该输入的验证码进行匹配
    print(cache_key)
    print(code,cache_value)
    if (code == cache_value):
        content = {
            'code': 200,
            'data': '验证成功'
        }
    else:
        content = {
            'code': 10010,
            'error': '验证失败'
        }
    return JsonResponse(content)


def password_new(request):
    #from dadashop.utils import md5
    #获取数据
    data = json.loads(request.body)
    email = data.get('email')
    password1 = md5(data.get('password1'))
    password2 = data.get('password2')
    #更新操作
    #from .models import  UserProfile
    try:
        UserProfile.objects.filter(email=email).update(password=password1)
        content = {
            'code':200,
            'data':'密码重置成功'
        }
    except Exception as e:
        content = {
            'code':10011,
            'error':'密码重置失败'
        }
    return JsonResponse(content)

@login_required
def change_password(request,username):
    #获取提交数据
    data = json.loads(request.body)
    oldpassword = md5(data.get('oldpassword'))
    password1 = md5(data.get('password1'))
    password2 = data.get('password2')
    #验证当前用户的旧密码是否正确
    userprofile_exists = UserProfile.objects.filter(username=username,password=oldpassword).exists()
    if not userprofile_exists:
        content = {
            'code':10012,
            'error':'旧密码错误'
        }
        return JsonResponse(content)
    try:
        UserProfile.objects.filter(username=username).update(password=password1)
        content = {
            'code':200,
            'data':'修改成功'
        }
    except Exception as e:
        content = {
            'code': 10013,
            'data': '修改失败'
        }
    return JsonResponse(content)