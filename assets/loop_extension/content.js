/*
 * TKK Playlist Loop + Shuffle - content script.
 *
 * YouTube ignores `loop` / `shuffle` query parameters on the normal /watch page
 * (they only work in the embed player), so the only reliable way to enable them
 * on the watch page is to click YouTube's own "Loop" and "Shuffle" toggles in
 * the playlist panel.
 *
 * This script waits for the playlist panel to appear and clicks each toggle
 * exactly once per page load. Because a freshly launched Chrome window always
 * starts with both toggles OFF, a single click reliably turns each ON, and
 * YouTube keeps them on for the rest of the session (they survive the SPA
 * navigation between videos, so we never need to click again).
 */
(function () {
  "use strict";

  var LOOP_DONE = false;
  var SHUFFLE_DONE = false;
  var DEADLINE = Date.now() + 90 * 1000; // keep trying for up to 90s
  var POLL_MS = 1000;

  function onPlaylistPage() {
    // Only act when a playlist is actually loaded (?list=... present).
    return location.href.indexOf("list=") !== -1;
  }

  // Find a button in the playlist panel whose accessible label contains the
  // given keyword ("loop" or "shuffle"). The two labels are unambiguous.
  function findButton(keyword) {
    var panel = document.querySelector("ytd-playlist-panel-renderer");
    if (!panel) {
      return null;
    }
    var nodes = panel.querySelectorAll(
      "button, yt-icon-button, tp-yt-paper-icon-button, ytd-toggle-button-renderer, a[role='button']"
    );
    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      var label = (
        el.getAttribute("aria-label") ||
        el.getAttribute("title") ||
        ""
      ).toLowerCase();
      if (label.indexOf(keyword) !== -1) {
        return el;
      }
    }
    return null;
  }

  // Best-effort check whether a toggle is already active, so we never turn an
  // already-on toggle back off.
  function alreadyOn(btn, keyword) {
    var pressed = btn.getAttribute("aria-pressed");
    if (pressed === "true") {
      return true;
    }
    var label = (btn.getAttribute("aria-label") || "").toLowerCase();
    if (label.indexOf(keyword + " is on") !== -1) {
      return true;
    }
    if (keyword === "loop" && label.indexOf("looping") !== -1) {
      return true;
    }
    if (keyword === "shuffle" && label.indexOf("shuffling") !== -1) {
      return true;
    }
    return false;
  }

  // Try to enable one toggle. Returns true once it has been handled.
  function tryEnable(keyword) {
    var btn = findButton(keyword);
    if (!btn) {
      return false; // panel/button not rendered yet; keep polling
    }
    if (!alreadyOn(btn, keyword)) {
      try {
        btn.click();
      } catch (e) {
        return false;
      }
    }
    return true;
  }

  var timer = setInterval(function () {
    if (onPlaylistPage()) {
      if (!LOOP_DONE) {
        LOOP_DONE = tryEnable("loop");
      }
      if (!SHUFFLE_DONE) {
        SHUFFLE_DONE = tryEnable("shuffle");
      }
    }
    if ((LOOP_DONE && SHUFFLE_DONE) || Date.now() > DEADLINE) {
      clearInterval(timer);
    }
  }, POLL_MS);
})();
