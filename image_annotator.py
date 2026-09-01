from pathlib import Path
from PIL import Image, ImageDraw, ImageOps

def draw_evidence(image_path: str | Path, extraction: dict, output_path: str | Path) -> str:
    """Draws normalized bounding boxes from Gemini onto the image."""
    with Image.open(image_path) as img:
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGBA")
        draw = ImageDraw.Draw(img)
        width, height = img.size
        
        for item in extraction.get("evidence", []):
            box = item.get("box_2d")
            if not box or len(box) != 4:
                continue
            
            ymin, xmin, ymax, xmax = box
            # Convert normalized 0-1000 to absolute pixels
            abs_xmin = (xmin / 1000.0) * width
            abs_ymin = (ymin / 1000.0) * height
            abs_xmax = (xmax / 1000.0) * width
            abs_ymax = (ymax / 1000.0) * height
            
            # Draw red rectangle and yellow label
            draw.rectangle([abs_xmin, abs_ymin, abs_xmax, abs_ymax], outline="red", width=4)
            field = item.get("field", "Unknown")
            draw.text((abs_xmin, max(0, abs_ymin - 15)), field, fill="yellow")
            
        img.save(output_path, format="PNG")
        return str(output_path)
