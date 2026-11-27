// ==UserScript==
// @name         iTalent 视频自动最高倍速
// @namespace    local.italent.speed
// @version      1.0.0
// @description  打开 iTalent 学习页后，视频出现即自动设为最高播放速度；支持 iframe 和 Shadow DOM。
// @match        *://*/*
// @run-at       document-start
// @grant        none
// ==/UserScript==

(function () {
  'use strict';

  // 16 是 Chrome 的上限；如果 16x 缓冲不过来，改成 8 或 4
  var RATE = 16;

  // 1) 锁住 playbackRate setter：任何想把速度改回 1x 的代码都会被抬回 RATE
  var proto = HTMLMediaElement.prototype;
  var desc = Object.getOwnPropertyDescriptor(proto, 'playbackRate');

  if (desc && desc.set && !desc.set.__maxSpeedPatched) {
    var nativeSet = desc.set;
    var nativeGet = desc.get;

    var setter = function (v) {
      var n = Number(v);
      if (!isFinite(n) || n < RATE) n = RATE;
      nativeSet.call(this, Math.min(n, 16));
    };
    setter.__maxSpeedPatched = true;

    Object.defineProperty(proto, 'playbackRate', {
      configurable: true,
      enumerable: desc.enumerable,
      get: nativeGet,
      set: setter
    });
  }

  function apply(video) {
    try {
      // 如果播放器在实例上覆盖了 playbackRate，先删掉，让原型 setter 生效
      var own = Object.getOwnPropertyDescriptor(video, 'playbackRate');
      if (own && own.configurable) delete video.playbackRate;

      video.playbackRate = RATE;
      video.defaultPlaybackRate = RATE;
    } catch (e) {}
  }

  function scan(root) {
    if (!root || !root.querySelectorAll) return;

    var videos = root.querySelectorAll('video');
    for (var i = 0; i < videos.length; i++) apply(videos[i]);

    // Shadow DOM
    var all = root.querySelectorAll('*');
    for (var j = 0; j < all.length; j++) {
      if (all[j].shadowRoot) scan(all[j].shadowRoot);
    }

    // 同源 iframe 兜底；跨域 iframe 由 Tampermonkey 在每个 frame 里各自执行
    var frames = root.querySelectorAll('iframe');
    for (var k = 0; k < frames.length; k++) {
      try {
        if (frames[k].contentDocument) scan(frames[k].contentDocument);
      } catch (e) {}
    }
  }

  function boot() {
    scan(document);

    // 播放器可能在点击“继续学习”后才创建 video，轮询兜底
    setInterval(function () {
      scan(document);
    }, 1200);

    // 视频开始播放、元数据加载、倍速被改动时都重新锁回 RATE
    document.addEventListener('play', function (e) {
      if (e.target && e.target.tagName === 'VIDEO') apply(e.target);
    }, true);

    document.addEventListener('loadedmetadata', function (e) {
      if (e.target && e.target.tagName === 'VIDEO') apply(e.target);
    }, true);

    document.addEventListener('canplay', function (e) {
      if (e.target && e.target.tagName === 'VIDEO') apply(e.target);
    }, true);

    document.addEventListener('ratechange', function (e) {
      if (e.target && e.target.tagName === 'VIDEO') apply(e.target);
    }, true);
  }

  if (document.documentElement) {
    boot();
  } else {
    document.addEventListener('DOMContentLoaded', boot);
  }
})();
