import httpx
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class RegionService:
    """
    Dịch vụ hỗ trợ nhận diện vùng miền qua IP để cá nhân hóa AI Influencer.
    """

    COUNTRY_LOCALE_MAP = {
        "VN": "vi-VN",
        "US": "en-US",
        "GB": "en-GB",
        "CA": "en-CA",
        "AU": "en-AU",
        "SG": "en-SG",
        "MY": "en-MY",
        "TH": "th-TH",
        "JP": "ja-JP",
        "KR": "ko-KR",
        "FR": "fr-FR",
        "DE": "de-DE",
        "ES": "es-ES",
        "IT": "it-IT",
        "NL": "nl-NL",
        "BR": "pt-BR",
        "MX": "es-MX",
        "AR": "es-AR",
        "IN": "en-IN",
    }

    COUNTRY_TIMEZONE_MAP = {
        "VN": "Asia/Ho_Chi_Minh",
        "US": "America/New_York",
        "GB": "Europe/London",
        "CA": "America/Toronto",
        "AU": "Australia/Sydney",
        "SG": "Asia/Singapore",
        "MY": "Asia/Kuala_Lumpur",
        "TH": "Asia/Bangkok",
        "JP": "Asia/Tokyo",
        "KR": "Asia/Seoul",
        "FR": "Europe/Paris",
        "DE": "Europe/Berlin",
        "ES": "Europe/Madrid",
        "IT": "Europe/Rome",
        "NL": "Europe/Amsterdam",
        "BR": "America/Sao_Paulo",
        "MX": "America/Mexico_City",
        "AR": "America/Argentina/Buenos_Aires",
        "IN": "Asia/Kolkata",
    }

    COUNTRY_CURRENCY_MAP = {
        "VN": "VND",
        "US": "USD",
        "GB": "GBP",
        "CA": "CAD",
        "AU": "AUD",
        "SG": "SGD",
        "MY": "MYR",
        "TH": "THB",
        "JP": "JPY",
        "KR": "KRW",
        "FR": "EUR",
        "DE": "EUR",
        "ES": "EUR",
        "IT": "EUR",
        "NL": "EUR",
        "BR": "BRL",
        "MX": "MXN",
        "AR": "ARS",
        "IN": "INR",
    }

    COUNTRY_NAME_MAP = {
        "VN": "Vietnam",
        "US": "United States",
        "GB": "United Kingdom",
        "CA": "Canada",
        "AU": "Australia",
        "SG": "Singapore",
        "MY": "Malaysia",
        "TH": "Thailand",
        "JP": "Japan",
        "KR": "South Korea",
        "FR": "France",
        "DE": "Germany",
        "ES": "Spain",
        "IT": "Italy",
        "NL": "Netherlands",
        "BR": "Brazil",
        "MX": "Mexico",
        "AR": "Argentina",
        "IN": "India",
    }
    
    def __init__(self):
        # Sử dụng dịch vụ miễn phí ip-api.com hoặc ipapi.co
        self.api_url = "http://ip-api.com/json/"

    async def build_region_profile(
        self,
        ip: Optional[str] = None,
        country_code_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Tạo profile vùng miền dùng cho browser/session.

        Nếu có country_code_override thì dùng profile tĩnh để tránh phụ thuộc network.
        """
        if country_code_override:
            return self._build_country_profile(country_code_override.upper(), source="override")

        if ip:
            return await self.get_region_info(ip=ip)

        return self._get_default_region()

    async def get_region_info(self, ip: Optional[str] = None, country_code_override: Optional[str] = None) -> Dict[str, Any]:
        """
        Lấy thông tin địa lý từ IP. Nếu có country_code_override, sẽ bỏ qua IP và trả về template quốc gia đó.
        """
        if country_code_override:
            logger.info(f"Manual region override: {country_code_override}")
            return self._build_country_profile(country_code_override.upper(), source="override")

        url = f"{self.api_url}{ip if ip else ''}"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=5.0)
                data = response.json()
                
                if data.get("status") == "fail":
                    logger.warning(f"IP Detection failed: {data.get('message')}")
                    return self._get_default_region()
                
                return self._augment_region_profile(
                    {
                        "country": data.get("country", "Vietnam"),
                        "countryCode": data.get("countryCode", "VN"),
                        "region": data.get("regionName", "Da Nang"),
                        "city": data.get("city", "Da Nang"),
                        "timezone": data.get("timezone", "Asia/Ho_Chi_Minh"),
                        "continent": self._map_to_continent(data.get("countryCode", "VN")),
                    }
                )
        except Exception as e:
            logger.error(f"Error detecting region from IP: {str(e)}")
            return self._get_default_region()

    def build_browser_context_settings(
        self,
        region_info: Optional[Dict[str, Any]] = None,
        platform: str = "generic",
    ) -> Dict[str, Any]:
        """
        Sinh config context cho browser theo vùng miền và platform.
        """
        region_info = region_info or self._get_default_region()
        locale = region_info.get("locale") or self._map_to_locale(region_info.get("countryCode", "VN"))
        timezone_id = region_info.get("browserTimezone") or region_info.get("timezone") or "Asia/Ho_Chi_Minh"
        form_factor = "mobile" if platform.lower() == "tiktok" else "desktop"

        if form_factor == "mobile":
            viewport = {"width": 393, "height": 873}
            user_agent = (
                "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Mobile Safari/537.36"
            )
        else:
            viewport = {"width": 1440, "height": 900}
            user_agent = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )

        return {
            "viewport": viewport,
            "user_agent": user_agent,
            "locale": locale,
            "timezone_id": timezone_id,
            "extra_http_headers": {
                "Accept-Language": locale.replace("_", "-"),
            },
            "device_scale_factor": 1,
            "has_touch": form_factor == "mobile",
            "is_mobile": form_factor == "mobile",
            "platform_hint": platform.lower(),
            "country_code": region_info.get("countryCode", "VN"),
            "continent": region_info.get("continent", "asia"),
            "currency": region_info.get("currency", "VND"),
        }

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

    def _map_to_locale(self, country_code: str) -> str:
        country_code = (country_code or "VN").upper()
        return self.COUNTRY_LOCALE_MAP.get(country_code, "en-US")

    def _build_country_profile(self, country_code: str, source: str = "static") -> Dict[str, Any]:
        country_code = (country_code or "VN").upper()
        return {
            "country": self.COUNTRY_NAME_MAP.get(country_code, "Vietnam"),
            "countryCode": country_code,
            "region": "Da Nang" if country_code == "VN" else "General",
            "city": "Da Nang" if country_code == "VN" else "General",
            "timezone": self.COUNTRY_TIMEZONE_MAP.get(country_code, "UTC"),
            "continent": self._map_to_continent(country_code),
            "locale": self._map_to_locale(country_code),
            "browserTimezone": self.COUNTRY_TIMEZONE_MAP.get(country_code, "UTC"),
            "currency": self.COUNTRY_CURRENCY_MAP.get(country_code, "USD"),
            "source": source,
        }

    def _augment_region_profile(self, region_info: Dict[str, Any]) -> Dict[str, Any]:
        country_code = (region_info.get("countryCode") or "VN").upper()
        region_info = dict(region_info)
        region_info.setdefault("locale", self._map_to_locale(country_code))
        region_info.setdefault("browserTimezone", region_info.get("timezone") or self.COUNTRY_TIMEZONE_MAP.get(country_code, "UTC"))
        region_info.setdefault("currency", self.COUNTRY_CURRENCY_MAP.get(country_code, "USD"))
        region_info.setdefault("source", "ip")
        return region_info

    def _get_default_region(self) -> Dict[str, Any]:
        return self._build_country_profile("VN", source="default")
