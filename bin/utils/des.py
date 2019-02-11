# encoding:utf-8
from pyDes import triple_des, CBC, PAD_PKCS5
import base64

from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5, PKCS1_PSS
from Crypto.Hash import SHA, SHA256, MD5
from Crypto.Cipher import PKCS1_v1_5 as Cipher_pkcs1_v1_5
from Crypto import Random

#签名私钥
signPrivateKey = '''-----BEGIN RSA PRIVATE KEY-----
                 MIIBVgIBADANBgkqhkiG9w0BAQEFAASCAUAwggE8AgEAAkEAqiK+jmlvJfxQSkuV44T8Pwwk5FGeYRi/7UQAQfp/9IQ0O3ad0h/ex+ABDPqUbiVYnU2LDmx+UtmvVwzF/AfRRwIDAQABAkEAoLejlPoqYhLAcf6HAF9+vbwmGXy0hXqQy3yiVbFiMEMn7Svb8h/fQ7ZLBvS+8OGpZOwIt6e6T3pGto/upppKsQIhAPNyfoNqPRtdpVEvWwtwNode1NXAm0Z16ycZ5U1Jez8PAiEAsuiJk1ZAFjr4k3gMq01qUb1pyT+02f/e9nXvSoXPykkCIQC7HkTZs53WW+tGdHSxXQW8lQpYZZuz08z0F/Zkqlc9xwIgNrIo/UZtKV62CD+3f9eXHY5O/Rvg6pTzUV4U3i+yqyECIQCNLE4bY0zvOJGv7hrPmcVZStmbL+cg9FrGKEu2n6z4MQ==
                 -----END RSA PRIVATE KEY-----'''
#固定平台签名公钥
signPublicKey = '''-----BEGIN PUBLIC KEY-----
                MFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAJZbLUlvQtyyGfFJOJnLs98Cv0nbHseAJ7kGIrFhVHf16Ewfa8asBmAToUM67Uspr7P5p/zxVTffN4YMrP+5400CAwEAAQ==
                -----END PUBLIC KEY-----'''

def encrypt_3des(data, appkey, mode=CBC,  IV='', pad=None, padmode=PAD_PKCS5):
    des3 = triple_des(appkey, mode=mode, IV=IV, pad=pad, padmode=padmode)
    res2 = des3.encrypt(data)
    result = base64.b64encode(res2)
    return result

def decrypt_3des(enc_data, appkey, mode=CBC,  IV='', pad=None, padmode=PAD_PKCS5):
    des3 = triple_des(appkey, mode=mode, IV=IV, pad=pad, padmode=padmode)
    raw = base64.b64decode(enc_data)
    result = des3.decrypt(raw)
    return result


def sign_(data, signPrivateKey):
    key = RSA.importKey(signPrivateKey)
    h = MD5.new(data)
    signer = PKCS1_v1_5.new(key)
    signature = signer.sign(h)
    return base64.b64encode(signature)

def unsign(data):
    key = RSA.importKey(signPrivateKey)
    # h = SHA.new(data)
    cipher = Cipher_pkcs1_v1_5.new(key)
    # signature = signer.sign(h)
    return cipher.decrypt(base64.b64decode(data), Random.new().read(15+SHA.digest_size))

def verify(data, signature, signPublicKey):
    key = RSA.importKey(signPublicKey)
    h = MD5.new(data)
    verifier = PKCS1_v1_5.new(key)
    if verifier.verify(h, base64.b64decode(signature)):
        return True
    return False



if __name__ == '__main__':
     appkey = "l4mdofLTvHkyONpdlyXBiaTv"
     vector = "12345678"
     data = "123456"
     en = encrypt_3des(data, appkey, IV=vector)
     print en
     de = decrypt_3des(en, appkey, IV=vector)
     print de
     signature = sign_(en, signPrivateKey)

     print signature
     # print unsign(signature)
     print verify(data, signature, signPublicKey)

     # print '------'
     # print rsa_sign(data)
     # print verify_sign(data , rsa_sign())