import json
import logging
import re
import time

import requests

from const import DIFY_API_KEY
API_KEY = DIFY_API_KEY


class AgentWorkflow(object):
    def __init__(self, query, keywords, summary, papers, scene, ttft, sub_query, evidence_search, trace=""):
        self.query = query
        self.keywords = keywords
        self.summary = summary
        self.papers = papers
        self.scene = scene
        self.ttft = ttft
        self.sub_query = sub_query
        self.evidence_search = evidence_search
        self.model = "gemini"
        self.trace = trace

    def get_ai_result(self):
        url = f"https://dify.test.dp.tech/v1/workflows/run"
        payload = {
            "inputs": {
                "query": self.query,
                "keywords": str(self.keywords),
                "summary": self.summary,
                "model": self.model,
                "papers": self.papers,
                "scene": self.scene,
                "TTFT": self.ttft,
                "sub_query": str(self.sub_query),
                "evidence_search": str(self.evidence_search),
                "trace": str(self.trace)
            },
            "response_mode": "streaming",
            "user": "test-assessment",
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        }
        for _ in range(2):
            # 发起提问
            response = requests.post(url, json=payload, headers=headers, stream=True)
            text = ""
            for chunk in response.iter_lines():
                line = chunk.decode("utf-8")
                # print(line)
                if line.startswith("data:"):
                    json_str = line.replace('data: ', '', 1)
                    data_dict = json.loads(json_str)
                    event = data_dict.get('event')
                    if event == "text_chunk":
                        text_value = data_dict['data']['text']
                        text += text_value
            if text != "":
                logging.info(text)
                return text
            time.sleep(3)
        return ""

    def get_score(self, content):
        # 定义目标字段
        if self.scene == "adk_science_navigator":
            target_fields = ["忠实度评分", "回答相关性评分",
                             "上下文相关性评分", "上下文精确率评分",
                             "首次响应时间评分",
                             "来源时效性评分", "Top6来源时效性评分", "来源质量评分", "Top6来源质量评分", "回答完整性",
                             "思考过程 / Query 改写准确性", "证据检索来源相关性", "输出格式自适应能力",
                             "限制条件识别能力", "回答逻辑性"]
        else:
            target_fields = ["忠实度评分", "回答相关性评分",
                             "上下文相关性评分", "上下文精确率评分",
                             "首次响应时间评分",
                             "文献时效性评分", "Top6文献时效性评分", "文献质量评分", "Top6文献质量评分", "回答完整性",
                             "思考过程 / Query 改写准确性", "证据检索来源相关性", "输出格式自适应能力",
                             "限制条件识别能力", "回答逻辑性"]
        field_pattern = '|'.join(re.escape(f) for f in target_fields)

        pattern = rf'''
        \*{{0,2}}                # 可选的 **
        ({field_pattern})        # 评分字段
        \*{{0,2}}                # 可选的 **
        \s*[：:]\s*              # 中英文冒号
        (\d+)                    # 分数
        \s*(?:分)?               # 可选的“分”\
        [ \t]*$                    # 行尾，禁止后面跟解释文本
        '''

        matches = re.findall(pattern, content, re.VERBOSE)

        result_dict = {field: int(score) for field, score in matches}
        if self.scene == "adk_science_navigator":
            new_data = {
                k.replace('来源', '文献') if k != '证据检索来源相关性' else k: v
                for k, v in result_dict.items()
            }
            result_dict = new_data

        logging.info(json.dumps(result_dict, ensure_ascii=False))
        return result_dict

    @staticmethod
    def extract_score_reasons(text: str):
        """
        强鲁棒版本：
        - 支持 “来源质量满分理由：” 这种前缀形式
        - 满分/扣分互不串台
        - 空理由不写入
        - 自动截断“优化建议”
        """
        result = {}

        # 1️⃣ 截断优化建议
        text = re.split(r'\*\*优化建议\*\*', text)[0]

        # 2️⃣ 按评分项切分
        sections = re.split(r'【([^】]+)】', text)

        for i in range(1, len(sections), 2):
            score_name = sections[i].strip()
            content = sections[i + 1]

            reasons = {}

            # 3️⃣ 核心修复点：允许前面带评分项名
            reason_pattern = re.compile(
                r'(?:.*?)(满分理由|扣分理由)：([\s\S]*?)(?=(?:\n.*?(?:满分理由|扣分理由)：)|$)',
                re.DOTALL
            )

            matches = reason_pattern.findall(content)

            for reason_type, reason_text in matches:
                cleaned = reason_text.strip()
                if cleaned:
                    reasons[reason_type] = cleaned

            if reasons:
                result[score_name] = reasons

        data = {
            k.replace('来源', '文献') if k != '证据检索来源相关性' else k: v
            for k, v in result.items()
        }
        logging.info(json.dumps(data, ensure_ascii=False))
        return data
