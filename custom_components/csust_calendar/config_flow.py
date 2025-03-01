from homeassistant import config_entries
import voluptuous as vol


class CSUSTCalendarConfigFlow(config_entries.ConfigFlow, domain="csust_calendar"):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        return self.async_create_entry(
            title="CSUST课程日历", data={}  # 不需要存储任何配置信息
        )
