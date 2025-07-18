#!/usr/bin/env python3
"""Performance analysis and reporting script.

This script provides tools for analyzing performance data, generating reports,
and identifying optimization opportunities from container performance tests.
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

try:
    from unified.performance.performance_collector import PerformanceCollector
except ImportError as e:
    print(f"Error importing performance modules: {e}")
    print("Please ensure you're running from the project root directory")
    sys.exit(1)

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class PerformanceAnalyzer:
    """Analyzes performance data and generates insights."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.collector = PerformanceCollector(data_dir)
        self.performance_data = {}
        self.baselines = {}

    def load_performance_data(self, filename: Optional[str] = None) -> bool:
        """Load performance data from file.

        Args:
            filename: Optional filename to load

        Returns:
            True if data loaded successfully
        """
        if filename:
            data_file = self.data_dir / filename
        else:
            # Find most recent performance data file
            data_files = list(self.data_dir.glob("lifecycle-performance-*.json"))
            if not data_files:
                print("No performance data files found")
                return False

            data_file = max(data_files, key=lambda f: f.stat().st_mtime)

        if not data_file.exists():
            print(f"Performance data file not found: {data_file}")
            return False

        try:
            with open(data_file) as f:
                data = json.load(f)

            self.performance_data = data
            self.baselines = data.get("baselines", {})

            print(f"Loaded performance data from: {data_file}")
            print(f"Data timestamp: {data.get('timestamp', 'Unknown')}")
            print(f"Environments: {len(data.get('environments', {}))}")

            return True

        except Exception as e:
            print(f"Error loading performance data: {e}")
            return False

    def analyze_startup_performance(self) -> Dict[str, Any]:
        """Analyze startup performance across environments.

        Returns:
            Analysis results
        """
        analysis = {
            "overall_stats": {},
            "environment_analysis": {},
            "container_analysis": {},
            "trends": {},
            "recommendations": [],
        }

        if not self.performance_data:
            return analysis

        environments = self.performance_data.get("environments", {})

        if not environments:
            return analysis

        # Overall statistics
        all_startup_times = []
        all_containers = []

        for env_name, env_data in environments.items():
            env_metrics = env_data.get("environment_metrics", {})
            avg_startup = env_metrics.get("average_startup_time")

            if avg_startup:
                all_startup_times.append(avg_startup)

            # Container analysis
            containers = env_data.get("containers", {})
            for container_name, container_data in containers.items():
                container_metrics = container_data.get("metrics", {})
                startup_duration = container_metrics.get("startup_duration")

                if startup_duration:
                    all_containers.append(
                        {"name": container_name, "environment": env_name, "startup_time": startup_duration}
                    )

        # Overall stats
        if all_startup_times:
            analysis["overall_stats"] = {
                "total_environments": len(environments),
                "average_startup_time": sum(all_startup_times) / len(all_startup_times),
                "min_startup_time": min(all_startup_times),
                "max_startup_time": max(all_startup_times),
                "startup_time_range": max(all_startup_times) - min(all_startup_times),
            }

        # Environment analysis
        for env_name, env_data in environments.items():
            env_metrics = env_data.get("environment_metrics", {})

            analysis["environment_analysis"][env_name] = {
                "container_count": env_metrics.get("container_count", 0),
                "average_startup_time": env_metrics.get("average_startup_time"),
                "slowest_container": env_metrics.get("slowest_container"),
                "fastest_container": env_metrics.get("fastest_container"),
                "health_check_failure_rate": env_metrics.get("health_check_failure_rate", 0),
            }

        # Container analysis
        if all_containers:
            # Sort by startup time
            sorted_containers = sorted(all_containers, key=lambda x: x["startup_time"], reverse=True)

            analysis["container_analysis"] = {
                "total_containers": len(all_containers),
                "slowest_containers": sorted_containers[:5],  # Top 5 slowest
                "fastest_containers": sorted_containers[-5:],  # Top 5 fastest
                "average_container_startup": sum(c["startup_time"] for c in all_containers) / len(all_containers),
            }

        # Generate recommendations
        analysis["recommendations"] = self._generate_startup_recommendations(analysis)

        return analysis

    def _generate_startup_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate startup performance recommendations.

        Args:
            analysis: Performance analysis data

        Returns:
            List of recommendations
        """
        recommendations = []

        # Check overall performance
        overall_stats = analysis.get("overall_stats", {})
        avg_startup = overall_stats.get("average_startup_time")

        if avg_startup:
            if avg_startup > 120:
                recommendations.append(
                    f"Overall average startup time is high ({avg_startup:.1f}s). Consider optimizing slow containers."
                )
            elif avg_startup > 60:
                recommendations.append(
                    f"Overall average startup time is moderate ({avg_startup:.1f}s). Room for improvement."
                )

        # Check environment-specific issues
        env_analysis = analysis.get("environment_analysis", {})
        slow_environments = []

        for env_name, env_data in env_analysis.items():
            env_startup = env_data.get("average_startup_time")
            if env_startup and env_startup > 90:
                slow_environments.append((env_name, env_startup))

        if slow_environments:
            slow_environments.sort(key=lambda x: x[1], reverse=True)
            for env_name, startup_time in slow_environments[:3]:
                recommendations.append(f"Environment {env_name} is slow ({startup_time:.1f}s startup)")

        # Check container-specific issues
        container_analysis = analysis.get("container_analysis", {})
        slowest_containers = container_analysis.get("slowest_containers", [])

        if slowest_containers:
            for container in slowest_containers[:3]:
                if container["startup_time"] > 60:
                    recommendations.append(
                        f"Container {container['name']} is slow ({container['startup_time']:.1f}s startup)"
                    )

        # Health check issues
        for env_name, env_data in env_analysis.items():
            failure_rate = env_data.get("health_check_failure_rate", 0)
            if failure_rate > 0.1:
                recommendations.append(
                    f"Environment {env_name} has high health check failure rate ({failure_rate:.1%})"
                )

        return recommendations

    def compare_environments(self) -> Dict[str, Any]:
        """Compare performance between environments.

        Returns:
            Comparison results
        """
        comparison = {"environment_comparison": {}, "performance_rankings": {}, "variance_analysis": {}}

        if not self.performance_data:
            return comparison

        environments = self.performance_data.get("environments", {})

        if len(environments) < 2:
            return comparison

        # Environment comparison
        env_metrics = {}
        for env_name, env_data in environments.items():
            metrics = env_data.get("environment_metrics", {})
            env_metrics[env_name] = {
                "startup_time": metrics.get("average_startup_time"),
                "container_count": metrics.get("container_count", 0),
                "failure_rate": metrics.get("health_check_failure_rate", 0),
            }

        comparison["environment_comparison"] = env_metrics

        # Performance rankings
        valid_envs = {k: v for k, v in env_metrics.items() if v["startup_time"] is not None}

        if valid_envs:
            sorted_by_startup = sorted(valid_envs.items(), key=lambda x: x[1]["startup_time"])
            comparison["performance_rankings"]["by_startup_time"] = [
                {"environment": env, "startup_time": metrics["startup_time"]} for env, metrics in sorted_by_startup
            ]

        # Variance analysis
        startup_times = [metrics["startup_time"] for metrics in valid_envs.values()]
        if len(startup_times) > 1:
            import statistics

            comparison["variance_analysis"] = {
                "mean": statistics.mean(startup_times),
                "stdev": statistics.stdev(startup_times),
                "variance": statistics.variance(startup_times),
                "coefficient_of_variation": statistics.stdev(startup_times) / statistics.mean(startup_times),
            }

        return comparison

    def analyze_trends(self, historical_files: List[str]) -> Dict[str, Any]:
        """Analyze performance trends over time.

        Args:
            historical_files: List of historical performance data files

        Returns:
            Trend analysis results
        """
        trends = {"time_series": {}, "performance_changes": {}, "trend_analysis": {}}

        # Load historical data
        historical_data = []
        for filename in historical_files:
            file_path = self.data_dir / filename
            if file_path.exists():
                try:
                    with open(file_path) as f:
                        data = json.load(f)
                        historical_data.append(
                            {"timestamp": data.get("timestamp"), "environments": data.get("environments", {})}
                        )
                except Exception as e:
                    logger.warning(f"Error loading historical file {filename}: {e}")

        # Sort by timestamp
        historical_data.sort(key=lambda x: x["timestamp"])

        # Analyze trends for each environment
        for env_name in self.performance_data.get("environments", {}):
            env_trends = []

            for data_point in historical_data:
                env_data = data_point["environments"].get(env_name, {})
                env_metrics = env_data.get("environment_metrics", {})
                startup_time = env_metrics.get("average_startup_time")

                if startup_time:
                    env_trends.append({"timestamp": data_point["timestamp"], "startup_time": startup_time})

            if len(env_trends) > 1:
                trends["time_series"][env_name] = env_trends

                # Calculate trend
                startup_times = [point["startup_time"] for point in env_trends]
                first_time = startup_times[0]
                last_time = startup_times[-1]

                trends["performance_changes"][env_name] = {
                    "first_measurement": first_time,
                    "last_measurement": last_time,
                    "absolute_change": last_time - first_time,
                    "percentage_change": ((last_time - first_time) / first_time) * 100,
                }

        return trends

    def generate_optimization_report(self) -> str:
        """Generate a comprehensive optimization report.

        Returns:
            Formatted report string
        """
        if not self.performance_data:
            return "No performance data available for analysis."

        # Perform analyses
        startup_analysis = self.analyze_startup_performance()
        env_comparison = self.compare_environments()

        # Generate report
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("CONTAINER PERFORMANCE OPTIMIZATION REPORT")
        report_lines.append("=" * 80)
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"Data source: {self.performance_data.get('timestamp', 'Unknown')}")
        report_lines.append("")

        # Overall statistics
        overall_stats = startup_analysis.get("overall_stats", {})
        if overall_stats:
            report_lines.append("OVERALL PERFORMANCE STATISTICS")
            report_lines.append("-" * 40)
            report_lines.append(f"Total Environments: {overall_stats['total_environments']}")
            report_lines.append(f"Average Startup Time: {overall_stats['average_startup_time']:.2f}s")
            report_lines.append(
                f"Startup Time Range: {overall_stats['min_startup_time']:.2f}s - {overall_stats['max_startup_time']:.2f}s"
            )
            report_lines.append(f"Performance Variance: {overall_stats['startup_time_range']:.2f}s")
            report_lines.append("")

        # Environment analysis
        env_analysis = startup_analysis.get("environment_analysis", {})
        if env_analysis:
            report_lines.append("ENVIRONMENT PERFORMANCE BREAKDOWN")
            report_lines.append("-" * 40)
            for env_name, env_data in env_analysis.items():
                startup_time = env_data.get("average_startup_time")
                container_count = env_data.get("container_count", 0)
                failure_rate = env_data.get("health_check_failure_rate", 0)

                status = (
                    "🔴" if startup_time and startup_time > 90 else "🟡" if startup_time and startup_time > 60 else "🟢"
                )

                report_lines.append(f"{status} {env_name}:")
                if startup_time:
                    report_lines.append(f"    Startup Time: {startup_time:.2f}s")
                report_lines.append(f"    Containers: {container_count}")
                if failure_rate > 0:
                    report_lines.append(f"    Health Failures: {failure_rate:.1%}")
                if env_data.get("slowest_container"):
                    report_lines.append(f"    Slowest Container: {env_data['slowest_container']}")
                report_lines.append("")

        # Container analysis
        container_analysis = startup_analysis.get("container_analysis", {})
        if container_analysis:
            report_lines.append("CONTAINER PERFORMANCE ANALYSIS")
            report_lines.append("-" * 40)

            slowest = container_analysis.get("slowest_containers", [])
            if slowest:
                report_lines.append("Slowest Containers:")
                for i, container in enumerate(slowest[:5], 1):
                    report_lines.append(
                        f"  {i}. {container['name']} ({container['environment']}): {container['startup_time']:.2f}s"
                    )
                report_lines.append("")

            fastest = container_analysis.get("fastest_containers", [])
            if fastest:
                report_lines.append("Fastest Containers:")
                for i, container in enumerate(fastest[:5], 1):
                    report_lines.append(
                        f"  {i}. {container['name']} ({container['environment']}): {container['startup_time']:.2f}s"
                    )
                report_lines.append("")

        # Environment comparison
        rankings = env_comparison.get("performance_rankings", {})
        if rankings:
            report_lines.append("ENVIRONMENT PERFORMANCE RANKINGS")
            report_lines.append("-" * 40)
            by_startup = rankings.get("by_startup_time", [])
            for i, env_data in enumerate(by_startup, 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                report_lines.append(f"{medal} {env_data['environment']}: {env_data['startup_time']:.2f}s")
            report_lines.append("")

        # Recommendations
        recommendations = startup_analysis.get("recommendations", [])
        if recommendations:
            report_lines.append("OPTIMIZATION RECOMMENDATIONS")
            report_lines.append("-" * 40)
            for i, rec in enumerate(recommendations, 1):
                report_lines.append(f"{i}. {rec}")
            report_lines.append("")

        # Variance analysis
        variance = env_comparison.get("variance_analysis", {})
        if variance:
            report_lines.append("PERFORMANCE CONSISTENCY ANALYSIS")
            report_lines.append("-" * 40)
            cv = variance.get("coefficient_of_variation", 0)
            if cv < 0.1:
                consistency = "🟢 Very Consistent"
            elif cv < 0.2:
                consistency = "🟡 Moderately Consistent"
            else:
                consistency = "🔴 Inconsistent"

            report_lines.append(f"Consistency Rating: {consistency}")
            report_lines.append(f"Coefficient of Variation: {cv:.3f}")
            report_lines.append(f"Standard Deviation: {variance.get('stdev', 0):.2f}s")
            report_lines.append("")

        return "\n".join(report_lines)

    def export_analysis(self, output_file: str) -> None:
        """Export analysis results to file.

        Args:
            output_file: Output file path
        """
        analysis_data = {
            "timestamp": datetime.now().isoformat(),
            "startup_analysis": self.analyze_startup_performance(),
            "environment_comparison": self.compare_environments(),
            "optimization_report": self.generate_optimization_report(),
        }

        output_path = self.data_dir / output_file

        with open(output_path, "w") as f:
            json.dump(analysis_data, f, indent=2)

        print(f"Analysis exported to: {output_path}")


def main():
    """Main entry point for the performance analyzer."""
    parser = argparse.ArgumentParser(
        description="Analyze container performance data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze latest performance data
  python scripts/analyze_performance.py

  # Analyze specific file
  python scripts/analyze_performance.py --file lifecycle-performance-20240115_103000.json

  # Generate optimization report
  python scripts/analyze_performance.py --report

  # Export analysis to file
  python scripts/analyze_performance.py --export analysis_results.json

  # Compare environments
  python scripts/analyze_performance.py --compare
        """,
    )

    parser.add_argument("--file", type=str, help="Specific performance data file to analyze")
    parser.add_argument(
        "--data-dir",
        type=str,
        default="performance_data",
        help="Performance data directory (default: performance_data)",
    )
    parser.add_argument("--report", action="store_true", help="Generate optimization report")
    parser.add_argument("--compare", action="store_true", help="Compare environments")
    parser.add_argument("--export", type=str, help="Export analysis to file")
    parser.add_argument("--trends", type=str, nargs="+", help="Analyze trends from historical files")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    # Configure logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Initialize analyzer
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        data_dir = project_root / args.data_dir

    analyzer = PerformanceAnalyzer(data_dir)

    print("Performance Data Analyzer")
    print(f"Data Directory: {data_dir}")

    # Load performance data
    if not analyzer.load_performance_data(args.file):
        sys.exit(1)

    try:
        # Execute requested analysis
        if args.report:
            print("\n" + analyzer.generate_optimization_report())

        if args.compare:
            print("\nEnvironment Comparison:")
            comparison = analyzer.compare_environments()

            rankings = comparison.get("performance_rankings", {})
            if rankings:
                print("Performance Rankings:")
                for env_data in rankings.get("by_startup_time", []):
                    print(f"  {env_data['environment']}: {env_data['startup_time']:.2f}s")

            variance = comparison.get("variance_analysis", {})
            if variance:
                print("\nPerformance Consistency:")
                print(f"  Coefficient of Variation: {variance.get('coefficient_of_variation', 0):.3f}")
                print(f"  Standard Deviation: {variance.get('stdev', 0):.2f}s")

        if args.trends:
            print("\nTrend Analysis:")
            trends = analyzer.analyze_trends(args.trends)

            for env_name, changes in trends.get("performance_changes", {}).items():
                change_pct = changes.get("percentage_change", 0)
                trend_indicator = "📈" if change_pct > 5 else "📉" if change_pct < -5 else "📊"
                print(f"  {trend_indicator} {env_name}: {change_pct:+.1f}% change")

        if args.export:
            analyzer.export_analysis(args.export)

        # Default analysis if no specific options
        if not any([args.report, args.compare, args.trends, args.export]):
            startup_analysis = analyzer.analyze_startup_performance()

            print("\nStartup Performance Summary:")
            overall_stats = startup_analysis.get("overall_stats", {})
            if overall_stats:
                print(f"  Average Startup Time: {overall_stats['average_startup_time']:.2f}s")
                print(
                    f"  Performance Range: {overall_stats['min_startup_time']:.2f}s - {overall_stats['max_startup_time']:.2f}s"
                )

            recommendations = startup_analysis.get("recommendations", [])
            if recommendations:
                print("\nTop Recommendations:")
                for i, rec in enumerate(recommendations[:3], 1):
                    print(f"  {i}. {rec}")

    except Exception as e:
        logger.error(f"Analysis error: {e}")
        print(f"❌ Analysis failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
