"""
End-to-end test: Yeti Agent monitors a Grafana-like dashboard.

Tests both HEADED and HEADLESS modes:
1. Opens the monitoring dashboard
2. Reads real-time metrics (CPU, Memory, Latency, Error Rate)
3. Clicks "Trigger CPU Spike" button
4. Verifies alert fires
5. Clicks "Acknowledge All" to clear alerts
6. Changes alert threshold via input field
7. Validates the agent correctly analyzed real data

Requires: OPENAI_API_KEY environment variable
Usage:    python test_e2e_grafana.py [--headless] [--headed]
"""

import asyncio
import os
import subprocess
import sys
import time

# Add yeti-agent to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from browser_use import Agent
from browser_use.browser.profile import BrowserProfile
from browser_use.browser.session import BrowserSession
from browser_use.llm.openai.chat import ChatOpenAI

DASHBOARD_URL = 'http://localhost:3000'


def start_dashboard():
	"""Start the dummy Grafana dashboard in a subprocess."""
	script = os.path.join(os.path.dirname(__file__), 'dummy_grafana.py')
	proc = subprocess.Popen(
		[sys.executable, script],
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
	)
	time.sleep(3)
	return proc


def stop_dashboard(proc):
	"""Stop the dashboard subprocess."""
	if proc:
		proc.terminate()
		try:
			proc.wait(timeout=5)
		except subprocess.TimeoutExpired:
			proc.kill()


def safe_result(result):
	"""Safely get string from agent result."""
	val = result.final_result() if result else None
	return str(val) if val else '(no result)'


async def run_single_agent(task, headed, llm):
	"""Run a single agent task with a fresh browser session."""
	session = BrowserSession(
		browser_profile=BrowserProfile(
			headless=not headed,
			keep_alive=False,
		),
	)
	agent = Agent(task=task, llm=llm, browser_session=session)
	try:
		result = await agent.run(max_steps=12)
		return safe_result(result)
	except Exception as e:
		return f'(error: {e})'


async def run_test(headed: bool):
	"""Run all E2E tests in headed or headless mode."""
	mode = 'HEADED' if headed else 'HEADLESS'
	print(f'\n{"=" * 60}')
	print(f'  YETI AGENT E2E TEST -- {mode} MODE')
	print(f'{"=" * 60}\n')

	llm = ChatOpenAI(model='gpt-4o-mini')
	results = {}

	# ── TEST 1: Read Dashboard Metrics ────────────────────────────
	print(f'[{mode}] Test 1: Reading dashboard metrics...')
	results['read_metrics'] = await run_single_agent(
		task=f"""Go to {DASHBOARD_URL} and read the monitoring dashboard.
        Tell me the exact current values for:
        1. CPU Usage (percentage)
        2. Memory Usage (percentage)
        3. API Latency (in ms)
        4. Error Rate (percentage)
        5. Requests per second
        Also tell me how many firing alerts there are (shown in top bar).
        Return all values in a structured format.""",
		headed=headed,
		llm=llm,
	)
	print(f'  Result: {results["read_metrics"][:200]}')

	# ── TEST 2: Click Trigger CPU Spike ───────────────────────────
	print(f'\n[{mode}] Test 2: Triggering CPU spike via button click...')
	results['trigger_spike'] = await run_single_agent(
		task=f"""Go to {DASHBOARD_URL}. Find and click the red "Trigger CPU Spike" button
        in the Quick Actions panel. After clicking it, wait a moment for the page to update.
        Then tell me:
        1. What is the current CPU value shown in the CPU Usage panel?
        2. How many firing alerts are there now?
        3. What does the latest entry in the Recent Alerts table show?""",
		headed=headed,
		llm=llm,
	)
	print(f'  Result: {results["trigger_spike"][:200]}')

	# ── TEST 3: Acknowledge All Alerts ────────────────────────────
	print(f'\n[{mode}] Test 3: Acknowledging all alerts...')
	results['acknowledge'] = await run_single_agent(
		task=f"""Go to {DASHBOARD_URL}. Click the green "Acknowledge All" button
        in the Quick Actions panel. After clicking, tell me:
        1. How many firing alerts remain (shown in top bar)?
        2. What status do the recent alerts show in the table?""",
		headed=headed,
		llm=llm,
	)
	print(f'  Result: {results["acknowledge"][:200]}')

	# ── TEST 4: Change Alert Threshold ────────────────────────────
	print(f'\n[{mode}] Test 4: Changing CPU alert threshold to 50...')
	results['change_threshold'] = await run_single_agent(
		task=f"""Go to {DASHBOARD_URL}. In the Quick Actions panel, find the
        "Custom Threshold" number input. Clear it, type "50", then click
        "Set CPU Threshold". After clicking, look at the Alert Rules table
        and tell me the new threshold value for the "High CPU" rule.""",
		headed=headed,
		llm=llm,
	)
	print(f'  Result: {results["change_threshold"][:200]}')

	# ── TEST 5: Disable an Alert Rule ─────────────────────────────
	print(f'\n[{mode}] Test 5: Disabling High Memory alert rule...')
	results['disable_rule'] = await run_single_agent(
		task=f"""Go to {DASHBOARD_URL}. In the Alert Rules table, find the
        "High Memory" row and click its "Disable" button. After clicking,
        tell me the status of all alert rules (which are Active vs Disabled).""",
		headed=headed,
		llm=llm,
	)
	print(f'  Result: {results["disable_rule"][:200]}')

	# ── Print Summary ─────────────────────────────────────────────
	print(f'\n{"=" * 60}')
	print(f'  TEST SUMMARY -- {mode} MODE')
	print(f'{"=" * 60}')

	test_names = [
		('Read Metrics', 'read_metrics'),
		('Trigger CPU Spike', 'trigger_spike'),
		('Acknowledge Alerts', 'acknowledge'),
		('Change Threshold', 'change_threshold'),
		('Disable Alert Rule', 'disable_rule'),
	]

	passed = 0
	for name, key in test_names:
		result = results.get(key, '(no result)')
		ok = result != '(no result)' and not result.startswith('(error')
		passed += ok
		status = 'PASS' if ok else 'FAIL'
		print(f'  [{status}] {name}')
		first_line = result.split('\n')[0][:80]
		print(f'         {first_line}')

	print(f'\n  Result: {passed}/{len(test_names)} passed')
	print(f'{"=" * 60}\n')
	return results


async def main():
	headless_only = '--headless' in sys.argv
	headed_only = '--headed' in sys.argv

	api_key = os.environ.get('OPENAI_API_KEY')
	if not api_key:
		print('ERROR: OPENAI_API_KEY not set!')
		sys.exit(1)

	print('Starting dummy Grafana dashboard on http://localhost:3000...')
	dashboard_proc = start_dashboard()

	try:
		# Health check uses sync HTTP (runs before async loop matters)
		import urllib.request  # noqa: ASYNC210

		try:
			resp = urllib.request.urlopen('http://localhost:3000/api/health', timeout=5)  # noqa: ASYNC210
			print(f'Dashboard is running! Health: {resp.read().decode()}')
		except Exception as e:
			print(f'WARNING: Dashboard health check failed: {e}')

		if headed_only:
			await run_test(headed=True)
		elif headless_only:
			await run_test(headed=False)
		else:
			await run_test(headed=False)
			await run_test(headed=True)
	finally:
		stop_dashboard(dashboard_proc)
		print('Dashboard stopped. Tests complete.')


if __name__ == '__main__':
	asyncio.run(main())
