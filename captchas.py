import random
import random
import string
from io import BytesIO
from captcha.image import ImageCaptcha
from PIL import Image
import os

def generate_captcha(captcha_length, characters_and_numbers):
    if characters_and_numbers == True:
        style = string.ascii_uppercase + string.digits
    else:
        style = string.ascii_uppercase
    random_string = ''.join(random.choices(style, k=captcha_length))

    captcha = ImageCaptcha()
    data: BytesIO = captcha.generate(random_string)

    image = Image.open(data)
    image.save(f'./captchas/{random_string}.png')

    return random_string

def delete_captcha(string):
    os.remove(f'./captchas/{string}.png')
