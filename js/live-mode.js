/* 实时模拟的开关键：宿主轮询、POST、顶部提示与键盘快捷键。
 *
 * 状态只有一个来源：scene.live（也就是 atmosphere.js 里的 uniform）。
 * 这个模块只做“把外部的意图搬到 scene 上，并把结果反馈给用户”。
 *
 * 优先级：URL ?live=0/1 > 宿主 /live > settings.js 的 atmosphere.live
 */
window.JupiterLiveMode = (function () {
  'use strict';

  const ENDPOINT = 'live';

  function create(options) {
    const scene = options.scene;
    const toastElement = options.toastElement;
    const pollMs = options.pollMs;
    const toastMs = options.toastMs;
    const override = options.override;   // null 表示“听宿主的”
    const onChange = options.onChange || function () {};
    let toastTimer = 0;
    let supported = !!scene.hasAtmosphere;

    function showToast(live) {
      if (!toastElement) return;
      toastElement.textContent = live ? '实时模拟 已开启' : '实时模拟 已关闭';
      toastElement.classList.add('show');
      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => toastElement.classList.remove('show'), toastMs);
    }

    function apply(value, announce) {
      if (!supported) return false;
      const before = scene.live;
      const live = scene.setLive(!!value);
      if (live !== before) {
        if (announce) showToast(live);
        onChange(live);
      }
      return live;
    }

    function toggle() {
      if (!supported) return false;
      return apply(!scene.live, true);
    }

    function persist(value) {
      fetch(ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ live: value }),
        keepalive: true,
      }).catch(() => {
        // 独立预览没有宿主服务，选择不会保存。
      });
    }

    // URL 参数优先；否则先沿用 settings.js 的默认值，再开始跟随宿主。
    if (override !== null) {
      apply(override, false);
    } else if (supported) {
      let polling = false;
      async function sync() {
        if (polling) return;
        polling = true;
        try {
          const response = await fetch(ENDPOINT, { cache: 'no-store' });
          if (response.ok) {
            const data = await response.json();
            if (typeof data.live === 'boolean' && data.live !== scene.live) {
              apply(data.live, true);
            }
          }
        } catch (error) {
          // 独立预览：保持 settings.js 的默认值。
        } finally {
          polling = false;
        }
      }
      sync();
      setInterval(sync, pollMs);
    }

    // 壁纸窗口没有键盘焦点，Ctrl+Alt+J 由宿主处理；这里服务加速预览窗口。
    addEventListener('keydown', event => {
      if (event.key !== 'l' && event.key !== 'L') return;
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      const live = toggle();
      if (live !== null) persist(live);
    });

    return {
      get live() { return scene.live; },
      get supported() { return supported; },
      toggle() {
        const live = toggle();
        if (live !== null) persist(live);
        return live;
      },
      set(value, save) {
        const live = apply(value, true);
        if (save) persist(live);
        return live;
      },
    };
  }

  return { create };
})();
