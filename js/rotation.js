/* 自转角度与“已自转 N 次”计数。
 *
 * 职责边界：
 *   - 由时间算出当前自转相位 turn ∈ [0,1)
 *   - 只在相位从一周末端跨回起点时把计数加一，不用“经过时间 ÷ 周期”
 *   - 把累计次数读写到宿主（GET/POST rotation-count），并处理宿主暂时不可用
 *   - 通过 onDisplay 回调把要显示的数字交给调用方，自己不做 DOM
 *
 * 宿主不可用（例如直接开预览页）时退化为纯前端计数，刷新即归零。
 */
window.JupiterRotation = (function () {
  'use strict';

  const ENDPOINT = 'rotation-count';
  const RETRY_MS = 3000;

  async function fetchSavedCount() {
    try {
      const response = await fetch(ENDPOINT, { cache: 'no-store' });
      if (!response.ok) return null;
      const data = await response.json();
      return Number.isSafeInteger(data.completed_turns) && data.completed_turns >= 0
        ? data.completed_turns : null;
    } catch (error) {
      return null;
    }
  }

  function create(options) {
    const demo = !!options.demo;
    const periodMs = options.periodMs;
    const onDisplay = options.onDisplay || function () {};
    const session = (crypto && crypto.randomUUID)
      ? crypto.randomUUID() : String(Math.random()).slice(2);

    let startTime = null;
    let previousTurn = null;
    let completed = 0;
    let saved = null;           // 宿主里的历史总数；null 表示还没读到
    let available = false;      // 是否能把增量写回宿主
    let acknowledged = 0;       // 宿主已确认收到的增量
    let pendingSave = false;
    let displayed = undefined;

    function refreshDisplay() {
      const value = saved === null ? null : saved + completed;
      if (value === displayed) return;
      displayed = value;
      onDisplay(value);
    }

    function saveProgress() {
      if (!available || completed <= acknowledged || pendingSave) return;
      pendingSave = true;
      fetch(ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session, completed }),
        keepalive: true,
      }).then(response => {
        if (!response.ok) throw new Error('Unable to save the rotation count');
        acknowledged = Math.max(acknowledged, completed);
      }).catch(() => {
        // 下次绘制重试；宿主把重复的增量视为同一批。
      }).finally(() => { pendingSave = false; });
    }

    function record(completedTurns) {
      refreshDisplay();
      saveProgress();
    }

    // 先显示已有次数，避免重启瞬间闪出一个 0。
    if (demo) {
      saved = 0;
      available = false;
      refreshDisplay();
    } else {
      refreshDisplay();  // 立即显示 “—”
      fetchSavedCount().then(total => {
        if (total !== null) {
          saved = total;
          available = true;
          refreshDisplay();
          record(completed);
        } else {
          // 宿主暂时没起来：每 3 秒再试，读到后把历史数字补上。
          const retry = setInterval(async () => {
            const retried = await fetchSavedCount();
            if (retried === null) return;
            clearInterval(retry);
            saved = retried;
            available = true;
            record(completed);
          }, RETRY_MS);
        }
      });
    }

    function turnAt(now) {
      if (startTime === null) startTime = now;
      const elapsed = Math.max(0, now - startTime);
      return (elapsed % periodMs) / periodMs;
    }

    return {
      periodMs,
      turnAt,
      /** 每次绘制（或暂停时每秒）调用一次：返回相位并更新计数。 */
      observe(now) {
        const turn = turnAt(now);
        // 只有看到相位从一周末端越过初始位置，才认为转完一圈。
        if (previousTurn !== null && previousTurn - turn > 0.5) completed += 1;
        previousTurn = turn;
        record(completed);
        return turn;
      },
      get completedTurns() { return completed; },
    };
  }

  return { create };
})();
