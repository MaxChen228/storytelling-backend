#!/usr/bin/env python3
"""
播客生成器性能分析工具
分析和可視化性能指標數據
"""

import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import statistics

from performance_tracker import PerformanceReport


class PerformanceAnalyzer:
    """性能分析器"""
    
    def __init__(self, data_dir: str = "./performance_logs"):
        self.data_dir = Path(data_dir)
        self.metrics_files = list(self.data_dir.glob("performance_*.json"))
        
    def load_all_sessions(self) -> List[Dict[str, Any]]:
        """載入所有會話數據"""
        sessions = []
        for file_path in self.metrics_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                    sessions.append(session_data)
            except Exception as e:
                print(f"⚠️ 載入 {file_path} 失敗: {e}")
        
        return sorted(sessions, key=lambda x: x['start_time'], reverse=True)
    
    def analyze_session_times(self, sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析會話時間統計"""
        if not sessions:
            return {"error": "無可用數據"}
        
        total_times = [s['total_duration'] for s in sessions if s.get('total_duration')]
        success_sessions = [s for s in sessions if s.get('success', False)]
        failed_sessions = [s for s in sessions if not s.get('success', True)]
        
        analysis = {
            "total_sessions": len(sessions),
            "success_count": len(success_sessions),
            "failure_count": len(failed_sessions),
            "success_rate": len(success_sessions) / len(sessions) * 100 if sessions else 0,
            "timing_stats": {}
        }
        
        if total_times:
            analysis["timing_stats"] = {
                "average_duration": statistics.mean(total_times),
                "median_duration": statistics.median(total_times),
                "min_duration": min(total_times),
                "max_duration": max(total_times),
                "std_deviation": statistics.stdev(total_times) if len(total_times) > 1 else 0
            }
        
        return analysis
    
    def analyze_stage_performance(self, sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析各階段性能"""
        stage_data = {}
        
        for session in sessions:
            if not session.get('success', False):
                continue
                
            for stage in session.get('stages', []):
                stage_name = stage['name']
                if stage_name not in stage_data:
                    stage_data[stage_name] = []
                
                if stage.get('duration'):
                    stage_data[stage_name].append(stage['duration'])
        
        stage_analysis = {}
        for stage_name, durations in stage_data.items():
            if durations:
                stage_analysis[stage_name] = {
                    "count": len(durations),
                    "average": statistics.mean(durations),
                    "median": statistics.median(durations),
                    "min": min(durations),
                    "max": max(durations),
                    "std_dev": statistics.stdev(durations) if len(durations) > 1 else 0
                }
        
        return stage_analysis
    
    def analyze_configuration_impact(self, sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析配置對性能的影響"""
        config_groups = {
            "english_level": {},
            "target_minutes": {},
            "input_type": {},
            "use_podcastfy_tts": {}
        }
        
        for session in sessions:
            if not session.get('success', False) or not session.get('total_duration'):
                continue
                
            config = session.get('config', {})
            duration = session['total_duration']
            
            for config_key in config_groups.keys():
                if config_key in config:
                    value = str(config[config_key])
                    if value not in config_groups[config_key]:
                        config_groups[config_key][value] = []
                    config_groups[config_key][value].append(duration)
        
        # 計算每個配置組的統計數據
        config_analysis = {}
        for config_key, groups in config_groups.items():
            config_analysis[config_key] = {}
            for value, durations in groups.items():
                if len(durations) >= 2:  # 至少需要2個數據點
                    config_analysis[config_key][value] = {
                        "count": len(durations),
                        "average": statistics.mean(durations),
                        "median": statistics.median(durations)
                    }
        
        return config_analysis
    
    def generate_performance_trends(self, sessions: List[Dict[str, Any]], days: int = 7) -> Dict[str, Any]:
        """生成性能趨勢分析"""
        cutoff_time = datetime.now().timestamp() - (days * 24 * 3600)
        recent_sessions = [s for s in sessions if s['start_time'] > cutoff_time]
        
        if not recent_sessions:
            return {"error": f"最近 {days} 天內無數據"}
        
        # 按日期分組
        daily_data = {}
        for session in recent_sessions:
            date_str = datetime.fromtimestamp(session['start_time']).strftime('%Y-%m-%d')
            if date_str not in daily_data:
                daily_data[date_str] = {"sessions": [], "total_time": 0, "success_count": 0}
            
            daily_data[date_str]["sessions"].append(session)
            if session.get('total_duration'):
                daily_data[date_str]["total_time"] += session['total_duration']
            if session.get('success', False):
                daily_data[date_str]["success_count"] += 1
        
        # 計算每日統計
        trends = {}
        for date, data in daily_data.items():
            session_count = len(data["sessions"])
            trends[date] = {
                "session_count": session_count,
                "average_time": data["total_time"] / session_count if session_count > 0 else 0,
                "success_rate": data["success_count"] / session_count * 100 if session_count > 0 else 0
            }
        
        return {"period_days": days, "daily_trends": trends}
    
    def find_performance_issues(self, sessions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """識別性能問題"""
        issues = []
        
        if not sessions:
            return issues
        
        # 檢查失敗率
        failure_rate = len([s for s in sessions if not s.get('success', True)]) / len(sessions) * 100
        if failure_rate > 10:  # 失敗率超過10%
            issues.append({
                "type": "high_failure_rate",
                "severity": "high" if failure_rate > 25 else "medium",
                "description": f"失敗率過高: {failure_rate:.1f}%",
                "recommendation": "檢查 API 配額、網路連接或配置問題"
            })
        
        # 檢查平均時間
        successful_sessions = [s for s in sessions if s.get('success', False) and s.get('total_duration')]
        if successful_sessions:
            avg_time = statistics.mean([s['total_duration'] for s in successful_sessions])
            if avg_time > 300:  # 超過5分鐘
                issues.append({
                    "type": "slow_performance",
                    "severity": "medium",
                    "description": f"平均生成時間過長: {avg_time:.1f}秒",
                    "recommendation": "考慮縮短目標長度或檢查網路延遲"
                })
        
        # 檢查時間變異性
        if len(successful_sessions) > 5:
            durations = [s['total_duration'] for s in successful_sessions]
            std_dev = statistics.stdev(durations)
            mean_duration = statistics.mean(durations)
            
            if std_dev / mean_duration > 0.5:  # 變異係數超過50%
                issues.append({
                    "type": "inconsistent_performance",
                    "severity": "low",
                    "description": f"性能不穩定: 標準差 {std_dev:.1f}秒",
                    "recommendation": "檢查系統負載或 API 響應時間變化"
                })
        
        return issues
    
    def generate_comprehensive_report(self) -> str:
        """生成綜合性能報告"""
        sessions = self.load_all_sessions()
        
        if not sessions:
            return "❌ 無可用的性能數據"
        
        # 執行各種分析
        session_analysis = self.analyze_session_times(sessions)
        stage_analysis = self.analyze_stage_performance(sessions)
        config_analysis = self.analyze_configuration_impact(sessions)
        trends = self.generate_performance_trends(sessions)
        issues = self.find_performance_issues(sessions)
        
        # 生成報告
        lines = []
        lines.append("=" * 80)
        lines.append("📊 播客生成器綜合性能分析報告")
        lines.append("=" * 80)
        lines.append(f"報告生成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"數據來源: {len(sessions)} 個會話")
        lines.append("")
        
        # 會話統計
        lines.append("📈 會話統計:")
        lines.append(f"  總會話數: {session_analysis['total_sessions']}")
        lines.append(f"  成功數: {session_analysis['success_count']}")
        lines.append(f"  失敗數: {session_analysis['failure_count']}")
        lines.append(f"  成功率: {session_analysis['success_rate']:.1f}%")
        lines.append("")
        
        # 時間統計
        if session_analysis.get('timing_stats'):
            stats = session_analysis['timing_stats']
            lines.append("⏱️ 時間統計:")
            lines.append(f"  平均耗時: {PerformanceReport.format_duration(stats['average_duration'])}")
            lines.append(f"  中位數: {PerformanceReport.format_duration(stats['median_duration'])}")
            lines.append(f"  最短時間: {PerformanceReport.format_duration(stats['min_duration'])}")
            lines.append(f"  最長時間: {PerformanceReport.format_duration(stats['max_duration'])}")
            lines.append(f"  標準差: {PerformanceReport.format_duration(stats['std_deviation'])}")
            lines.append("")
        
        # 階段分析
        if stage_analysis:
            lines.append("🔍 各階段性能分析:")
            for stage_name, stats in stage_analysis.items():
                lines.append(f"  {stage_name}:")
                lines.append(f"    平均: {PerformanceReport.format_duration(stats['average'])}")
                lines.append(f"    範圍: {PerformanceReport.format_duration(stats['min'])} - {PerformanceReport.format_duration(stats['max'])}")
                lines.append(f"    樣本數: {stats['count']}")
            lines.append("")
        
        # 配置影響分析
        if config_analysis:
            lines.append("⚙️ 配置對性能的影響:")
            for config_key, groups in config_analysis.items():
                if groups:
                    lines.append(f"  {config_key}:")
                    for value, stats in groups.items():
                        lines.append(f"    {value}: {PerformanceReport.format_duration(stats['average'])} (樣本數: {stats['count']})")
            lines.append("")
        
        # 性能問題
        if issues:
            lines.append("⚠️ 發現的性能問題:")
            for issue in issues:
                severity_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}
                icon = severity_icon.get(issue['severity'], "ℹ️")
                lines.append(f"  {icon} {issue['description']}")
                lines.append(f"     建議: {issue['recommendation']}")
            lines.append("")
        else:
            lines.append("✅ 未發現明顯的性能問題")
            lines.append("")
        
        # 趨勢分析
        if trends.get('daily_trends'):
            lines.append(f"📊 最近 {trends['period_days']} 天趨勢:")
            for date, data in sorted(trends['daily_trends'].items()):
                lines.append(f"  {date}: {data['session_count']} 會話, "
                           f"平均 {PerformanceReport.format_duration(data['average_time'])}, "
                           f"成功率 {data['success_rate']:.1f}%")
            lines.append("")
        
        lines.append("=" * 80)
        
        return "\n".join(lines)


def main():
    """主程序"""
    parser = argparse.ArgumentParser(description="播客生成器性能分析工具")
    parser.add_argument("--data-dir", default="./performance_logs", 
                       help="性能數據目錄 (默認: ./performance_logs)")
    parser.add_argument("--session", help="分析特定會話 ID")
    parser.add_argument("--summary", action="store_true", help="顯示簡要摘要")
    parser.add_argument("--full-report", action="store_true", help="生成完整報告")
    parser.add_argument("--trends", type=int, default=7, help="趨勢分析天數 (默認: 7)")
    
    args = parser.parse_args()
    
    analyzer = PerformanceAnalyzer(args.data_dir)
    
    if not analyzer.metrics_files:
        print(f"❌ 在 {args.data_dir} 中未找到性能數據文件")
        return
    
    print(f"📊 找到 {len(analyzer.metrics_files)} 個性能數據文件")
    
    if args.session:
        # 分析特定會話
        session_file = analyzer.data_dir / f"performance_{args.session}.json"
        if session_file.exists():
            with open(session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            print(f"\n會話 {args.session} 詳細分析:")
            print("-" * 60)
            print(f"開始時間: {session_data.get('start_datetime', 'N/A')}")
            print(f"總耗時: {PerformanceReport.format_duration(session_data.get('total_duration', 0))}")
            print(f"狀態: {'✅ 成功' if session_data.get('success') else '❌ 失敗'}")
            
            if session_data.get('stages'):
                print(f"\n階段詳情:")
                for stage in session_data['stages']:
                    status = "✅" if stage.get('success') else "❌"
                    duration = PerformanceReport.format_duration(stage.get('duration', 0))
                    print(f"  {status} {stage['name']}: {duration}")
        else:
            print(f"❌ 會話文件不存在: {session_file}")
    
    elif args.summary:
        # 顯示簡要摘要
        sessions = analyzer.load_all_sessions()
        session_analysis = analyzer.analyze_session_times(sessions)
        
        print(f"\n📊 性能摘要:")
        print(f"總會話數: {session_analysis['total_sessions']}")
        print(f"成功率: {session_analysis['success_rate']:.1f}%")
        if session_analysis.get('timing_stats'):
            avg_time = session_analysis['timing_stats']['average_duration']
            print(f"平均耗時: {PerformanceReport.format_duration(avg_time)}")
    
    elif args.full_report:
        # 生成完整報告
        report = analyzer.generate_comprehensive_report()
        print(report)
        
        # 保存報告到文件
        report_file = analyzer.data_dir / f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n📄 完整報告已保存至: {report_file}")
    
    else:
        # 默認顯示最近的會話
        sessions = analyzer.load_all_sessions()
        print(f"\n最近 5 個會話:")
        print("-" * 60)
        for session in sessions[:5]:
            session_id = session['session_id']
            start_time = datetime.fromtimestamp(session['start_time']).strftime('%m-%d %H:%M')
            duration = PerformanceReport.format_duration(session.get('total_duration', 0))
            status = "✅" if session.get('success') else "❌"
            
            print(f"{status} {session_id} | {start_time} | {duration}")
        
        print(f"\n💡 使用 --full-report 查看完整分析報告")
        print(f"💡 使用 --session <session_id> 查看特定會話詳情")


if __name__ == "__main__":
    main()