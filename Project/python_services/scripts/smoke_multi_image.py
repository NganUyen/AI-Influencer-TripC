import asyncio
import httpx
import os
import json

async def test_multi_image_gen():
    backend_url = "http://localhost:8000"
    token = os.getenv("INTERNAL_API_TOKEN", "your-internal-token")
    
    headers = {"x-internal-api-token": token}
    payload = {
        "prompt": "A futuristic city in the style of cyberpunk",
        "num_images": 2,
        "aspect_ratio": "16:9"
    }
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        print(f"Sending request to {backend_url}/api/media/generate/image")
        try:
            response = await client.post(
                f"{backend_url}/api/media/generate/image",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            result = response.json()
            
            print("Response received:")
            print(json.dumps(result, indent=2))
            
            if "images" in result and len(result["images"]) == 2:
                print("\nSUCCESS: Received 2 images.")
            else:
                print(f"\nFAILURE: Expected 2 images, got {len(result.get('images', []))}")
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_multi_image_gen())
