/* Offline 4K WebGL wallpaper using spacecraft global maps of Jupiter. */
(() => {
  'use strict';
  const canvas = document.getElementById('sky');
  const status = document.getElementById('status');
  const params = new URLSearchParams(location.search);
  const demo = params.has('demo');
  const mapName = ['cassini', 'hubble', 'merged'].includes(params.get('map'))
    ? params.get('map') : 'cassini';
  const cassini = mapName === 'cassini';
  const merged = mapName === 'merged';
  if (demo) document.body.classList.add('preview');
  const targetWidth = Math.max(3840, Math.round(innerWidth * devicePixelRatio));
  const targetHeight = Math.max(2160, Math.round(innerHeight * devicePixelRatio));
  // Keep the original 4K scene coordinates, but allocate pixels only around
  // the planet. The rest of the desktop is the page's static black background.
  const radius = Math.ceil(0.720 * targetHeight / 2 + 8);
  const centerX = targetWidth / 2 + 0.30 * targetHeight / 2;
  const centerY = targetHeight / 2 + 0.015 * targetHeight / 2;
  const left = Math.max(0, Math.floor(centerX - radius));
  const bottom = Math.max(0, Math.floor(centerY - radius));
  const right = Math.min(targetWidth, Math.ceil(centerX + radius));
  const top = Math.min(targetHeight, Math.ceil(centerY + radius));
  canvas.width = right - left;
  canvas.height = top - bottom;
  canvas.style.left = `${left * innerWidth / targetWidth}px`;
  canvas.style.top = `${innerHeight * (1 - top / targetHeight)}px`;
  canvas.style.width = `${canvas.width * innerWidth / targetWidth}px`;
  canvas.style.height = `${canvas.height * innerHeight / targetHeight}px`;
  const gl = canvas.getContext('webgl2', {
    antialias: false, alpha: false, depth: false, stencil: false,
    powerPreference: 'high-performance', preserveDrawingBuffer: false
  });
  if (!gl) {
    document.body.classList.add('error');
    status.textContent = '无法启动 WebGL 2。请更新显卡驱动，或在 Chrome 中启用硬件加速。';
    return;
  }

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
    out vec4 outColor;
    const float PI = 3.141592653589793;
    const float POLAR_RATIO = 66854.0 / 71492.0;

    void main() {
      vec2 p = (gl_FragCoord.xy + u_origin - 0.5 * u_resolution) / (0.5 * u_resolution.y);
      p.x -= 0.30;               // keep the left side free for desktop icons
      p.y -= 0.015;
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
      vec2 uv = vec2(fract(u_initial_phase + longitude / (2.0 * PI) - u_rotation),
                     0.5 + latitude / PI);
      // Hubble's map lacks the extreme poles; Cassini covers them.
      uv.y = clamp(uv.y, u_polar_limit, 1.0 - u_polar_limit);
      // A small negative LOD bias avoids unnecessary mipmap softness.
      vec3 clouds = texture(u_map, uv, -0.5).rgb;

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
                 merged ? 0.83 : cassini ? 0.36 : 0.645);
    gl.uniform1f(gl.getUniformLocation(program, 'u_polar_limit'),
                 mapName === 'hubble' ? 0.058 : 0.001);
    gl.uniform1f(gl.getUniformLocation(program, 'u_planetographic'),
                 cassini ? 0.0 : 1.0);
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
    image.onload = () => {
      gl.bindTexture(gl.TEXTURE_2D, map);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB8, gl.RGB,
                    gl.UNSIGNED_BYTE, image);
      gl.generateMipmap(gl.TEXTURE_2D);
      const start = performance.now();
      // System III sidereal spin: 9 h 55 m 30 s. Demo mode makes it visible.
      const periodMs = demo ? 30000 : (9 * 3600 + 55 * 60 + 30) * 10;
      function draw(now = performance.now()) {
        const turn = ((now - start) % periodMs) / periodMs;
        gl.uniform1f(rotationLocation, turn);
        gl.drawArrays(gl.TRIANGLES, 0, 3);
      }
      draw(start);
      // Fast motion follows display refresh. When Chromium treats the desktop
      // window as occluded, a timer keeps it moving at the same target rate.
      const radiusPx = 0.720 * innerHeight * devicePixelRatio / 2;
      const frameIntervalMs = demo ? 1000 / 60 : Math.min(500, Math.max(1000 / 60,
        periodMs * 0.15 / (2 * Math.PI * radiusPx)));
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
        setInterval(updatePlaybackState, 1000);
      }
      if (frameIntervalMs < 100) {
        let lastDraw = start;
        let lastAnimationFrame = start;
        function onAnimationFrame(now) {
          lastAnimationFrame = now;
          if (!paused && now - lastDraw >= frameIntervalMs - 1) {
            draw(now);
            lastDraw = now;
          }
          requestAnimationFrame(onAnimationFrame);
        }
        requestAnimationFrame(onAnimationFrame);
        setInterval(() => {
          const now = performance.now();
          if (!paused && now - lastAnimationFrame > 100 &&
              now - lastDraw >= frameIntervalMs - 1) {
            draw(now);
            lastDraw = now;
          }
        }, frameIntervalMs);
      } else {
        setInterval(() => { if (!paused) draw(); }, frameIntervalMs);
      }
      const sourceName = merged ? 'Cassini + Juno 8K' : cassini ? 'NASA/Cassini 2000' : 'NASA/Hubble 2015';
      status.textContent = `${targetWidth}×${targetHeight} 场景 · ${demo ? '30 秒预览一周' : `${Math.round(periodMs / 1000)} 秒一周`} · ${sourceName}`;
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
})();
