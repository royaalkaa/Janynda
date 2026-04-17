/**
 * special.js — версия для слабовидящих (самостоятельная реализация)
 * Структура HTML по стандарту lidrekon.ru / ГОСТ Р 52872
 */
(function () {
  'use strict';

  var KEY = 'sp_v2';

  /* ── Default state ── */
  var defaults = {
    open:    false,
    stOpen:  false,   // settings panel open
    font:    1,       // 1/2/3
    color:   1,       // 1-5
    ff:      1,       // 1=Arial, 2=Times
    ls:      1,       // letter-spacing 1/2/3
    lh:      1,       // line-height 1/2/3
    images:  true,
    audio:   false
  };

  var state = Object.assign({}, defaults);

  /* ── Storage ── */
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {}
  }
  function load() {
    try {
      var s = JSON.parse(localStorage.getItem(KEY) || 'null');
      if (s) Object.assign(state, s);
    } catch (e) {}
  }

  /* ── Helpers ── */
  function qAll(sel) { return [].slice.call(document.querySelectorAll(sel)); }
  function q(sel)    { return document.querySelector(sel); }

  /* ── Apply all state classes to <body> ── */
  function applyClasses() {
    var b = document.body;

    /* Remove all sp-* classes */
    var kept = [].filter.call(b.classList, function (c) { return c.indexOf('sp-') !== 0; });
    b.className = kept.join(' ');

    if (state.color  > 1) b.classList.add('sp-c'  + state.color);
    if (state.font   > 1) b.classList.add('sp-f'  + state.font);
    if (state.ff     > 1) b.classList.add('sp-ff' + state.ff);
    if (state.ls     > 1) b.classList.add('sp-ls' + state.ls);
    if (state.lh     > 1) b.classList.add('sp-lh' + state.lh);
    if (!state.images)    b.classList.add('sp-noimages');
    if (state.open)       b.classList.add('sp-open');

    /* Update CSS variable for layout offset */
    var panel = document.getElementById('special');
    if (panel && state.open) {
      setTimeout(function () {
        var h = panel.offsetHeight;
        document.documentElement.style.setProperty('--sp-h', h + 'px');
      }, 0);
    } else {
      document.documentElement.style.setProperty('--sp-h', '0px');
    }
  }

  /* ── Update active states on all buttons ── */
  function syncButtons() {
    /* font */
    qAll('.special-font-size button').forEach(function (b) {
      b.classList.toggle('active', +b.value === state.font);
    });
    /* color — both toolbar and settings */
    qAll('.special-color button').forEach(function (b) {
      b.classList.toggle('active', +b.value === state.color);
    });
    /* font-family */
    qAll('.special-font-family button').forEach(function (b) {
      b.classList.toggle('active', +b.value === state.ff);
    });
    /* letter-spacing */
    qAll('.special-letter-spacing button').forEach(function (b) {
      b.classList.toggle('active', +b.value === state.ls);
    });
    /* line-height */
    qAll('.special-line-height button').forEach(function (b) {
      b.classList.toggle('active', +b.value === state.lh);
    });
    /* image toggle */
    var ib = q('.special-images button');
    if (ib) ib.classList.toggle('active', !state.images);
    /* audio toggle */
    var ab = q('.special-audio button');
    if (ab) ab.classList.toggle('active', state.audio);
    /* eye buttons */
    qAll('.sp-eye-btn, .sp-eye-tab').forEach(function (b) {
      b.classList.toggle('active', state.open);
    });
  }

  function render() {
    var panel = document.getElementById('special');
    var sb    = document.getElementById('special-settings-body');
    if (panel) panel.classList.toggle('sp-open', state.open);
    if (sb)    sb.classList.toggle('sp-settings-open', state.stOpen && state.open);
    applyClasses();
    syncButtons();
  }

  /* ─────────────────────────────────────
     Public: toggle panel (eye icon)
  ───────────────────────────────────── */
  window.toggleSpecial = function () {
    state.open = !state.open;
    if (!state.open) state.stOpen = false;
    render();
    save();
  };

  /* ─────────────────────────────────────
     DOMContentLoaded — wire up buttons
  ───────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', function () {
    load();
    render();

    /* font size */
    qAll('.special-font-size button').forEach(function (btn) {
      btn.addEventListener('click', function () {
        state.font = +this.value;
        render(); save();
      });
    });

    /* color (all .special-color buttons) */
    qAll('.special-color button').forEach(function (btn) {
      btn.addEventListener('click', function () {
        state.color = +this.value;
        render(); save();
      });
    });

    /* images */
    var imgBtn = q('.special-images button');
    if (imgBtn) {
      imgBtn.addEventListener('click', function () {
        state.images = !state.images;
        render(); save();
      });
    }

    /* audio (text-to-speech) */
    var audBtn = q('.special-audio button');
    if (audBtn) {
      audBtn.addEventListener('click', function () {
        state.audio = !state.audio;
        if (!state.audio && window.speechSynthesis) {
          window.speechSynthesis.cancel();
        }
        render(); save();
        if (state.audio) {
          document.addEventListener('mouseup', speakSelected);
        } else {
          document.removeEventListener('mouseup', speakSelected);
        }
      });
      if (state.audio) {
        document.addEventListener('mouseup', speakSelected);
      }
    }

    /* settings open */
    var stBtn = q('.special-settings button');
    if (stBtn) {
      stBtn.addEventListener('click', function () {
        state.stOpen = !state.stOpen;
        render(); save();
      });
    }

    /* font family */
    qAll('.special-font-family button').forEach(function (btn) {
      btn.addEventListener('click', function () {
        state.ff = +this.value;
        render(); save();
      });
    });

    /* letter spacing */
    qAll('.special-letter-spacing button').forEach(function (btn) {
      btn.addEventListener('click', function () {
        state.ls = +this.value;
        render(); save();
      });
    });

    /* line height */
    qAll('.special-line-height button').forEach(function (btn) {
      btn.addEventListener('click', function () {
        state.lh = +this.value;
        render(); save();
      });
    });

    /* reset */
    var resetBtn = q('.special-reset button');
    if (resetBtn) {
      resetBtn.addEventListener('click', function () {
        Object.assign(state, defaults, { open: state.open });
        render(); save();
      });
    }

    /* close settings */
    var closeBtn = q('.special-settings-close button');
    if (closeBtn) {
      closeBtn.addEventListener('click', function () {
        state.stOpen = false;
        render(); save();
      });
    }

    /* quit — normal version */
    var quitBtn = q('.special-quit button');
    if (quitBtn) {
      quitBtn.addEventListener('click', function () {
        Object.assign(state, defaults);
        render(); save();
      });
    }
  });

  /* ─────────────────────────────────────
     Text-to-speech on mouse selection
  ───────────────────────────────────── */
  function speakSelected() {
    var sel = window.getSelection();
    if (!sel || !sel.toString().trim()) return;
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    var u = new SpeechSynthesisUtterance(sel.toString().trim());
    u.lang = document.documentElement.lang || 'ru-RU';
    window.speechSynthesis.speak(u);
  }

})();
