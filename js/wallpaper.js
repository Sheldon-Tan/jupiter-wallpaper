/* 壁纸入口：把场景、自转计数、实时开关与页面装配起来。
 *
 * 这里只做编排，不实现具体算法：
 *   URL 参数 → JupiterScene（画）
 *            → JupiterRotation（转与计数）
 *            → JupiterLiveMode（开关、提示）
 *            → 帧调度与状态文字
 */
(() => {
  'use strict';

  const settings = window.JUPITER_SETTINGS;
  const params = new URLSearchParams(location.search);

  /* ---- URL 参数：预览与调试用，缺省时全部交给 settings.js ------------- */
  const demo = params.has('demo');
  const mapName = Object.prototype.hasOwnProperty.call(settings.maps, params.get('map'))
    ? params.get('map') : 'cassini';
  const numberParam = (name, transform) => {
    const raw = params.get(name);
    if (raw === null) return null;
    const value = Number(raw);
    if (!Number.isFinite(value)) return null;
    return transform ? transform(value) : value;
  };
  const phaseOverride = numberParam('phase');
  const flowOverride = numberParam('flow');
  const turnOverride = numberParam('turn', value => ((value % 1) + 1) % 1);
  const markParam = (params.get('mark') || '').split(',').map(Number);
  const mark = markParam.length === 2 && markParam.every(Number.isFinite)
    ? { u: markParam[0], v: markParam[1] } : null;
  // ?live=1 / ?live=0 覆盖宿主设置与 settings.js。
  const liveParam = params.get('live');
  const liveOverride = liveParam === null
    ? null : !(liveParam === '0' || liveParam === 'false');

  if (demo) document.body.classList.add('preview');

  const canvas = document.getElementById('sky');
  const status = document.getElementById('status');
  const countElement = document.getElementById('rotation-count');
  const toastElement = document.getElementById('mode-toast');

  function showError(message) {
    document.body.classList.add('error');
    status.textContent = message;
    console.error(message);
  }

  /* ---- 场景与两个逻辑模块 -------------------------------------------- */
  let scene;
  try {
    scene = window.JupiterScene.create({ canvas, mapName, phase: phaseOverride, mark });
  } catch (error) {
    showError(`渲染错误：${error.message}`);
    return;
  }

  const periodSeconds = demo
    ? settings.rotation.demoPeriodSeconds
    : settings.rotation.periodSeconds;
  const rotation = window.JupiterRotation.create({
    demo,
    periodMs: periodSeconds * 1000,
    onDisplay(total) {
      countElement.textContent = total === null ? '—' : total.toLocaleString('en-US');
    },
  });

  function formatPeriod(seconds) {
    if (seconds < 60) return `${seconds} 秒一周`;
    const minutes = Math.floor(seconds / 60);
    const rest = Math.round(seconds - minutes * 60);
    return rest ? `${minutes} 分 ${rest} 秒一周` : `${minutes} 分一周`;
  }

  const dimensions = scene.dimensions;
  const baseStatus = `${dimensions.width}×${dimensions.height} 场景 · `
    + `${demo ? '加速预览' : formatPeriod(periodSeconds)} · ${scene.label}`;

  let liveMode = null;
  function refreshStatus() {
    status.textContent = liveMode && liveMode.supported
      ? `${baseStatus} · 实时模拟${liveMode.live ? '开' : '关'}（Ctrl+Alt+J 切换）`
      : baseStatus;
  }

  liveMode = window.JupiterLiveMode.create({
    scene,
    toastElement,
    pollMs: settings.live.pollMs,
    toastMs: settings.live.toastMs,
    override: liveOverride,
    onChange: refreshStatus,
  });
  refreshStatus();

  /* ---- 播放状态：前台窗口遮住桌面时暂停绘制 --------------------------- */
  let paused = false;
  if (!demo) {
    async function updatePlaybackState() {
      try {
        const response = await fetch('playback', { cache: 'no-store' });
        if (response.ok) paused = (await response.json()).paused;
      } catch (error) {
        paused = false;
      }
    }
    updatePlaybackState();
    setInterval(() => {
      // 暂停时也要检查相位，否则会漏计转过的圈数。
      rotation.observe(performance.now());
      updatePlaybackState();
    }, 1000);
  }

  /* ---- 帧调度与大气时钟 ---------------------------------------------- */
  let flowSeconds = flowOverride === null ? 0 : flowOverride;
  let lastFlowTime = null;
  let lastDraw = 0;
  let lastFrame = 0;

  // 只包围木星的画布，半径随窗口高度变化；用它估算“慢速自转”需要多少刷新。
  const radiusPx = settings.scene.planetRadius * innerHeight * devicePixelRatio / 2;
  const idleIntervalMs = demo ? 1000 / 60 : Math.min(500, Math.max(1000 / 60,
    periodSeconds * 1000 * 0.15 / (2 * Math.PI * radiusPx)));

  // 实时模拟必须持续刷新，静止壁纸沿用原来的省电间隔。
  function frameInterval() {
    return (demo || liveMode.live) ? 1000 / 60 : idleIntervalMs;
  }

  function draw(now) {
    const turn = turnOverride !== null ? turnOverride : rotation.observe(now);
    if (flowOverride === null && !paused && liveMode.live) {
      const delta = lastFlowTime === null ? 0
        : Math.min(0.25, Math.max(0, (now - lastFlowTime) / 1000));
      flowSeconds += delta;
    }
    lastFlowTime = now;
    scene.setFlowTime(flowSeconds);
    scene.draw(turn);
  }

  scene.ready.then(() => {
    const start = performance.now();
    lastDraw = start;
    lastFrame = start;
    draw(start);

    function onAnimationFrame(now) {
      lastFrame = now;
      if (!paused && now - lastDraw >= frameInterval() - 1) {
        draw(now);
        lastDraw = now;
      }
      requestAnimationFrame(onAnimationFrame);
    }
    requestAnimationFrame(onAnimationFrame);

    // Chromium 会节流被遮挡窗口的 rAF；这个保险定时器补上缺失的帧。
    setInterval(() => {
      const now = performance.now();
      if (!paused && now - lastFrame > 100 && now - lastDraw >= frameInterval() - 1) {
        draw(now);
        lastDraw = now;
      }
    }, 200);
  }, error => {
    showError(`渲染错误：${error.message}`);
  });
})();
