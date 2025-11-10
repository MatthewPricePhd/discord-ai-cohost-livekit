#!/usr/bin/env python3
"""
Simple runner script for Discord AI Co-Host Bot
"""
import sys
import asyncio

if __name__ == "__main__":
    try:
        from src.main import main
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
        sys.exit(0)
    except Exception as e:
        print(f"Failed to start AI Co-Host Bot: {e}")
        sys.exit(1)