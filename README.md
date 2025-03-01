# home_csust_calendar

Home Assistant 自定义集成，用于将长沙理工大学的课表导入到日历中

## 配置方法

1. 爬取课表
   在项目根目录下运行`calendar_crawler.py`脚本，爬取您的课表信息并生成`timetable.json`文件：

   ```bash
   python calendar_crawler.py
   ```

   生成的`timetable.json`文件将保存在项目根目录下。

2. 拷贝课表文件
   将生成的`timetable.json`文件拷贝到集成的根目录中：
