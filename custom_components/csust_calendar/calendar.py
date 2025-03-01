# type: ignore
from datetime import datetime, timedelta
import logging
import json
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    async_add_entities([CSUSTCalendarEntity(config_entry)], True)


class CSUSTCalendarEntity(CalendarEntity):
    def __init__(self, config_entry):
        self._config_entry = config_entry
        self._events = []
        self._attr_name = "CSUST课程日历"
        self._attr_unique_id = f"csust_calendar_{config_entry.entry_id}"

    @property
    def event(self):
        return self._events[0] if self._events else None

    async def async_get_events(self, hass, start_date, end_date):
        return [e for e in self._events if e.start >= start_date and e.end <= end_date]

    async def async_update(self):
        """异步更新课程数据"""
        try:
            file_path = self.hass.config.path("timetable.json")
            data = await self.hass.async_add_executor_job(
                self._load_timetable, file_path
            )
            self._events = await self.hass.async_add_executor_job(
                self._convert_to_events,
                data["timetable"],
                data["metadata"]["start_date"],
                data["metadata"]["sections"],
            )
        except Exception as e:
            _LOGGER.error("更新课程表失败: %s", str(e))
            self._events = []

    def _load_timetable(self, file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _convert_to_events(self, timetable, start_date_str, sections_metadata):
        events = []
        tz = dt_util.get_time_zone(self.hass.config.time_zone)

        try:
            semester_start = dt_util.as_local(
                datetime.strptime(start_date_str, "%Y-%m-%d")
            ).date()
        except Exception as e:
            _LOGGER.error("无效的学期开始日期: %s", str(e))
            return []

        for course in timetable:
            # 处理周次类型（单双周）
            weeks = course["weeks"]
            if course["week_type"] == "odd":
                weeks = [w for w in weeks if w % 2 == 1]
            elif course["week_type"] == "even":
                weeks = [w for w in weeks if w % 2 == 0]

            # 查找对应节次的时间段
            matched_section = next(
                (
                    s
                    for s in sections_metadata
                    if set(course["sections"]) == set(s["sections"])
                ),
                None,
            )
            if not matched_section:
                continue

            # 解析时间范围
            start_str, end_str = matched_section["time"].split("-")
            start_time = datetime.strptime(start_str, "%H:%M").time()
            end_time = datetime.strptime(end_str, "%H:%M").time()

            # 转换星期数值到中文（用于计算）
            weekday_map = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            weekday_str = weekday_map[course["weekday"] - 1]

            # 生成每个周次的事件
            for week in weeks:
                course_date = self._calculate_date(semester_start, week, weekday_str)
                start_datetime = dt_util.as_local(
                    datetime.combine(course_date, start_time)
                )
                end_datetime = dt_util.as_local(datetime.combine(course_date, end_time))

                events.append(
                    CalendarEvent(
                        start=start_datetime,
                        end=end_datetime,
                        summary=course["course_name"],
                        description=course["teacher"],
                        location=course["classroom"],
                    )
                )

        return events

    def _calculate_date(self, semester_start_date, week, weekday_str):
        """计算具体的上课日期"""
        weekdays = {
            "周一": 0,
            "周二": 1,
            "周三": 2,
            "周四": 3,
            "周五": 4,
            "周六": 5,
            "周日": 6,
        }

        # 找到学期开始当周的周日
        if semester_start_date.weekday() == 6:
            first_sunday = semester_start_date
        else:
            days_since_sunday = (semester_start_date.weekday() + 1) % 7
            first_sunday = semester_start_date - timedelta(days=days_since_sunday)

        # 计算目标周次
        target_week_sunday = first_sunday + timedelta(weeks=week - 1)
        return target_week_sunday + timedelta(days=weekdays[weekday_str] + 1)
