from django.shortcuts import render
from django.http import HttpResponse
from django.http import JsonResponse
from .models import  Catalog,SKU,SaleAttrValue
from django.db.models import  F
from django.conf import  settings
from django.core.paginator import Paginator
import json

def index(request):
    data = []
    catalog_queryset = Catalog.objects.values(catalog_id=F('id'),catalog_name=F('name'))
    for catalog in catalog_queryset:
        sku_querylist = list(SKU.objects.values('caption','name','price',image=F('default_image_url'),skuid=F('id'),).filter(is_launched=True,spu__in=Catalog.objects.get(pk=catalog['catalog_id']).spu_set.all())[:3])
        catalog.update({'sku':sku_querylist})
        data.append(catalog)
    '''
    data = []
    catalog_queryset = Catalog.objects.all()
    for catalog in catalog_queryset:
        #################################################
        sku_list =[]
        sku_queryset = SKU.objects.filter(is_launched=True,spu__in=Catalog.objects.get(pk=catalog.id).spu_set.all())[:3]
        for sku in sku_queryset:
            sku_list.append({
                'skuid':sku.id,
                'name':sku.name,
                'price':sku.price,
                'caption':sku.caption,
                'image':sku.default_image_url.name ##???
            })

        #################################################
        data.append({
            'catalog_id':catalog.id,
            'catalog_name':catalog.name,
            'sku':sku_list
        })
    '''
    #################################################################
    content = {
        'code':200,
        'base_url':request.build_absolute_uri(settings.MEDIA_URL),
        'data':data
    }
    return JsonResponse(content)

def catalogs(request,id):
    #要获取当前分类下的所有正常上架的商品  -- 结果集内嵌套字典
    sku_queryset = SKU.objects.values('name','price',skuid=F('id'),image=F('default_image_url')).filter(is_launched=True,spu__in=Catalog.objects.get(pk=id).spu_set.all())
    #指定每页要显示的记录数量
    per_page = 1
    #分页器
    paginator = Paginator(object_list=sku_queryset,per_page=per_page)
    #获取通过URL地址栏传递的页码
    page = request.GET.get("page")
    #根据页码来获取当前页的数据
    paged_sku_objects = paginator.get_page(page)
    content = {
        'code':200,
        'base_url':request.build_absolute_uri(settings.MEDIA_URL),
        'paginator':{
            'total':paginator.count,#指总记录数  -- 也可以采用sku_queryset.count()方法取代
            'pagesize':per_page #每页有几条
        },
        # 现在要返回当前这一页中的所有商品，每件商品都以字典的格式返回
        'data':list(paged_sku_objects.object_list) #在本案例中即可以采用object_list属性，也可以省略
    }
    return JsonResponse(content)

def detail(request,id):
    #根据主键获取当前商品 -- 返回模型实例
    sku_object = SKU.objects.get(pk=id)
    #获取当前商品所属的SPU的属性名称
    sku_object_spusaleattr = sku_object.spu.spusaleattr_set.values('id','name') #一正一反
    # print(sku_object_spusaleattr)
    sku_sale_attr_id = list(sku_object_spusaleattr.values_list('id',flat=True))
    sku_sale_attr_names = list(sku_object_spusaleattr.values_list('name',flat=True))
    #print(sku_sale_attr_id)
    #print(sku_sale_attr_names)
    ##############################################################
    sku_sale_attr_val_queryset = SaleAttrValue.objects.filter(spu_sale_attr__in=sku_sale_attr_id)
    sku_sale_attr_val_id = list(sku_sale_attr_val_queryset.values_list('id',flat=True))
    sku_sale_attr_val_names = list(sku_sale_attr_val_queryset.values_list('name',flat=True))
    # print(sku_sale_attr_val_queryset)
    # print(sku_sale_attr_val_id)
    # print(sku_sale_attr_val_names)
    ##############################################################
    sku_all_sale_attr_vals_name = {spu_id:[item.name for item in sku_sale_attr_val_queryset if spu_id == item.spu_sale_attr_id ] for spu_id in sku_sale_attr_id}
    sku_all_sale_attr_vals_id = {spu_id:[item.id for item in sku_sale_attr_val_queryset if spu_id == item.spu_sale_attr_id ] for spu_id in sku_sale_attr_id}
    # print(sku_all_sale_attr_vals_name)
    # print(sku_all_sale_attr_vals_id)
    ##############################################################
    content = {
            'code': 200,
            'base_url': request.build_absolute_uri(settings.MEDIA_URL),
            'data': {
                # 当前商品所属类别的信息
                'catalog_id': sku_object.spu.catalog.id, #两次正向关系
                'catalog_name': sku_object.spu.catalog.name, #两次正向关系

                # 当前商品的信息
                'name': sku_object.name,
                'caption': sku_object.caption,
                'price': sku_object.price,
                'image': sku_object.default_image_url.name,#需要注意的是：模型中的字段数据为ImageField
                'spu': sku_object.spu_id, #或者采用sku_object.spu.id(采用正向关系)

                # 详情图片(为固定值)
                'detail_image': 'v2-1.jpg',

                # 当前商品所属的SPU属性名称信息
                'sku_sale_attr_id': sku_sale_attr_id,
                'sku_sale_attr_names': sku_sale_attr_names,

                # 当前商品所属的SPU属性的值的信息
                'sku_sale_attr_val_id': sku_sale_attr_val_id,
                'sku_sale_attr_val_names': sku_sale_attr_val_names,

                # SPU属性名称和属性值的对应关系
                'sku_all_sale_attr_vals_id':sku_all_sale_attr_vals_id,
                'sku_all_sale_attr_vals_name': sku_all_sale_attr_vals_name,

                # 类6和类7：规格属性名和规格属性值
                "spec": {
                    "批次": "2000",
                    "数量": "2000",
                    "年份": "2000"
                }
            }

        }
    return JsonResponse(content)

def sku(request):
    data = json.loads(request.body)
    spuid = data.get('spuid')
    '''
    请求的数据格式为{*SPU属性ID:值,spuid:当前商品所属的SPU的ID}
    基本的实现原理是：
    1.首先获取当前SPU下的所有商品,按两个属性，每个属性有两个值来计算的话就可以得到4件商品(正常情况下)
    2.但是这4件商品中只有一件商品是切换SKU时的唯一商品，那么就需要再从这4件商品中进行过滤
    过滤的条件就是：根据请求数据中所提供的属性名称和值进行判断,如某个SPU两个属性：颜色和尺寸，
    颜色(假设ID5)有：红色(假设ID为1)和绿色(假设ID为：2)
    尺寸(假设ID6)有：15寸(假设ID为3)和16寸(假设ID为4)
    第一步的得到的数据就是
    商品名称    颜色      尺寸
    A          1(红色)    3(15寸)
    B          1(红色)    4(16寸)
    C          2(绿色)    3(15寸) 
    D          2(绿色)    6(16寸)  
    再假设现在提交的数据是 {5:1,6:3 ，先经过 {5:1}进行过滤，此时的结果为：
    A          1(红色)    3(15寸)
    B          1(红色)    4(16寸)
    再经过{6,3} 过滤,结果为：
    A          1(红色)    3(15寸)
    '''
    print('原来的',data)
    data.pop('spuid')
    print('删除后的',data)
    #首先获取当前SPU下的所有商品
    sku_queryset = SKU.objects.filter(spu=spuid)
    # i = 1
    #然后根据属性值循环进行过滤
    for _,value in data.items():
        sku_queryset = sku_queryset.filter(sale_attr_value=value)
        # print(f'第{i}次的结果为:',sku_queryset)
        # i+=1
    if sku_queryset:
        content = {
            'code':200,
            'data':sku_queryset.first().id
        }

    else:
        content = {
            'code':10020,
            'error':'对不起，商品不存在'
        }
    return JsonResponse(content)

