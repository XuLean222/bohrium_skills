import typing as t
import os
import time
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import AzureOpenAI
from tqdm import tqdm

# ========== Azure OpenAI 配置（从环境变量读取，请勿提交密钥到代码库）==========
AZURE_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "")
AZURE_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")
DEPLOYMENT_NAME = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

# 统一使用 client 作为 AzureOpenAI 客户端名称，便于在其它函数中直接调用
client = AzureOpenAI(
    api_key=AZURE_API_KEY,
    azure_endpoint=AZURE_ENDPOINT,
    api_version=API_VERSION
)

# ========== 候选意图列表 ==========
# 主意图和隐含意图只能从这个列表中选择
VALID_INTENTS = [
    '文献检索',
    '写作',
    '知识问答',
    '计算推理',
    '辅助写作',
    '方案设计', 
    '学者相关',
    '多模态',
    '出题',
    '日常聊天',
    '陈述类观点',
    '无效提问'
]

# ========== 候选动作列表 ==========
# 动作只能从这个列表中选择，如需补充就自行概括出一个找工具的动词
VALID_ACTIONS = [
    '找文献(search)',
    '读文献(read)',
    '画图(科研绘图)',
    '找学者(scholar)',
    '简单写作(综述/摘要/大纲等)',
    '辅助写作(润色/翻译)',
    '深度调研(深度研究)',
    '长文本写作',
    '论文评价与审稿',
    '方案设计'
]

# ========== 候选限制条件列表 ==========
# 限制条件只能从这个列表中选择，如需补充就自行概括出一个query中的限制条件
VALID_CONSTRAINTS = [
    '时间限制',
    '质量限制',
    '作者限制',
    '期刊限制',
    '数量限制',
    '语言限制',
    '篇幅限制',
    '结构限制',
    '输出格式',
    '期刊类型限制'
]

# ========== 构建四类意图识别 Prompt ==========
def build_system_prompt() -> str:
    """构建 system 消息，包含所有规则和定义"""
    return """
    ## Role ##
    你是一名科研智能体意图识别专家,专门负责识别用户的科研需求。

    ## Task ##
    请从以下四个维度分析用户Query,识别出:
    1. **主意图**(只能有1个)
    2. **隐含意图**(可以有多个,按优先级排序,用逗号分隔)
    3. **动作**(至少要有一个，可以有多个,按优先级排序,用逗号分隔)
    4. **限制条件**(可以有多个,用逗号分隔)

    ## Context ##

    ### 1. 主意图 (只能选择一个)

    主意图是用户最核心、最主要的需求,从以下选项中选择:

    #### 1.1 文献检索
    文献检索是指用户需要查找、获取学术文献和研究资料的需求。包括按主题检索、精准定位特定文献、限定时间或质量的检索等。核心特征是用户明确表达要"找文献"、"搜论文"。

    **核心特征**:
    - 必须包含明确的查找、检索、搜索意图,或者没有明确的关键动词但只包含一个或几个短词,比如"DeepSeek"
    - 关键动词:找、搜索、查找、检索、寻找、获取
    - 检索对象:论文、文献、研究、资料、paper、article
    - 可能包含限定条件:主题、作者、年份、期刊、质量
    - 关键短语示例:
    - "找XX相关的论文"
    - "检索XX的文献"
    - "搜索XX发表的研究"
    - "查找高引用的XX论文"
    - "XX的研究"
    - "DeepSeek"
    - "Transformer"
    - "介绍下DeepSeek"
    - 区别于写作:检索是"找"文献,写作是"写"内容
    - 区别于知识问答:检索要获取文献,问答要获取科学知识

    #### 1.2 写作
    写作是指从零开始创作学术内容的需求,不是基于已有文本的修改。包括写文献综述、研究进展、摘要、大纲、报告等。核心特征是用户要求"生成"、"写"、"创作"新内容。

    **核心特征**:
    - 必须是从0到1的创作需求
    - 关键动词:写、生成、创作、撰写、产出、制作
    - 创作对象:综述、摘要、大纲、报告、论文、引言、方法、研究现状、研究发展、研究展望等
    - 用户通常提供主题和要求,但没有现成文本
    - 关键短语示例:
    - "写一篇XX综述"
    - "生成XX的摘要"
    - "为XX写一个大纲"
    - "帮我写开题报告"
    - 区别于辅助写作:写作是从零创作,辅助写作是修改已有内容
    - 区别于文献检索:写作是创作内容,检索是查找文献

    #### 1.3 知识问答
    知识问答是指用户询问概念、原理、方法、事实等知识性问题,期待获得解释或答案。包括概念定义、原理机制、方法说明、对比分析等。核心特征是疑问句式和求知意图。

    **核心特征**:
    - 必须是疑问句或陈述句中包含明确的询问对象
    - 关键疑问词:什么、为什么、如何、怎么、是否、有哪些、谁、何时
    - 询问对象:概念、原理、方法、机制、事实、应用场景
    - 疑问句通常以"?"结尾或明显的提问语气,陈述句包含明确的询问对象
    - 关键句式示例:
    - "什么是XX?"
    - "XX如何工作?"
    - "为什么XX有效?"
    - "区别一下XX和YY"
    - "阐述一下XX的机制"
    - 区别于方案设计:问答是"是什么|为什么",方案是"怎么做"
    - 区别于文献检索:问答要问科学知识,不包含只包含一个或几个短词的query,比如"DeepSeek";检索要找文献,包含一个或几个短词的query,比如"DeepSeek"

    #### 1.4 计算推理
    计算推理是指需要进行数学计算、公式推导或逻辑推理的需求。包括数值计算、公式推导、逻辑分析等。核心特征是涉及定量分析或推理过程。

    **核心特征**:
    - 必须涉及计算、推导或推理
    - 关键词:计算、推导、证明、求解、分析、推理
    - 包含数学元素:数字、公式、方程、变量、逻辑关系
    - 关键句式示例:
    - "计算XX的值"
    - "推导XX公式"
    - "证明XX"
    - "如果XX,能否推出YY"
    - 区别于知识问答:计算推理产生数值|公式|结论,问答解释概念
    - 答案特征:数值结果、公式表达式、逻辑结论

    #### 1.5 辅助写作
    辅助写作是指对已有文本进行二次加工的需求,不是从零创作。包括润色、翻译、纠错等。核心特征是用户提供了原文,要求修改或转换。

    **核心特征**:
    - 必须基于已有文本进行操作
    - 关键动词:润色、修改、优化、翻译、改写、扩写、纠错、校对
    - 用户通常会提供原始文本
    - 关键句式示例:
    - "帮我润色这段文字:..."
    - "把这段话翻译成英文"
    - "检查这段文字的语法错误"
    - "优化这个段落"
    - 区别于写作:辅助写作有原文,写作无原文
    - 核心判断:是否有"待处理的已有文本"

    #### 1.6 方案设计
    方案设计是指用户需要获得研究方案、实验设计或实施计划。包括研究方案、实验方案、研究做法、可行性分析等。核心特征是询问"怎么做"、"如何设计"。

    **核心特征**:
    - 必须是寻求操作性指导或设计方案
    - 关键词:设计、方案、计划、如何做、怎么实施、步骤、流程
    - 询问重点:研究设计、实验设计、技术路线、实施方法
    - 关键句式示例:
    - "设计一个实验验证XX"
    - "如何设计研究方案"
    - "怎么实现XX"
    - "评估XX的可行性"
    - 区别于知识问答:方案设计要"怎么做"(操作),问答要"是什么"(知识)
    - 核心判断:是否需要可执行的方案或设计

    #### 1.7 学者相关
    学者相关是指用户询问特定学者或研究团队的信息,包括研究方向、学术成果等。核心特征是询问对象是"人"(学者、教授、研究员、团队)。

    **核心特征**:
    - 必须涉及特定学者或研究团队
    - 关键词:教授、研究员、学者、专家、团队、XX老师
    - 通常包含人名或团队名称
    - 关键句式示例:
    - "XX教授的研究方向是什么"
    - "XX学者发表了哪些论文"
    - "XX团队主要研究什么"
    - 区别于学科相关:学者相关问"某人研究什么",学科相关问"某领域研究什么"
    - 核心判断:询问对象是否为具体的人或团队

    #### 1.8 多模态
    多模态是指处理图片、图表或其他视觉内容的需求。包括解读图片(图生文)和生成图片(文生图)。核心特征是涉及视觉内容。

    **核心特征**:
    - 必须涉及图片、图表或视觉内容
    - 关键词:图、图片、图表、图像、可视化、架构图
    - 两种情况:
    1. 有图片上传+要求分析 → 图生文
    2. 要求生成图片 → 文生图
    - 关键句式示例:
    - "解读这张图片"(图生文)
    - "这个图表显示了什么"(图生文)
    - "画一个架构图"(文生图)
    - "生成流程图"(文生图)
    - 优先级最高:有图片输入时优先识别为多模态

    #### 1.9 出题
    出题是指用户要求生成题目,包括测试题、研究方向推荐、研究题目生成等。核心特征是"生成题目"的需求。

    **核心特征**:
    - 必须明确要求生成用于练习/考试/测试的题目
    - 关键词:出题、生成题目、命题、设计题目、题目
    - 三种类型:
    1. 练习|考试题:测试题目
    2. 研究方向:推荐研究方向
    3. 研究题目:论文标题、项目名称
    - 关键句式示例:
    - "出几道XX题"(练习题)
    - "推荐一些研究方向"(研究方向)
    - "生成论文题目"(研究题目)
    - 区别于知识问答:出题是生成题目,问答是回答问题

    #### 1.10 日常聊天
    日常聊天是指非学术性、非任务性的日常交流,包括问候、闲聊、产品咨询等。核心特征是轻松、非正式、无学术任务。

    **核心特征**:
    - 不涉及具体的学术任务或专业知识
    - 判断理由:
    - 问候语:你好、hi、hello
    - 闲聊话题:天气、生活、兴趣爱好
    - 产品咨询:询问Agent功能
    - 轻松、非正式的语气
    - 关键句式示例:
    - "你好"(问候)
    - "你能做什么"(产品咨询)
    - "今天天气不错"(闲聊)
    - 区别于陈述类观点:聊天非学术,陈述类观点涉及学术内容

    #### 1.11 陈述类观点
    陈述类观点是指用户发表学术观点、陈述专业想法,但没有明确任务需求。核心特征是陈述句+学术内容+无任务指令。

    **核心特征**:
    - 必须是陈述句,非疑问句或祈使句
    - 表达学术观点或专业看法
    - 无明显的动作指令(不是"帮我写"、"帮我找")
    - 判断理由:
    - 陈述语气
    - 学术或专业内容
    - 无任务需求
    - 关键句式示例:
    - "现在大模型参数太多了"
    - "深度学习的可解释性很重要"
    - "这个方法似乎有局限性"
    - 区别于聊天:陈述类观点涉及学术|专业内容,聊天是轻松话题
    - 区别于文献检索:陈述类观点是陈述句,不包含一个或几个短词的query,比如"DeepSeek";检索是包含一个或几个短词的query,比如"DeepSeek"
    - 处理方式:识别后应询问用户是否需要转化为具体任务

    #### 1.12 无效提问
    无效提问是指用户查询本身存在问题,导致无法有效执行或理解的需求。这类问题不是科研Agent能力的问题,而是用户提问本身存在缺陷。

    **核心特征**:
    - **语义模糊类**: 查询表达不清晰、含糊不清、存在歧义,无法明确理解用户意图
    - 指代不明: "那个东西"、"帮我看看"、"就是那个"、"你知道的"
    - 缺少关键信息: "帮我找论文"(未说明找什么论文)
    - 表达过于简略: "论文"、"研究"(无法判断具体需求)
    - **缺乏执行前提类**: 查询缺少必要的上下文信息或前置条件,无法执行
    - 未提供修改内容: "帮我修改一下"
    - 未提供结果数据: "分析这个结果"(未提供结果数据或来源)
    - 未指明总结对象: "总结一下"
    - 缺少前文上下文: "继续"、"接着"
    - **无意义/重复类**: 查询本身无实际意义、完全重复或测试性输入
    - 纯符号或乱码: "asdfgh"、"123456"、"？？？"、"???"
    - 完全重复的查询: 连续多次输入相同内容
    - 测试性输入: "test"、"测试"、"hello"
    - 无意义的组合词: "论文论文论文"、"研究研究研究"
    - 区别于其他意图: 无效提问是查询本身的问题,而非科研任务需求,不包含"一个或几个短词/短语的query"(如"DeepSeek",这是文献检索),不包含"给出论文题目与出处"的query(这是文献检索),不包含"给出研究方向"的query (这是文献检索)
    - 处理方式: 识别后应提示用户完善查询,提供更具体的信息

    ### 2. 隐含意图 (可以有多个,按优先级排序)

    隐含意图是用户在主意图之外,可能还包含的其他意图。隐含意图应该从**主意图的候选集合**中选择,但**必须排除已经选为主意图的那个意图**。

    **主意图候选集合**:
    1. **文献检索** - 用户需要查找、获取学术文献和研究资料
    2. **写作** - 从零开始创作学术内容(综述、摘要、大纲、报告等)
    3. **知识问答** - 询问概念、原理、方法、事实等知识性问题
    4. **计算推理** - 需要进行数学计算、公式推导或逻辑推理
    5. **辅助写作** - 对已有文本进行二次加工(润色、翻译、纠错等)
    6. **方案设计** - 需要获得研究方案、实验设计或实施计划
    7. **学者相关** - 询问特定学者或研究团队的信息
    8. **多模态** - 处理图片、图表或其他视觉内容
    9. **出题** - 要求生成题目(测试题、研究方向推荐、研究题目生成等)
    10. **日常聊天** - 非学术性、非任务性的日常交流
    11. **陈述类观点** - 发表学术观点、陈述专业想法,但没有明确任务需求
    12. **无效提问** - 用户查询本身存在问题,导致无法有效执行或理解

    **隐含意图识别规则**:
    - 从上述12个候选意图中,选择除了主意图之外的其他意图
    - **"无效提问"不在隐含意图的候选集合中,隐含意图不能是"无效提问"**
    - 如果query中只包含主意图,没有其他意图,则隐含意图填"无"
    - 可以有多个隐含意图,按优先级排序,用逗号分隔
    - 隐含意图的判断标准与主意图相同,请参考主意图部分的详细说明
    - 隐含意图的判断结果应与主意图的判断结果互斥,即隐含意图不能与主意图相同
    - 如果主意图已经能满足用户需求,则隐含意图填"无"

    **示例**:
    - 主意图:文献检索,隐含意图:写作 (如"找三篇论文,然后写综述")
    - 主意图:知识问答,隐含意图:方案设计 (如"解释Transformer原理,并设计实验验证")
    - 主意图:写作,隐含意图:无 (如"写一篇综述",只有写作需求)


    ### 3. 动作 (至少要有一个，可以有多个,按优先级排序,用逗号分隔开)

    动作是完成用户需求所需的**具体操作步骤/调用的具体 Agent 能力**。需要根据主意图、隐含意图和 query 内容,确定需要哪些动作,并按执行的优先级或逻辑顺序排序。

    **可能的动作(请优先从以下集合中选择,可以有多个)**:
    - **找文献(search)**: 负责检索和筛选文献,对应 **search Agent**
    - 典型信号: "找文献"、"检索论文"、"搜索XX相关研究"、"帮我找几篇..."、给出 DOI/标题/链接、解释...的原理、简单术语解释
    - 相关意图: 知识问答、文献检索、写作、辅助写作、方案设计、学者相关、多模态、出题
    - 作用: 根据主题/条件从文献库中查找合适的文献，用文献回答问题

    - **读文献(read)**: 负责读取、解析和总结具体文献内容,对应 **read Agent**
    - 典型信号: "阅读这篇文献"、"帮我解读/总结这篇论文"、给出 DOI/标题/链接、 抽取出论文里有的内容
    - 作用: 打开单篇或少量文献,做内容理解、摘要或要点提取

    - **画图(科研绘图)**: 负责科研相关的图表/示意图/流程图生成,对应 **科研绘图 Agent**
    - 典型信号: "画图"、"画一个XX结构图"、"生成XX流程图"、"画一张示意图"
    - 作用: 将文字描述转化为科研场景下的可视化图形

    - **找学者(scholar)**: 负责查找学者/团队及其研究信息,对应 **scholar Agent**
    - 典型信号: "找做XX的学者"、"有哪些人在研究XX"、"推荐几个相关团队"
    - 作用: 帮助用户定位合适的学者、团队或合作对象

    - **简单写作(综述/摘要/大纲等)**: 负责相对**短篇幅、结构清晰**的写作任务,对应 **写作 Agent**
    - 典型信号: "写综述"、"写摘要"、"写大纲"、"写一段引言" 等
    - 字数在5000字以内
    - 作用: 基于给定主题或少量素材,生成综述、摘要、大纲、段落级文本等

    - **辅助写作**: 负责基于已有文本进行语言层面的加工,对应 **辅助写作 Agent**
    - 典型信号: "润色这段话"、"翻译成英文/中文"、"优化表达"、"改写这段文字"
    - 区别于找文献(search)：辅助写作不包含标注引用，标注引用属于找文献(search)
    - 作用: 对已有文本进行润色、翻译、表达优化、轻度改写等

    - **深度调研(深度研究) **: 负责**大范围文献检索+深入思考总结**的综合性写作任务,对应 **深度研究 Agent**
    - 典型信号: "做一个深度调研"、"系统梳理XX领域发展脉络"、"写一篇完整的长篇综述/研究报告" 等
    - 需要输出字数在5000字及以上
    - 作用: 结合多篇文献和多轮推理,完成结构复杂、篇幅较长的深度分析和总结性写作

    - **长文本写作**: 负责长文本的写作需求的输出,对应 **论文写作 Agent**
    - 典型信号: "写一篇完整的长篇综述/研究报告"、"写一篇完整的论文" 等
    - 字数在5000字及以上
    - 作用: 结合多篇文献和多轮推理,完成结构复杂、篇幅较长的深度分析和总结性写作
    
    - **论文评价与审稿**: 负责对论文进行评价、审稿或提供修改建议,对应 **论文评价 Agent**
    - 典型信号: "评价这篇论文"、"审稿"、"给这篇论文提建议"、"修改建议" 等
    - 作用: 对已有论文进行质量评估、审稿意见或修改建议

    - **方案设计**: 负责研究方案、实验设计或实施计划的设计,对应 **方案设计 Agent**
    - 典型信号: "设计一个研究方案"、"如何设计实验"、"制定技术路线" 等
    - 作用: 提供研究方案、实验设计或实施计划

    **动作输出要求**:
    - **动作至少要有一个，必须从上述10个动作集合中选择,不能输出其他动作,也不能被主意图、隐含意图、限制条件的内容影响**
    - **动作输出必须严格按照候选集合中的格式，不能增加、删除或改写任何一个字**
    - 例如：必须输出"找文献(search)"，不能输出"找文献"、"找文献(搜索)"、"找文献(search"等
    - 例如：必须输出"简单写作(综述/摘要/大纲等)"，不能输出"简单写作"、"简单写作(综述)"等
    - 例如：必须输出"辅助写作(润色/翻译)"，不能输出"辅助写作"、"辅助写作(润色)"等
    - 如果确实需要的动作不在上述10个动作集合中,请自行概括出一个找工具的动词
    - 考虑用户的潜在目标和动机
    - 一定要是一个动词
    - 至少要有一个,可以有多个,用逗号分隔
    - 动作列中请直接输出上述动作名称(如:"找文献(search),读文献(read),简单写作(综述/摘要/大纲等)"),按实际执行顺序排列
    - **重要提醒**: 动作的判断必须严格基于用户query中表达的具体操作需求,不要被主意图、隐含意图、限制条件的内容影响


    ### 4. 限制条件 (可以有多个)
    限制条件是用户对结果的约束要求。从query中提取所有显式或隐式的限制条件。

    #### 4.1 文献相关限制

    **时间限制**:
    - 定义: 对文献发表时间的约束
    - 特征:
    - 绝对时间:"2023年"、"2020-2023年"、"21世纪"
    - 相对时间:"最新"、"最近"、"近期"、"近年来"
    - 时间范围:"过去5年"、"近三年"、"XX年以来"
    - 时间节点:"XX年之后"、"XX年以前"
    - 示例:"最近三年"、"2023年"、"近期"

    **质量限制**:
    - 定义: 对文献学术质量的约束
    - 特征:
    - 引用相关:"高引"、"高被引"、"引用量"、"citation"
    - 期刊相关:"顶刊"、"顶会"、"权威期刊"、"核心期刊"、"Q1区"
    - 影响力:"经典"、"里程碑"、"开创性"、"奠基性"
    - 具体期刊:"Nature"、"Science"、"Cell"、顶会名称
    - 影响因子:"IF"、"影响因子"、"高分"
    - 示例:"高引用的"、"顶刊发表的"、"经典论文"

    **作者限制**:
    - 定义: 限定特定作者的文献
    - 特征:
    - 包含作者姓名(中文或英文)
    - 包含"XX写的"、"XX教授的"
    - 包含"XX et al."
    - 年份+作者组合
    - 示例:"张三教授的"、"某某作者"、"XX团队"

    **期刊限制**:
    - 定义: 限定特定期刊或会议
    - 特征:
    - 明确提到期刊名称
    - 明确提到会议名称
    - 如"Nature"、"Science"、"CVPR"、"NeurIPS"
    - 示例:"Nature上的"、"发表在Science"、"CVPR论文"

    **数量限制**:
    - 定义: 限定文献数量
    - 特征:
    - 明确的数字:"三篇"、"5篇"、"10篇"
    - 模糊的数量:"若干篇"、"一些"、"几篇"
    - 示例:"三篇"、"5篇"、"若干篇"

    #### 4.2 内容相关限制

    **语言限制**:
    - 定义: 限定语种，如英语、法语、印尼语、韩语等多种国家的语言
    - 特征:
    - 明确提到"中文"、"英文"、"日文"等
    - 或要求"翻译成XX语"
    - 示例:"中文"、"英文"、"翻译成中文"

    **篇幅限制**:
    - 定义: 对输出长度的约束
    - 特征:
    - 明确字数:"500字"、"1000字以内"
    - 模糊长度:"简短"、"详细"、"简要"、"详尽"
    - 示例:"500字"、"简短"、"详细"

    #### 4.3 格式相关限制

    **结构限制**:
    - 定义: 对输出结构的约束
    - 特征:
    - "分三部分"、"包含背景和方法"
    - "分为引言、方法、结果、讨论"
    - 要求特定章节或部分
    - 示例:"分三部分"、"包含背景和方法"

    **输出格式**:
    - 定义: 对输出形式的约束
    - 特征:
    - "表格形式"、"列表"、"段落"
    - "Markdown格式"、"纯文本"
    - "带编号"、"分点列出"
    - 示例:"表格形式"、"列表"、"段落"

    **判断原则**:
    - **限制条件必须从上述限制条件集合中选择,不能输出其他限制条件,也不能被主意图、隐含意图、动作的内容影响**
    - 如果query中确实存在限制条件但不在上述集合中,请自行概括出一个query中的限制条件(如"数据类型限制"、"精度限制"等)
    - 从query中提取所有显式或隐式的限制条件
    - 可以为空(填"无")
    - 可以有多个,用逗号分隔
    - **重要提醒**: 限制条件的判断必须严格基于用户query中表达的具体约束要求,不要被主意图、隐含意图、动作的内容影响

    ## 【输出时必须逐字照抄的候选值】##
    以下为系统唯一接受的取值，识别结果栏必须从下列列表中**逐字照抄**，不得自创、不得改写、不得省略或增加括号与标点。
    **主意图/隐含意图**（只能从下面12个中选，主意图选1个，隐含意图可多选或填"无"）：
    文献检索、写作、知识问答、计算推理、辅助写作、方案设计、学者相关、多模态、出题、日常聊天、陈述类观点、无效提问
    **动作**（至少选1个，只能从下面10个中选，可多选，逐字照抄包括英文括号）：
    找文献(search)、读文献(read)、画图(科研绘图)、找学者(scholar)、简单写作(综述/摘要/大纲等)、辅助写作(润色/翻译)、深度调研(深度研究)、长文本写作、论文评价与审稿、方案设计
    **限制条件**（可多选或填"无"）：时间限制、质量限制、作者限制、期刊限制、数量限制、语言限制、篇幅限制、结构限制、输出格式、期刊类型限制

    ## Output Format ##
    请严格以「四行表格」形式输出识别结果,不得输出任何额外解释性文字。
    表格要求:

    - 共四行数据(不含表头)
    - 固定四列:维度名称、识别结果、置信度、判断理由
    - 不得新增、删除或调整列

    表格列定义如下:
    | 维度名称 | 识别结果 | 置信度 | 判断理由 |

    字段说明:

    - 维度名称: 固定为"主意图"、"隐含意图"、"动作"、"限制条件"
    - 识别结果:
    - 主意图:只能有1个
    - 隐含意图:可以有多个,用逗号分隔,无则填"无"
    - 动作:至少要有一个，可以有多个,按优先级排序,用逗号分隔
    - 限制条件:可以有多个,用逗号分隔,无则填"无"

    - 置信度: 必须是0.0-1.0之间的数值(一位小数),不能是文字
    - 高置信度(0.8-1.0):关键词明确,边界清晰,无歧义
    - 中置信度(0.4-0.8):部分关键词模糊,可能有多种解释
    - 低置信度(0.0-0.4):表达不清,需要进一步确认用户意图

    - 判断理由: 用分号(;)列出1-3个用于判断的关键信号

    示例输出格式(仅示意):
    | 维度名称 | 识别结果 | 置信度 | 判断理由 |
    | 主意图 | 文献检索 | 0.9 | 包含"找文献";检索对象为论文;限定研究主题 |
    | 隐含意图 | 写作 | 0.7 | 后续要写综述暗示需系统整理;用户可能需要深入理解该领域 |
    | 动作 | 找文献,简单写作(综述/摘要/大纲等) | 0.9 | 先找文献;再写综述;有明确连接词"然后" |
    | 限制条件 | 时间限制,数量限制 | 0.8 | 明确要求"最近三年";指定"三篇" |

    ## Execution Rule ##

    - 必须输出四行数据,分别对应四个维度
    - **识别结果栏只能填写上文【输出时必须逐字照抄的候选值】中的内容，不得自创、不得改写、不得输出"未识别"或"ERROR"。**
    - 主意图只能有1个
    - **主意图和隐含意图只能从以下12个候选意图中选择,不能输出其他意图**:
    1. 文献检索
    2. 写作
    3. 知识问答
    4. 计算推理
    5. 辅助写作
    6. 方案设计
    7. 学者相关
    8. 多模态
    9. 出题
    10. 日常聊天
    11. 陈述类观点
    12. 无效提问
    - **重要限制**: "无效提问"不在隐含意图的候选集合中,隐含意图不能是"无效提问"
    - **重要提醒**: 主意图和隐含意图的判断必须严格基于用户query的核心需求,不要被"动作"或"限制条件"的内容影响。例如:
    - 如果用户query是"深度研究XX",主意图应该是"写作",而不是"深度研究"(这是动作,不是主意图)
    - 如果用户query是"高引用的论文",主意图应该是"文献检索",而不是"高引用"(这是限制条件,不是主意图)
    - **动作必须从以下10个动作集合中选择,不能输出其他动作,也不能被主意图、隐含意图、限制条件的内容影响**:
    1. 找文献(search)
    2. 读文献(read)
    3. 画图(科研绘图)
    4. 找学者(scholar)
    5. 简单写作(综述/摘要/大纲等)
    6. 辅助写作(润色/翻译)
    7. 深度调研(深度研究)
    8. 长文本写作
    9. 论文评价与审稿
    10. 方案设计
    - **动作输出必须严格按照上述格式，不能增加、删除或改写任何一个字**
    - 如果确实需要的动作不在上述10个动作集合中,请自行概括出一个找工具的动词
    - **限制条件必须从以下限制条件集合中选择,不能输出其他限制条件,也不能被主意图、隐含意图、动作的内容影响**:
    1. 时间限制
    2. 质量限制
    3. 作者限制
    4. 期刊限制
    5. 数量限制
    6. 语言限制
    7. 篇幅限制
    8. 输出格式
    9. 期刊类型限制
    - 如果query中确实存在限制条件但不在上述集合中,请自行概括出一个query中的限制条件
    - 隐含意图、动作、限制条件可以有多个,用逗号分隔
    - 动作需要按优先级或逻辑顺序排序
    - 如果某个维度无结果,填"无"
    - 置信度必须是0.0-1.0之间的一位小数
    - 不要输出任何表格之外的文字

    ### Priority Rule ##

    **主意图优先级规则**:
    - 如果识别出主意图是无效提问，再判断是不是文献检索，如一个或几个短词、论文标题和出处、研究方向等，如果是，则归为文献检索，否则归为无效提问
    - **如果识别出主意图是"无效提问",则不需要进行后续的隐含意图、动作和限制条件的判断，隐含意图、动作和限制条件应填"无"**
    - **除去"无效提问"的主意图之外,其他主意图必须至少识别出一个动作**
    """


def build_user_prompt(query: str) -> str:
    """构建 user 消息，只包含用户 query"""
    return f"""
## Input ##
用户Query:{query}
"""


def find_best_match_intent(invalid_intent: str, query: str = '') -> str:
    """
    当识别出的意图不在候选列表中时，从12个候选意图中选择最接近的一个
    Args:
        invalid_intent: 不在候选列表中的意图（可为空或 None，此时仅根据 query 匹配）
        query: 用户查询（可选，用于更精确的匹配）
    Returns:
        最接近的候选意图
    """
    if invalid_intent is None:
        invalid_intent = ''
    invalid_intent = (invalid_intent or '').strip()
    invalid_intent_lower = invalid_intent.lower()
    
    # 关键词映射：将常见错误意图映射到正确的候选意图
    keyword_mapping = {
        # 深度研究/深度调研 -> 写作（因为深度研究通常是写作任务）
        '深度研究': '写作',
        '深度调研': '写作',
        '研究': '写作',
        # 其他可能的映射可以根据实际情况添加
    }
    
    # 先检查关键词映射
    for key, value in keyword_mapping.items():
        if key in invalid_intent:
            return value
    
    # 如果没有匹配，根据query内容智能选择
    if query:
        query_lower = query.lower()
        # 检查query中的关键词来判断最可能的意图
        if any(word in query_lower for word in ['找', '搜索', '检索', '查找', '论文', '文献']):
            return '文献检索'
        elif any(word in query_lower for word in ['写', '生成', '创作', '撰写', '综述', '摘要', '大纲']):
            return '写作'
        elif any(word in query_lower for word in ['什么', '为什么', '如何', '怎么', '是什么', '？', '?']):
            return '知识问答'
        elif any(word in query_lower for word in ['计算', '推导', '证明', '求解']):
            return '计算推理'
        elif any(word in query_lower for word in ['润色', '翻译', '修改', '优化']):
            return '辅助写作'
        elif any(word in query_lower for word in ['设计', '方案', '计划', '如何做']):
            return '方案设计'
        elif any(word in query_lower for word in ['教授', '学者', '研究员', '团队']):
            return '学者相关'
        elif any(word in query_lower for word in ['图', '图片', '图表', '图像']):
            return '多模态'
        elif any(word in query_lower for word in ['出题', '题目', '命题']):
            return '出题'
    
    # 默认返回"知识问答"（最通用的意图）
    return '知识问答'


def normalize_intent_to_valid(intent: str) -> str:
    """
    将模型输出的意图规范化为候选列表中的精确值（优先信任模型识别结果，只做格式/同义修正）。
    仅当模型输出与候选明显同义或为常见笔误时做映射，避免直接落入基于 query 的智能匹配。
    """
    if not intent or not intent.strip():
        return intent
    intent = intent.strip()
    if intent in VALID_INTENTS:
        return intent
    # 同义/常见笔误映射（优先采用模型给出的意图类别，只做字符串修正）
    intent_mapping = {
        '文献搜索': '文献检索',
        '文献查找': '文献检索',
        '检索': '文献检索',
        '深度研究': '写作',
        '深度调研': '写作',
        '日常对话': '日常聊天',
        '闲聊': '日常聊天',
        '观点陈述': '陈述类观点',
        '陈述观点': '陈述类观点',
        '无效问题': '无效提问',
        '无法识别': '无效提问',
    }
    if intent in intent_mapping:
        return intent_mapping[intent]
    # 包含关系：模型可能多打了字或带了前后缀
    for v in VALID_INTENTS:
        if v in intent or intent in v:
            return v
    return intent


def validate_and_fix_intent(intent: str, query: str = '') -> tuple[str, bool]:
    """
    验证意图是否在候选列表中
    Args:
        intent: 待验证的意图
        query: 用户查询（用于智能匹配）
    Returns:
        (验证后的意图, 是否在候选列表中)
    """
    if not intent or intent.strip() == '':
        return (find_best_match_intent('', query), False)
    
    # 去除首尾空格
    intent = intent.strip()
    
    # 特殊值：ERROR和"未识别"需要重新识别
    if intent in ['ERROR', '未识别']:
        return (find_best_match_intent(intent, query), False)
    
    # '无'保持不变
    if intent == '无':
        return (intent, True)
    
    # 检查是否在候选列表中
    if intent in VALID_INTENTS:
        return (intent, True)
    
    # 先尝试规范化（同义/笔误/包含关系），优先信任模型识别结果
    normalized = normalize_intent_to_valid(intent)
    if normalized in VALID_INTENTS:
        return (normalized, True)
    
    # 仅当无法规范化到候选时，才用 query 做智能匹配
    matched_intent = find_best_match_intent(intent, query)
    return (matched_intent, False)


def find_best_match_action(invalid_action: str, query: str = '') -> str:
    """
    当识别出的动作不在候选列表中时，从10个候选动作中选择最接近的一个，或概括出一个找工具的动词
    Args:
        invalid_action: 不在候选列表中的动作（可为空或 None，此时仅根据 query 匹配）
        query: 用户查询（可选，用于更精确的匹配）
    Returns:
        最接近的候选动作或概括的找工具动词
    """
    if invalid_action is None:
        invalid_action = ''
    invalid_action = (invalid_action or '').strip()
    invalid_action_lower = invalid_action.lower()
    
    # 关键词映射：将常见错误动作映射到正确的候选动作
    keyword_mapping = {
        # 搜索/查找相关 -> 找文献
        '搜索': '找文献(search)',
        '查找': '找文献(search)',
        '检索': '找文献(search)',
        '找': '找文献(search)',
        # 阅读/解析相关 -> 读文献
        '阅读': '读文献(read)',
        '解析': '读文献(read)',
        '总结': '读文献(read)',
        '解读': '读文献(read)',
        # 绘图相关 -> 画图
        '绘图': '画图(科研绘图)',
        '生成图': '画图(科研绘图)',
        '制作图': '画图(科研绘图)',
        # 学者相关 -> 找学者
        '找学者': '找学者(scholar)',
        '查找学者': '找学者(scholar)',
        # 写作相关 -> 简单写作或长文本写作
        '写': '简单写作(综述/摘要/大纲等)',
        '写作': '简单写作(综述/摘要/大纲等)',
        # 辅助写作相关 -> 辅助写作
        '润色': '辅助写作(润色/翻译)',
        '翻译': '辅助写作(润色/翻译)',
        # 评价相关 -> 论文评价与审稿
        '评价': '论文评价与审稿',
        '审稿': '论文评价与审稿',
        # 设计相关 -> 方案设计
        '设计': '方案设计',
        '方案': '方案设计',
        '实验方法': '方案设计',
        '实验设计': '方案设计',
        '实验方案': '方案设计',
        '实验计划': '方案设计',
        '实验流程': '方案设计',
        '实验步骤': '方案设计',
        '实验步骤': '方案设计',
    }
    
    # 先检查关键词映射
    for key, value in keyword_mapping.items():
        if key in invalid_action:
            return value
    
    # 如果没有匹配，根据query内容智能选择或概括
    if query:
        query_lower = query.lower()
        # 检查query中的关键词来判断最可能的动作
        if any(word in query_lower for word in ['找', '搜索', '检索', '查找', '论文', '文献']):
            return '找文献(search)'
        elif any(word in query_lower for word in ['阅读', '解读', '总结', '解析']):
            return '读文献(read)'
        elif any(word in query_lower for word in ['画', '图', '绘图', '图表']):
            return '画图(科研绘图)'
        elif any(word in query_lower for word in ['写', '生成', '创作', '撰写', '综述', '摘要']):
            if any(word in query_lower for word in ['长篇', '完整', '长文本']):
                return '长文本写作'
            else:
                return '简单写作(综述/摘要/大纲等)'
        elif any(word in query_lower for word in ['润色', '翻译', '修改', '优化']):
            return '辅助写作(润色/翻译)'
        elif any(word in query_lower for word in ['评价', '审稿', '建议']):
            return '论文评价与审稿'
        elif any(word in query_lower for word in ['设计', '方案', '计划']):
            return '方案设计'
        elif any(word in query_lower for word in ['学者', '教授', '研究员', '团队']):
            return '找学者(scholar)'
    
    # 如果无法匹配，概括为一个找工具的动词
    return '找文献(search)'


def normalize_action_to_valid_format(action: str) -> str:
    """
    将动作规范化为候选集合中的完整格式（优先信任模型输出，只做格式/标点修正）。
    如果动作部分匹配候选集合中的某个动作，返回候选集合中的完整格式。
    Args:
        action: 待规范化的动作
    Returns:
        候选集合中的完整动作格式，如果无法匹配则返回原动作
    """
    if not action or not action.strip():
        return action
    # 统一全角括号、多余空格，便于与候选精确匹配
    action = action.strip().replace('（', '(').replace('）', ')')
    action = ' '.join(action.split())

    # 精确匹配
    if action in VALID_ACTIONS:
        return action

    # 去掉括号内外的多余空格后再匹配（如 "找文献 (search)"、"找文献（search）" -> "找文献(search)"）
    action_no_spaces = action.replace(' ', '')
    for va in VALID_ACTIONS:
        if va.replace(' ', '') == action_no_spaces:
            return va

    # 部分匹配映射表：将常见的不完整格式映射到完整的候选格式
    partial_match_mapping = {
        # 找文献相关
        '找文献': '找文献(search)',
        '找文献(search': '找文献(search)',
        '找文献(搜索)': '找文献(search)',
        '找文献(检索)': '找文献(search)',
        'search': '找文献(search)',
        '搜索': '找文献(search)',
        '查找': '找文献(search)',
        '检索': '找文献(search)',
        # 读文献相关
        '读文献': '读文献(read)',
        '读文献(read': '读文献(read)',
        'read': '读文献(read)',
        '阅读': '读文献(read)',
        '解读': '读文献(read)',
        '解析': '读文献(read)',
        '总结': '读文献(read)',
        # 画图相关
        '画图': '画图(科研绘图)',
        '画图(科研绘图': '画图(科研绘图)',
        '画图(绘图)': '画图(科研绘图)',
        '绘图': '画图(科研绘图)',
        '生成图': '画图(科研绘图)',
        '制作图': '画图(科研绘图)',
        # 找学者相关
        '找学者': '找学者(scholar)',
        '找学者(scholar': '找学者(scholar)',
        'scholar': '找学者(scholar)',
        '查找学者': '找学者(scholar)',
        # 简单写作相关
        '简单写作': '简单写作(综述/摘要/大纲等)',
        '简单写作(综述': '简单写作(综述/摘要/大纲等)',
        '简单写作(摘要': '简单写作(综述/摘要/大纲等)',
        '写作': '简单写作(综述/摘要/大纲等)',
        '写': '简单写作(综述/摘要/大纲等)',
        # 辅助写作相关
        '辅助写作': '辅助写作(润色/翻译)',
        '辅助写作(润色': '辅助写作(润色/翻译)',
        '辅助写作(翻译': '辅助写作(润色/翻译)',
        '润色': '辅助写作(润色/翻译)',
        '翻译': '辅助写作(润色/翻译)',
        # 深度调研相关
        '深度调研': '深度调研(深度研究)',
        '深度调研(深度研究': '深度调研(深度研究)',
        '深度研究': '深度调研(深度研究)',
        '深度调研(研究)': '深度调研(深度研究)',
        # 长文本写作
        '长文本写作': '长文本写作',
        '长文本': '长文本写作',
        '长篇写作': '长文本写作',
        # 论文评价相关
        '论文评价与审稿': '论文评价与审稿',
        '论文评价': '论文评价与审稿',
        '评价': '论文评价与审稿',
        '审稿': '论文评价与审稿',
        # 方案设计
        '方案设计': '方案设计',
        '设计': '方案设计',
        '方案': '方案设计',
    }
    
    # 检查部分匹配映射
    for key, value in partial_match_mapping.items():
        if key in action or action in key:
            return value

    # 包含关系：模型可能多打/少打字（如 "找文献(search）" 或 "简单写作(综述/摘要/大纲等）"）
    for va in VALID_ACTIONS:
        if action in va or va in action:
            return va

    # 如果无法匹配，返回原动作（后续会通过智能匹配处理）
    return action


def validate_and_fix_action(action: str, query: str = '') -> tuple[str, bool]:
    """
    验证动作是否在候选列表中，确保输出严格匹配候选集合中的格式
    Args:
        action: 待验证的动作
        query: 用户查询（用于智能匹配）
    Returns:
        (验证后的动作（候选集合中的完整格式）, 是否在候选列表中)
    """
    if not action or action.strip() == '':
        return (find_best_match_action('', query), False)
    
    # 去除首尾空格
    action = action.strip()
    
    # '无'保持不变
    if action == '无':
        return (action, True)
    
    # 先尝试规范化动作格式
    normalized_action = normalize_action_to_valid_format(action)
    
    # 检查规范化后的动作是否在候选列表中（精确匹配）
    if normalized_action in VALID_ACTIONS:
        return (normalized_action, True)
    
    # 如果不在候选列表中，使用智能匹配（智能匹配会返回候选集合中的完整格式）
    matched_action = find_best_match_action(action, query)
    return (matched_action, False)


def validate_and_fix_actions(actions_str: str, query: str = '') -> str:
    """
    验证动作是否都在候选列表中，过滤掉不在候选列表中的动作，并使用智能匹配
    确保至少有一个动作（如果为空或"无"，则根据query智能匹配一个动作）
    Args:
        actions_str: 逗号分隔的动作字符串
        query: 用户查询（用于智能匹配）
    Returns:
        验证后的动作字符串（只包含在候选列表中的动作，用逗号分隔，至少有一个）
    """
    # 分割动作
    if not actions_str or actions_str.strip() == '' or actions_str == '无':
        actions = []
    else:
        actions = [item.strip() for item in actions_str.split(',') if item.strip()]
    
    # 验证每个动作
    valid_actions = []
    for action in actions:
        validated_action, is_valid = validate_and_fix_action(action, query)
        # 只保留有效的动作（排除'无'）
        if validated_action != '无':
            valid_actions.append(validated_action)
    
    # 如果没有有效的动作，根据query智能匹配一个动作（确保至少有一个）
    if not valid_actions:
        matched_action = find_best_match_action('', query)
        valid_actions.append(matched_action)
    
    # 去重并返回验证后的动作，用逗号分隔
    unique_actions = []
    for action in valid_actions:
        if action not in unique_actions:
            unique_actions.append(action)
    
    return ', '.join(unique_actions)


def find_best_match_constraint(invalid_constraint: str, query: str = '') -> str:
    """
    当识别出的限制条件不在候选列表中时，从限制条件集合中选择最接近的一个，或概括出一个限制条件
    Args:
        invalid_constraint: 不在候选列表中的限制条件
        query: 用户查询（可选，用于更精确的匹配）
    Returns:
        最接近的候选限制条件或概括的限制条件
    """
    invalid_constraint_lower = invalid_constraint.lower()
    
    # 关键词映射：将常见错误限制条件映射到正确的候选限制条件
    keyword_mapping = {
        # 时间相关 -> 时间限制
        '时间': '时间限制',
        '年份': '时间限制',
        '最新': '时间限制',
        '最近': '时间限制',
        '近期': '时间限制',
        # 质量相关 -> 质量限制
        '质量': '质量限制',
        '高引': '质量限制',
        '顶刊': '质量限制',
        '经典': '质量限制',
        # 作者相关 -> 作者限制
        '作者': '作者限制',
        '教授': '作者限制',
        # 期刊相关 -> 期刊限制
        '期刊': '期刊限制',
        '会议': '期刊限制',
        # 数量相关 -> 数量限制
        '数量': '数量限制',
        '几篇': '数量限制',
        '篇': '数量限制',
        # 语言相关 -> 语言限制
        '阿拉伯文': '语言限制',
        '中文': '语言限制',
        '英文': '语言限制',
        # 篇幅相关 -> 篇幅限制
        '篇幅': '篇幅限制',
        '字数': '篇幅限制',
        '长度': '篇幅限制',
        # 结构相关 -> 结构限制
        '结构': '结构限制',
        # 格式相关 -> 输出格式
        '格式': '输出格式',
        '表格': '输出格式',
        # 期刊范围相关 -> 期刊类型限制
        '国内': '期刊类型限制',
        '国际': '期刊类型限制',
        '国外': '期刊类型限制',
        '仅国外': '期刊类型限制',
        '仅国内': '期刊类型限制',
        '国内国外': '期刊类型限制',
        '国外国内': '期刊类型限制',
        '国内外': '期刊类型限制',
    }
    
    # 先检查关键词映射
    for key, value in keyword_mapping.items():
        if key in invalid_constraint:
            return value
    
    # 如果没有匹配，根据query内容智能选择或概括
    if query:
        query_lower = query.lower()
        # 检查query中的关键词来判断最可能的限制条件
        if any(word in query_lower for word in ['时间', '年份', '最新', '最近', '近期']):
            return '时间限制'
        elif any(word in query_lower for word in ['质量', '高引', '顶刊', '经典']):
            return '质量限制'
        elif any(word in query_lower for word in ['作者', '教授', '写的']):
            return '作者限制'
        elif any(word in query_lower for word in ['期刊', '会议', 'Nature', 'Science']):
            return '期刊限制'
        elif any(word in query_lower for word in ['数量', '几篇', '篇']):
            return '数量限制'
        elif any(word in query_lower for word in ['阿拉伯文', '中文', '英文', '法文', '印尼文', '韩文']):
            return '语言限制'
        elif any(word in query_lower for word in ['篇幅', '字数', '长度', '简短', '详细']):
            return '篇幅限制'
        elif any(word in query_lower for word in ['结构', '部分', '章节']):
            return '结构限制'
        elif any(word in query_lower for word in ['格式', '表格', '列表']):
            return '输出格式'
        elif any(word in query_lower for word in ['国内', '国际', '国外', '仅国外', '仅国内', '国内外']):
            return '期刊类型限制'
    
    # 如果无法匹配，概括为一个限制条件
    return '其他限制'


def validate_and_fix_constraint(constraint: str, query: str = '') -> tuple[str, bool]:
    """
    验证限制条件是否在候选列表中
    Args:
        constraint: 待验证的限制条件
        query: 用户查询（用于智能匹配）
    Returns:
        (验证后的限制条件, 是否在候选列表中)
    """
    if not constraint or constraint.strip() == '':
        return (constraint, False)
    
    # 去除首尾空格
    constraint = constraint.strip()
    
    # '无'保持不变
    if constraint == '无':
        return (constraint, True)
    
    # 检查是否在候选列表中（精确匹配或部分匹配）
    for valid_constraint in VALID_CONSTRAINTS:
        if constraint == valid_constraint or constraint in valid_constraint or valid_constraint in constraint:
            return (valid_constraint, True)
    
    # 如果不在候选列表中，使用智能匹配
    matched_constraint = find_best_match_constraint(constraint, query)
    return (matched_constraint, False)


def validate_and_fix_constraints(constraints_str: str, query: str = '') -> str:
    """
    验证限制条件是否都在候选列表中，过滤掉不在候选列表中的限制条件，并使用智能匹配
    Args:
        constraints_str: 逗号分隔的限制条件字符串
        query: 用户查询（用于智能匹配）
    Returns:
        验证后的限制条件字符串（只包含在候选列表中的限制条件，用逗号分隔）
    """
    if not constraints_str or constraints_str.strip() == '' or constraints_str == '无':
        return constraints_str
    
    # 分割限制条件
    constraints = [item.strip() for item in constraints_str.split(',') if item.strip()]
    
    # 验证每个限制条件
    valid_constraints = []
    for constraint in constraints:
        validated_constraint, is_valid = validate_and_fix_constraint(constraint, query)
        # 只保留有效的限制条件（排除'无'）
        if validated_constraint != '无':
            valid_constraints.append(validated_constraint)
    
    # 如果没有有效的限制条件，返回"无"
    if not valid_constraints:
        return '无'
    
    # 去重并返回验证后的限制条件，用逗号分隔
    unique_constraints = []
    for constraint in valid_constraints:
        if constraint not in unique_constraints:
            unique_constraints.append(constraint)
    
    return ', '.join(unique_constraints)


def validate_and_fix_implied_intents(implied_intents_str: str, query: str = '') -> str:
    """
    验证隐含意图是否都在候选列表中，过滤掉不在候选列表中的意图，并使用智能匹配
    注意："无效提问"不在隐含意图的候选集合中，会被过滤掉
    Args:
        implied_intents_str: 逗号分隔的隐含意图字符串
        query: 用户查询（用于智能匹配）
    Returns:
        验证后的隐含意图字符串（只包含在候选列表中的意图，用逗号分隔，不包含"无效提问"）
    """
    if not implied_intents_str or implied_intents_str.strip() == '' or implied_intents_str == '无':
        return implied_intents_str
    
    # 分割隐含意图
    intents = [item.strip() for item in implied_intents_str.split(',') if item.strip()]
    
    # 验证每个意图
    valid_intents = []
    for intent in intents:
        validated_intent, is_valid = validate_and_fix_intent(intent, query)
        # 只保留有效的意图（排除'无'和'无效提问'）
        if validated_intent != '无' and validated_intent != '无效提问':
            valid_intents.append(validated_intent)
    
    # 如果没有有效的隐含意图，返回"无"
    if not valid_intents:
        return '无'
    
    # 去重并返回验证后的意图，用逗号分隔
    unique_intents = []
    for intent in valid_intents:
        if intent not in unique_intents:
            unique_intents.append(intent)
    
    return ', '.join(unique_intents)


def analyze_four_category_intent(query: str, retry_on_error: bool = True):
    """
    分析用户query的四类意图
    Args:
        query: 用户查询
        retry_on_error: 如果主意图是ERROR或不在候选列表中，是否重新识别一次（默认True）
    Returns:
        dict: {
            '主意图': {'result': str, 'confidence': str, 'reason': str},
            '隐含意图': {'result': str, 'confidence': str, 'reason': str},
            '动作': {'result': str, 'confidence': str, 'reason': str},
            '限制条件': {'result': str, 'confidence': str, 'reason': str}
        }
    """
    # API调用异常（网络错误、限流等）应该抛出，以便重试机制处理
    # 解析错误应该返回错误结果，不需要重试
    max_attempts = 3 if retry_on_error else 1  # 最多尝试3次：初始1次 + 重试2次
    
    for attempt in range(max_attempts):
        try:
            response = client.chat.completions.create(
                model=DEPLOYMENT_NAME,
                messages=[
                    {"role": "system", "content": build_system_prompt()},
                    {"role": "user", "content": build_user_prompt(query)}
                ],
                temperature=0,
                max_completion_tokens=3000
            )

            content = response.choices[0].message.content.strip()
            result = parse_four_category_output(content)
            
            # ========== 以下代码注释掉，就只保留限制条件的识别和输出 ==========
            # 验证主意图是否在候选列表中
            main_intent = result.get('主意图', {}).get('result', '')
            validated_main_intent, is_valid = validate_and_fix_intent(main_intent, query)
            
            # 如果主意图不在候选列表中或者是ERROR，且允许重试，则重新识别一次
            if not is_valid and retry_on_error and attempt < max_attempts - 1:
                if main_intent == 'ERROR':
                    print(f"警告: query='{query[:50]}...' 主意图为ERROR，重新识别中（第{attempt + 2}次尝试）...")
                else:
                    print(f"警告: query='{query[:50]}...' 主意图'{main_intent}'不在候选列表中，重新识别中（第{attempt + 2}次尝试）...")
                time.sleep(0.5)  # 短暂延迟后重试
                continue
            
            # 更新主意图（如果不在候选列表中，使用智能匹配的结果）
            if not is_valid:
                original_intent = main_intent
                result['主意图']['result'] = validated_main_intent
                if original_intent != validated_main_intent:
                    result['主意图']['reason'] = f'主意图"{original_intent}"不在候选列表中，已智能匹配为"{validated_main_intent}"'
                    print(f"警告: query='{query[:50]}...' 主意图'{original_intent}'不在候选列表中，已智能匹配为'{validated_main_intent}'")
            else:
                result['主意图']['result'] = validated_main_intent
            
            # 优先级规则：如果主意图是"无效提问"，则不需要进行后续的隐含意图、动作和限制条件的判断
            if validated_main_intent == '无效提问':
                result['隐含意图']['result'] = '无'
                result['隐含意图']['reason'] = '主意图为无效提问，跳过隐含意图判断'
                result['动作']['result'] = '无'
                result['动作']['reason'] = '主意图为无效提问，跳过动作判断'
                result['限制条件']['result'] = '无'
                result['限制条件']['reason'] = '主意图为无效提问，跳过限制条件判断'
                return result
            
            # 验证隐含意图是否都在候选列表中（"无效提问"不在隐含意图的候选集合中）
            implied_intents_str = result.get('隐含意图', {}).get('result', '')
            validated_implied_intents = validate_and_fix_implied_intents(implied_intents_str, query)
            
            # 如果隐含意图被修正，更新结果
            if validated_implied_intents != implied_intents_str:
                original_implied_intents = implied_intents_str
                result['隐含意图']['result'] = validated_implied_intents
                # 检查是否是因为"无效提问"被过滤
                if '无效提问' in original_implied_intents:
                    result['隐含意图']['reason'] = f'"无效提问"不在隐含意图的候选集合中，已过滤'
                    print(f"警告: query='{query[:50]}...' 隐含意图包含'无效提问'，已过滤: {original_implied_intents} -> {validated_implied_intents}")
                elif validated_implied_intents != '无' and validated_implied_intents != implied_intents_str:
                    result['隐含意图']['reason'] = f'部分隐含意图不在候选列表中，已过滤修正'
                    print(f"警告: query='{query[:50]}...' 隐含意图已被过滤修正: {original_implied_intents} -> {validated_implied_intents}")
            
            # 验证动作是否都在候选列表中，确保至少有一个动作
            actions_str = result.get('动作', {}).get('result', '')
            validated_actions = validate_and_fix_actions(actions_str, query)
            
            # 如果动作被修正或为空，更新结果
            if validated_actions != actions_str:
                original_actions = actions_str
                result['动作']['result'] = validated_actions
                # 如果原来为空或"无"，说明是智能匹配添加的动作
                if not original_actions or original_actions.strip() == '' or original_actions == '无':
                    result['动作']['reason'] = f'动作为空，已根据query智能匹配为"{validated_actions}"'
                    print(f"警告: query='{query[:50]}...' 动作为空，已智能匹配为'{validated_actions}'")
                else:
                    result['动作']['reason'] = f'部分动作不在候选列表中，已过滤修正'
                    print(f"警告: query='{query[:50]}...' 动作已被过滤修正: {original_actions} -> {validated_actions}")
            else:
                # 确保动作不为空（即使没有修正，也要检查）
                if not validated_actions or validated_actions.strip() == '' or validated_actions == '无':
                    matched_action = find_best_match_action('', query)
                    result['动作']['result'] = matched_action
                    result['动作']['reason'] = f'动作为空，已根据query智能匹配为"{matched_action}"'
                    print(f"警告: query='{query[:50]}...' 动作为空，已智能匹配为'{matched_action}'")
            # ========== 以上代码注释掉，就只保留限制条件的识别和输出 ==========
            
            # 验证限制条件是否都在候选列表中
            constraints_str = result.get('限制条件', {}).get('result', '')
            validated_constraints = validate_and_fix_constraints(constraints_str, query)
            
            # 如果限制条件被修正，更新结果
            if validated_constraints != constraints_str:
                original_constraints = constraints_str
                result['限制条件']['result'] = validated_constraints
                if validated_constraints != '无' and validated_constraints != constraints_str:
                    result['限制条件']['reason'] = f'部分限制条件不在候选列表中，已过滤修正'
                    print(f"警告: query='{query[:50]}...' 限制条件已被过滤修正: {original_constraints} -> {validated_constraints}")
            
            return result

        except Exception as e:
            # 对于API调用异常（网络错误、限流、超时等），抛出异常以便重试
            error_str = str(e).lower()
            if any(keyword in error_str for keyword in ['rate limit', 'timeout', 'connection', 'network', '429', '503', '502']):
                # 这些是可重试的错误，如果是最后一次尝试则使用智能匹配
                if attempt < max_attempts - 1:
                    print(f"警告: query='{query[:50]}...' API调用异常，等待后重试...")
                    time.sleep(1.0)  # 等待后重试
                    continue
                else:
                    # 最后一次尝试也失败，使用智能匹配
                    print(f"警告: query='{query[:50]}...' API调用异常，使用智能匹配...")
                    # ========== 以下代码注释掉，就只保留限制条件的识别和输出 ==========
                    matched_intent = find_best_match_intent('', query)
                    # 如果主意图是"无效提问"，动作应为"无"；否则至少有一个动作
                    if matched_intent == '无效提问':
                        matched_action = '无'
                        action_reason = '主意图为无效提问，跳过动作判断'
                    else:
                        matched_action = find_best_match_action('', query)
                        action_reason = f'API调用异常，已使用智能匹配:{str(e)[:100]}'
                    # ========== 以上代码注释掉，就只保留限制条件的识别和输出 ==========
                    return {
                        '主意图': {'result': matched_intent, 'confidence': '0.3', 'reason': f'API调用异常，已使用智能匹配:{str(e)[:100]}'},
                        '隐含意图': {'result': '无', 'confidence': '0.0', 'reason': 'API调用异常，无法识别'},
                        '动作': {'result': matched_action, 'confidence': '0.3', 'reason': action_reason},
                        '限制条件': {'result': '无', 'confidence': '0.0', 'reason': 'API调用异常，无法识别'}
                    }
            else:
                # 其他错误（如认证错误等），使用智能匹配而不是返回ERROR
                print(f"警告: 处理 query='{query[:50]}...' 时发生异常: {e}，使用智能匹配...")
                # ========== 以下代码注释掉，就只保留限制条件的识别和输出 ==========
                matched_intent = find_best_match_intent('', query)
                # 如果主意图是"无效提问"，动作应为"无"；否则至少有一个动作
                if matched_intent == '无效提问':
                    matched_action = '无'
                    action_reason = '主意图为无效提问，跳过动作判断'
                else:
                    matched_action = find_best_match_action('', query)
                    action_reason = f'调用异常，已使用智能匹配:{str(e)[:100]}'
                # ========== 以上代码注释掉，就只保留限制条件的识别和输出 ==========
                return {
                    '主意图': {'result': matched_intent, 'confidence': '0.3', 'reason': f'调用异常，已使用智能匹配:{str(e)[:100]}'},
                    '隐含意图': {'result': '无', 'confidence': '0.0', 'reason': '调用异常，无法识别'},
                    '动作': {'result': matched_action, 'confidence': '0.3', 'reason': action_reason},
                    '限制条件': {'result': '无', 'confidence': '0.0', 'reason': '调用异常，无法识别'}
                }
    
    # 如果所有尝试都失败，使用智能匹配而不是返回ERROR
    print(f"警告: query='{query[:50]}...' 所有尝试都失败，使用智能匹配...")
    # ========== 以下代码注释掉，就只保留限制条件的识别和输出 ==========
    matched_intent = find_best_match_intent('', query)
    # 如果主意图是"无效提问"，动作应为"无"；否则至少有一个动作
    if matched_intent == '无效提问':
        matched_action = '无'
        action_reason = '主意图为无效提问，跳过动作判断'
    else:
        matched_action = find_best_match_action('', query)
        action_reason = '重试后仍然失败，已使用智能匹配'
    # ========== 以上代码注释掉，就只保留限制条件的识别和输出 ==========
    return {
        '主意图': {'result': matched_intent, 'confidence': '0.3', 'reason': '重试后仍然失败，已使用智能匹配'},
        '隐含意图': {'result': '无', 'confidence': '0.0', 'reason': '重试后仍然失败，无法识别'},
        '动作': {'result': matched_action, 'confidence': '0.3', 'reason': action_reason},
        '限制条件': {'result': '无', 'confidence': '0.0', 'reason': '重试后仍然失败，无法识别'}
    }

def parse_four_category_output(text: str) -> dict:
    """
    从模型返回的 Markdown 表格中解析四类意图:
    | 维度名称 | 识别结果 | 置信度 | 判断理由 |
    | 主意图 | xxx | xxx | xxx |
    | 隐含意图 | xxx | xxx | xxx |
    | 动作 | xxx | xxx | xxx |
    | 限制条件 | xxx | xxx | xxx |
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    result_dict = {
        '主意图': {'result': '未识别', 'confidence': '0.0', 'reason': '输出格式异常'},
        '隐含意图': {'result': '未识别', 'confidence': '0.0', 'reason': '输出格式异常'},
        '动作': {'result': '未识别', 'confidence': '0.0', 'reason': '输出格式异常'},
        '限制条件': {'result': '未识别', 'confidence': '0.0', 'reason': '输出格式异常'}
    }

    dimension_names = ['主意图', '隐含意图', '动作', '限制条件']
    found_count = 0

    for line in lines:
        if line.startswith("|") and line.count("|") >= 4:  # 至少4个|才是数据行(包含首尾)
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 4 and cells[0] in dimension_names:
                dimension = cells[0]
                result_dict[dimension] = {
                    'result': cells[1] if len(cells) > 1 else '未识别',
                    'confidence': cells[2] if len(cells) > 2 else '0.0',
                    'reason': cells[3] if len(cells) > 3 else '输出格式异常'
                }
                found_count += 1

    # 如果解析失败，打印调试信息
    if found_count < 4:
        print(f"警告: 解析失败，只找到 {found_count}/4 个维度")
        print(f"原始输出前500字符: {text[:500]}")

    return result_dict

def main():
    input_file = r"user_data_analysis/data/限制条件重跑20260113.xlsx"
    output_file = r"user_data_analysis/data/限制条件重跑20260113-query限制条件识别.xlsx"    
    # 检查输入文件是否存在
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"输入文件不存在: {input_file}")
    
    print(f"开始处理，输入文件: {input_file}")
    print(f"输出文件: {output_file}")
    
    # 读取输入文件，保留所有原有列
    try:
        df = pd.read_excel(input_file)
        print(f"成功读取输入文件，共 {len(df)} 行, {len(df.columns)} 列")
        print(f"原有列: {', '.join(df.columns.tolist())}")
    except Exception as e:
        raise Exception(f"读取输入文件失败: {e}")

    if "query" not in df.columns:
        raise ValueError(f"输入文件中必须包含 query 列，当前列: {', '.join(df.columns.tolist())}")

    # 并行处理单条 query 的封装函数
    def _process_query(q: t.Any):
        if pd.isna(q):
            return {
                '主意图': {'result': '', 'confidence': '', 'reason': ''},
                '隐含意图': {'result': '', 'confidence': '', 'reason': ''},
                '动作': {'result': '', 'confidence': '', 'reason': ''},
                '限制条件': {'result': '', 'confidence': '', 'reason': ''}
            }
        q_str = str(q)
        return analyze_four_category_intent(q_str)

    queries = df["query"].tolist()
    
    # 批次处理配置
    BATCH_SIZE = 50  # 每批处理的查询数量
    BATCH_DELAY = 2.0  # 每批之间的延迟（秒）
    MAX_WORKERS = 5  # 并行处理的工作线程数
    MAX_RETRIES = 3  # 最大重试次数
    RETRY_DELAY = 1.0  # 重试延迟（秒）
    
    # 带重试的处理函数
    def _process_query_with_retry(q: t.Any, retry_count: int = 0):
        """带重试机制的查询处理函数"""
        try:
            return _process_query(q)
        except Exception as e:
            if retry_count < MAX_RETRIES:
                time.sleep(RETRY_DELAY * (retry_count + 1))  # 递增延迟
                return _process_query_with_retry(q, retry_count + 1)
            else:
                print(f"\n警告: 查询处理失败（已重试{MAX_RETRIES}次）: {str(q)[:50]}... 错误: {e}")
                return {
                    '主意图': {'result': 'ERROR', 'confidence': '0.0', 'reason': f'处理失败: {str(e)[:100]}'},
                    '隐含意图': {'result': 'ERROR', 'confidence': '0.0', 'reason': f'处理失败: {str(e)[:100]}'},
                    '动作': {'result': 'ERROR', 'confidence': '0.0', 'reason': f'处理失败: {str(e)[:100]}'},
                    '限制条件': {'result': 'ERROR', 'confidence': '0.0', 'reason': f'处理失败: {str(e)[:100]}'}
                }
    
    # 分批处理查询
    results = []
    total_batches = (len(queries) + BATCH_SIZE - 1) // BATCH_SIZE
    
    print(f"\n开始分批处理，共 {len(queries)} 条查询，分为 {total_batches} 批，每批 {BATCH_SIZE} 条")
    
    for batch_idx in range(total_batches):
        start_idx = batch_idx * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, len(queries))
        batch_queries = queries[start_idx:end_idx]
        batch_indices = list(range(start_idx, end_idx))
        
        print(f"\n处理第 {batch_idx + 1}/{total_batches} 批（索引 {start_idx}-{end_idx-1}）...")
        
        # 处理当前批次
        batch_results = [None] * len(batch_queries)
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # 提交任务
            future_to_idx = {
                executor.submit(_process_query_with_retry, q): idx 
                for idx, q in enumerate(batch_queries)
            }
            
            # 收集结果
            with tqdm(total=len(batch_queries), desc=f"批次 {batch_idx + 1}/{total_batches}") as pbar:
                for future in as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    try:
                        batch_results[idx] = future.result()
                    except Exception as e:
                        print(f"\n错误: 批次 {batch_idx + 1} 中索引 {idx} 处理失败: {e}")
                        batch_results[idx] = {
                            '主意图': {'result': 'ERROR', 'confidence': '0.0', 'reason': f'批次处理失败: {str(e)[:100]}'},
                            '隐含意图': {'result': 'ERROR', 'confidence': '0.0', 'reason': f'批次处理失败: {str(e)[:100]}'},
                            '动作': {'result': 'ERROR', 'confidence': '0.0', 'reason': f'批次处理失败: {str(e)[:100]}'},
                            '限制条件': {'result': 'ERROR', 'confidence': '0.0', 'reason': f'批次处理失败: {str(e)[:100]}'}
                        }
                    finally:
                        pbar.update(1)
        
        # 添加到总结果
        results.extend(batch_results)
        
        # 批次间延迟（最后一批不需要延迟）
        if batch_idx < total_batches - 1:
            print(f"批次 {batch_idx + 1} 完成，等待 {BATCH_DELAY} 秒后处理下一批...")
            time.sleep(BATCH_DELAY)
    
    print(f"\n所有批次处理完成，共处理 {len(results)} 条结果")

    # 辅助函数：将逗号分隔的字符串拆分为列表
    def split_by_comma(s: str) -> list:
        if not s or s == '无' or s == 'ERROR' or s == '未识别':
            return []
        return [item.strip() for item in str(s).split(',') if item.strip()]
    
    # 辅助函数：展开多个值为多列
    def expand_dimension(results: list, dimension: str, max_count: int = None) -> dict:
        """
        将某个维度的多个值展开为多列
        返回: {列名: 列数据列表}
        """
        # 先找出最大数量
        if max_count is None:
            max_count = 0
            for r in results:
                values = split_by_comma(r[dimension]['result'])
                max_count = max(max_count, len(values))
            # 至少为1（即使没有值，也要有一列）
            max_count = max(max_count, 1)
        
        columns = {}
        for i in range(max_count):
            idx = i + 1
            columns[f'{dimension}{idx}名称'] = []
            columns[f'{dimension}{idx}置信度'] = []
            columns[f'{dimension}{idx}判断理由'] = []
        
        for r in results:
            values = split_by_comma(r[dimension]['result'])
            confidence = r[dimension]['confidence']
            reason = r[dimension]['reason']
            
            # 填充所有列
            for i in range(max_count):
                idx = i + 1
                if i < len(values):
                    columns[f'{dimension}{idx}名称'].append(values[i])
                    columns[f'{dimension}{idx}置信度'].append(confidence)
                    columns[f'{dimension}{idx}判断理由'].append(reason)
                else:
                    columns[f'{dimension}{idx}名称'].append('')
                    columns[f'{dimension}{idx}置信度'].append('')
                    columns[f'{dimension}{idx}判断理由'].append('')
        
        return columns
    
    # 在原有 DataFrame 基础上添加新列(保留所有原有列)
    # ========== 以下代码注释掉，就只保留限制条件的识别和输出 ==========
    # 主意图：固定3列（只有1个）
    df["主意图名称"] = [r['主意图']['result'] for r in results]
    df["主意图置信度"] = [r['主意图']['confidence'] for r in results]
    df["主意图判断理由"] = [r['主意图']['reason'] for r in results]
    
    # 隐含意图：展开为多列
    implied_intent_cols = expand_dimension(results, '隐含意图')
    for col_name, col_data in implied_intent_cols.items():
        df[col_name] = col_data
    # print(f"隐含意图展开为 {len(implied_intent_cols) // 3} 组列（每组3列：名称、置信度、判断理由）")
    
    # 动作：展开为多列
    action_cols = expand_dimension(results, '动作')
    for col_name, col_data in action_cols.items():
        df[col_name] = col_data
    # print(f"动作展开为 {len(action_cols) // 3} 组列（每组3列：名称、置信度、判断理由）")
    # ========== 以上代码注释掉，就只保留限制条件的识别和输出 ==========
    
    # 限制条件：展开为多列
    constraint_cols = expand_dimension(results, '限制条件')
    for col_name, col_data in constraint_cols.items():
        df[col_name] = col_data
    # print(f"限制条件展开为 {len(constraint_cols) // 3} 组列（每组3列：名称、置信度、判断理由）")

    # 添加query字数统计列
    df["query字数"] = df["query"].apply(lambda x: len(str(x)) if pd.notna(x) else 0)

    # 保存到输出文件，保留所有原有列和新添加的列
    try:
        # 确保输出目录存在
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        df.to_excel(output_file, index=False)
        print(f"\n分析完成,结果已保存到 {output_file}")
        # print(f"输出文件包含 {len(df.columns)} 列: {', '.join(df.columns.tolist())}")
    except Exception as e:
        print(f"\n错误: 保存文件失败: {e}")
        raise

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
    except Exception as e:
        print(f"\n\n程序执行出错: {e}")
        import traceback
        traceback.print_exc()
        raise