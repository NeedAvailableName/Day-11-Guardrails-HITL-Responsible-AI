"""
Monitoring and Alerting for Lab 11 Production Pipeline
"""
import time

class SecurityMonitor:
    """Tracks metrics across plugins and fires alerts when safety thresholds are breached."""

    def __init__(self, plugins, block_threshold=0.2):
        """
        Args:
            plugins: List of plugin instances (RateLimit, Input, Output, Judge)
            block_threshold: Fraction (0-1) of blocked requests that triggers an alert
        """
        self.plugins = {p.name: p for p in plugins if hasattr(p, 'name')}
        self.block_threshold = block_threshold
        self.total_requests = 0

    def check_metrics(self):
        """Analyze current stats and print alerts."""
        print("\n" + "-" * 50)
        print("SECURITY MONITORING REPORT")
        print("-" * 50)

        # 1. Rate Limiting
        rl = self.plugins.get("rate_limiter")
        if rl:
            print(f"  Rate Limit Hits: {rl.block_count}")
            if rl.block_count > 5:
                print("  [ALERT] High volume of rate-limit hits detected! Potential DDoS or scraping.")

        # 2. Input/Output Blocks
        input_g = self.plugins.get("input_guardrail")
        output_g = self.plugins.get("output_guardrail")
        
        total_blocked = 0
        if input_g:
            total_blocked += getattr(input_g, "blocked_count", 0)
            print(f"  Input Guardrail Blocks: {getattr(input_g, 'blocked_count', 0)}")
        
        if output_g:
            total_blocked += getattr(output_g, "blocked_count", 0)
            print(f"  Output Guardrail Blocks: {getattr(output_g, 'blocked_count', 0)}")

        # 3. Judge Failures
        judge = self.plugins.get("enhanced_judge")
        if judge:
            print(f"  QA Judge Failures: {judge.fail_count}")
            if judge.fail_count > 3:
                print("  [ALERT] Multiple judge failures! Model output quality is degrades.")

        print("-" * 50)
        return total_blocked
