import asyncio
import os
import sys

# Add python_services to path
sys.path.append(os.path.join(os.getcwd(), 'python_services'))

async def test_summary():
    try:
        from services.quota_monitor_service import QuotaMonitorService
        print("Import successful")
        summary = await QuotaMonitorService.get_summary(days=30)
        print("Summary retrieved successfully")
        print(summary)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_summary())
