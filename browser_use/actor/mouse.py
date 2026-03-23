"""Mouse class for mouse operations."""

import logging

from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from cdp_use.cdp.input.commands import DispatchMouseEventParameters, SynthesizeScrollGestureParameters
	from cdp_use.cdp.input.types import MouseButton

	from browser_use.browser.session import BrowserSession

logger = logging.getLogger(__name__)

# JavaScript to inject a visual cursor overlay into the page
_VISUAL_CURSOR_JS = r"""
(function() {
  if (window.__yetiCursorActive) return;
  window.__yetiCursorActive = true;

  // Create cursor element
  var cursor = document.createElement('div');
  cursor.id = '__yeti-visual-cursor';
  cursor.style.cssText = 'position:fixed;width:20px;height:20px;border-radius:50%;background:rgba(255,68,68,0.7);border:2px solid #ff4444;pointer-events:none;z-index:2147483647;transition:left 0.15s ease-out,top 0.15s ease-out;transform:translate(-50%,-50%);box-shadow:0 0 8px rgba(255,68,68,0.5);display:none;';
  document.body.appendChild(cursor);

  // Create click ripple element
  var ripple = document.createElement('div');
  ripple.id = '__yeti-click-ripple';
  ripple.style.cssText = 'position:fixed;width:40px;height:40px;border-radius:50%;border:3px solid #ff4444;pointer-events:none;z-index:2147483646;transform:translate(-50%,-50%);opacity:0;display:none;';
  document.body.appendChild(ripple);

  window.__yetiMoveCursor = function(x, y) {
    cursor.style.display = 'block';
    cursor.style.left = x + 'px';
    cursor.style.top = y + 'px';
  };

  window.__yetiClickEffect = function(x, y) {
    cursor.style.display = 'block';
    cursor.style.left = x + 'px';
    cursor.style.top = y + 'px';
    // Pulse the cursor
    cursor.style.background = 'rgba(255,255,0,0.9)';
    cursor.style.width = '16px';
    cursor.style.height = '16px';
    setTimeout(function() {
      cursor.style.background = 'rgba(255,68,68,0.7)';
      cursor.style.width = '20px';
      cursor.style.height = '20px';
    }, 200);
    // Show ripple
    ripple.style.display = 'block';
    ripple.style.left = x + 'px';
    ripple.style.top = y + 'px';
    ripple.style.opacity = '1';
    ripple.style.width = '20px';
    ripple.style.height = '20px';
    ripple.style.transition = 'none';
    setTimeout(function() {
      ripple.style.transition = 'all 0.4s ease-out';
      ripple.style.width = '60px';
      ripple.style.height = '60px';
      ripple.style.opacity = '0';
    }, 10);
  };
})();
"""


class Mouse:
	"""Mouse operations for a target."""

	def __init__(self, browser_session: 'BrowserSession', session_id: str | None = None, target_id: str | None = None):
		self._browser_session = browser_session
		self._client = browser_session.cdp_client
		self._session_id = session_id
		self._target_id = target_id

	async def _show_visual_cursor(self, x: int, y: int, is_click: bool = False) -> None:
		"""Show a visual cursor indicator at the given coordinates (headed mode only)."""
		try:
			if self._browser_session.browser_profile.headless:
				return
			# Inject the cursor overlay if not already present
			await self._client.send.Runtime.evaluate(
				params={'expression': _VISUAL_CURSOR_JS, 'returnByValue': True},
				session_id=self._session_id,
			)
			# Move or click
			if is_click:
				await self._client.send.Runtime.evaluate(
					params={'expression': f'window.__yetiClickEffect && window.__yetiClickEffect({x}, {y})', 'returnByValue': True},
					session_id=self._session_id,
				)
			else:
				await self._client.send.Runtime.evaluate(
					params={'expression': f'window.__yetiMoveCursor && window.__yetiMoveCursor({x}, {y})', 'returnByValue': True},
					session_id=self._session_id,
				)
		except Exception:
			pass  # Visual cursor is non-critical

	async def click(self, x: int, y: int, button: 'MouseButton' = 'left', click_count: int = 1) -> None:
		"""Click at the specified coordinates."""
		# Show visual cursor at click position
		await self._show_visual_cursor(x, y, is_click=True)

		# Mouse press
		press_params: 'DispatchMouseEventParameters' = {
			'type': 'mousePressed',
			'x': x,
			'y': y,
			'button': button,
			'clickCount': click_count,
		}
		await self._client.send.Input.dispatchMouseEvent(
			press_params,
			session_id=self._session_id,
		)

		# Mouse release
		release_params: 'DispatchMouseEventParameters' = {
			'type': 'mouseReleased',
			'x': x,
			'y': y,
			'button': button,
			'clickCount': click_count,
		}
		await self._client.send.Input.dispatchMouseEvent(
			release_params,
			session_id=self._session_id,
		)

	async def down(self, button: 'MouseButton' = 'left', click_count: int = 1) -> None:
		"""Press mouse button down."""
		params: 'DispatchMouseEventParameters' = {
			'type': 'mousePressed',
			'x': 0,  # Will use last mouse position
			'y': 0,
			'button': button,
			'clickCount': click_count,
		}
		await self._client.send.Input.dispatchMouseEvent(
			params,
			session_id=self._session_id,
		)

	async def up(self, button: 'MouseButton' = 'left', click_count: int = 1) -> None:
		"""Release mouse button."""
		params: 'DispatchMouseEventParameters' = {
			'type': 'mouseReleased',
			'x': 0,  # Will use last mouse position
			'y': 0,
			'button': button,
			'clickCount': click_count,
		}
		await self._client.send.Input.dispatchMouseEvent(
			params,
			session_id=self._session_id,
		)

	async def move(self, x: int, y: int, steps: int = 1) -> None:
		"""Move mouse to the specified coordinates."""
		# TODO: Implement smooth movement with multiple steps if needed
		_ = steps  # Acknowledge parameter for future use

		# Show visual cursor movement
		await self._show_visual_cursor(x, y, is_click=False)

		params: 'DispatchMouseEventParameters' = {'type': 'mouseMoved', 'x': x, 'y': y}
		await self._client.send.Input.dispatchMouseEvent(params, session_id=self._session_id)

	async def scroll(self, x: int = 0, y: int = 0, delta_x: int | None = None, delta_y: int | None = None) -> None:
		"""Scroll the page using robust CDP methods."""
		if not self._session_id:
			raise RuntimeError('Session ID is required for scroll operations')

		# Method 1: Try mouse wheel event (most reliable)
		try:
			# Get viewport dimensions
			layout_metrics = await self._client.send.Page.getLayoutMetrics(session_id=self._session_id)
			viewport_width = layout_metrics['layoutViewport']['clientWidth']
			viewport_height = layout_metrics['layoutViewport']['clientHeight']

			# Use provided coordinates or center of viewport
			scroll_x = x if x > 0 else viewport_width / 2
			scroll_y = y if y > 0 else viewport_height / 2

			# Calculate scroll deltas (positive = down/right)
			scroll_delta_x = delta_x or 0
			scroll_delta_y = delta_y or 0

			# Dispatch mouse wheel event
			await self._client.send.Input.dispatchMouseEvent(
				params={
					'type': 'mouseWheel',
					'x': scroll_x,
					'y': scroll_y,
					'deltaX': scroll_delta_x,
					'deltaY': scroll_delta_y,
				},
				session_id=self._session_id,
			)
			return

		except Exception:
			pass

		# Method 2: Fallback to synthesizeScrollGesture
		try:
			params: 'SynthesizeScrollGestureParameters' = {'x': x, 'y': y, 'xDistance': delta_x or 0, 'yDistance': delta_y or 0}
			await self._client.send.Input.synthesizeScrollGesture(
				params,
				session_id=self._session_id,
			)
		except Exception:
			# Method 3: JavaScript fallback
			scroll_js = f'window.scrollBy({delta_x or 0}, {delta_y or 0})'
			await self._client.send.Runtime.evaluate(
				params={'expression': scroll_js, 'returnByValue': True},
				session_id=self._session_id,
			)
