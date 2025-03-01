from datetime import datetime
import json
import re
import sys
import aiohttp
from bs4 import BeautifulSoup
import base64
import asyncio


class CSUSTCourseSpider:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        }
        self.session = aiohttp.ClientSession(headers=self.headers)

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(headers=self.headers)
        return self

    async def __aexit__(self, *err):
        await self.session.close()

    async def login(self, student_id, password):
        login_url = "http://xk.csust.edu.cn/jsxsd/xk/LoginToXk"
        encoded = f"{base64.b64encode(student_id.encode()).decode()}%%%{base64.b64encode(password.encode()).decode()}"

        form_data = {"userAccount": student_id, "userPassword": "", "encoded": encoded}

        async with self.session.post(
            login_url, data=form_data, allow_redirects=False
        ) as response:
            # 检查登录是否成功
            if "JSESSIONID" not in response.cookies:
                raise Exception("登录失败：未获取有效的JSESSIONID")

    def parse_weeks(self, week_str):
        """解析周次字符串，返回结构化的周次数据"""
        week_type = "all"  # all/odd/even
        clean_str = re.sub(r"\s+", "", week_str)

        # 提取周次类型
        if "单周" in clean_str:
            week_type = "odd"
            clean_str = clean_str.replace("单周", "")
        elif "双周" in clean_str:
            week_type = "even"
            clean_str = clean_str.replace("双周", "")

        # 移除周次相关描述文字
        clean_str = re.sub(r"周.*", "", clean_str)

        # 解析周次范围
        weeks = []
        for part in clean_str.split(","):
            if "-" in part:
                try:
                    start, end = map(int, part.split("-"))
                    weeks.extend(range(start, end + 1))
                except:
                    continue
            elif part.isdigit():
                weeks.append(int(part))

        # 根据类型过滤
        if week_type == "odd":
            weeks = [w for w in weeks if w % 2 == 1]
        elif week_type == "even":
            weeks = [w for w in weeks if w % 2 == 0]

        return {
            "original": week_str.strip(),
            "type": week_type,
            "list": sorted(list(set(weeks))),  # 去重排序
        }

    async def get_timetable(self):
        timetable_url = "http://xk.csust.edu.cn/jsxsd/xskb/xskb_list.do"
        async with self.session.get(timetable_url) as response:
            text = await response.text()

            if "用户登录" in text:
                raise Exception("会话已过期，请重新登录")

            soup = BeautifulSoup(text, "html.parser")
            return await self.parse_timetable(soup)

    async def parse_timetable(self, soup):
        """解析课表HTML"""
        courses = []
        table = soup.find("table", {"id": "kbtable"})
        rows = table.find_all("tr")[1:-1]  # 跳过表头和备注行

        for row in rows:
            time_slot = " ".join(row.th.get_text(strip=True).split())  # 清理时间段

            # 获取星期对应的列索引（跳过第一个th）
            for day_idx, td in enumerate(row.find_all("td")):
                day = self.get_weekday(day_idx)
                self.parse_course_td(td, day, time_slot, courses)

        return courses

    def parse_course_td(self, td, day, time_slot, courses):
        """解析单个课程单元格（优化结构版）"""
        for content_div in td.find_all("div", class_="kbcontent"):
            text = content_div.get_text("\n", strip=True)
            if not text or text == " ":
                continue

            # 基础解析
            raw_period = re.search(r"第.+节", time_slot).group()
            raw_time = re.search(r"\d{2}:\d{2}-\d{2}:\d{2}", time_slot).group()
            start_time, end_time = raw_time.split("-")

            course_info = {
                "name": "",
                "classroom": "",
                "teacher": "",
                "day": day,
                "weeks": {},
                "start_time": start_time,
                "end_time": end_time,
                "original": {
                    "period": raw_period,
                    "time_slot": raw_time,
                    "detail_time": "",
                    "raw_text": text.strip(),
                },
            }

            # 提取课程名称
            name_part = content_div.find(string=True, recursive=False)
            if name_part:
                course_info["name"] = name_part.strip().split("\n")[0]

            # 解析详细信息
            for font in content_div.find_all("font"):
                title = font.get("title", "")
                value = font.text.strip()

                if "老师" in title:
                    course_info["teacher"] = value
                elif "周次" in title:
                    # 合并单双周信息到周次字符串
                    week_str, time_str = value, ""
                    if "(" in value:
                        week_str, time_str = value.split("(", 1)
                        time_str = time_str.replace(")", "").strip()
                    course_info["original"]["detail_time"] = time_str
                    course_info["weeks"] = self.parse_weeks(week_str)
                elif "教室" in title:
                    course_info["classroom"] = value

            if course_info["name"]:
                courses.append(course_info)

    def get_weekday(self, index):
        """根据列索引获取星期"""
        weekdays = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"]
        return weekdays[index]


async def main():
    spider = CSUSTCourseSpider()

    student_id = input("请输入学号: ")
    password = input("请输入密码: ")
    semester_start = input("请输入学期开始日期 (格式: YYYY-MM-DD): ")

    try:
        await spider.login(student_id, password)
        timetable = await spider.get_timetable()

        # 保存JSON文件
        data = {
            "timetable": timetable,
            "metadata": {
                "total_courses": len(timetable),
                "update_time": datetime.now().isoformat(),
                "semester_start": semester_start,
            },
        }

        with open("timetable.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print("课程数据已保存到timetable.json")

    except Exception as e:
        print(f"操作失败：{str(e)}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
