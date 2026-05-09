import base64
import io

from PIL import Image, ImageGrab


class ScreenCapture:
    @staticmethod
    def capture_jpeg_base64(max_side: int = 1280, quality: int = 78) -> str:
        image = ImageGrab.grab(all_screens=True)
        image = image.convert("RGB")
        width, height = image.size
        largest = max(width, height)
        if largest > max_side:
            scale = max_side / largest
            image = image.resize((int(width * scale), int(height * scale)), Image.LANCZOS)

        output = io.BytesIO()
        image.save(output, format="JPEG", quality=quality, optimize=True)
        return base64.b64encode(output.getvalue()).decode("ascii")
