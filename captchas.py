import random
import random
import string
from io import BytesIO
from captcha.image import ImageCaptcha
from PIL import Image
import os

def generate_captcha():
    random_string = ''.join(random.choices(string.ascii_uppercase, k=6))

    captcha = ImageCaptcha()
    data: BytesIO = captcha.generate(random_string)

    image = Image.open(data)
    image.save(f'./captchas/{random_string}.png')

    return random_string

def delete_captcha(string):
    os.remove(f'./captchas/{string}.png')
