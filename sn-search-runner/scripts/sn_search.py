import logging
import re
import time
import requests


def get_keywords(history_data):
    for data in history_data:
        channel = data.get('channel')
        if channel:
            ui_info = channel.get('uiInfo')
            if ui_info:
                sub_type = ui_info.get('subType')
                if sub_type == "@bohrium-chat/common/thinking-list":
                    content = ui_info.get('content')
                    if content:
                        payload = content.get('payload')
                        if payload:
                            keywords_obj = payload[0]
                            if isinstance(keywords_obj, dict) and keywords_obj.get('type') == "keyword":
                                keywords = keywords_obj.get('payload')
                                return keywords
    return []


def get_summary(history_data):
    for data in history_data:
        channel = data.get('channel')
        if channel:
            ui_info = channel.get('uiInfo')
            if ui_info:
                sub_type = ui_info.get('subType')
                if sub_type == '@bohrium-chat/common/markdown':
                    content = ui_info.get('content')
                    if content:
                        if content.get('type') == 'summary':
                            text = content.get('text')
                            if text:
                                return text
    return ''

def get_mix_list(history_data):
    resource_data = []
    paper_list = []
    for data in history_data:
        channel = data.get('channel')
        if channel:
            ui_info = channel.get('uiInfo')
            if ui_info:
                sub_type = ui_info.get('subType')
                if sub_type == '@bohrium-chat/snp/sider-tab/v2':
                    content = ui_info.get('content')
                    if content:
                        tabs = content.get('tabs')
                        if len(tabs) == 2:
                            for tab in tabs:
                                if tab.get('id') == 'used':
                                    items = tab.get('items')
                                    for item in items:
                                        resource_id = item.get('resourceId')
                                        resource_data.append(resource_id)
    if resource_data:
        for data in history_data:
            channel = data.get('channel')
            if channel:
                ui_info = channel.get('uiInfo')
                if ui_info:
                    sub_type = ui_info.get('subType')
                    if sub_type == '@bohrium-chat/snp/cards-data':
                        content = ui_info.get('content')
                        if content:
                            data = content.get('data')
                            if data:
                                resource_map = data.get('resourceMap')
                                if resource_map:
                                    for resource_id in resource_data:
                                        for k,v in resource_map.items():
                                            if resource_id == k:
                                                paper_list.append(v)
                                    return paper_list
    return paper_list



def get_sn_agent_summary(history_data):
    for data in history_data:
        channel = data.get('channel')
        if channel:
            role = channel.get('role')
            if role == 'assistant':
                ui_info = channel.get('uiInfo')
                if ui_info:
                    sub_type = ui_info.get('subType')
                    if sub_type == '@bohrium-chat/common/markdown':
                        content = ui_info.get('content')
                        if content:
                            text = content.get('text')
                            if text:
                                return text

    return ''

def get_sub_query(history_data):
    sub_query = []
    for data in history_data:
        channel = data.get('channel')
        if channel:
            ui_info = channel.get('uiInfo')
            if ui_info:
                sub_type = ui_info.get('subType')
                if sub_type == '@bohrium-chat/common/thought-chain':
                    content = ui_info.get('content')
                    if content:
                        children = content.get('children')
                        if children:
                            for child in children:
                                if child.get('type') == 'search':
                                    content = child.get('content')
                                    if content:
                                        queries = content.get('queries')
                                        for query in queries:
                                            _query = query.get('query')
                                            sub_query.append(_query)


    return sub_query

def get_evidence_search(history_data):
    evidence_search = []
    for data in history_data:
        channel = data.get('channel')
        if channel:
            ui_info = channel.get('uiInfo')
            if ui_info:
                sub_type = ui_info.get('subType')
                if sub_type == '@bohrium-chat/common/thought-chain':
                    content = ui_info.get('content')
                    if content:
                        children = content.get('children')
                        if children:
                            for child in children:
                                if child.get('type') == 'search':
                                    content = child.get('content')
                                    if content:
                                        channel = content.get('channel')
                                        if channel:
                                            for c in channel:
                                                name = c.get('name')
                                                evidence_search.append(name)

    return evidence_search

class SNSearch:
    def __init__(self, env, scene, token, user_id, org_id, watchtower_token):
        self.env = env
        self.scene = scene
        self.token = token
        self.user_id = user_id
        self.org_id = org_id
        self.watchtower_token = watchtower_token

    def ai_search_result(self, query, model, discipline, journal_type):
        answer_result = {
            "keywords": [],
            "summary": "",
            "papers": "",
            "share_url": "",
            "sub_query": [],
            "evidence_search": [],
            "session_id": ""
        }
        # 获取session_id
        # 构建提问参数
        if self.scene == "adk_science_navigator":
            payload = {
                "query": query,
                "model": model,
                "discipline": discipline,
                "scene": "adk_science_navigator",
                "SNPReq": {
                    "sessionId": "",
                    "channel": {
                        "schema": "fe",
                        "version": "v1",
                        "agent": "",
                        "branchId": "",
                        "sourceSessionId": "", "sourceQuestionId": "",
                        "questionId": "",
                        "answerId": "af101eaa-f869-49d2-9de6-3a4ae750test",
                        "messageId": "0a11ae98-2066-4c73-b406-14c5cbebtest",
                        "role": "user", "auth": 1, "uiInfo": {
                            "localMessageId": "478a4c28-36be-4ad5-8501-3541dd57test",
                            "layout": "main", "type": "ui",
                            "subType": "@bohrium-chat/common/markdown",
                            "content": {"text": query},
                            "response": {},
                            "actionList": [{"key": "text", "action": "append"}]},
                        "entities": [], "state": {}, "meta": {}}, "system": {
                        "payload": {
                            "model": model, "agentId": "science_navigator", "sessionId": "",
                            "scene": "adk_science_navigator", "streaming": True,
                            "biz": {
                                "uploadList": [],
                                "sn": {"discipline": discipline, "journal_type": journal_type, "model": model}}}}},
                "resource_id_list": [],
                "journal_type": journal_type,
                "snp_version": "1.0.0"
            }
        else:
            payload = {
                "query": query,
                "model": model,
                "discipline": discipline,
                "scene": "paper",
                "agentId": "sn",
                "SNPReq": {
                    "sessionId": "",
                    "channel": {
                        "schema": "fe",
                        "version": "v1",
                        "agent": "",
                        "branchId": "",
                        "sourceSessionId": "", "sourceQuestionId": "",
                        "questionId": "",
                        "answerId": "af101eaa-f869-49d2-9de6-3a4ae750test",
                        "messageId": "0a11ae98-2066-4c73-b406-14c5cbebtest",
                        "role": "user", "auth": 1, "uiInfo": {
                            "localMessageId": "478a4c28-36be-4ad5-8501-3541dd57test",
                            "layout": "main", "type": "ui",
                            "subType": "@bohrium-chat/common/markdown",
                            "content": {"text": query},
                            "response": {},
                            "actionList": [{"key": "text", "action": "append"}]},
                        "entities": [], "state": {}, "meta": {}}, "system": {
                        "payload": {
                            "model": model, "agentId": "sn", "sessionId": "", "scene": "paper", "streaming": True,
                            "biz": {
                                "uploadList": [],
                                "sn": {"discipline": discipline, "journal_type": journal_type, "model": model}}}}},
                "resource_id_list": [],
                "journal_type": journal_type,
                "snp_version": "1.0.0"
            }
        headers = {
            "Content-Type": "application/json",
            "content-language": "zh-cn",
            "Authorization": "Bearer " + self.token
        }
        bohrium_host = f"https://www.bohrium.com" if self.env == "prod" else f"https://www.{self.env}.bohrium.com"
        url = f"{bohrium_host}/bohrapi/v1/sigma-search/api/v4/ai_search/sessions"

        # 发起提问
        response = requests.post(url, json=payload, headers=headers)
        # 获取返回结果
        result = response.json()
        if result.get("code") != 0:
            logging.error(result)
            raise Exception(result)
        res_data = result.get("data")
        if res_data and (session_id := res_data.get("sessionId")):
            logging.info(f"创建session成功：{session_id}")
            answer_result = self.get_question_details(session_id, answer_result)
        return answer_result

    def get_question_details(self, session_id, answer_result):
        timeout = 360
        time_interval = 10
        bohrium_host = f"https://www.bohrium.com" if self.env == "prod" else f"https://www.{self.env}.bohrium.com"
        if self.scene == "adk_science_navigator":
            url = f"{bohrium_host}/bohrapi/v1/sigma-search/api/v4/{session_id}/history"
            headers = {
                "Content-Type": "application/json",
                "Authorization": "Bearer " + self.token
            }
        else:
            bohrium_host = f"https://www.bohrium.com" if self.env == "prod" else f"https://www.{self.env}.bohrium.com"
            url = f"{bohrium_host}/api/v4/{session_id}/history"
            headers = {
                "X-User-Id": self.user_id,
                "X-Org-Id": self.org_id,
                "Content-Type": "application/json",
                "Authorization": "Bearer " + self.token
            }
        logging.info(f"开始获取详情：{session_id}")
        while timeout > 0:
            response = requests.get(url, headers=headers)
            result = response.json()
            data = result.get('data')
            if data:
                need_stream = data.get('need_stream')
                time.sleep(1)
                if need_stream is False and (history_data := data.get('historyData')) and len(history_data) > 2:
                    if self.scene == "adk_science_navigator":
                        keywords = get_keywords(history_data)
                        summary = get_sn_agent_summary(history_data)
                        paper_list = get_mix_list(history_data)
                        papers = self.format_mix_papers(paper_list)
                        sub_query = get_sub_query(history_data)
                        evidence_search = get_evidence_search(history_data)
                    else:
                        keywords = get_keywords(history_data)
                        summary = get_summary(history_data)
                        all_paper_list = self.get_paper_list(history_data, session_id, "all")
                        summary = self.remap_citations(summary, all_paper_list)
                        reference_paper_list = self.get_paper_list(history_data, session_id, "used")
                        papers = self.format_papers(reference_paper_list)
                        sub_query = []
                        evidence_search = []
                    answer_result = {
                        "keywords": keywords,
                        "summary": summary,
                        "papers": papers,
                        "sub_query": sub_query,
                        "evidence_search": evidence_search,
                    }
                    # logging.info(f"answer_result: {answer_result}")
                    logging.info(f"详情获取成功：{session_id}")
                    break
                else:
                    time.sleep(time_interval)
                    timeout -= time_interval
            else:
                time.sleep(time_interval)
                timeout -= time_interval
        if timeout <= 0:
            logging.info("wait question to be succeeded  timeout")
        self.share_ai_search_result(session_id)
        bohrium_host = f"https://www.bohrium.com" if self.env == "prod" else f"https://www.{self.env}.bohrium.com"
        answer_result["share_url"] = f"{bohrium_host}/chat/share/{session_id}"
        if self.scene == "adk_science_navigator":
            summary_first_token = 10000
        else:
            question_id = self.get_question_id(session_id)
            summary_first_token = self.get_first_token(question_id, session_id)
        answer_result["summary_first_token"] = summary_first_token
        answer_result["session_id"] = session_id
        return answer_result

    def get_paper_list(self, history_data, session_id, tab_id):
        answer_id = history_data[0].get("channel").get("answerId")
        bohrium_host = f"https://www.bohrium.com" if self.env == "prod" else f"https://www.{self.env}.bohrium.com"
        url = f"{bohrium_host}/bohrapi/v1/sigma-search/api/v4/{session_id}/sider?siderId=sider-{answer_id}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + self.token
        }
        # 获取返回结果
        response = requests.get(url, headers=headers)
        result = response.json()
        data = result.get('data')
        tabs = data.get("tabs")
        for papers in tabs:
            if papers.get("id") == tab_id:
                items = papers.get("items")
                return items
        return []

    @staticmethod
    def format_papers(paper_list):
        formatted_entries = []
        for paper in paper_list:
            authors = paper.get("author", [])
            entry = {
                "type": "paper",
                "Title": paper.get('titleEn', ''),
                "Author": authors,
                "Journal": paper.get('journal', ''),
                "Abstract": paper.get('abstract', ''),
                "doi": paper.get('doi', '') or '',
                "Link": paper.get('link', ''),
                "PublicationDate": paper.get('publicationDate', ''),
            }
            formatted_entries.append(entry)
        return formatted_entries

    def share_ai_search_result(self, session_id):
        bohrium_host = f"https://www.bohrium.com" if self.env == "prod" else f"https://www.{self.env}.bohrium.com"
        url = f"{bohrium_host}/bohrapi/v1/sigma-search/api/v1/ai_search/sessions_extended/{session_id}"
        headers = {
            "Authorization": "Bearer " + self.token
        }
        r = requests.patch(url=url, json={"share": 1}, headers=headers)

    def get_first_token(self, question_id, session_id):
        bohrium_host = f"https://www.bohrium.com" if self.env == "prod" else f"https://www.{self.env}.bohrium.com"
        url_sigma = f"{bohrium_host}/api/v1/ai_search/search_records/?question_id={question_id}"
        headers_sigma = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + self.watchtower_token
        }
        try:
            for _ in range(5):
                response_sigma = requests.get(url_sigma, json={}, headers=headers_sigma)
                result_sigma = response_sigma.json()
                summary_list = result_sigma[0].get('summaryList')
                if summary_list:
                    summary_first_token = summary_list[0].get("firstTokenTime")
                    logging.info(f"{session_id} summary_first_token: {str(summary_first_token)}")
                    return summary_first_token
                time.sleep(2)
            else:
                logging.info(f"No summary_first_token")
        except Exception as e:
            logging.error(f"get first token error: {e}, url: {url_sigma}")
        return 10000

    def get_question_id(self, session_id):
        bohrium_host = f"https://www.bohrium.com" if self.env == "prod" else f"https://www.{self.env}.bohrium.com"
        url_sigma = f"{bohrium_host}/api/v1/ai_search/sessions/{session_id}"
        headers_sigma = {
            "Content-Type": "application/json",
            "authorization": "Bearer " + self.watchtower_token
        }
        response = requests.get(url_sigma, json={}, headers=headers_sigma)
        logging.info(f"result_sigma: {str(response.text)}")
        result_sigma = response.json()
        questions = result_sigma.get("questions")
        question_id = ""
        if questions:
            question_id = questions[0].get("id")
        return question_id

    @staticmethod
    def format_mix_papers(paper_list):
        formatted_entries = []
        for paper in paper_list:
            bohrium_type = paper.get("@bohrium-type", "")
            citation_id = paper.get('resourceId', '')

            if bohrium_type == "@bohrium/card-type/paper":
                title = paper.get("titleEn") or paper.get("title") or ""
                entry = {
                    "type": "paper",
                    "Title": title,
                    "Author": paper.get("authors", []),
                    "Journal": paper.get('journal', ''),
                    "Abstract": paper.get('abstract', ''),
                    "doi": paper.get('doi', '') or '',
                    "PublicationDate": paper.get('publicationDate', ''),
                    "citation_id": citation_id,
                }
                formatted_entries.append(entry)

            elif bohrium_type == "@bohrium/card-type/web":
                entry = {
                    "type": "web",
                    "Title": paper.get("title", ''),
                    "site": paper.get("site", ''),
                    "snippet": paper.get("snippet", ''),
                    "url": paper.get("url", ''),
                    "citation_id": citation_id,
                }
                formatted_entries.append(entry)

            elif bohrium_type == "@bohrium/card-type/news":
                entry = {
                    "type": "news",
                    "Title": paper.get("title", ''),
                    "site": paper.get("site", ''),
                    "snippet": paper.get("snippet", ''),
                    "url": paper.get("url", ''),
                    "data_source": paper.get("data_source", ''),
                    "date": paper.get("date", ''),
                    "citation_id": citation_id,
                }
                formatted_entries.append(entry)

            elif bohrium_type == "@bohrium/card-type/science-pedia":
                entry = {
                    "type": "science-pedia",
                    "Title": paper.get("title", ''),
                    "snippet": paper.get("snippet", ''),
                    "url": paper.get("url", ''),
                    "key_points": paper.get("key_points", ''),
                    "citation_id": citation_id,
                }
                formatted_entries.append(entry)

        return formatted_entries

    @staticmethod
    def remap_citations(summary, references):
        """
        根据 summary 中出现的 citation:x，
        从原始 references 中抽取对应文献并生成新列表，
        同时重映射 summary 中的 citation 编号。

        参数：
            summary (str): 含有 [citation:x] 的摘要文本
            references (List[str]): 原始文献列表（第1篇在 index 0）

        返回：
            new_summary (str): citation 编号已重排的 summary
            new_references (List[str]): 按出现顺序生成的新文献列表
        """

        # 1. 找出所有 citation:x
        citation_numbers = re.findall(r'\[citation:(\d+)\]', summary)
        citation_numbers = [int(n) for n in citation_numbers]

        # 2. 按首次出现顺序去重
        seen = {}
        ordered_unique = []
        for n in citation_numbers:
            if n not in seen:
                seen[n] = True
                ordered_unique.append(n)

        # 3. 构建“旧编号 → 新编号”的映射
        old_to_new = {old: new_idx + 1 for new_idx, old in enumerate(ordered_unique)}

        # 4. 构建新文献列表
        new_references = [
            references[old_idx - 1]  # 注意：citation:1 对应 references[0]
            for old_idx in ordered_unique
        ]

        # 5. 替换 summary 中的 citation 编号
        def replace_citation(match):
            old_num = int(match.group(1))
            return f"[citation:{old_to_new[old_num]}]"

        new_summary = re.sub(r'\[citation:(\d+)\]', replace_citation, summary)

        return new_summary
