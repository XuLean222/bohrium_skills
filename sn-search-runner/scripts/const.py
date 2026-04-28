SN_TOKEN = ""  # 填入你的 Bohrium API token
LARK_APP_TOKEN = ""  # 填入飞书多维表格 app_token
LARK_TABLE_ID = ""  # 填入飞书数据表 table_id
DIFY_API_KEY = ""  # 填入 Dify API Key

env_map = {
    "test": {
        "url": "https://bohrium-opik-latest.test.dp.tech/api",
        "project_name": "test",
        "workspace": "default",
    },
    "uat": {
        "url": "https://bohrium-opik-latest.test.dp.tech/api",
        "project_name": "uat",
        "workspace": "default",
    },
    "prod": {
        "url": "https://bohrium-opik-new.dp.tech/api",
        "project_name": "prod",
        "workspace": "default",
    }
}