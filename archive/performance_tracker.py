#!/usr/bin/env python3
"""
播客生成器性能追蹤器
提供詳細的運行時間統計和性能分析
"""

import time
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path
import functools
import logging

logger = logging.getLogger(__name__)

@dataclass
class StageMetrics:
    """單個階段的性能指標"""
    name: str
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    success: bool = True
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def finish(self, success: bool = True, error_message: Optional[str] = None, **metadata):
        """結束階段計時"""
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        self.success = success
        self.error_message = error_message
        if metadata:
            self.metadata = metadata

@dataclass
class SessionMetrics:
    """整個會話的性能指標"""
    session_id: str
    start_time: float
    config: Dict[str, Any]
    stages: List[StageMetrics]
    total_duration: Optional[float] = None
    end_time: Optional[float] = None
    success: bool = True
    output_files: Optional[Dict[str, str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        return {
            "session_id": self.session_id,
            "start_time": self.start_time,
            "start_datetime": datetime.fromtimestamp(self.start_time).isoformat(),
            "end_time": self.end_time,
            "end_datetime": datetime.fromtimestamp(self.end_time).isoformat() if self.end_time else None,
            "total_duration": self.total_duration,
            "success": self.success,
            "config": self.config,
            "output_files": self.output_files,
            "stages": [
                {
                    "name": stage.name,
                    "start_time": stage.start_time,
                    "end_time": stage.end_time,
                    "duration": stage.duration,
                    "success": stage.success,
                    "error_message": stage.error_message,
                    "metadata": stage.metadata
                }
                for stage in self.stages
            ]
        }

class PerformanceTracker:
    """性能追蹤器主類"""
    
    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.session_metrics: Optional[SessionMetrics] = None
        self.current_stage: Optional[StageMetrics] = None
        
    def start_session(self, config: Dict[str, Any]) -> None:
        """開始追蹤會話"""
        self.session_metrics = SessionMetrics(
            session_id=self.session_id,
            start_time=time.time(),
            config=config,
            stages=[]
        )
        logger.info(f"⏱️ 開始性能追蹤會話: {self.session_id}")
    
    def start_stage(self, stage_name: str) -> StageMetrics:
        """開始追蹤階段"""
        if self.current_stage and not self.current_stage.end_time:
            # 自動結束前一個階段
            self.current_stage.finish()
        
        self.current_stage = StageMetrics(
            name=stage_name,
            start_time=time.time()
        )
        
        if self.session_metrics:
            self.session_metrics.stages.append(self.current_stage)
        
        logger.info(f"⏱️ 開始階段: {stage_name}")
        return self.current_stage
    
    def finish_stage(self, success: bool = True, error_message: Optional[str] = None, **metadata) -> None:
        """結束當前階段"""
        if self.current_stage:
            self.current_stage.finish(success, error_message, **metadata)
            duration = self.current_stage.duration or 0
            status = "✅" if success else "❌"
            logger.info(f"⏱️ 完成階段: {self.current_stage.name} {status} ({duration:.2f}s)")
    
    def finish_session(self, success: bool = True, output_files: Optional[Dict[str, str]] = None) -> SessionMetrics:
        """結束追蹤會話"""
        if not self.session_metrics:
            raise ValueError("尚未開始會話追蹤")
        
        # 結束當前階段（如果有）
        if self.current_stage and not self.current_stage.end_time:
            self.current_stage.finish()
        
        # 完成會話
        self.session_metrics.end_time = time.time()
        self.session_metrics.total_duration = self.session_metrics.end_time - self.session_metrics.start_time
        self.session_metrics.success = success
        self.session_metrics.output_files = output_files
        
        logger.info(f"⏱️ 完成會話: {self.session_id} ({self.session_metrics.total_duration:.2f}s)")
        return self.session_metrics
    
    def get_summary(self) -> Dict[str, Any]:
        """獲取性能摘要"""
        if not self.session_metrics:
            return {"error": "尚未開始會話追蹤"}
        
        total_time = self.session_metrics.total_duration or 0
        stages_summary = []
        
        for stage in self.session_metrics.stages:
            if stage.duration:
                percentage = (stage.duration / total_time * 100) if total_time > 0 else 0
                stages_summary.append({
                    "name": stage.name,
                    "duration": stage.duration,
                    "percentage": percentage,
                    "success": stage.success
                })
        
        return {
            "session_id": self.session_id,
            "total_duration": total_time,
            "stages_count": len(self.session_metrics.stages),
            "success": self.session_metrics.success,
            "stages": stages_summary
        }
    
    def save_metrics(self, output_dir: Optional[str] = None) -> str:
        """保存性能指標到文件"""
        if not self.session_metrics:
            raise ValueError("尚未完成會話追蹤")
        
        if output_dir:
            metrics_dir = Path(output_dir)
        else:
            metrics_dir = Path("./performance_logs")
        
        metrics_dir.mkdir(exist_ok=True)
        
        metrics_file = metrics_dir / f"performance_{self.session_id}.json"
        
        with open(metrics_file, 'w', encoding='utf-8') as f:
            json.dump(self.session_metrics.to_dict(), f, indent=2, ensure_ascii=False)
        
        logger.info(f"📊 性能指標已保存: {metrics_file}")
        return str(metrics_file)

def time_stage(stage_name: str):
    """裝飾器：自動計時方法執行時間"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # 檢查是否有性能追蹤器
            if hasattr(self, 'performance_tracker') and self.performance_tracker:
                self.performance_tracker.start_stage(stage_name)
                try:
                    result = func(self, *args, **kwargs)
                    self.performance_tracker.finish_stage(success=True)
                    return result
                except Exception as e:
                    self.performance_tracker.finish_stage(success=False, error_message=str(e))
                    raise
            else:
                return func(self, *args, **kwargs)
        return wrapper
    return decorator

class PerformanceReport:
    """性能報告生成器"""
    
    @staticmethod
    def format_duration(seconds: float) -> str:
        """格式化時間顯示"""
        if seconds < 1:
            return f"{seconds*1000:.0f}ms"
        elif seconds < 60:
            return f"{seconds:.2f}s"
        else:
            minutes = int(seconds // 60)
            remaining_seconds = seconds % 60
            return f"{minutes}m {remaining_seconds:.1f}s"
    
    @staticmethod
    def generate_console_report(tracker: PerformanceTracker) -> str:
        """生成控制台報告"""
        if not tracker.session_metrics:
            return "❌ 尚未完成性能追蹤"
        
        metrics = tracker.session_metrics
        total_time = metrics.total_duration or 0
        
        lines = []
        lines.append("=" * 60)
        lines.append("📊 播客生成性能報告")
        lines.append("=" * 60)
        lines.append(f"會話 ID: {metrics.session_id}")
        lines.append(f"開始時間: {datetime.fromtimestamp(metrics.start_time).strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"總耗時: {PerformanceReport.format_duration(total_time)}")
        lines.append(f"狀態: {'✅ 成功' if metrics.success else '❌ 失敗'}")
        lines.append("")
        
        # 配置信息
        lines.append("🔧 配置信息:")
        lines.append(f"  英語等級: {metrics.config.get('english_level', 'N/A')}")
        lines.append(f"  目標時長: {metrics.config.get('target_minutes', 'N/A')} 分鐘")
        lines.append(f"  輸入類型: {metrics.config.get('input_type', 'N/A')}")
        lines.append("")
        
        # 階段分析
        lines.append("⏱️ 各階段耗時:")
        for stage in metrics.stages:
            if stage.duration:
                percentage = (stage.duration / total_time * 100) if total_time > 0 else 0
                status = "✅" if stage.success else "❌"
                duration_str = PerformanceReport.format_duration(stage.duration)
                lines.append(f"  {status} {stage.name:<20} {duration_str:>8} ({percentage:5.1f}%)")
            else:
                lines.append(f"  ⚠️ {stage.name:<20} {'未完成':>8}")
        
        lines.append("")
        
        # 輸出文件
        if metrics.output_files:
            lines.append("📁 輸出文件:")
            for file_type, file_path in metrics.output_files.items():
                lines.append(f"  {file_type}: {file_path}")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    @staticmethod
    def generate_summary_report(tracker: PerformanceTracker) -> str:
        """生成簡要報告"""
        summary = tracker.get_summary()
        
        if "error" in summary:
            return f"❌ {summary['error']}"
        
        total_time = PerformanceReport.format_duration(summary['total_duration'])
        status = "✅ 成功" if summary['success'] else "❌ 失敗"
        
        return f"📊 {summary['session_id']}: {total_time} {status} ({summary['stages_count']} 階段)"

# 全局性能追蹤器實例
_global_tracker: Optional[PerformanceTracker] = None

def get_global_tracker() -> Optional[PerformanceTracker]:
    """獲取全局性能追蹤器"""
    return _global_tracker

def set_global_tracker(tracker: PerformanceTracker) -> None:
    """設置全局性能追蹤器"""
    global _global_tracker
    _global_tracker = tracker

def create_performance_tracker(session_id: Optional[str] = None) -> PerformanceTracker:
    """創建並設置全局性能追蹤器"""
    tracker = PerformanceTracker(session_id)
    set_global_tracker(tracker)
    return tracker