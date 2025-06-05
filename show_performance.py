#!/usr/bin/env python3
"""
パフォーマンスレポート表示スクリプト
"""
from utils import PerformanceReporter, print_banner

def main():
    print_banner()
    
    reporter = PerformanceReporter()
    reporter.print_report()

if __name__ == "__main__":
    main()