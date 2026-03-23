from django.http import JsonResponse

def test_cors(request):
    return JsonResponse({'message': 'Hello, world!'})
