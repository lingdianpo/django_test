import hashlib
import jwt
from  django.conf import settings
def md5(string):
    md5 = hashlib.md5()
    string += settings.SALT_FOR_PASSWORD
    md5.update(string.encode())
    return md5.hexdigest()

def jwt_encode(payload):
    string = jwt.encode(payload=payload,key=settings.JWT_SECRET_KEY)
    return string

def jwt_decode(string):
    payload = jwt.decode(jwt=string,key=settings.JWT_SECRET_KEY,algorithms='HS256')
    return payload