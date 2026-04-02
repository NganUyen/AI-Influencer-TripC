"""
Compositor module for capture pipeline.
Handles image composition with overlays, highlights, and text.
"""

from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont

from .capture_models import SceneCaptureSpec, SceneCaptureResult
from .exceptions import CaptureCompositorError

# Try to import from config, fallback to default
try:
    from .capture_config import TARGET_SIZE
except ImportError:
    TARGET_SIZE = (1080, 960)


def composite_overlay(
    input_path: str,
    output_path: str,
    spec: SceneCaptureSpec,
    campaign_id: Optional[str] = None
) -> SceneCaptureResult:
    """
    Compose image with overlays based on scene specification.
    
    Args:
        input_path: Path to input image
        output_path: Path to save composed image
        spec: Scene capture specification with headline, highlight, etc.
        campaign_id: Optional campaign ID for error reporting
        
    Returns:
        SceneCaptureResult with subtitle_text and subtitle_position
        
    Raises:
        Exception: If image processing fails, includes campaign_id in message
    """
    try:
        # Open image
        img = Image.open(input_path)
        
        # Đảm bảo output luôn đúng 1080x960
        if img.size != TARGET_SIZE:
            img = img.resize(TARGET_SIZE)
        
        draw = ImageDraw.Draw(img)
        
        # Draw headline if exists
        if spec.headline:
            try:
                font = ImageFont.truetype("arial.ttf", 44)
            except Exception:
                font = ImageFont.load_default()
            draw.text((48, 48), spec.headline, fill="#FFFFFF", font=font)
        
        # Draw highlight region if exists
        if spec.highlight_region:
            region = spec.highlight_region
            # Calculate rectangle coordinates
            x1, y1 = region.x, region.y
            x2, y2 = x1 + region.w, y1 + region.h
            
            # Draw rectangle with border
            draw.rectangle(
                [(x1, y1), (x2, y2)],
                outline=region.border_color,
                width=3
            )
            
            # Apply zoom if needed
            if region.zoom_factor > 1.0:
                # Crop and zoom region
                cropped = img.crop((x1, y1, x2, y2))
                zoom_w = max(1, int(region.w * region.zoom_factor))
                zoom_h = max(1, int(region.h * region.zoom_factor))
                zoomed = cropped.resize((zoom_w, zoom_h))
                paste_x = max(0, x1 - (zoom_w - region.w) // 2)
                paste_y = max(0, y1 - (zoom_h - region.h) // 2)
                img.paste(zoomed, (paste_x, paste_y))
        
        # Create output directory if needed
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Save composed image
        img.save(output_path)
        
        # Return result with subtitle data
        # Subtitle is NOT rendered in top-half (that's for bottom-half assembly)
        return SceneCaptureResult(
            scene_index=spec.scene_index,
            image_path=output_path,
            subtitle_text=spec.script_text,
            success=True
        )
        
    except OSError as e:
        # Include campaign_id in error message
        error_msg = f"Image processing failed for campaign {campaign_id}: {e}"
        raise CaptureCompositorError(error_msg) from e
