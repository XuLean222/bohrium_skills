import os
import typing as t
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from openai import AzureOpenAI
from tqdm import tqdm

# ========== 学科/领域 规则分类 ==========
def classify_subject_field(question: str) -> tuple[str, str]:
    """
    基于关键词的学科+领域两级分类，与 subject_analyze_csv 逻辑一致。
    返回 (学科, 领域)；无法匹配时返回 ("通用", "通用")。
    """
    if not question or not str(question).strip():
        return "通用", "通用"
    q_lower = str(question).lower().strip()

    # Subject: Computer Science
    if any(k in q_lower for k in ['ai', 'deep learning', 'machine learning', 'neural network', 'yolo', 'cnn', 'transformer', 'llm', 'gpt', 'algorithm', 'python', 'code', 'software', 'computer', 'data science', 'image recognition', 'vision', 'language model', 'privacy', 'cloud computing', 'big data', 'unimol', 'cybersecurity', 'complex network', 'network theory', '深度学习', '机器学习', '神经网络', '算法', '代码', '软件', '计算机', '数据科学', '图像识别', '语言模型', '大模型', '智能', '隐私', '云计算', '大数据', '网络安全', '复杂网络']):
        subject = '计算机科学'
        field = '人工智能'
        if any(k in q_lower for k in ['vision', 'image', '图像']): field = '计算机视觉'
        elif any(k in q_lower for k in ['language', 'text', 'nlp', '语言', '文本']): field = '自然语言处理'
        elif any(k in q_lower for k in ['algorithm', 'optimization', '算法', '优化']): field = '算法'
        elif any(k in q_lower for k in ['privacy', 'security', '安全', '隐私']): field = '网络与信息安全'
        elif any(k in q_lower for k in ['cloud', 'big data', '云', '大数据']): field = '大数据与云计算'
        elif any(k in q_lower for k in ['complex network', 'network theory', '复杂网络']): field = '网络科学'
        return subject, field

    # Subject: Engineering
    if any(k in q_lower for k in ['sensor', 'dsp', 'signal processing', 'optical', 'interconnect', 'combustion', 'engine', 'prechamber', 'fluid', 'flow', 'channel', 'robot', 'automation', 'manufacturing', 'control', 'vehicle', 'automotive', 'battery management', 'grid', 'power', 'jet', 'spray', 'nozzle', 'simulation', '传感器', '信号处理', '光互连', '燃烧', '发动机', '预燃室', '流体', '明渠', '绕流', '机器人', '自动化', '制造', '控制', '车辆', '汽车', '电网', '电力', '通信', 'communication', 'wireless', '无线', '射流', '喷管', '仿真']):
        subject = '工程学'
        field = '工程学'
        if any(k in q_lower for k in ['sensor', 'instrument', 'measure', '传感器', '测量', '仪器']): field = '仪器科学'
        elif any(k in q_lower for k in ['communication', 'optical', 'wireless', 'dsp', 'signal', '通信', '光', '无线', '信号']): field = '电子与通信工程'
        elif any(k in q_lower for k in ['combustion', 'engine', 'vehicle', 'automotive', 'jet', 'spray', '燃烧', '发动机', '车辆', '汽车', '射流', '喷管']): field = '动力工程与工程热物理'
        elif any(k in q_lower for k in ['fluid', 'flow', 'water', '流体', '水利', '明渠', '绕流']): field = '水利工程/流体力学'
        elif any(k in q_lower for k in ['robot', 'automation', 'control', 'manufacturing', 'simulation', '机器人', '自动化', '控制', '制造', '仿真']): field = '控制科学与工程'
        elif any(k in q_lower for k in ['grid', 'power', 'electric', '电网', '电力', '电气']): field = '电气工程'
        return subject, field

    # Subject: Statistics & Mathematics
    if any(k in q_lower for k in ['statistics', 'statistical', 'inference', 'probability', 'regression', 'high-dimensional', 'sparse', 'math', 'calculus', 'algebra', 'equation', 'optimization', '统计', '推断', '概率', '回归', '高维', '稀疏', '数学', '微积分', '代数', '方程', '优化', 'questionnaire', 'scale', '问卷', '量表']):
        subject = '数学与统计学'
        field = '统计学'
        if any(k in q_lower for k in ['math', 'calculus', 'algebra', 'equation', '数学', '微积分', '代数', '方程']): field = '数学'
        return subject, field

    # Subject: Medicine（放在化学之前：含「酸」的胆酸/去氧胆酸/药理/代谢类应归医学而非化学）
    if any(k in q_lower for k in ['medicine', 'cancer', 'tumor', 'patient', 'disease', 'drug', 'clinical', 'health', 'hospital', 'doctor', 'surgery', 'treatment', 'medical', 'diabetes', 'lung cancer', 'carcinoma', 'chemotherapy', 'pharmacokinetics', 'metabolism', 'epidemiology', 'anatomy', 'physiology', 'pathology', 'fracture', 'bone', 'spine', 'arthritis', 'anesthesia', 'complication', 'disulfiram', '医学', '肿瘤', '癌症', '病人', '疾病', '药物', '临床', '健康', '医院', '医生', '手术', '治疗', '药学', '糖尿病', '肺癌', '癌', '化疗', '药代', '代谢', '流行病学', '解剖', '生理', '病理', 'vaccine', '疫苗', '骨折', '脊柱', '关节炎', '麻醉', '并发症', '双硫仑', '药理', '药理活性', '胆酸', '去氧胆酸', '糖代谢', '脂代谢', '代谢性疾病']):
        subject = '医学'
        field = '医学'
        if any(k in q_lower for k in ['cancer', 'tumor', 'oncology', 'carcinoma', '肿瘤', '癌症', '癌']): field = '肿瘤学'
        elif any(k in q_lower for k in ['drug', 'pharmacy', 'pharmacokinetics', 'disulfiram', '药物', '药学', '药代', '双硫仑', '药理', '药理活性', '胆酸', '去氧胆酸', '糖代谢', '脂代谢', '代谢性疾病']): field = '药学'
        elif any(k in q_lower for k in ['surgery', 'operation', 'anesthesia', 'fracture', 'bone', 'spine', '手术', '外科', '麻醉', '骨折', '脊柱']): field = '外科学'
        elif any(k in q_lower for k in ['clinical', 'diagnosis', 'therapy', 'diabetes', 'arthritis', '临床', '诊断', '治疗', '糖尿病', '关节炎']): field = '临床医学'
        elif any(k in q_lower for k in ['public health', 'epidemiology', 'health', '公共卫生', '流行病', '健康']): field = '公共卫生'
        return subject, field

    # Subject: Chemistry（在医学之后：避免「去氧胆酸」等因含「酸」被误判为化学）
    if any(k in q_lower for k in ['chemistry', 'compound', 'synthesis', 'reaction', 'catalyst', 'dft', 'mof', 'acid', 'base', 'organic', 'inorganic', 'polymer', 'molecular', 'atom', 'bond', 'hplc', 'chromatography', 'spectroscopy', 'crystallization', 'methanol', 'fertilizer', 'nitro', 'preparation', 'adsorption', 'extraction', 'chemical', 'epr', 'esr', 'spectrum', 'resonance', '化学', '化合物', '合成', '反应', '催化', '酸', '碱', '有机', '无机', '聚合物', '分子', '原子', '键', '吸附', '提取', '色谱', '光谱', '结晶', '甲醇', '复合肥', '硝基', '制备', '化工', '分析', '共振', '波谱']):
        subject = '化学'
        field = '化学'
        if any(k in q_lower for k in ['organic', '有机']): field = '有机化学'
        elif any(k in q_lower for k in ['inorganic', '无机']): field = '无机化学'
        elif any(k in q_lower for k in ['catalyst', 'photocatalyst', '催化']): field = '催化化学'
        elif any(k in q_lower for k in ['dft', 'molecular dynamics', 'simulation', 'computation', '计算', '模拟']): field = '计算化学'
        elif any(k in q_lower for k in ['polymer', 'plastic', '聚合物', '塑料', '高分子']): field = '高分子化学'
        elif any(k in q_lower for k in ['analysis', 'analytical', 'hplc', 'chromatography', 'spectroscopy', 'detection', 'epr', 'esr', 'spectrum', 'resonance', '分析', '色谱', '光谱', '检测', '波谱', '共振']): field = '分析化学'
        elif any(k in q_lower for k in ['chemical engineering', 'fertilizer', 'industrial', '化工', '肥料', '工业']): field = '化学工程'
        return subject, field

    # Subject: Materials Science
    if any(k in q_lower for k in ['material', 'battery', 'graphene', 'alloy', 'metal', 'ceramic', 'semiconductor', 'nanotube', 'nanowire', 'film', 'crystal', 'steel', 'titanate', 'perovskite', 'composite', '材料', '电池', '石墨烯', '合金', '金属', '陶瓷', '半导体', '纳米', '薄膜', '晶体', '钢', '钛酸钡', 'batio3', '钙钛矿', '复合材料', 'superconductor', '超导']):
        subject = '材料科学'
        field = '材料科学'
        if any(k in q_lower for k in ['battery', 'storage', 'energy', 'electrode', 'anode', 'cathode', '电池', '储能', '电极', '负极', '正极']): field = '能源材料'
        elif any(k in q_lower for k in ['semiconductor', 'chip', 'electronic', '半导体', '芯片', '电子']): field = '电子材料'
        elif any(k in q_lower for k in ['alloy', 'steel', 'metal', 'magnesium', 'aluminum', 'copper', '合金', '钢', '金属', '镁', '铝', '铜']): field = '金属材料'
        elif any(k in q_lower for k in ['ceramic', 'glass', 'cement', '陶瓷', '玻璃', '水泥']): field = '无机非金属材料'
        return subject, field

    # Subject: Biology
    if any(k in q_lower for k in ['biology', 'gene', 'protein', 'cell', 'virus', 'bacteria', 'dna', 'rna', 'enzyme', 'plant', 'animal', 'microbe', 'phage', 'pathogen', 'fungi', 'antioxidant', 'genetics', 'ecology', 'biodiversity', 'tissue', 'expression', 'database', 'maize', 'corn', '生物', '基因', '蛋白', '细胞', '病毒', '细菌', '酶', '植物', '动物', '微生物', 'fer', '乙烯', '生长', '发育', '噬菌体', '病原菌', '真菌', '抗氧化', '遗传', '生态', '多样性', '组织', '表达', '数据库', '玉米', '水稻']):
        subject = '生物学'
        field = '生物学'
        if any(k in q_lower for k in ['plant', 'crop', 'agriculture', 'maize', 'rice', 'cotton', 'corn', '植物', '农', '玉米', '水稻', '棉花']): field = '植物学'
        elif any(k in q_lower for k in ['gene', 'dna', 'rna', 'genome', 'expression', 'database', '基因', '遗传', '表达', '数据库']): field = '遗传学与生物信息学'
        elif any(k in q_lower for k in ['microbe', 'bacteria', 'virus', 'phage', 'fungi', 'pathogen', '微生物', '细菌', '病毒', '噬菌体', '真菌', '病原']): field = '微生物学'
        elif any(k in q_lower for k in ['ecology', 'environment', 'biodiversity', '生态', '环境', '多样性']): field = '生态学'
        return subject, field

    # Subject: Physics
    if any(k in q_lower for k in ['physics', 'quantum', 'mechanics', 'optics', 'thermodynamics', 'electromagnetism', 'relativity', 'gravity', 'force', 'energy', 'wave', 'particle', 'astronomy', 'universe', 'black hole', 'galaxy', '物理', '量子', '力学', '光学', '热力学', '电磁', '相对论', '引力', '力', '能量', '波', '粒子', '天文', '宇宙', '黑洞', '星系']):
        subject = '物理学'
        field = '物理学'
        if any(k in q_lower for k in ['quantum', '量子']): field = '量子物理'
        elif any(k in q_lower for k in ['mechanics', 'force', 'fluid', '力学', '流体']): field = '力学'
        elif any(k in q_lower for k in ['astronomy', 'universe', 'star', 'planet', '天文', '宇宙', '星']): field = '天文学'
        return subject, field

    # Subject: Psychology
    if any(k in q_lower for k in ['psychology', 'mental', 'depression', 'cognitive', 'behavior', 'emotion', 'anxiety', 'stress', 'therapy', 'counseling', 'autism', 'personality', 'social', '心理', '精神', '抑郁', '认知', '行为', '情绪', '焦虑', '压力', '治疗', '咨询', '自闭症', '人格', '社会']):
        subject = '心理学'
        field = '心理学'
        if any(k in q_lower for k in ['depression', 'anxiety', 'mental health', 'therapy', '抑郁', '焦虑', '心理健康', '治疗']): field = '临床心理学'
        elif any(k in q_lower for k in ['cognitive', 'learning', 'memory', '认知', '学习', '记忆']): field = '认知心理学'
        elif any(k in q_lower for k in ['social', 'interaction', '社会', '交往']): field = '社会心理学'
        elif any(k in q_lower for k in ['child', 'development', 'autism', '儿童', '发展', '自闭症']): field = '发展心理学'
        return subject, field

    # Subject: Education
    if any(k in q_lower for k in ['education', 'student', 'teaching', 'school', 'university', 'learning', 'curriculum', 'pedagogy', 'classroom', '教育', '学生', '教学', '学校', '大学', '学习', '课程', '课堂']):
        subject = '教育学'
        field = '教育学'
        return subject, field

    # Subject: Economics/Management
    if any(k in q_lower for k in ['economy', 'finance', 'market', 'business', 'management', 'stock', 'trade', 'industry', 'company', 'corporate', 'marketing', 'consumer', 'hr', 'human resource', 'supply chain', 'accounting', 'audit', '经济', '金融', '市场', '商业', '管理', '股票', '贸易', '产业', '公司', '企业', '营销', '消费者', '人力资源', '供应链', '会计', '审计']):
        subject = '经济与管理'
        field = '经济学'
        if any(k in q_lower for k in ['management', 'company', 'corporate', 'hr', 'supply chain', '管理', '公司', '企业', '人力', '供应链']): field = '管理学'
        elif any(k in q_lower for k in ['finance', 'stock', 'investment', '金融', '股票', '投资']): field = '金融学'
        elif any(k in q_lower for k in ['marketing', 'consumer', 'market', '营销', '消费者', '市场']): field = '市场营销'
        elif any(k in q_lower for k in ['accounting', 'audit', '会计', '审计']): field = '会计学'
        return subject, field

    # Subject: Environment
    if any(k in q_lower for k in ['environment', 'pollution', 'climate', 'water', 'waste', 'ecology', 'carbon', 'wastewater', 'green', 'sustainability', '环境', '污染', '气候', '水', '废物', '生态', '碳', '废水', '绿色', '可持续']):
        subject = '环境科学'
        field = '环境科学'
        if any(k in q_lower for k in ['water', 'wastewater', '水', '废水']): field = '水环境'
        elif any(k in q_lower for k in ['ecology', 'ecosystem', '生态']): field = '生态学'
        return subject, field

    # Subject: Geography/Geology
    if any(k in q_lower for k in ['geography', 'geology', 'earth', 'rock', 'mineral', 'soil', 'mountain', 'river', 'plateau', 'basin', 'subduction', 'crust', 'volatile', 'seismic', 'earthquake', '地理', '地质', '地球', '岩石', '矿物', '土壤', '山', '河', '盆地', '俯冲带', '陆壳', '挥发性', '地震']):
        subject = '地球科学'
        field = '地质学'
        if any(k in q_lower for k in ['geography', 'city', 'urban', '地理', '城市']): field = '地理学'
        elif any(k in q_lower for k in ['seismic', 'earthquake', 'structure', '地震', '构造']): field = '地球物理学'
        return subject, field

    # Subject: History/Humanities/Social Science
    if any(k in q_lower for k in ['history', 'culture', 'philosophy', 'art', 'literature', 'language', 'religion', 'novel', 'music', 'design', 'social', 'society', 'law', 'politics', 'policy', 'government', '历史', '文化', '哲学', '艺术', '文学', '语言', '宗教', '小说', '音乐', '设计', '社会', '法律', '政治', '政策', '政府']):
        subject = '人文社科'
        field = '人文社科'
        if any(k in q_lower for k in ['history', '历史']): field = '历史学'
        elif any(k in q_lower for k in ['literature', 'novel', '文学', '小说', '红楼梦', '百年孤独']): field = '文学'
        elif any(k in q_lower for k in ['philosophy', '哲学']): field = '哲学'
        elif any(k in q_lower for k in ['art', 'music', 'design', '艺术', '音乐', '设计']): field = '艺术学'
        elif any(k in q_lower for k in ['law', 'legal', 'arbitration', '法律', '法学', '仲裁']): field = '法学'
        elif any(k in q_lower for k in ['politics', 'policy', 'government', '政治', '政策', '政府']): field = '政治学'
        elif any(k in q_lower for k in ['social', 'society', 'sociology', '社会']): field = '社会学'
        return subject, field

    return '通用', '通用'


# ========== Azure OpenAI 配置（从环境变量读取，请勿提交密钥到代码库）==========
AZURE_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "")
AZURE_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")
DEPLOYMENT_NAME = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

client = AzureOpenAI(
    api_key=AZURE_API_KEY,
    azure_endpoint=AZURE_ENDPOINT,
    api_version=API_VERSION
)


ALLOWED_DOMAINS: t.List[str] = [
    "地理科学",
    "物理与天体物理",
    "数学",
    "农林科学",
    "材料科学",
    "计算机科学",
    "环境科学与生态学",
    "化学",
    "工程技术",
    "生物学",
    "医学",
    "综合性学科",
    "法学",
    "心理学",
    "教育学",
    "经济学",
    "管理学",
    "人文科学",
    "定量金融学",
    "统计数据",
    "电气工程与系统科学",
]

# 模型可能输出的“别名”或近义学科名 → 映射到 ALLOWED_DOMAINS 中的标准名称
# 避免因输出“药学”“药理学”等未在列表中的词而被判为“未知”
DOMAIN_ALIAS_TO_STANDARD: t.Dict[str, str] = {
    "药学": "医学",
    "药理学": "医学",
    "药物学": "医学",
    "临床医学": "医学",
    "基础医学": "医学",
    "生物医学": "医学",
    "医药": "医学",
    "生命科学": "生物学",
    "生物": "生物学",
    "材料": "材料科学",
    "环境科学": "环境科学与生态学",
    "生态学": "环境科学与生态学",
    "计算机": "计算机科学",
    "物理": "物理与天体物理",
    "数学与统计": "数学",
    "统计": "数学",
    "金融": "定量金融学",
    "经管": "管理学",
    "管理": "管理学",
}


def build_domain_prompt(query: str) -> str:
    """
    构建领域识别prompt（只允许从 ALLOWED_DOMAINS 中选择或输出“未知”）
    """
    domain_list_text = "\n".join(ALLOWED_DOMAINS)
    return f"""
根据用户问题所属的学科大类，从下面列表中**只选一个**作为输出，不要自创学科名。

用户问题：{query}

要求：
1. 优先从语义和专业术语推断学科（如涉及药物、代谢、疾病机制、药理活性、临床等 → 选「医学」；涉及化合物合成、反应、材料制备等 → 可选「化学」或「材料科学」）。
2. 药学、药理学、药物学、临床医学、基础医学、生物医学等均归入「医学」，请直接输出「医学」而非「药学」等。
3. 只允许从下列学科大类中选择一个，否则输出「未知」。

学科大类（仅限以下，必须逐字照抄其中一个）：
{domain_list_text}

输出格式：<类别名称>
若无法判断或更合适的类别不在上述列表中，请输出 <未知>。
"""


def _analyze_domain_by_llm(query: str, client: AzureOpenAI = None, model: str = None) -> str:
    """
    仅通过 LLM 识别学科大类（ALLOWED_DOMAINS 中之一或「未知」），供规则未命中时兜底。
    """
    # 使用全局客户端和模型配置，如果未传入参数
    if client is None:
        client = globals()['client']
    if model is None:
        model = DEPLOYMENT_NAME
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "你是一名学科分类专家，专门负责判断用户问题的学科归属。",
                },
                {"role": "user", "content": build_domain_prompt(query)},
            ],
            temperature=0,
            max_completion_tokens=2000,
        )

        content = response.choices[0].message.content.strip()
        # 提取类别名称，去除可能的格式标记
        domain = content.replace("<", "").replace(">", "").strip()

        # 如果模型自己输出了"未知"或类似表达，直接返回未知
        if "未知" in domain or "无法判断" in domain:
            return "未知"

        # 先检查是否为“别名”，映射到标准学科名（避免药学/药理学等被判为未知）
        domain_trimmed = domain.strip()
        if domain_trimmed in DOMAIN_ALIAS_TO_STANDARD:
            return DOMAIN_ALIAS_TO_STANDARD[domain_trimmed]
        for alias, standard in DOMAIN_ALIAS_TO_STANDARD.items():
            if alias in domain:
                return standard

        # 在允许列表中查找匹配的领域（只返回一个，按给定顺序优先）
        for d in ALLOWED_DOMAINS:
            if d in domain:
                return d

        # 如果模型输出的类别不在允许列表中，则一律视为未知
        return "未知"

    except Exception as e:
        # 出错时返回未知，避免在主流程中断
        return "未知"


def analyze_subject_and_domain(query: str, client: AzureOpenAI = None, model: str = None) -> tuple[str, str]:
    """
    识别用户查询的学科 + 领域（两级），与 subject_analyze_csv 分类逻辑一致。
    先按关键词规则得到学科/领域；规则未命中（通用/通用）时再用 LLM 兜底得到学科大类。

    Returns:
        (学科, 领域)
    """
    subject, field = classify_subject_field(query)
    if subject != "通用" or field != "通用":
        return subject, field
    # 规则未命中，用 LLM 兜底
    domain = _analyze_domain_by_llm(query, client=client, model=model)
    if domain == "未知":
        return "未知", "未知"
    return domain, domain


def analyze_domain(query: str, client: AzureOpenAI = None, model: str = None) -> str:
    """
    仅返回领域（与原有调用方式兼容，如 run_all_classifications）。
    等价于 analyze_subject_and_domain(query)[1]。
    """
    _, field = analyze_subject_and_domain(query, client=client, model=model)
    return field


# ========== 主流程 ==========
def main():
    """
    主流程：读取 xlsx，对 query 列做学科+领域分类（规则优先，LLM 兜底），输出含「学科」「领域」两列。
    """
    # 输入和输出文件路径（可根据实际需要修改）
    input_file = r"/root/xl/user_data_analysis/data/20251203-20251210数据_只含title.xlsx"
    output_file = r"/root/xl/user_data_analysis/data/20251203-20251210数据_只含title_学科领域分类.xlsx"

    # 读取输入文件
    df = pd.read_excel(input_file)

    # 检查必要的列是否存在
    if "query" not in df.columns:
        raise ValueError("输入文件中必须包含 query 列")

    # 单条查询：返回 (学科, 领域)
    def _classify_query(q):
        if pd.isna(q):
            return "", ""
        return analyze_subject_and_domain(str(q))

    queries = df["query"].tolist()

    with ThreadPoolExecutor(max_workers=5) as executor:
        result_list = list(
            tqdm(
                executor.map(_classify_query, queries),
                total=len(queries),
                desc="学科/领域分类（并行）",
            )
        )

    subjects, fields = zip(*result_list) if result_list else ([], [])
    df["学科"] = list(subjects)
    df["领域"] = list(fields)

    df.to_excel(output_file, index=False)
    print(f"学科/领域分类完成，结果已保存到 {output_file}")


if __name__ == "__main__":
    main()

