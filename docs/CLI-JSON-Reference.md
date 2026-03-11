# LAZY CLI JSON 接口描述

通过启用选项`--json`，LAZY CLI 支持以 JSON 格式返回结果，以适配下游客户端和Agent调用。

如果你正在开发基于 LAZY CLI 的下游客户端，需要一个方便的数据结构用于解析，或你正在为 LAZY CLI 编写 Skills，这个文档会有你所需要的。

## 支持命令

- course:
  - list
  - view:
    - syllabus
    - coursewares
    - members
    - rollcalls
- resource:
  - list
  - download
  - remove
  - upload
- assignment:
  - todo
  - view
  - submit

## course命令组

### list

**Command**: `lazy course list --json`

**Schema**:

- status(bool): 若返回 `false`，则发生错误
- description(str): 结果描述，若报错，则返回错误描述
- result(array): 
  - name(str): 课程名称
  - id(str): 课程ID
  - time(str): 课程时间
  - teachers(str): 任课教师名字
  - department_name: 开课院系
  - academic_year: 开课学年

**Example**

```json
{
    "status": true, 
    "description": "Courses List",
    "result": [
        {
            "name": "广义弹幕力学：非线性轨迹中的概率躲避论", 
            "id": "114514", 
            "time": "周二第3,4,5节, 周四第3,4,5节", 
            "teachers": "八云紫",
            "department_name": "境界科学研究部", 
            "academic_year": "2025-2026"
        }
    ]
}
```

### view 

#### syllabus

**Command**: `lazy course view syllabus <COURSE_ID> --json`

**Schema**:

- status(bool): 若返回 `false`，则发生错误
- description(str): 结果描述，若报错，则返回错误描述
- result(array):
  - course_name(str): 课程名称
  - course_id(int): 课程ID
  - modules(array):
    - index(int): 章节序号（从0开始）
    - id(int): 章节ID
    - name(str): 章节名称
  
**Example**

```json
{
    "status": true, 
    "description": "Syllabus View", 
    "result": {
        "course_name": "广义弹幕力学：非线性轨迹中的概率躲避论", 
        "course_id": 114514, 
        "modules": [
            {
                "index": 0, 
                "id": 2333, 
                "name": "从常识到非想：弹幕力学公理化体系的建立" 
            }
        ]
    }
}
```

---

**Command**: `lazy course view syllabus <COURSE_ID> -m <MODULE_ID> --json`

**Schema**:

- status(bool): 若返回 `false`，则发生错误
- description(str): 结果描述，若报错，则返回错误描述
- result(array):
  - course_name(str): 课程名称
  - course_id(int): 课程ID
  - modules(array):
    - name(str): 章节名称
    - activities(array):
      - title(str): 任务名称
      - type(str): 任务类型
      - id(int): 任务ID
      - completion(str): 完成状态
      - start_time:(str): 开始时间
      - is_started(bool): 是否开始
      - end_time(str): 结束时间
      - is_closed(bool): 是否结束
      - uploads(array):
        - filename(str): 文件名
        - id(int): 文件ID
        - size(str): 文件大小
    - exams(array):
      - title(str): 测试名称
      - type(str): 测试类型
      - id(int): 测试ID
      - completion(str): 完成状态
      - start_time(str): 开始时间
      - is_started(bool): 是否开始
      - end_time(str): 结束时间
      - is_closed(bool): 是否结束
    - classroom(array):
      - title(str): 测课堂测试名称
      - type(str): 课堂测试类型
      - id(int): 课堂测试ID
      - start_time(str): 开始时间
      - status(str): 课堂测试状态
      - completion(bool): 是否完成

**Example**

```json
{
    "status": true, 
    "description": "Syllabus View", 
    "result": {
        "course_name": "广义弹幕力学：非线性轨迹中的概率躲避论", 
        "course_id": 114514, 
        "modules": [
            {
                "name": "从常识到非想：弹幕力学公理化体系的建立" ,
                "activities": [
                  {
                    "title": "概率论与数理统计：弹幕修正版",
                    "type": "资料",
                    "id": 12345,
                    "completion": "No need to complete",
                    "start_time": "null",
                    "is_started": true,
                    "end_time": "null",
                    "is_closed": false,
                    "uploads": [
                      {
                        "filename": "概率论与数理统计：弹幕修正版.pdf",
                        "id": 6666,
                        "size": "8.4 MB"
                      }
                    ]
                  }
                ],
                "exams": [
                  {
                    "title": "课后测试",
                    "type": "测试",
                    "id": 7657,
                    "completion": true,
                    "start_time": "2077-01-01 18:30:00",
                    "is_started": true,
                    "end_time": "2077-01-02 18:30:00",
                    "is_closed": true
                  }
                ],
                "classroom_tests": [
                  {
                    "title": "课堂小测",
                    "type": "课堂任务",
                    "id": 316170,
                    "start_time": "2077-01-01 15:27:35",
                    "status": "In progress",
                    "completion": true
                  }
                ]
            }
        ]
    }
}
```

#### coursewares

**Command**: `lazy course view coursewares <COURSE_ID> --json`

**Schema**:

- status(bool): 若返回 `false`，则发生错误
- description(str): 结果描述，若报错，则返回错误描述
- result(array):
  - id(str): 课件ID
  - name(str): 课件名称
  - size(str): 课件大小
  - update_time(str): 上传时间

**Example**

```json
{
  "status": true, 
  "description": "Coursewares View", 
  "result": [
    {
      "id": "666", 
      "name": "概率论与数理统计：弹幕修正版.pdf", 
      "size": "8.4 MB", 
      "update_time": "2077-01-01 01:00:00"
    }
  ]
}
```

#### rollcalls

**Command**: `lazy course view rollcalls <COURSE_ID> -json`

**Schema**：

- status(bool): 若返回 `false`，则发生错误
- description(str): 结果描述，若报错，则返回错误描述
- result(array):
  - id(str): 签到事件ID
  - time(str): 签到事件发起时间
  - type(str): 签到类型
  - status(str): 签到状态

**Example**

```json
{
  "status": true, 
  "description": "Rollcalls View", 
  "result": [
    {
      "id": "666", 
      "time": "2077-01-01 01:00:00",
      "type": "雷达点名",
      "status": "Signed in"
    }
  ]
}
```