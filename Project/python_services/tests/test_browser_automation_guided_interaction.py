import pytest

from services.browser_automation import BrowserAutomationService


class _FakeLocator:
    def __init__(self, should_exist: bool):
        self.should_exist = should_exist
        self.clicked = False

    async def count(self):
        return 1 if self.should_exist else 0

    @property
    def first(self):
        return self

    async def click(self, timeout=1500):
        self.clicked = True


class _FakePage:
    def __init__(self):
        self.locators = {
            "Hero CTA": _FakeLocator(True),
        }
        self.wait_called = False

    def get_by_text(self, text, exact=False):
        return self.locators.get(text, _FakeLocator(False))

    async def wait_for_load_state(self, state, timeout=2500):
        self.wait_called = True


@pytest.mark.asyncio
async def test_attempt_guided_interaction_clicks_matching_text():
    service = BrowserAutomationService()
    page = _FakePage()

    await service._attempt_guided_interaction(
        page=page,
        target_selector="Hero CTA",
        action_text="Click the hero CTA and hold on the signup button",
        visual_success_criteria="Hero CTA is visible",
    )

    assert page.locators["Hero CTA"].clicked is True
    assert page.wait_called is True
