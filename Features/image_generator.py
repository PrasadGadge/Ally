# import asyncio
# from random import randint
# import requests
# import os
# from TextToSpeech.Fast_DF_TTS import speak

# try:
#     from PIL import Image
# except Exception:
#     Image = None

# try:
#     from dotenv import get_key
# except Exception:
#     _DOTENV_WARNED = False
#     def get_key(*args, **kwargs):
#         global _DOTENV_WARNED
#         if not _DOTENV_WARNED:
#             print("[ImageGen] python-dotenv not available; using empty API key.")
#             _DOTENV_WARNED = True
#         return None

# # FIX: runwayml/SD-v1-5 dropped by hf-inference. Using FLUX.1-schnell + fallbacks.
_HF_MODELS = [
    "black-forest-labs/FLUX.1-schnell",
    "stabilityai/stable-diffusion-xl-base-1.0",
]
API_URL = f"https://api-inference.huggingface.co/models/{_HF_MODELS[0]}"

# headers = {
#     "Authorization": f"Bearer {get_key('.env', 'HuggingFaceAPIKey')}",
#     "Content-Type": "application/json"
# }

# if not os.path.exists("image_storage"):
#     os.makedirs("image_storage")


# async def query(payload):
#     response = await asyncio.to_thread(
#         requests.post,
#         API_URL,
#         headers=headers,
#         json=payload
#     )

#     print("Status Code:", response.status_code)

#     if response.status_code != 200:
#         print("Error Response:", response.text)
#         return None

#     # Check if response is actually image
#     if "image" not in response.headers.get("content-type", ""):
#         print("Not an image! Response was:", response.text)
#         return None

#     return response.content


# async def generate_images(prompt: str):
#     tasks = []

#     for i in range(4):
#         seed = randint(0, 1000000)

#         payload = {
#             "inputs": f"{prompt}, ultra high detail, 4k, seed={seed}"
#         }

#         tasks.append(asyncio.create_task(query(payload)))

#     responses = await asyncio.gather(*tasks)

#     for i, content in enumerate(responses):
#         if content:
#             with open(f"Data/{prompt.replace(' ', '_')}{i+1}.jpg", "wb") as f:
#                 f.write(content)

#     return True


# def GenerateImages(prompt: str):
#     asyncio.run(generate_images(prompt))
#     speak("Boss, the task is complete. Your image has been successfully created.")


import asyncio
from random import randint
import requests
import os
from TextToSpeech.Fast_DF_TTS import speak

try:
    from PIL import Image
except Exception:
    Image = None

try:
    from dotenv import get_key
except Exception:
    _DOTENV_WARNED = False
    def get_key(*args, **kwargs):
        global _DOTENV_WARNED
        if not _DOTENV_WARNED:
            print("[ImageGen] python-dotenv not available; using empty API key.")
            _DOTENV_WARNED = True
        return None

# FIX: runwayml/SD-v1-5 dropped by hf-inference. Using FLUX.1-schnell + fallbacks.
_HF_MODELS = [
    "black-forest-labs/FLUX.1-schnell",
    "stabilityai/stable-diffusion-xl-base-1.0",
]
API_URL = f"https://api-inference.huggingface.co/models/{_HF_MODELS[0]}"

headers = {
    "Authorization": f"Bearer {get_key('.env', 'HuggingFaceAPIKey')}",
    "Content-Type": "application/json"
}

IMAGE_DIR = "image_storage"   # FIX: was os.makedirs("image_storage") but saving to "Data/"
if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)


async def query(payload):
    for model in _HF_MODELS:
        url = f"https://api-inference.huggingface.co/models/{model}"
        response = await asyncio.to_thread(requests.post, url, headers=headers, json=payload)
        print(f"[ImageGen] {model} → {response.status_code}")
        if response.status_code == 200:
            return response.content
        print(f"[ImageGen] Failed: {response.text[:100]}")
    print("[ImageGen] All models failed.")
    return None

    # Check if response is actually image
    if "image" not in response.headers.get("content-type", ""):
        print("Not an image! Response was:", response.text)
        return None

    return response.content


async def generate_images(prompt: str):
    tasks = []

    for i in range(4):
        seed = randint(0, 1000000)

        payload = {
            "inputs": f"{prompt}, ultra high detail, 4k, seed={seed}"
        }

        tasks.append(asyncio.create_task(query(payload)))

    responses = await asyncio.gather(*tasks)

    for i, content in enumerate(responses):
        if content:
            filename = f"{prompt.replace(' ', '_')}_{i+1}.jpg"
            filepath = os.path.join(IMAGE_DIR, filename)
            with open(filepath, "wb") as f:
                f.write(content)

    return True


def GenerateImages(prompt: str):
    asyncio.run(generate_images(prompt))
    speak("Boss, the task is complete. Your image has been successfully created.")