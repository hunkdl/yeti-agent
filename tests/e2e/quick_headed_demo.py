"""
Quick headed demo: Watch Yeti Agent interact with a Grafana dashboard.
Shows visual cursor, clicks, and data reading.
Dashboard must already be running on localhost:3000.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from browser_use import Agent
from browser_use.browser.profile import BrowserProfile
from browser_use.browser.session import BrowserSession
from browser_use.llm.openai.chat import ChatOpenAI

DASHBOARD_URL = "http://localhost:3000"


async def main():
    llm = ChatOpenAI(model="gpt-4o-mini")

    # ── Demo 1: Read metrics + Click spike button + Acknowledge ──
    print("\n" + "=" * 60)
    print("  YETI AGENT — HEADED DEMO")
    print("  Watch the browser window for visual cursor indicators!")
    print("=" * 60 + "\n")

    session = BrowserSession(
        browser_profile=BrowserProfile(
            headless=False,
            keep_alive=True,  # Keep browser open between tasks
            demo_mode=True,   # Show agent log panel in browser
            highlight_elements=True,
            wait_between_actions=0.5,  # Slow down so user can see
        ),
    )

    print("[1/3] Reading dashboard metrics...")
    agent1 = Agent(
        task=f"""Go to {DASHBOARD_URL} and read ALL the monitoring metrics.
        Tell me the exact values for CPU Usage, Memory Usage, API Latency,
        Error Rate, and Requests/sec. Also count the firing alerts.""",
        llm=llm,
        browser_session=session,
    )
    result1 = await agent1.run(max_steps=8)
    r1 = result1.final_result() if result1 else "(no result)"
    print(f"  Result: {r1}\n")

    print("[2/3] Clicking 'Trigger CPU Spike' button...")
    agent2 = Agent(
        task=f"""On the current page ({DASHBOARD_URL}), click the red
        "Trigger CPU Spike" button. Wait 3 seconds, then read the new
        CPU value and tell me if an alert was triggered.""",
        llm=llm,
        browser_session=session,
    )
    result2 = await agent2.run(max_steps=8)
    r2 = result2.final_result() if result2 else "(no result)"
    print(f"  Result: {r2}\n")

    print("[3/3] Clicking 'Acknowledge All' then changing threshold...")
    agent3 = Agent(
        task=f"""On the current page ({DASHBOARD_URL}):
        1. Click the green "Acknowledge All" button
        2. Then change the Custom Threshold input to "50"
        3. Click "Set CPU Threshold"
        4. Finally click the "Disable" button next to "High Memory" rule
        Tell me the final state of all alert rules.""",
        llm=llm,
        browser_session=session,
    )
    result3 = await agent3.run(max_steps=12)
    r3 = result3.final_result() if result3 else "(no result)"
    print(f"  Result: {r3}\n")

    # Keep browser open for 10 seconds so user can see final state
    print("Browser staying open for 10 seconds so you can see the results...")
    await asyncio.sleep(10)

    await session.kill()
    print("\nDemo complete!")


if __name__ == "__main__":
    asyncio.run(main())
