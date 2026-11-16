"""Shared presentation assets. No simulation state or input behavior."""
from functools import lru_cache
from PIL import Image, ImageDraw
from ursina import Texture

@lru_cache(maxsize=32)
def rounded_surface(width, height):
    """Antialiased white mask, tinted by Entity.color; cached per aspect ratio."""
    w = max(8, int(width * 1000))
    h = max(8, int(height * 1000))
    image = Image.new('RGBA', (w * 2, h * 2), (255, 255, 255, 0))
    ImageDraw.Draw(image).rounded_rectangle((0, 0, w * 2 - 1, h * 2 - 1),
        radius=min(16, h // 3), fill=(255, 255, 255, 255))
    return Texture(image.resize((w, h), Image.Resampling.LANCZOS))
