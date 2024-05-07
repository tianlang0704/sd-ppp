from PIL import Image
import numpy as np

class ImageCache:
    data = dict()
    image_id_inc = 0

def cache_images(images):
    ret = []
    for (batch_number, image) in enumerate(images):
        i = 255. * image.cpu().numpy()
        img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
        ImageCache.image_id_inc += 1
        image_id = ImageCache.image_id_inc
        ImageCache.data[image_id] = img
        ret.append(image_id)
    return ret