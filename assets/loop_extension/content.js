/*
 * TKK Playlist Loop + Shuffle + Autoplay - content script.
 *
 * YouTube ignores `loop` / `shuffle` query parameters on the normal /watch page
 * (they only work in the embed player), so the only reliable way to enable them
 * on the watch page is to click YouTube's own "Loop" and "Shuffle" toggles in
 * the playlist panel.
 *
 * In addition, Chrome does not autoplay media in background / non-active tabs,
 * so when several playlist tabs are opened per window only the visible one
 * starts. Because this content script runs in EVERY tab (visible or hidden), it
 * also force-starts playback by calling video.play() / clicking the play button
 * until the video is playing. Combined with the launch flag
 * --autoplay-policy=no-user-gesture-required, this makes every tab play.
 *
 * The loop/shuffle toggles are clicked exactly once per page load; the play
 * watchdog keeps running so a tab that gets paused (e.g. a "Video paused,
 * continue watching?" prompt, or a late-loading player) is resumed.
 */
(function () {
  "use strict";

  var LOOP_DONE = false;
  var SHUFFLE_DONE = false;
  var TOGGLE_DEADLINE = Date.now() + 90 * 1000; // try toggles for up to 90s
  var TOGGLE_POLL_MS = 1000;
  var PLAY_POLL_MS = 2500;

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

  // Force the video to play if it is paused. Runs in every tab, including
  // hidden/background ones, so all playlists start rather than only the visible
  // one.
  function ensurePlaying() {
    var video = document.querySelector("video");
    if (!video) {
      return;
    }
    if (video.paused) {
      var promise = null;
      try {
        promise = video.play();
      } catch (e) {
        promise = null;
      }
      if (promise && typeof promise.catch === "function") {
        promise.catch(function () {
          // Autoplay was blocked; fall back to clicking the play button.
          var btn = document.querySelector(
            ".ytp-large-play-button, .ytp-play-button"
          );
          if (btn && video.paused) {
            try {
              btn.click();
            } catch (e2) {
              /* ignore */
            }
          }
        });
      }
    }
  }

  var toggleTimer = setInterval(function () {
    if (onPlaylistPage()) {
      if (!LOOP_DONE) {
        LOOP_DONE = tryEnable("loop");
      }
      if (!SHUFFLE_DONE) {
        SHUFFLE_DONE = tryEnable("shuffle");
      }
    }
    if ((LOOP_DONE && SHUFFLE_DONE) || Date.now() > TOGGLE_DEADLINE) {
      clearInterval(toggleTimer);
    }
  }, TOGGLE_POLL_MS);

  // Keep nudging playback for the life of the tab.
  setInterval(ensurePlaying, PLAY_POLL_MS);
})();
