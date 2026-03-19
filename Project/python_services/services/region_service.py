import httpx
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class RegionService:
    """
    Dịch vụ hỗ trợ nhận diện vùng miền qua IP để cá nhân hóa AI Influencer.
    """
    
    def __init__(self):
        # Sử dụng dịch vụ miễn phí ip-api.com hoặc ipapi.co
        self.api_url = "http://ip-api.com/json/"

    async def get_region_info(self, ip: Optional[str] = None, country_code_override: Optional[str] = None) -> Dict[str, Any]:
        """
        Lấy thông tin địa lý từ IP. Nếu có country_code_override, sẽ bỏ qua IP và trả về template quốc gia đó.
        """
        if country_code_override:
            logger.info(f"Manual region override: {country_code_override}")
            return {
                "country": f"Manual ({country_code_override})",
                "countryCode": country_code_override.upper(),
                "region": "Manual Override",
                "city": "Manual Override",
                "timezone": "UTC",
                "continent": self._map_to_continent(country_code_override.upper())
            }

        url = f"{self.api_url}{ip if ip else ''}"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=5.0)
                data = response.json()
                
                if data.get("status") == "fail":
                    logger.warning(f"IP Detection failed: {data.get('message')}")
                    return self._get_default_region()
                
                return {
                    "country": data.get("country", "Vietnam"),
                    "countryCode": data.get("countryCode", "VN"),
                    "region": data.get("regionName", "Da Nang"),
                    "city": data.get("city", "Da Nang"),
                    "timezone": data.get("timezone", "Asia/Ho_Chi_Minh"),
                    "continent": self._map_to_continent(data.get("countryCode", "VN"))
                }
        except Exception as e:
            logger.error(f"Error detecting region from IP: {str(e)}")
            return self._get_default_region()

    def _map_to_continent(self, country_code: str) -> str:
        """
        Logic mapping đơn giản từ mã quốc gia sang 5 châu lục chính.
        """
        # Đây là bản mapping rút gọn, có thể mở rộng thêm
        asia_codes = ["VN", "CN", "JP", "KR", "TH", "IN", "SG", "MY"]
        europe_codes = ["FR", "DE", "GB", "IT", "ES", "NL", "RU"]
        america_codes = ["US", "CA", "BR", "MX", "AR"]
        africa_codes = ["NG", "ZA", "EG", "KE", "MA"]
        australia_codes = ["AU", "NZ"]

        if country_code in asia_codes: return "asia"
        if country_code in europe_codes: return "europe"
        if country_code in america_codes: return "america"
        if country_code in africa_codes: return "africa"
        if country_code in australia_codes: return "australia"
        
        return "asia" # Default

    def _get_default_region(self) -> Dict[str, Any]:
        return {
            "country": "Vietnam",
            "countryCode": "VN",
            "region": "Da Nang",
            "city": "Da Nang",
            "timezone": "Asia/Ho_Chi_Minh",
            "continent": "asia"
        }
