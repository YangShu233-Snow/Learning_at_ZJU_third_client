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

**Command**