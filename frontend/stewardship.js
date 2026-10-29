/* Attaches the Stewardship page stylesheet.
   The page itself (stewardshipPage, loadStewardshipQueues) lives in app.js. This file only
   loads /stewardship.css, whose rules are scoped to that page's element ids, so the shared
   theme (styles.neo.css) does not need to change. Do not add page logic here. */
(function () {
  if (document.getElementById('stwCss')) return;
  var l = document.createElement('link');
  l.id = 'stwCss'; l.rel = 'stylesheet'; l.href = '/stewardship.css?v=2';
  document.head.appendChild(l);
})();