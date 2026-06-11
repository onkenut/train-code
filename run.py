#!/usr/bin/env python3
"""SmartLit - 智能文献管理器启动脚本"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from smartlit.main import main

if __name__ == "__main__":
    main()
