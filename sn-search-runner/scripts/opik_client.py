# -*- coding: utf-8 -*-
"""
Opik Trace Service - 基于 Opik SDK 提供 trace 查询服务
"""
import logging
from typing import List, Optional

import opik
from opik.rest_api.types.trace_public import TracePublic

import const

logger = logging.getLogger(__name__)


class OpikClient:
    """Opik Trace 服务，封装 Opik SDK 提供 trace 相关操作"""

    def __init__(
        self,
        env,
        project_name: Optional[str] = None,
        workspace: Optional[str] = None,
        host: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        初始化 OpikTraceService

        Args:
            project_name: 项目名称，不提供则使用 Default Project
            workspace: 工作空间名称，不提供则使用 default
            host: Opik 服务地址
            api_key: API 密钥
        """
        self._client = opik.Opik(
            project_name=const.env_map.get(env).get("project_name"),
            workspace=const.env_map.get(env).get("workspace"),
            host=const.env_map.get(env).get("url"),
            #api_key="Cp5Sb8W4EcIOH53jF7uRvlPb3",
        )

    def get_trace_by_id(self, trace_id: str) -> TracePublic:
        """
        根据 trace ID 获取单个 trace

        Args:
            trace_id: trace 的唯一标识

        Returns:
            TracePublic 对象

        Raises:
            Exception: 当 trace 不存在或请求失败时抛出
        """
        try:
            trace = self._client.rest_client.traces.get_trace_by_id(id=trace_id)
            logger.info(f"成功获取 trace: {trace_id}")
            return trace
        except Exception as e:
            logger.error(f"获取 trace 失败, trace_id={trace_id}, error: {e}")
            raise

    def get_traces_by_project(
        self,
        project_name: Optional[str] = None,
        page: int = 1,
        size: int = 50,
        filters: Optional[str] = None,
        truncate: bool = True,
    ) -> List[TracePublic]:
        """
        根据项目名称分页获取 traces

        Args:
            project_name: 项目名称，不提供则使用初始化时的项目
            page: 页码，从 1 开始
            size: 每页数量，默认 50
            filters: 过滤条件字符串
            truncate: 是否截断 input/output/metadata

        Returns:
            TracePublic 对象列表
        """
        try:
            trace_page = self._client.rest_client.traces.get_traces_by_project(
                project_name=project_name or self._client.project_name,
                page=page,
                size=size,
                filters=filters,
                truncate=truncate,
            )
            traces = trace_page.content or []
            logger.info(
                f"获取 traces 成功, project={project_name or self._client.project_name}, "
                f"page={page}, size={size}, total={trace_page.total}"
            )
            return traces
        except Exception as e:
            logger.error(f"获取 traces 失败, project={project_name}, error: {e}")
            raise

    def search_traces(
        self,
        project_name: Optional[str] = None,
        filter_string: Optional[str] = None,
        max_results: int = 1000,
        truncate: bool = True,
    ) -> List[TracePublic]:
        """
        搜索 traces，支持 Opik Query Language (OQL) 过滤

        filter_string 格式: "<COLUMN> <OPERATOR> <VALUE> [AND <COLUMN> <OPERATOR> <VALUE>]*"
        支持的列: id, name, start_time, end_time, status, tags, metadata 等
        支持的操作符: =, !=, >, <, >=, <=, contains, not_contains

        示例:
            - 'name = "my-trace"'
            - 'start_time >= "2025-01-01T00:00:00Z"'
            - 'tags contains "production"'

        Args:
            project_name: 项目名称，不提供则使用初始化时的项目
            filter_string: OQL 过滤字符串
            max_results: 最大返回数量，默认 1000
            truncate: 是否截断 input/output/metadata

        Returns:
            TracePublic 对象列表
        """
        try:
            traces = self._client.search_traces(
                project_name=project_name or self._client.project_name,
                filter_string=filter_string,
                max_results=max_results,
                truncate=truncate,
            )
            logger.info(
                f"搜索 traces 成功, project={project_name or self._client.project_name}, "
                f"filter={filter_string}, 结果数={len(traces)}"
            )
            return traces
        except Exception as e:
            logger.error(
                f"搜索 traces 失败, project={project_name}, "
                f"filter={filter_string}, error: {e}"
            )
            return ""

    def get_trace_stats(
        self,
        project_name: Optional[str] = None,
        filters: Optional[str] = None,
    ):
        """
        获取 trace 统计信息

        Args:
            project_name: 项目名称
            filters: 过滤条件字符串

        Returns:
            ProjectStatsPublic 对象
        """
        try:
            stats = self._client.rest_client.traces.get_trace_stats(
                project_name=project_name or self._client.project_name,
                filters=filters,
            )
            logger.info(f"获取 trace 统计信息成功, project={project_name or self._client.project_name}")
            return stats
        except Exception as e:
            logger.error(f"获取 trace 统计信息失败, error: {e}")
            return ""

    def get_llm_span_io(self, trace_id: str, model_name: str = "gemini-3-flash-preview"):
        """
        获取指定 trace 下某个 LLM span 的 input/output
        """
        try:
            spans = self._client.search_spans(trace_id=trace_id)
            for span in spans:
                if span.type == "llm":
                    return span
            return ""
        except Exception as e:
            logger.error(
                f"搜索 span 失败, trace_id={trace_id}, "
                f"error: {e}"
            )
            return ""

    def flush(self, timeout: Optional[int] = None) -> bool:
        """刷新缓冲区，确保所有消息发送完成"""
        return self._client.flush(timeout=timeout)

    def close(self, timeout: Optional[int] = None):
        """关闭客户端连接"""
        self._client.end(timeout=timeout)
