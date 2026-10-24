/* Offline 4K WebGL wallpaper using spacecraft global maps of Jupiter. */
(() => {
  'use strict';
  const canvas = document.getElementById('sky');
  const status = document.getElementById('status');
  const rotationCount = document.getElementById('rotation-count');
  const params = new URLSearchParams(location.search);
  const demo = params.has('demo');
  const mapName = ['cassini', 'hubble', 'merged'].includes(params.get('map'))
    ? params.get('map') : 'cassini';
  const cassini = mapName === 'cassini';
  const merged = mapName === 'merged';
  const requestedPhase = params.get('phase');
  const phaseOverride = requestedPhase !== null && Number.isFinite(Number(requestedPhase))
    ? Number(requestedPhase) : null;
  // ?live=1 / ?live=0 overrides both the host setting and atmosphere.js.
  const requestedLive = params.get('live');
  const liveOverride = requestedLive === null
    ? null : !(requestedLive === '0' || requestedLive === 'false');
  // ?flow=<seconds> freezes the atmosphere at one instant, for still previews.
  const requestedFlow = params.get('flow');
  const flowOverride = requestedFlow !== null && Number.isFinite(Number(requestedFlow))
    ? Number(requestedFlow) : null;
  // ?turn=0.25 freezes the spin angle, so stills differ only in the atmosphere.
  const requestedTurn = params.get('turn');
  const turnOverride = requestedTurn !== null && Number.isFinite(Number(requestedTurn))
    ? ((Number(requestedTurn) % 1) + 1) % 1 : null;
  // ?mark=u,v paints a green dot at one map texel; used to place vortices.
  const markParam = (params.get('mark') || '').split(',').map(Number);
  const markU = markParam.length === 2 && markParam.every(Number.isFinite) ? markParam[0] : -1;
  const markV = markU >= 0 ? markParam[1] : -1;
  if (demo) document.body.classList.add('preview');
  async function loadSavedCount() {
    try {
      const response = await fetch('rotation-count', { cache: 'no-store' });
      if (!response.ok) return null;
      const data = await response.json();
      return Number.isSafeInteger(data.completed_turns) && data.completed_turns >= 0
        ? data.completed_turns : null;
    } catch (error) {
      return null;
    }
  }
  // Fetch the saved total as soon as the page loads, independently of the
  // large planetary texture. Never show a temporary zero on restart.
  const initialCount = demo ? Promise.resolve(0) : loadSavedCount();
  initialCount.then(total => {
    rotationCount.textContent = total === null ? '—' : total.toLocaleString('en-US');
  });
  const targetWidth = Math.max(3840, Math.round(innerWidth * devicePixelRatio));
  const targetHeight = Math.max(2160, Math.round(innerHeight * devicePixelRatio));
  // Keep the original 4K scene coordinates, but allocate pixels only around
  // the planet. The rest of the desktop is the page's static black background.
  const radius = Math.ceil(0.720 * targetHeight / 2 + 8);
  const centerX = targetWidth / 2;
  const centerY = targetHeight / 2;
  const left = Math.max(0, Math.floor(centerX - radius));
  const bottom = Math.max(0, Math.floor(centerY - radius));
  const right = Math.min(targetWidth, Math.ceil(centerX + radius));
  const top = Math.min(targetHeight, Math.ceil(centerY + radius));
  canvas.width = right - left;
  canvas.height = top - bottom;
  function positionCanvas() {
    // The host attaches and enlarges Chrome after this script starts.
    // Use one scale on both axes so other screen aspect ratios stay round.
    const scale = innerHeight / targetHeight;
    canvas.style.left = `${innerWidth / 2 + (left - targetWidth / 2) * scale}px`;
    canvas.style.top = `${innerHeight / 2 - (top - targetHeight / 2) * scale}px`;
    canvas.style.width = `${canvas.width * scale}px`;
    canvas.style.height = `${canvas.height * scale}px`;
  }
  positionCanvas();
  addEventListener('resize', positionCanvas);
  const gl = canvas.getContext('webgl2', {
    antialias: false, alpha: false, depth: false, stencil: false,
    powerPreference: 'high-performance', preserveDrawingBuffer: false
  });
  if (!gl) {
    document.body.classList.add('error');
    status.textContent = '无法启动 WebGL 2。请更新显卡驱动，或在 Chrome 中启用硬件加速。';
    return;
  }

  const atmosphereModule = window.JupiterAtmosphere || null;
  const atmosphereGLSL = atmosphereModule ? atmosphereModule.GLSL : `
    uniform float u_flowTime;
    uniform float u_live;
    uniform float u_contrast;
    vec3 jupiterAtmosphere(vec2 uv, float t) { return vec3(uv, 0.5); }`;

  const vertex = `#version 300 es
    precision highp float;
    void main() {
      vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
      gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
    }`;
  const fragment = `#version 300 es
    precision highp float;
    uniform vec2 u_resolution;
    uniform vec2 u_origin;
    uniform sampler2D u_map;
    uniform float u_rotation;
    uniform float u_initial_phase;
    uniform float u_polar_limit;
    uniform float u_planetographic;
    uniform vec2 u_mark;
    ${atmosphereGLSL}
    out vec4 outColor;
    const float PI = 3.141592653589793;
    const float POLAR_RATIO = 66854.0 / 71492.0;

    void main() {
      vec2 p = (gl_FragCoord.xy + u_origin - 0.5 * u_resolution) / (0.5 * u_resolution.y);
      // Apparent north-pole tilt. The actual obliquity to Jupiter's orbit is ~3.1°.
      const float a = 0.0541052;
      vec2 q = vec2(cos(a) * p.x + sin(a) * p.y,
                    -sin(a) * p.x + cos(a) * p.y);
      const float R = 0.720;
      float shape = dot(q / vec2(R, R * POLAR_RATIO),
                        q / vec2(R, R * POLAR_RATIO));
      vec3 background = vec3(0.0);
      if (shape > 1.003) {
        outColor = vec4(background, 1.0);
        return;
      }

      // Orthographic ray / oblate spheroid intersection.
      float z = R * sqrt(max(0.0, 1.0 - shape));
      vec3 normal = normalize(vec3(q.x, q.y / (POLAR_RATIO * POLAR_RATIO), z));
      float horizontal = length(vec2(q.x, z));
      float planetocentric = atan(q.y, horizontal);
      float planetographic = atan(q.y / (POLAR_RATIO * POLAR_RATIO), horizontal);
      float latitude = mix(planetocentric, planetographic, u_planetographic);
      float longitude = atan(q.x, z);
      // With north up, cloud features drift left-to-right as Jupiter turns.
      vec2 uv = vec2(u_initial_phase + longitude / (2.0 * PI) - u_rotation,
                     0.5 + latitude / PI);
      // GL_REPEAT wraps u; keeping it unwrapped preserves correct mipmap derivatives.
      // Hubble's map lacks the extreme poles; Cassini covers them.
      uv.y = clamp(uv.y, u_polar_limit, 1.0 - u_polar_limit);

      // Live weather: displace the lookup with the Jovian wind field.
      float cloud = 0.5;
      vec2 deck = uv;
      if (u_live > 0.5) {
        vec3 atmosphere = jupiterAtmosphere(uv, u_flowTime);
        deck = atmosphere.xy;
        cloud = atmosphere.z;
      }
      // A negative LOD bias avoids unnecessary mipmap softness.  The gradients
      // come from the undistorted uv, so warping never turns the map blurry.
      vec2 dX = dFdx(uv) * 0.70710678;
      vec2 dY = dFdy(uv) * 0.70710678;
      vec3 clouds = textureGrad(u_map, deck, dX, dY).rgb;
      // Tracer brightness modulation; exactly 1.0 when live weather is off.
      clouds *= 1.0 + (cloud - 0.5) * u_contrast;
      // Calibration marker (?mark=u,v): a small green dot at one map texel.
      if (u_mark.x >= 0.0) {
        vec2 gap = deck - u_mark;
        gap.x -= floor(gap.x + 0.5);
        if (length(gap * vec2(1.0, 2.0)) < 0.006) clouds = vec3(0.1, 1.0, 0.2);
      }

      // Single distant sun: diffuse cloud reflection and a faint limb haze.
      vec3 sun = normalize(vec3(-0.48, 0.23, 0.85));
      float incidence = max(dot(normal, sun), 0.0);
      float lit = 0.10 + 0.96 * incidence;
      float limb = pow(1.0 - max(normal.z, 0.0), 3.4);
      vec3 planet = clouds * lit;
      planet += vec3(0.105, 0.145, 0.19) * limb * incidence * 0.35;
      float aa = max(fwidth(shape), 0.001);
      float cover = 1.0 - smoothstep(1.0 - aa, 1.0 + aa, shape);
      outColor = vec4(mix(background, planet, cover), 1.0);
    }`;

  function compile(type, source) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS))
      throw new Error(gl.getShaderInfoLog(shader));
    return shader;
  }
  let atmo = null;
  let refreshStatus = () => {};
  // Ctrl+Alt+J works from any application, so the wallpaper window itself has
  // no focus and cannot show a native tooltip.  A brief pill in the middle of
  // the sky confirms the new state without stealing attention.
  const modeToast = document.getElementById('mode-toast');
  let modeToastTimer = 0;
  function showModeToast(live) {
    if (!modeToast) return;
    modeToast.textContent = live ? '实时模拟 已开启' : '实时模拟 已关闭';
    modeToast.classList.add('show');
    clearTimeout(modeToastTimer);
    modeToastTimer = setTimeout(() => modeToast.classList.remove('show'), 1900);
  }
  try {
    const program = gl.createProgram();
    gl.attachShader(program, compile(gl.VERTEX_SHADER, vertex));
    gl.attachShader(program, compile(gl.FRAGMENT_SHADER, fragment));
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS))
      throw new Error(gl.getProgramInfoLog(program));
    gl.useProgram(program);
    gl.bindVertexArray(gl.createVertexArray());
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.uniform2f(gl.getUniformLocation(program, 'u_resolution'), targetWidth, targetHeight);
    gl.uniform2f(gl.getUniformLocation(program, 'u_origin'), left, bottom);
    gl.uniform1i(gl.getUniformLocation(program, 'u_map'), 0);
    gl.uniform1f(gl.getUniformLocation(program, 'u_initial_phase'),
                 phaseOverride ?? (merged ? 0.83 : cassini ? 0.36 : 0.645));
    gl.uniform1f(gl.getUniformLocation(program, 'u_polar_limit'),
                 mapName === 'hubble' ? 0.058 : 0.001);
    gl.uniform1f(gl.getUniformLocation(program, 'u_planetographic'),
                 cassini ? 0.0 : 1.0);
    gl.uniform2f(gl.getUniformLocation(program, 'u_mark'), markU, markV);
    // Wind lookup table, tracer field and vortex table live in atmosphere.js.
    if (atmosphereModule) {
      atmo = atmosphereModule.create(gl, program, mapName);
      if (liveOverride !== null) atmo.setLive(liveOverride);
    }
    const rotationLocation = gl.getUniformLocation(program, 'u_rotation');
    const map = gl.createTexture();
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, map);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
    const image = new Image();
    image.onload = async () => {
      gl.bindTexture(gl.TEXTURE_2D, map);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB8, gl.RGB,
                    gl.UNSIGNED_BYTE, image);
      gl.generateMipmap(gl.TEXTURE_2D);
      let savedTurns = await initialCount;
      let counterAvailable = !demo && savedTurns !== null;
      if (savedTurns === null) savedTurns = 0;
      const counterSession = crypto.randomUUID();
      let acknowledgedTurns = 0;
      let pendingSave = false;
      let displayedTurns = -1;
      function recordTurns(completed) {
        const total = savedTurns + completed;
        if ((counterAvailable || demo) && total !== displayedTurns) {
          rotationCount.textContent = total.toLocaleString('en-US');
          displayedTurns = total;
        }
        if (!counterAvailable || completed <= acknowledgedTurns || pendingSave) return;
        pendingSave = true;
        fetch('rotation-count', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session: counterSession, completed }),
          keepalive: true
        }).then(response => {
          if (!response.ok) throw new Error('Unable to save the rotation count');
          acknowledgedTurns = Math.max(acknowledgedTurns, completed);
        }).catch(() => {
          // Retry on the next draw; the server treats repeated values as one turn.
        }).finally(() => { pendingSave = false; });
      }
      if (!counterAvailable && !demo) {
        let retrying = false;
        setInterval(async () => {
          if (counterAvailable || retrying) return;
          retrying = true;
          const total = await loadSavedCount();
          retrying = false;
          if (total !== null) {
            savedTurns = total;
            counterAvailable = true;
            recordTurns(completedTurns);
          }
        }, 3000);
      }
      const start = performance.now();
      // Base System III period: 9 h 55 m 30 s. The desktop multiplier speeds it up.
      const periodMs = demo ? 30000 : (9 * 3600 + 55 * 60 + 30) * 10;
      let previousTurn = null;
      let completedTurns = 0;
      let paused = false;
      // Atmosphere clock. It advances only while live weather is on screen, so
      // pausing the wallpaper or switching the effect off and on again resumes
      // from the same flow state instead of jumping.
      let flowSeconds = flowOverride ?? 0;
      let lastFlowTime = null;
      function observeRotation(now = performance.now()) {
        const elapsed = Math.max(0, now - start);
        const turn = turnOverride !== null ? turnOverride
          : (elapsed % periodMs) / periodMs;
        // Crossing from the end of the circle back to its initial orientation
        // is the only event that advances the counter.
        if (previousTurn !== null && previousTurn - turn > 0.5) completedTurns += 1;
        previousTurn = turn;
        recordTurns(completedTurns);
        return turn;
      }
      function draw(now = performance.now()) {
        const turn = observeRotation(now);
        if (atmo) {
          if (flowOverride === null && !paused && atmo.live) {
            const delta = lastFlowTime === null ? 0
              : Math.min(0.25, Math.max(0, (now - lastFlowTime) / 1000));
            flowSeconds += delta;
          }
          lastFlowTime = now;
          atmo.setTime(flowSeconds);
        }
        gl.uniform1f(rotationLocation, turn);
        gl.drawArrays(gl.TRIANGLES, 0, 3);
      }
      draw(start);
      // Fast motion follows display refresh. When Chromium treats the desktop
      // window as occluded, a timer keeps it moving at the same target rate.
      const radiusPx = 0.720 * innerHeight * devicePixelRatio / 2;
      const idleIntervalMs = demo ? 1000 / 60 : Math.min(500, Math.max(1000 / 60,
        periodMs * 0.15 / (2 * Math.PI * radiusPx)));
      // Live weather must keep moving even when the paper itself turns slowly,
      // so it always runs at display rate; the static wallpaper keeps the old
      // power-saving interval.
      function frameInterval() {
        return (demo || (atmo && atmo.live)) ? 1000 / 60 : idleIntervalMs;
      }
      if (!demo) {
        async function updatePlaybackState() {
          try {
            const response = await fetch('playback', { cache: 'no-store' });
            if (response.ok) {
              paused = (await response.json()).paused;
            }
          } catch (error) {
            paused = false;
          }
        }
        updatePlaybackState();
        setInterval(() => {
          // Count orientation crossings even while drawing is paused.
          observeRotation();
          updatePlaybackState();
        }, 1000);
      }
      let lastDraw = start;
      let lastFrame = start;
      function onAnimationFrame(now) {
        lastFrame = now;
        if (!paused && now - lastDraw >= frameInterval() - 1) {
          draw(now);
          lastDraw = now;
        }
        requestAnimationFrame(onAnimationFrame);
      }
      requestAnimationFrame(onAnimationFrame);
      // A 200 ms guard covers Chromium throttling rAF for an occluded desktop
      // window; it never double-draws while rAF is healthy.
      setInterval(() => {
        const now = performance.now();
        if (!paused && now - lastFrame > 100 &&
            now - lastDraw >= frameInterval() - 1) {
          draw(now);
          lastDraw = now;
        }
      }, 200);
      const sourceName = merged ? 'Cassini + Juno 8K' : cassini ? 'NASA/Cassini 2000' : 'NASA/Hubble 2015';
      const baseStatus = `${targetWidth}×${targetHeight} 场景 · `
        + `${demo ? '30 秒预览一周' : `${Math.round(periodMs / 1000)} 秒一周`} · ${sourceName}`;
      refreshStatus = () => {
        status.textContent = atmo
          ? `${baseStatus} · 实时大气${atmo.live ? '开' : '关'}（Ctrl+Alt+J 切换）`
          : baseStatus;
      };
      refreshStatus();
      // The host stores the on/off choice, so the wallpaper, the toggle script
      // and the global hotkey all share one setting.  A URL parameter wins.
      if (atmo && liveOverride === null) {
        async function updateLiveState() {
          try {
            const response = await fetch('live', { cache: 'no-store' });
            if (response.ok) {
              const data = await response.json();
              if (typeof data.live === 'boolean' && data.live !== atmo.live) {
                showModeToast(data.live);
                atmo.setLive(data.live);
                refreshStatus();
              }
            }
          } catch (error) {
            // Standalone preview: atmosphere.js stays the source of truth.
          }
        }
        updateLiveState();
        setInterval(updateLiveState, 250);
      }
      window.jupiterReady = true;
    };
    image.onerror = () => { throw new Error('NASA 木星纹理加载失败'); };
    image.src = merged ? 'assets/jupiter_cassini_juno_8k.png'
      : cassini ? 'assets/jupiter_cassini_2000.png' : 'assets/jupiter_hubble_2015.png';
  } catch (error) {
    document.body.classList.add('error');
    status.textContent = `渲染错误：${error.message}`;
    console.error(error);
  }

  // Keyboard shortcut. The wallpaper window normally sits behind the desktop
  // icons and has no focus, so Ctrl+Alt+J in wallpaper_host.py is the primary
  // switch; this one works in the accelerated preview window.
  function applyLive(next, persist) {
    if (!atmo) return;
    const before = atmo.live;
    const live = atmo.setLive(next);
    refreshStatus();
    if (live !== before) showModeToast(live);
    if (!persist) return;
    fetch('live', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ live }),
      keepalive: true
    }).catch(() => {
      // Standalone preview has no host server; the choice is not persisted.
    });
  }
  addEventListener('keydown', (event) => {
    if (event.key !== 'l' && event.key !== 'L') return;
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    if (!atmo) return;
    applyLive(!atmo.live, true);
  });
})();



